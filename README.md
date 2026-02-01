# frc-video-tools

A collection of video processing tools for FRC content creation.

## Dependencies

- **Python 3.10+**
- **FFmpeg** (includes ffprobe)

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
