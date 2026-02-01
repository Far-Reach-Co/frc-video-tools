# frc-video-tools

A collection of video processing tools for FRC content creation.

## Dependencies

- **Python 3.10+**
- **FFmpeg** (includes ffprobe)
- **yt-dlp** (for downloading Twitch clips)

### Installing FFmpeg

**macOS (Homebrew):**
```bash
brew install ffmpeg
```

**Ubuntu/Debian:**
```bash
sudo apt install ffmpeg
```

**Windows:**
Download from https://ffmpeg.org/download.html and add to PATH.

### Installing yt-dlp

```bash
pip install yt-dlp
```

Or via Homebrew on macOS:
```bash
brew install yt-dlp
```

### Python Dependencies

```bash
pip install -r requirements.txt
```

---

## process_twitch_clips.py

Automated pipeline that fetches Twitch clips, crops them for Shorts, and uploads to Google Drive.

### Setup

1. **Create a `.env` file** with the following variables:

```env
# Twitch API credentials (from https://dev.twitch.tv/console)
TWITCH_CLIENT_ID=your_client_id
TWITCH_CLIENT_SECRET=your_client_secret
TWITCH_BROADCASTER_ID=broadcaster_id_to_fetch_clips_from

# Google Drive (for uploading processed clips)
GOOGLE_CLIENT_SECRETS_FILE=path/to/client_secrets.json
GOOGLE_DRIVE_FOLDER_ID=folder_id_for_uploads
```

2. **Get Twitch API credentials:**
   - Go to https://dev.twitch.tv/console
   - Create a new application
   - Copy the Client ID and generate a Client Secret

3. **Get Google Drive credentials:**
   - Go to https://console.cloud.google.com
   - Create a project and enable the Google Drive API
   - Create OAuth 2.0 credentials (Desktop app)
   - Download the JSON file and set `GOOGLE_CLIENT_SECRETS_FILE` to its path

4. **Find the broadcaster ID:**
   - Use the Twitch API or a tool like https://www.streamweasels.com/tools/convert-twitch-username-to-user-id/

### Usage

```bash
python3 process_twitch_clips.py [options]
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--dry-run` | - | List clips without processing or uploading |
| `-x`, `--x-offset` | `0` | Horizontal offset in pixels for cropping |
| `-y`, `--y-offset` | `0` | Vertical offset in pixels for cropping |

### Examples

Dry run to see what clips would be processed:
```bash
python3 process_twitch_clips.py --dry-run
```

Process all new clips:
```bash
python3 process_twitch_clips.py
```

Process with custom crop offset:
```bash
python3 process_twitch_clips.py -x 200
```

### How it works

1. Authenticates with Twitch API using client credentials
2. Fetches all clips for the configured broadcaster
3. Filters out already-processed clips (tracked in `processed_clips.json`)
4. For each new clip:
   - Downloads using yt-dlp (same quality as Twitch download button)
   - Crops to 9:16 aspect ratio using ffmpeg
   - Uploads to Google Drive
   - Marks as processed
5. On first run, authenticates with Google (opens browser for OAuth)

---

## crop_for_shorts.py

Batch crop MP4 videos to 9:16 aspect ratio for TikTok/YouTube Shorts.

### Usage

```bash
python3 crop_for_shorts.py <input_dir> <output_dir> [options]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `input_dir` | Directory containing input MP4 files |
| `output_dir` | Directory for output files (created if doesn't exist) |

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--suffix` | `_shorts` | Suffix added to output filenames |
| `-x`, `--x-offset` | `0` | Horizontal offset in pixels from left edge |
| `-y`, `--y-offset` | `0` | Vertical offset in pixels from top edge |

### Examples

Basic usage (crops from left edge):
```bash
python3 crop_for_shorts.py ./raw_clips ./shorts_output
```

With horizontal offset to capture different part of frame:
```bash
python3 crop_for_shorts.py ./raw_clips ./shorts_output -x 200
```

Custom suffix:
```bash
python3 crop_for_shorts.py ./raw_clips ./shorts_output --suffix "_tiktok"
```

### How it works

1. Reads each MP4 file from the input directory
2. Calculates the crop dimensions needed for 9:16 aspect ratio
3. Applies x/y offset (clamped to valid bounds)
4. Outputs cropped video with audio preserved
