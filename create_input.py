#!/usr/bin/env python3
"""Generate a sample input.mp4 with Japanese TTS audio and silent gaps."""
import subprocess
import os

WORKDIR = "/home/user/YouTube-project-pingpong"
os.chdir(WORKDIR)

# Japanese segments with silence gaps
segments = [
    ("こんにちは。今日はピンポン動画の編集パイプラインをご紹介します。", 4.0),
    (None, 2.0),  # silence
    ("まず最初に、卓球の基本的なルールについて説明します。", 4.0),
    (None, 2.5),  # silence
    ("サーブは必ずテーブルの後ろから打ちます。ボールを上に投げてから打つのがルールです。", 5.0),
    (None, 3.0),  # silence
    ("次に、ラリーのコツについてお話しします。フォームが大切です。", 4.5),
    (None, 2.0),  # silence
    ("最後に、練習方法についてまとめます。毎日の練習が上達への近道です。", 4.5),
]

# Generate audio segments
audio_parts = []
current_time = 0.0

for i, seg in enumerate(segments):
    text, duration = seg
    if text is None:
        # silence
        sil_file = f"{WORKDIR}/tmp_sil_{i}.wav"
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", f"anullsrc=r=22050:cl=mono",
            "-t", str(duration),
            sil_file
        ], capture_output=True)
        audio_parts.append(sil_file)
    else:
        speech_file = f"{WORKDIR}/tmp_speech_{i}.wav"
        subprocess.run([
            "espeak-ng", "-v", "ja", "-s", "140", "-w", speech_file, text
        ], capture_output=True)
        # Pad/trim to target duration
        padded_file = f"{WORKDIR}/tmp_padded_{i}.wav"
        subprocess.run([
            "ffmpeg", "-y", "-i", speech_file,
            "-af", f"apad=whole_dur={duration}",
            "-t", str(duration),
            padded_file
        ], capture_output=True)
        audio_parts.append(padded_file)

# Concatenate all audio parts
concat_list = f"{WORKDIR}/concat_audio.txt"
with open(concat_list, "w") as f:
    for p in audio_parts:
        f.write(f"file '{p}'\n")

subprocess.run([
    "ffmpeg", "-y", "-f", "concat", "-safe", "0",
    "-i", concat_list,
    "-ar", "22050", "-ac", "1",
    f"{WORKDIR}/full_audio.wav"
], capture_output=True, check=True)

# Get total audio duration
result = subprocess.run([
    "ffprobe", "-v", "quiet", "-print_format", "json",
    "-show_format", f"{WORKDIR}/full_audio.wav"
], capture_output=True, text=True)
import json
info = json.loads(result.stdout)
total_duration = float(info["format"]["duration"])
print(f"Total audio duration: {total_duration:.2f}s")

# Generate video with colored background and Japanese text overlays
# We'll create a simple colorful video
video_file = f"{WORKDIR}/full_video.mp4"
subprocess.run([
    "ffmpeg", "-y",
    "-f", "lavfi",
    "-i", f"color=c=0x1a1a2e:size=1280x720:rate=30:duration={total_duration}",
    "-vf", (
        f"drawtext=fontsize=48:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2-80"
        f":text='ピンポン入門':enable='between(t,0,{total_duration})',"
        f"drawtext=fontsize=28:fontcolor=0x00d4ff:x=(w-text_w)/2:y=(h-text_h)/2"
        f":text='卓球の基本を学ぼう':enable='between(t,0,{total_duration})'"
    ),
    "-c:v", "libx264", "-preset", "fast",
    video_file
], capture_output=True, check=True)

# Combine video + audio → input.mp4
subprocess.run([
    "ffmpeg", "-y",
    "-i", video_file,
    "-i", f"{WORKDIR}/full_audio.wav",
    "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
    "-shortest",
    f"{WORKDIR}/input.mp4"
], capture_output=True, check=True)

print("input.mp4 generated successfully!")

# Cleanup temp files
for f in audio_parts:
    try: os.remove(f)
    except: pass
for f in [concat_list, video_file, f"{WORKDIR}/full_audio.wav"]:
    try: os.remove(f)
    except: pass
for i in range(len(segments)):
    for prefix in ["tmp_speech_", "tmp_sil_", "tmp_padded_"]:
        try: os.remove(f"{WORKDIR}/{prefix}{i}.wav")
        except: pass
