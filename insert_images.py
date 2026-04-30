#!/usr/bin/env python3
"""Step 5: Generate 3 content-aware images and insert them into the video."""
import subprocess
import json
import os
from PIL import Image, ImageDraw, ImageFont

WORKDIR = "/home/user/YouTube-project-pingpong"
os.chdir(WORKDIR)

INPUT = "with_subtitles.mp4"
OUTPUT = "with_images.mp4"

# Get video duration
res = subprocess.run(
    ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", INPUT],
    capture_output=True, text=True
)
total_dur = float(json.loads(res.stdout)["format"]["duration"])
print(f"Input duration: {total_dur:.2f}s")

# Content-aware image definitions (based on video transcript)
# Insert at 3 points: after intro, after rules section, after serving explanation
images_config = [
    {
        "name": "image1_rules.png",
        "title": "卓球のルール",
        "subtitle": "基本ルールをマスターしよう！",
        "emoji_text": "🏓",
        "bg_color": (26, 42, 108),     # deep blue
        "accent_color": (0, 212, 255),
        "insert_time": 2.5,            # after intro
        "display_dur": 2.0,
    },
    {
        "name": "image2_serve.png",
        "title": "サーブの打ち方",
        "subtitle": "ボールを上に投げてから打つ！",
        "emoji_text": "⬆",
        "bg_color": (17, 68, 42),      # deep green
        "accent_color": (0, 255, 128),
        "insert_time": 6.5,            # after rules
        "display_dur": 2.0,
    },
    {
        "name": "image3_practice.png",
        "title": "毎日の練習",
        "subtitle": "継続は力なり！",
        "emoji_text": "💪",
        "bg_color": (68, 17, 17),      # deep red
        "accent_color": (255, 128, 0),
        "insert_time": 14.0,           # near end
        "display_dur": 2.0,
    },
]

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

def generate_image(cfg):
    img = Image.new("RGB", (W, H), cfg["bg_color"])
    draw = ImageDraw.Draw(img)

    # Draw gradient-like stripes
    for i in range(0, H, 4):
        alpha = int(255 * (0.3 + 0.7 * i / H))
        r = int(cfg["bg_color"][0] * (1 - i/H) + cfg["accent_color"][0] * (i/H) * 0.3)
        g = int(cfg["bg_color"][1] * (1 - i/H) + cfg["accent_color"][1] * (i/H) * 0.3)
        b = int(cfg["bg_color"][2] * (1 - i/H) + cfg["accent_color"][2] * (i/H) * 0.3)
        draw.line([(0, i), (W, i)], fill=(r, g, b))

    # Decorative border
    border_w = 8
    draw.rectangle([border_w, border_w, W-border_w, H-border_w],
                   outline=cfg["accent_color"], width=border_w)

    # Decorative diagonal lines
    for x in range(0, W+H, 80):
        draw.line([(x, 0), (x-H, H)], fill=(*cfg["accent_color"], 40), width=2)

    # Central circle decoration
    cx, cy = W // 2, H // 2
    for r in [200, 180, 160]:
        draw.ellipse([cx-r, cy-r, cx+r, cy+r],
                     outline=cfg["accent_color"], width=2)

    # Ping pong ball decoration
    ball_r = 60
    draw.ellipse([cx-ball_r, cy-ball_r-30, cx+ball_r, cy+ball_r-30],
                 fill="white", outline=cfg["accent_color"], width=4)
    # Ball curve line
    draw.arc([cx-ball_r, cy-ball_r-30, cx+ball_r, cy+ball_r-30],
             start=0, end=180, fill=cfg["accent_color"], width=3)

    # Title text
    font_title = find_jp_font(56)
    font_sub = find_jp_font(34)
    font_small = find_jp_font(24)

    title = cfg["title"]
    subtitle = cfg["subtitle"]

    # Title with shadow
    bbox = draw.textbbox((0, 0), title, font=font_title)
    tw = bbox[2] - bbox[0]
    tx = (W - tw) // 2
    ty = H // 2 + 100
    draw.text((tx+2, ty+2), title, font=font_title, fill=(0, 0, 0))
    draw.text((tx, ty), title, font=font_title, fill="white")

    # Subtitle
    bbox2 = draw.textbbox((0, 0), subtitle, font=font_sub)
    sw = bbox2[2] - bbox2[0]
    sx = (W - sw) // 2
    sy = ty + 70
    draw.text((sx+1, sy+1), subtitle, font=font_sub, fill=(0, 0, 0))
    draw.text((sx, sy), subtitle, font=font_sub, fill=cfg["accent_color"])

    img.save(cfg["name"])
    print(f"  Generated: {cfg['name']}")
    return cfg["name"]

# Generate all images
print("Generating content-aware images...")
for cfg in images_config:
    generate_image(cfg)

# Convert each image to a 2-second video clip
print("\nConverting images to video clips...")
image_clips = []
for cfg in images_config:
    clip_file = cfg["name"].replace(".png", "_clip.mp4")
    subprocess.run([
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", cfg["name"],
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
        "-t", str(cfg["display_dur"]),
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "128k",
        "-pix_fmt", "yuv420p",
        "-vf", "scale=1280:720",
        clip_file
    ], capture_output=True, check=True)
    print(f"  Created clip: {clip_file}")
    image_clips.append((cfg["insert_time"], cfg["display_dur"], clip_file))

# Build the final video by inserting image clips at the specified times
# Strategy: split the base video at each insert point, interleave image clips
print("\nInserting image clips into video...")

# Sort by insert time
image_clips.sort(key=lambda x: x[0])

# Get video streams info
res = subprocess.run([
    "ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", INPUT
], capture_output=True, text=True)
streams = json.loads(res.stdout)["streams"]
has_audio = any(s["codec_type"] == "audio" for s in streams)

# Split the base video into segments around insert points
base_segments = []
prev_t = 0.0

for insert_t, display_dur, clip_file in image_clips:
    # Segment before insert point
    if insert_t - prev_t > 0.05:
        seg_file = f"base_seg_{len(base_segments):03d}.mp4"
        subprocess.run([
            "ffmpeg", "-y",
            "-ss", str(prev_t), "-to", str(insert_t),
            "-i", INPUT,
            "-c:v", "libx264", "-preset", "fast",
            "-c:a", "aac",
            "-avoid_negative_ts", "make_zero",
            seg_file
        ], capture_output=True, check=True)
        base_segments.append(("base", seg_file))

    base_segments.append(("image", clip_file))
    prev_t = insert_t

# Final segment after last insert
if total_dur - prev_t > 0.05:
    seg_file = f"base_seg_{len(base_segments):03d}.mp4"
    subprocess.run([
        "ffmpeg", "-y",
        "-ss", str(prev_t),
        "-i", INPUT,
        "-c:v", "libx264", "-preset", "fast",
        "-c:a", "aac",
        "-avoid_negative_ts", "make_zero",
        seg_file
    ], capture_output=True, check=True)
    base_segments.append(("base", seg_file))

print(f"  Split into {len(base_segments)} segments")

# Concatenate all segments
concat_list = "concat_final.txt"
with open(concat_list, "w") as f:
    for seg_type, seg_file in base_segments:
        f.write(f"file '{WORKDIR}/{seg_file}'\n")

subprocess.run([
    "ffmpeg", "-y",
    "-f", "concat", "-safe", "0",
    "-i", concat_list,
    "-c:v", "libx264", "-preset", "fast", "-crf", "20",
    "-c:a", "aac", "-b:a", "128k",
    OUTPUT
], capture_output=True, check=True)

res = subprocess.run(
    ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", OUTPUT],
    capture_output=True, text=True
)
out_dur = float(json.loads(res.stdout)["format"]["duration"])
print(f"\nOutput: {OUTPUT} ({out_dur:.2f}s, added {out_dur - total_dur:.2f}s of image clips)")

# Cleanup
for seg_type, seg_file in base_segments:
    if seg_type == "base" and os.path.exists(seg_file):
        os.remove(seg_file)
for cfg in images_config:
    clip = cfg["name"].replace(".png", "_clip.mp4")
    if os.path.exists(clip):
        os.remove(clip)
if os.path.exists(concat_list):
    os.remove(concat_list)
