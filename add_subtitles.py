#!/usr/bin/env python3
"""Step 4: Generate SRT subtitle file and burn into video."""
import subprocess
import json
import os

WORKDIR = "/home/user/YouTube-project-pingpong"
os.chdir(WORKDIR)

INPUT = "no_silence.mp4"
OUTPUT = "with_subtitles.mp4"
SRT_FILE = "subtitles.srt"

def seconds_to_srt_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

# Load adjusted transcript
with open("transcript_adjusted.json", "r", encoding="utf-8") as f:
    segments = json.load(f)

# Write SRT file
with open(SRT_FILE, "w", encoding="utf-8") as f:
    for i, seg in enumerate(segments, 1):
        start_t = seconds_to_srt_time(seg["start"])
        end_t = seconds_to_srt_time(seg["end"])
        f.write(f"{i}\n")
        f.write(f"{start_t} --> {end_t}\n")
        f.write(f"{seg['text']}\n\n")

print(f"SRT file written: {SRT_FILE}")
with open(SRT_FILE, "r", encoding="utf-8") as f:
    print(f.read())

# Check if Japanese font is available
font_result = subprocess.run(["fc-list", ":lang=ja"], capture_output=True, text=True)
ja_fonts = [l for l in font_result.stdout.split("\n") if l.strip()]
if ja_fonts:
    font_path = ja_fonts[0].split(":")[0].strip()
    print(f"Using Japanese font: {font_path}")
else:
    # Install Japanese font if not available
    print("Installing Japanese fonts...")
    subprocess.run(["apt-get", "install", "-y", "fonts-noto-cjk"], capture_output=True)
    font_result = subprocess.run(["fc-list", ":lang=ja"], capture_output=True, text=True)
    ja_fonts = [l for l in font_result.stdout.split("\n") if l.strip()]
    font_path = ja_fonts[0].split(":")[0].strip() if ja_fonts else ""
    print(f"Font installed: {font_path}")

# Burn subtitles using ffmpeg subtitles filter
# Use subtitles filter with force_style for Japanese font
force_style = f"FontName=Noto Sans CJK JP,FontSize=22,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2,Shadow=1,Alignment=2"

result = subprocess.run([
    "ffmpeg", "-y",
    "-i", INPUT,
    "-vf", f"subtitles={SRT_FILE}:force_style='{force_style}'",
    "-c:v", "libx264", "-preset", "fast", "-crf", "20",
    "-c:a", "copy",
    OUTPUT
], capture_output=True, text=True)

if result.returncode != 0:
    print("Warning: subtitles filter with force_style failed, trying simpler approach...")
    print(result.stderr[-500:])
    # Fallback: use drawtext with ASS subtitles
    result2 = subprocess.run([
        "ffmpeg", "-y",
        "-i", INPUT,
        "-vf", f"subtitles={SRT_FILE}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "copy",
        OUTPUT
    ], capture_output=True, text=True)
    if result2.returncode != 0:
        print("Fallback also failed:", result2.stderr[-300:])
        raise RuntimeError("Subtitle burning failed")

print(f"\nSubtitles burned into {OUTPUT}")
res = subprocess.run(
    ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", OUTPUT],
    capture_output=True, text=True
)
dur = float(json.loads(res.stdout)["format"]["duration"])
print(f"Output duration: {dur:.2f}s")
