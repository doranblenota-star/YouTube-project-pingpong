#!/usr/bin/env python3
"""Step 3: Detect and cut silence (-40dB) from input.mp4."""
import subprocess
import json
import re
import os

WORKDIR = "/home/user/YouTube-project-pingpong"
os.chdir(WORKDIR)

INPUT = "input.mp4"
OUTPUT = "no_silence.mp4"
SILENCE_DB = -40
SILENCE_MIN_DURATION = 0.5  # skip silences shorter than this

# Detect silence using ffmpeg silencedetect
print(f"Detecting silence below {SILENCE_DB}dB...")
result = subprocess.run(
    ["ffmpeg", "-i", INPUT, "-af",
     f"silencedetect=noise={SILENCE_DB}dB:d={SILENCE_MIN_DURATION}",
     "-f", "null", "-"],
    capture_output=True, text=True
)
stderr = result.stderr

# Parse silence_start and silence_end
silence_starts = [float(m) for m in re.findall(r"silence_start: ([\d.]+)", stderr)]
silence_ends = [float(m) for m in re.findall(r"silence_end: ([\d.]+)", stderr)]

# Get total duration
dur_match = re.search(r"Duration: (\d+):(\d+):([\d.]+)", stderr)
h, m, s = int(dur_match.group(1)), int(dur_match.group(2)), float(dur_match.group(3))
total_duration = h*3600 + m*60 + s

print(f"Total duration: {total_duration:.2f}s")
print(f"Found {len(silence_starts)} silence region(s)")
for i, (ss, se) in enumerate(zip(silence_starts, silence_ends)):
    print(f"  Silence {i+1}: {ss:.2f}s - {se:.2f}s ({se-ss:.2f}s)")

# Build list of non-silent segments
# Add small buffer (0.15s) around each silence boundary
BUFFER = 0.15
silence_intervals = list(zip(silence_starts, silence_ends))

audio_segments = []
prev_end = 0.0
for ss, se in silence_intervals:
    seg_end = max(prev_end, ss - BUFFER)
    if seg_end - prev_end > 0.1:
        audio_segments.append((prev_end, seg_end))
    prev_end = min(total_duration, se + BUFFER)

# Add final segment
if total_duration - prev_end > 0.1:
    audio_segments.append((prev_end, total_duration))

print(f"\nKeeping {len(audio_segments)} audio segment(s):")
for i, (start, end) in enumerate(audio_segments):
    print(f"  Segment {i+1}: {start:.2f}s - {end:.2f}s ({end-start:.2f}s)")

# Extract each segment
segment_files = []
for i, (start, end) in enumerate(audio_segments):
    seg_file = f"seg_{i:03d}.mp4"
    subprocess.run([
        "ffmpeg", "-y",
        "-ss", str(start), "-to", str(end),
        "-i", INPUT,
        "-c:v", "libx264", "-preset", "fast",
        "-c:a", "aac",
        "-avoid_negative_ts", "make_zero",
        seg_file
    ], capture_output=True, check=True)
    segment_files.append(seg_file)
    print(f"  Extracted: {seg_file}")

# Concatenate all segments
concat_list = "concat_segments.txt"
with open(concat_list, "w") as f:
    for sf in segment_files:
        f.write(f"file '{WORKDIR}/{sf}'\n")

subprocess.run([
    "ffmpeg", "-y",
    "-f", "concat", "-safe", "0",
    "-i", concat_list,
    "-c:v", "copy", "-c:a", "copy",
    OUTPUT
], capture_output=True, check=True)

# Get output duration
res = subprocess.run(
    ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", OUTPUT],
    capture_output=True, text=True
)
out_dur = float(json.loads(res.stdout)["format"]["duration"])
print(f"\nOutput: {OUTPUT} ({out_dur:.2f}s, removed {total_duration-out_dur:.2f}s of silence)")

# Cleanup segment files
for sf in segment_files:
    os.remove(sf)
os.remove(concat_list)

# Update transcript timing to match cut video
with open("transcript.json", "r", encoding="utf-8") as f:
    segments = json.load(f)

# Map original timestamps to new timestamps after silence removal
def map_time(original_t, audio_segments, silence_intervals):
    """Map original timestamp to post-silence-removal timestamp."""
    removed = 0.0
    for ss, se in silence_intervals:
        effective_ss = max(0, ss - BUFFER)
        effective_se = min(se + BUFFER, total_duration)
        if original_t > effective_se:
            removed += effective_se - effective_ss
        elif original_t > effective_ss:
            removed += original_t - effective_ss
    return max(0.0, original_t - removed)

updated_segments = []
for seg in segments:
    new_start = map_time(seg["start"], audio_segments, silence_intervals)
    new_end = map_time(seg["end"], audio_segments, silence_intervals)
    if new_end - new_start > 0.1:
        updated_segments.append({
            "start": round(new_start, 2),
            "end": round(new_end, 2),
            "text": seg["text"]
        })

with open("transcript_adjusted.json", "w", encoding="utf-8") as f:
    json.dump(updated_segments, f, ensure_ascii=False, indent=2)

print("\nAdjusted transcript timings saved to transcript_adjusted.json")
for seg in updated_segments:
    print(f"  [{seg['start']:.2f}s - {seg['end']:.2f}s] {seg['text'][:40]}...")
