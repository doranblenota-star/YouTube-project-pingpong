#!/usr/bin/env python3
"""Step 6: Add 5-second end card and export as output.mp4."""
import subprocess
import json
import os
from PIL import Image, ImageDraw, ImageFont

WORKDIR = "/home/user/YouTube-project-pingpong"
os.chdir(WORKDIR)

INPUT = "with_images.mp4"
OUTPUT = "output.mp4"
ENDCARD_IMG = "endcard.png"
ENDCARD_CLIP = "endcard_clip.mp4"
W, H = 1280, 720

def find_jp_font(size=48):
    font_paths = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except:
                pass
    return ImageFont.load_default()

# Generate end card image
print("Generating end card image...")
img = Image.new("RGB", (W, H), (10, 10, 30))
draw = ImageDraw.Draw(img)

# Background gradient
for y in range(H):
    t = y / H
    r = int(10 + 40 * t)
    g = int(10 + 20 * t)
    b = int(30 + 80 * t)
    draw.line([(0, y), (W, y)], fill=(r, g, b))

# Large decorative ping pong table
cx, cy = W // 2, H // 2 - 40
# Table
table_w, table_h = 500, 280
tx, ty = cx - table_w//2, cy - table_h//2
draw.rectangle([tx, ty, tx+table_w, ty+table_h], fill=(0, 80, 30), outline=(255, 255, 255), width=3)
# Table net
net_x = cx
draw.line([(net_x, ty), (net_x, ty+table_h)], fill="white", width=4)
# Table center line
draw.line([(tx, cy), (tx+table_w, cy)], fill="white", width=2)
# Ball
draw.ellipse([cx+80, cy-60, cx+110, cy-30], fill="white", outline=(200, 200, 200), width=2)

# Gold border
for i in range(3):
    draw.rectangle([6+i*3, 6+i*3, W-6-i*3, H-6-i*3], outline=(255, 215, 0), width=1)

# Main text
font_big = find_jp_font(62)
font_mid = find_jp_font(36)
font_small = find_jp_font(26)

# Title shadow + text
title = "ご視聴ありがとうございました！"
bbox = draw.textbbox((0, 0), title, font=font_big)
tw = bbox[2] - bbox[0]
tx_pos = (W - tw) // 2
draw.text((tx_pos+3, H-160+3), title, font=font_big, fill=(0, 0, 0))
draw.text((tx_pos, H-160), title, font=font_big, fill=(255, 230, 50))

# Sub text
sub = "チャンネル登録・高評価よろしくお願いします！"
bbox2 = draw.textbbox((0, 0), sub, font=font_mid)
sw = bbox2[2] - bbox2[0]
sx = (W - sw) // 2
draw.text((sx+2, H-95+2), sub, font=font_mid, fill=(0, 0, 0))
draw.text((sx, H-95), sub, font=font_mid, fill=(200, 230, 255))

# Channel name
ch = "🏓 ピンポンチャンネル"
bbox3 = draw.textbbox((0, 0), ch, font=font_small)
cw = bbox3[2] - bbox3[0]
cx_pos = (W - cw) // 2
draw.text((cx_pos, 20), ch, font=font_small, fill=(150, 200, 255))

img.save(ENDCARD_IMG)
print(f"  Saved: {ENDCARD_IMG}")

# Convert end card image to 5-second video with fade-in
subprocess.run([
    "ffmpeg", "-y",
    "-loop", "1", "-i", ENDCARD_IMG,
    "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
    "-t", "5",
    "-vf", "scale=1280:720,fade=t=in:st=0:d=0.5",
    "-c:v", "libx264", "-preset", "fast", "-crf", "20",
    "-c:a", "aac", "-b:a", "128k",
    "-pix_fmt", "yuv420p",
    ENDCARD_CLIP
], capture_output=True, check=True)
print(f"  Created 5-second end card clip: {ENDCARD_CLIP}")

# Get input duration
res = subprocess.run(
    ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", INPUT],
    capture_output=True, text=True
)
input_dur = float(json.loads(res.stdout)["format"]["duration"])
print(f"\nBase video duration: {input_dur:.2f}s")

# Add fade-out to last 1 second of base video
base_faded = "base_faded.mp4"
subprocess.run([
    "ffmpeg", "-y", "-i", INPUT,
    "-vf", f"fade=t=out:st={input_dur-1.0}:d=1.0",
    "-c:v", "libx264", "-preset", "fast", "-crf", "20",
    "-c:a", "copy",
    base_faded
], capture_output=True, check=True)
print("  Added fade-out to base video")

# Concatenate: base video + end card
concat_list = "concat_output.txt"
with open(concat_list, "w") as f:
    f.write(f"file '{WORKDIR}/{base_faded}'\n")
    f.write(f"file '{WORKDIR}/{ENDCARD_CLIP}'\n")

subprocess.run([
    "ffmpeg", "-y",
    "-f", "concat", "-safe", "0",
    "-i", concat_list,
    "-c:v", "libx264", "-preset", "medium", "-crf", "20",
    "-c:a", "aac", "-b:a", "128k",
    "-movflags", "+faststart",
    OUTPUT
], capture_output=True, check=True)

# Get final output info
res = subprocess.run(
    ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", OUTPUT],
    capture_output=True, text=True
)
info = json.loads(res.stdout)
out_dur = float(info["format"]["duration"])
out_size = int(info["format"]["size"])
streams = info["streams"]

print(f"\n{'='*50}")
print(f"✅ output.mp4 完成！")
print(f"{'='*50}")
print(f"  Duration : {out_dur:.2f}s ({out_dur/60:.1f}分)")
print(f"  File size: {out_size / 1024 / 1024:.2f} MB")
for s in streams:
    if s["codec_type"] == "video":
        print(f"  Video    : {s['codec_name']} {s.get('width')}x{s.get('height')} @ {s.get('r_frame_rate')} fps")
    elif s["codec_type"] == "audio":
        print(f"  Audio    : {s['codec_name']} {s.get('sample_rate')}Hz")

# Cleanup
for f in [base_faded, ENDCARD_CLIP, concat_list]:
    if os.path.exists(f):
        os.remove(f)

print("\n処理完了！output.mp4 が出力されました。")
