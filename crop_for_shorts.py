#!/usr/bin/env python3
"""
Crop MP4 videos to 9:16 aspect ratio (TikTok/YouTube Shorts) from the left portion.
"""

import argparse
import subprocess
import sys
from pathlib import Path


def get_video_dimensions(video_path: Path) -> tuple[int, int]:
    """Get video width and height using ffprobe."""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=p=0",
        str(video_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    width, height = map(int, result.stdout.strip().split(","))
    return width, height


def crop_video_for_shorts(input_path: Path, output_path: Path, x_offset: int = 0, y_offset: int = 0) -> bool:
    """
    Crop video to 9:16 aspect ratio.
    Returns True on success, False on failure.
    """
    try:
        width, height = get_video_dimensions(input_path)

        # Calculate crop dimensions for 9:16 aspect ratio
        # Target aspect ratio: 9/16 = 0.5625
        target_ratio = 9 / 16
        current_ratio = width / height

        if current_ratio > target_ratio:
            # Video is wider than 9:16, crop width
            crop_width = int(height * target_ratio)
            crop_height = height
        else:
            # Video is taller/equal to 9:16, crop height
            crop_width = width
            crop_height = int(width / target_ratio)

        # Clamp offsets to valid range
        max_x = max(0, width - crop_width)
        max_y = max(0, height - crop_height)
        x_offset = min(x_offset, max_x)
        y_offset = min(y_offset, max_y)

        # Build ffmpeg command
        crop_filter = f"crop={crop_width}:{crop_height}:{x_offset}:{y_offset}"

        cmd = [
            "ffmpeg",
            "-i", str(input_path),
            "-vf", crop_filter,
            "-c:v", "libx264",  # Use H.264 codec
            "-crf", "18",  # High quality (lower = better, 18 is visually lossless)
            "-preset", "medium",  # Balance between speed and compression
            "-c:a", "copy",  # Copy audio without re-encoding
            "-y",  # Overwrite output
            str(output_path)
        ]

        print(f"Processing: {input_path.name}")
        print(f"  Original: {width}x{height}")
        print(f"  Cropped:  {crop_width}x{crop_height} at offset ({x_offset}, {y_offset})")

        subprocess.run(cmd, check=True, capture_output=True)

        # Validate output file
        if not output_path.exists():
            print(f"  Error: Output file was not created")
            return False

        output_size = output_path.stat().st_size
        if output_size < 10000:  # Less than 10KB is suspicious
            print(f"  Error: Output file too small ({output_size} bytes), likely corrupted")
            return False

        print(f"  Saved to: {output_path} ({output_size / 1024 / 1024:.1f} MB)")
        return True

    except subprocess.CalledProcessError as e:
        print(f"  Error processing {input_path.name}: {e.stderr.decode() if e.stderr else e}")
        return False
    except Exception as e:
        print(f"  Error processing {input_path.name}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Crop MP4 videos to 9:16 aspect ratio (TikTok/YouTube Shorts) from the left portion."
    )
    parser.add_argument(
        "input_dir",
        type=Path,
        help="Directory containing input MP4 files"
    )
    parser.add_argument(
        "output_dir",
        type=Path,
        help="Directory for output files"
    )
    parser.add_argument(
        "--suffix",
        default="_shorts",
        help="Suffix to add to output filenames (default: _shorts)"
    )
    parser.add_argument(
        "-x", "--x-offset",
        type=int,
        default=0,
        help="Horizontal offset in pixels from the left (default: 0)"
    )
    parser.add_argument(
        "-y", "--y-offset",
        type=int,
        default=0,
        help="Vertical offset in pixels from the top (default: 0)"
    )

    args = parser.parse_args()

    # Validate input directory
    if not args.input_dir.is_dir():
        print(f"Error: Input directory does not exist: {args.input_dir}")
        sys.exit(1)

    # Create output directory if needed
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Find all MP4 files
    mp4_files = list(args.input_dir.glob("*.mp4")) + list(args.input_dir.glob("*.MP4"))

    if not mp4_files:
        print(f"No MP4 files found in {args.input_dir}")
        sys.exit(1)

    print(f"Found {len(mp4_files)} MP4 file(s)\n")

    success_count = 0
    for input_path in sorted(mp4_files):
        output_name = f"{input_path.stem}{args.suffix}.mp4"
        output_path = args.output_dir / output_name

        if crop_video_for_shorts(input_path, output_path, args.x_offset, args.y_offset):
            success_count += 1
        print()

    print(f"Completed: {success_count}/{len(mp4_files)} videos processed successfully")


if __name__ == "__main__":
    main()
