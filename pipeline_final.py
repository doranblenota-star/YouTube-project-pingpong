#!/usr/bin/env python3
"""
Complete video editing pipeline using ffmpeg filter_complex for precise timing.
Rebuilds everything from no_silence.mp4 with correct timestamps.
"""
import subprocess
import json
import os
from PIL import Image, ImageDraw, ImageFont

WORKDIR = "/home/user/YouTube-project-pingpong"
os.chdir(WORKDIR)

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
            except Exception:
                pass
    return ImageFont.load_default()

def run(cmd, check=True):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if check and r.returncode != 0:
        print("STDERR:", r.stderr[-600:])
        raise RuntimeError(f"Command failed: {' '.join(cmd[:5])}")
    return r

def get_duration(path):
    r = run(["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", path])
    return float(json.loads(r.stdout)["format"]["duration"])

# ─── Re-encode no_silence.mp4 to reset timestamps to 0 ───────────────────────
print("Step A: Re-encoding no_silence.mp4 to clean timestamps...")
run([
    "ffmpeg", "-y", "-i", "no_silence.mp4",
    "-c:v", "libx264", "-preset", "fast", "-crf", "20",
    "-c:a", "aac", "-b:a", "128k",
    "-ar", "44100",        # normalize sample rate
    "-pix_fmt", "yuv420p",
    "clean_base.mp4"
])
base_dur = get_duration("clean_base.mp4")
print(f"  clean_base.mp4 duration: {base_dur:.2f}s")

# ─── Burn subtitles ───────────────────────────────────────────────────────────
print("\nStep B: Burning subtitles...")
force_style = "FontName=Noto Serif CJK JP,FontSize=22,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2,Shadow=1,Alignment=2"
run([
    "ffmpeg", "-y", "-i", "clean_base.mp4",
    "-vf", f"subtitles=subtitles.srt:force_style='{force_style}'",
    "-c:v", "libx264", "-preset", "fast", "-crf", "20",
    "-c:a", "copy",
    "subtitled_base.mp4"
])
print(f"  subtitled_base.mp4 ready")

# ─── Generate 3 content-aware images ─────────────────────────────────────────
print("\nStep C: Generating images...")

images_config = [
    {
        "name": "image1_rules.png",
        "title": "卓球のルール",
        "subtitle": "基本ルールをマスターしよう！",
        "bg_color": (20, 40, 100),
        "accent_color": (0, 200, 255),
        "insert_at": 2.0,    # seconds in clean_base timeline
        "duration": 2.5,
    },
    {
        "name": "image2_serve.png",
        "title": "サーブの打ち方",
        "subtitle": "ボールを上に投げてから打つ！",
        "bg_color": (15, 60, 35),
        "accent_color": (0, 230, 110),
        "insert_at": 6.0,
        "duration": 2.5,
    },
    {
        "name": "image3_practice.png",
        "title": "毎日の練習",
        "subtitle": "継続は力なり！上達への近道",
        "bg_color": (60, 15, 15),
        "accent_color": (255, 120, 0),
        "insert_at": 13.0,
        "duration": 2.5,
    },
]

def make_image(cfg):
    img = Image.new("RGB", (W, H), cfg["bg_color"])
    draw = ImageDraw.Draw(img)

    # Background gradient
    bg = cfg["bg_color"]
    ac = cfg["accent_color"]
    for y in range(H):
        t = y / H
        r = int(bg[0] + (ac[0] - bg[0]) * t * 0.25)
        g = int(bg[1] + (ac[1] - bg[1]) * t * 0.25)
        b = int(bg[2] + (ac[2] - bg[2]) * t * 0.25)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # Border
    for i in range(3):
        draw.rectangle([6+i*3, 6+i*3, W-7-i*3, H-7-i*3], outline=ac, width=2)

    # Ping pong ball
    cx, cy = W//2, H//2 - 40
    for r in [220, 195, 170]:
        draw.ellipse([cx-r, cy-r, cx+r, cy+r], outline=(*ac, 60), width=1)
    ball_r = 55
    draw.ellipse([cx+70, cy-65, cx+70+ball_r*2, cy-65+ball_r*2],
                 fill="white", outline=ac, width=3)
    draw.arc([cx+70, cy-65, cx+70+ball_r*2, cy-65+ball_r*2],
             start=30, end=150, fill=ac, width=3)

    # Table silhouette
    tw, th = 360, 200
    draw.rectangle([cx-tw//2, cy-th//2, cx+tw//2, cy+th//2],
                   fill=(0, 70, 25), outline="white", width=2)
    draw.line([(cx, cy-th//2), (cx, cy+th//2)], fill="white", width=3)
    draw.line([(cx-tw//2, cy), (cx+tw//2, cy)], fill="white", width=2)

    # Text
    f_big = find_jp_font(60)
    f_mid = find_jp_font(36)

    # Title
    title = cfg["title"]
    bb = draw.textbbox((0, 0), title, font=f_big)
    tx = (W - (bb[2]-bb[0])) // 2
    ty_pos = H - 185
    draw.text((tx+3, ty_pos+3), title, font=f_big, fill=(0, 0, 0))
    draw.text((tx, ty_pos), title, font=f_big, fill="white")

    # Subtitle
    sub = cfg["subtitle"]
    bb2 = draw.textbbox((0, 0), sub, font=f_mid)
    sx = (W - (bb2[2]-bb2[0])) // 2
    draw.text((sx+2, ty_pos+72), sub, font=f_mid, fill=(0, 0, 0))
    draw.text((sx, ty_pos+70), sub, font=f_mid, fill=ac)

    img.save(cfg["name"])
    print(f"  {cfg['name']} saved")

for cfg in images_config:
    make_image(cfg)

# ─── Convert images to video clips (with silent audio) ───────────────────────
print("\nStep D: Converting images to video clips...")
for cfg in images_config:
    clip = cfg["name"].replace(".png", "_clip.mp4")
    run([
        "ffmpeg", "-y",
        "-loop", "1", "-i", cfg["name"],
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
        "-t", str(cfg["duration"]),
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "128k",
        "-pix_fmt", "yuv420p",
        "-vf", "scale=1280:720",
        "-r", "30",
        clip
    ])
    print(f"  {clip} ready ({cfg['duration']}s)")

# ─── Generate end card ────────────────────────────────────────────────────────
print("\nStep E: Generating end card...")
img = Image.new("RGB", (W, H), (8, 8, 25))
draw = ImageDraw.Draw(img)
# Gradient
for y in range(H):
    t = y / H
    draw.line([(0, y), (W, y)], fill=(int(8+35*t), int(8+15*t), int(25+70*t)))

# Gold borders
for i in range(4):
    draw.rectangle([5+i*4, 5+i*4, W-5-i*4, H-5-i*4], outline=(255, 200, 0), width=1)

# Trophy / ping pong illustration
cx, cy = W//2, H//2 - 50
for r in [180, 155, 130]:
    draw.ellipse([cx-r, cy-r, cx+r, cy+r], outline=(255, 200, 0, 50), width=1)
ball_r = 65
draw.ellipse([cx-ball_r, cy-ball_r-10, cx+ball_r, cy+ball_r-10],
             fill="white", outline=(200, 200, 200), width=3)
draw.arc([cx-ball_r, cy-ball_r-10, cx+ball_r, cy+ball_r-10],
         start=20, end=160, fill=(100, 180, 255), width=4)

# Text
f_big = find_jp_font(58)
f_mid = find_jp_font(34)
f_sm  = find_jp_font(24)

title = "ご視聴ありがとうございました！"
bb = draw.textbbox((0, 0), title, font=f_big)
tx = (W - (bb[2]-bb[0])) // 2
draw.text((tx+3, H-165+3), title, font=f_big, fill=(0,0,0))
draw.text((tx, H-165), title, font=f_big, fill=(255, 230, 50))

sub = "チャンネル登録・高評価よろしくお願いします！"
bb2 = draw.textbbox((0, 0), sub, font=f_mid)
sx = (W - (bb2[2]-bb2[0])) // 2
draw.text((sx+2, H-97+2), sub, font=f_mid, fill=(0,0,0))
draw.text((sx, H-97), sub, font=f_mid, fill=(180, 210, 255))

ch = "ピンポンチャンネル"
bb3 = draw.textbbox((0, 0), ch, font=f_sm)
cx3 = (W - (bb3[2]-bb3[0])) // 2
draw.text((cx3, 22), ch, font=f_sm, fill=(140, 190, 255))

img.save("endcard.png")

run([
    "ffmpeg", "-y",
    "-loop", "1", "-i", "endcard.png",
    "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
    "-t", "5",
    "-vf", "scale=1280:720,fade=t=in:st=0:d=0.8,fade=t=out:st=4.2:d=0.8",
    "-c:v", "libx264", "-preset", "fast", "-crf", "20",
    "-c:a", "aac", "-b:a", "128k",
    "-pix_fmt", "yuv420p",
    "-r", "30",
    "endcard_clip.mp4"
])
print("  endcard_clip.mp4 ready (5s)")

# ─── Build final video using filter_complex concat ────────────────────────────
print("\nStep F: Assembling final output.mp4 with filter_complex...")

# Build the segment list for filter_complex concat
# Order: base[0..t1] -> img1 -> base[t1..t2] -> img2 -> base[t2..t3] -> img3 -> base[t3..end] -> endcard
insert_points = sorted(images_config, key=lambda x: x["insert_at"])

# Extract base video segments precisely using -accurate_seek
base_segs = []
prev_t = 0.0
for i, cfg in enumerate(insert_points):
    ins_t = cfg["insert_at"]
    seg_f = f"final_base_{i:02d}.mp4"
    if ins_t - prev_t > 0.05:
        run([
            "ffmpeg", "-y",
            "-ss", str(prev_t),
            "-to", str(ins_t),
            "-i", "subtitled_base.mp4",
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-c:a", "aac", "-b:a", "128k",
            "-ar", "44100",
            "-reset_timestamps", "1",
            "-pix_fmt", "yuv420p",
            seg_f
        ])
        base_segs.append(seg_f)
    prev_t = ins_t

# Final base segment
last_seg = f"final_base_{len(insert_points):02d}.mp4"
run([
    "ffmpeg", "-y",
    "-ss", str(prev_t),
    "-i", "subtitled_base.mp4",
    "-c:v", "libx264", "-preset", "fast", "-crf", "20",
    "-c:a", "aac", "-b:a", "128k",
    "-ar", "44100",
    "-reset_timestamps", "1",
    "-pix_fmt", "yuv420p",
    last_seg
])
base_segs.append(last_seg)

# Build the ordered file list: base0, img1, base1, img2, base2, img3, base3, endcard
ordered = []
for i, cfg in enumerate(insert_points):
    if i < len(base_segs) - 1:
        ordered.append(base_segs[i])
    ordered.append(cfg["name"].replace(".png", "_clip.mp4"))
ordered.append(base_segs[-1])
ordered.append("endcard_clip.mp4")

print(f"  Concatenating {len(ordered)} clips:")
total_expected = 0.0
for f in ordered:
    d = get_duration(f)
    total_expected += d
    print(f"    {f}: {d:.2f}s")
print(f"  Expected total: {total_expected:.2f}s")

# Write concat file
with open("final_concat.txt", "w") as f:
    for clip in ordered:
        f.write(f"file '{WORKDIR}/{clip}'\n")

run([
    "ffmpeg", "-y",
    "-f", "concat", "-safe", "0",
    "-i", "final_concat.txt",
    "-c:v", "libx264", "-preset", "medium", "-crf", "20",
    "-c:a", "aac", "-b:a", "128k",
    "-movflags", "+faststart",
    "-pix_fmt", "yuv420p",
    "output.mp4"
])

# Final verification
out_dur = get_duration("output.mp4")
r = run(["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", "output.mp4"])
streams = json.loads(r.stdout)["streams"]
size_bytes = os.path.getsize("output.mp4")

print(f"\n{'='*55}")
print(f"  output.mp4 完成！")
print(f"{'='*55}")
print(f"  Duration : {out_dur:.2f}s ({int(out_dur//60)}分{int(out_dur%60)}秒)")
print(f"  File size: {size_bytes/1024/1024:.2f} MB")
for s in streams:
    if s["codec_type"] == "video":
        fps = s.get("r_frame_rate","?")
        print(f"  Video    : {s['codec_name']} {s.get('width')}x{s.get('height')} {fps}fps")
    elif s["codec_type"] == "audio":
        print(f"  Audio    : {s['codec_name']} {s.get('sample_rate')}Hz {s.get('channel_layout','')}")

print(f"\n処理内容:")
print(f"  [1] Whisper文字起こし (日本語) → 5セグメント")
print(f"  [2] 無音カット (−40dB) → 11.52秒削除")
print(f"  [3] SRT字幕生成・焼き付け → 5行")
print(f"  [4] 内容別画像3枚挿入 (各2.5秒)")
print(f"       image1: 卓球のルール (t={insert_points[0]['insert_at']}s)")
print(f"       image2: サーブの打ち方 (t={insert_points[1]['insert_at']}s)")
print(f"       image3: 毎日の練習 (t={insert_points[2]['insert_at']}s)")
print(f"  [5] エンドカード5秒追加")
print(f"  → output.mp4 書き出し完了")

# Cleanup temp files
for f in base_segs + ["final_concat.txt", "endcard_clip.mp4", "clean_base.mp4", "subtitled_base.mp4"]:
    if os.path.exists(f):
        os.remove(f)
for cfg in images_config:
    clip = cfg["name"].replace(".png", "_clip.mp4")
    if os.path.exists(clip):
        os.remove(clip)
print("\n一時ファイルをクリーンアップしました。")
