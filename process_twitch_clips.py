#!/usr/bin/env python3
"""
Twitch Clips to Shorts Pipeline

Fetches Twitch clips, processes them with crop_for_shorts, and uploads to Google Drive.
"""

import argparse
import json
import os
import sys
import tempfile
import subprocess

from pathlib import Path

import requests
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from crop_for_shorts import crop_video_for_shorts

# Load environment variables from .env file
load_dotenv()

PROCESSED_CLIPS_FILE = Path("processed_clips.json")
TOKEN_FILE = Path("gdrive_token.json")
SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def get_drive_service():
    """Authenticate with Google Drive using OAuth2."""
    creds = None

    # Load existing token
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    # Refresh or get new token
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError as err:
                # Handle revoked/expired refresh tokens by forcing a new OAuth flow.
                print(f"Stored Google token refresh failed ({err}); re-authenticating...")
                creds = None
                if TOKEN_FILE.exists():
                    TOKEN_FILE.unlink()

        if not creds or not creds.valid:
            client_secrets_file = os.getenv("GOOGLE_CLIENT_SECRETS_FILE")
            if not client_secrets_file:
                raise ValueError("GOOGLE_CLIENT_SECRETS_FILE must be set in .env")
            flow = InstalledAppFlow.from_client_secrets_file(client_secrets_file, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save token for next run
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    return build("drive", "v3", credentials=creds)


def get_twitch_access_token() -> str:
    """Get Twitch access token using client credentials flow."""
    client_id = os.getenv("TWITCH_CLIENT_ID")
    client_secret = os.getenv("TWITCH_CLIENT_SECRET")

    if not client_id or not client_secret:
        raise ValueError("TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET must be set in .env")

    response = requests.post(
        "https://id.twitch.tv/oauth2/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "client_credentials",
        },
    )
    response.raise_for_status()
    return response.json()["access_token"]


def fetch_clips(access_token: str, broadcaster_id: str) -> list[dict]:
    """Fetch clips for a broadcaster from Twitch API."""
    client_id = os.getenv("TWITCH_CLIENT_ID")
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Client-Id": client_id,
    }

    clips = []
    cursor = None

    while True:
        params = {"broadcaster_id": broadcaster_id, "first": 100}
        if cursor:
            params["after"] = cursor

        response = requests.get(
            "https://api.twitch.tv/helix/clips",
            headers=headers,
            params=params,
        )
        response.raise_for_status()
        data = response.json()

        clips.extend(data.get("data", []))

        # Handle pagination
        cursor = data.get("pagination", {}).get("cursor")
        if not cursor:
            break

    return clips


def load_processed_clips() -> set[str]:
    """Load set of already processed clip IDs."""
    if PROCESSED_CLIPS_FILE.exists():
        with open(PROCESSED_CLIPS_FILE) as f:
            return set(json.load(f))
    return set()


def save_processed_clips(processed: set[str]):
    """Save processed clip IDs to file."""
    with open(PROCESSED_CLIPS_FILE, "w") as f:
        json.dump(sorted(processed), f, indent=2)


def download_clip(clip: dict, dest_dir: Path) -> Path:
    """Download a Twitch clip using yt-dlp."""

    clip_url = clip["url"]

    # Sanitize filename
    safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in clip["title"])
    safe_title = safe_title[:100]  # Limit length
    dest_path = dest_dir / f"{safe_title}.mp4"

    # Use yt-dlp to download the clip
    result = subprocess.run(
        [
            "yt-dlp",
            "--no-warnings",
            "-o", str(dest_path),
            clip_url,
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp failed: {result.stderr}")

    # Validate the downloaded file
    if not dest_path.exists():
        raise RuntimeError(f"Download failed: {dest_path} not created")

    file_size = dest_path.stat().st_size
    if file_size < 10000:  # Less than 10KB is suspicious
        raise RuntimeError(f"Downloaded file too small ({file_size} bytes), likely corrupted")

    return dest_path


def upload_to_drive(service, file_path: Path, folder_id: str, title: str) -> str:
    """Upload a file to Google Drive and return the file ID."""
    # Sanitize title for Drive filename
    safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in title)
    safe_title = safe_title[:100]

    file_metadata = {
        "name": f"{safe_title}.mp4",
        "parents": [folder_id],
    }

    media = MediaFileUpload(str(file_path), mimetype="video/mp4", resumable=True)

    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id",
    ).execute()

    return file.get("id")


def main():
    parser = argparse.ArgumentParser(
        description="Fetch Twitch clips, process for Shorts, and upload to Google Drive."
    )
    parser.add_argument(
        "-x", "--x-offset",
        type=int,
        default=0,
        help="Horizontal offset in pixels for cropping (default: 0)"
    )
    parser.add_argument(
        "-y", "--y-offset",
        type=int,
        default=0,
        help="Vertical offset in pixels for cropping (default: 0)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List clips without processing or uploading"
    )

    args = parser.parse_args()

    # Validate environment variables
    required_vars = [
        "TWITCH_CLIENT_ID",
        "TWITCH_CLIENT_SECRET",
        "TWITCH_BROADCASTER_ID",
    ]
    if not args.dry_run:
        required_vars.extend([
            "GOOGLE_CLIENT_SECRETS_FILE",
            "GOOGLE_DRIVE_FOLDER_ID",
        ])

    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        print(f"Error: Missing environment variables: {', '.join(missing)}")
        print("Create a .env file with the required variables.")
        sys.exit(1)

    # Get Twitch access token
    print("Authenticating with Twitch...")
    access_token = get_twitch_access_token()

    # Fetch clips
    broadcaster_id = os.getenv("TWITCH_BROADCASTER_ID")
    print(f"Fetching clips for broadcaster {broadcaster_id}...")
    clips = fetch_clips(access_token, broadcaster_id)
    print(f"Found {len(clips)} total clips")

    # Filter out already processed clips
    processed = load_processed_clips()
    new_clips = [c for c in clips if c["id"] not in processed]
    print(f"New clips to process: {len(new_clips)}")

    if not new_clips:
        print("No new clips to process.")
        return

    if args.dry_run:
        print("\n--- DRY RUN: Clips that would be processed ---")
        for clip in new_clips:
            print(f"  - {clip['title']} (ID: {clip['id']}, Views: {clip['view_count']})")
        return

    # Initialize Google Drive service
    print("\nAuthenticating with Google Drive...")
    folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
    drive_service = get_drive_service()

    # Process each clip
    success_count = 0
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        for clip in new_clips:
            clip_id = clip["id"]
            title = clip["title"]
            print(f"\nProcessing: {title}")

            try:
                # Download clip
                print("  Downloading...")
                downloaded_path = download_clip(clip, temp_path)

                # Process with crop script
                print("  Cropping for Shorts...")
                cropped_path = temp_path / f"{downloaded_path.stem}_shorts.mp4"
                if not crop_video_for_shorts(downloaded_path, cropped_path, args.x_offset, args.y_offset):
                    print(f"  Failed to crop clip: {title}")
                    continue

                # Upload to Drive
                print("  Uploading to Google Drive...")
                file_id = upload_to_drive(drive_service, cropped_path, folder_id, title)
                print(f"  Uploaded with ID: {file_id}")

                # Mark as processed
                processed.add(clip_id)
                save_processed_clips(processed)
                success_count += 1

            except Exception as e:
                print(f"  Error processing clip {title}: {e}")
                continue

    print(f"\nCompleted: {success_count}/{len(new_clips)} clips processed successfully")


if __name__ == "__main__":
    main()
