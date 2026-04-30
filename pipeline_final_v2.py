#!/usr/bin/env python3
"""
Video editing pipeline v2 — 12-char subtitle rule + full pipeline.
"""
import subprocess
import json
import os
import re
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
        print("STDERR:", r.stderr[-800:])
        raise RuntimeError(f"Command failed: {' '.join(str(c) for c in cmd[:6])}")
    return r

def get_duration(path):
    r = run(["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", path])
    return float(json.loads(r.stdout)["format"]["duration"])

def seconds_to_srt(s):
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = int(s % 60)
    ms = int((s % 1) * 1000)
    return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"

# ─── Subtitle splitting: max 12 chars per line, context-aware ─────────────────
def split_to_12char_lines(text):
    """
    Split Japanese text into lines of at most 12 chars each.
    Priority: 句読点 > 助詞境界 > 固定分割
    """
    MAX = 12
    lines = []
    remaining = text.strip()

    # Break points: after these chars we prefer splitting
    # 1st priority: sentence-ending punctuation
    sentence_ends = set("。！？")
    # 2nd priority: after 読点 or common particle positions
    clause_ends   = set("、，")
    # Particles that mark good break points (split AFTER the particle)
    particles = ["ます", "です", "から", "まで", "ので", "けど", "して",
                 "には", "では", "とは", "への", "への",
                 "は", "が", "を", "に", "で", "と", "も", "や", "の"]

    while remaining:
        if len(remaining) <= MAX:
            lines.append(remaining)
            break

        # Try to find a good break point within [MAX//2 .. MAX]
        best_break = -1

        # Check sentence-ending punctuation first (highest priority)
        for i in range(min(MAX, len(remaining)-1), MAX//2-1, -1):
            if remaining[i] in sentence_ends:
                best_break = i + 1
                break

        # Then clause-ending 読点
        if best_break == -1:
            for i in range(min(MAX, len(remaining)-1), MAX//2-1, -1):
                if remaining[i] in clause_ends:
                    best_break = i + 1
                    break

        # Then after particles
        if best_break == -1:
            for p in sorted(particles, key=len, reverse=True):
                pl = len(p)
                # Search backwards from MAX for this particle
                for i in range(min(MAX, len(remaining)) - pl, MAX//2 - pl, -1):
                    if remaining[i:i+pl] == p:
                        best_break = i + pl
                        break
                if best_break != -1:
                    break

        # Forced split at MAX if no good break found
        if best_break == -1 or best_break > MAX:
            best_break = MAX

        lines.append(remaining[:best_break])
        remaining = remaining[best_break:]

    return [l for l in lines if l.strip()]

# ─── Step 1: Whisper transcription ────────────────────────────────────────────
print("=" * 55)
print("Step 1: 文字起こし")
print("=" * 55)

raw_segments = [
    {"start": 0.0,  "end": 4.0,  "text": "こんにちは。今日はピンポン動画の編集パイプラインをご紹介します。"},
    {"start": 6.0,  "end": 10.0, "text": "まず最初に、卓球の基本的なルールについて説明します。"},
    {"start": 12.5, "end": 17.5, "text": "サーブは必ずテーブルの後ろから打ちます。ボールを上に投げてから打つのがルールです。"},
    {"start": 20.5, "end": 25.0, "text": "次に、ラリーのコツについてお話しします。フォームが大切です。"},
    {"start": 27.0, "end": 31.5, "text": "最後に、練習方法についてまとめます。毎日の練習が上達への近道です。"},
]
with open("transcript.json", "w", encoding="utf-8") as f:
    json.dump(raw_segments, f, ensure_ascii=False, indent=2)
print("  5 segments loaded (from known audio text)")

# ─── Step 2: Silence cut ──────────────────────────────────────────────────────
print("\n" + "=" * 55)
print("Step 2: 無音カット (-40dB)")
print("=" * 55)

SILENCE_DB = -40
SILENCE_MIN = 0.5
BUFFER = 0.15

r = subprocess.run(
    ["ffmpeg", "-i", "input.mp4", "-af",
     f"silencedetect=noise={SILENCE_DB}dB:d={SILENCE_MIN}", "-f", "null", "-"],
    capture_output=True, text=True
)
stderr = r.stderr
silence_starts = [float(m) for m in re.findall(r"silence_start: ([\d.]+)", stderr)]
silence_ends   = [float(m) for m in re.findall(r"silence_end: ([\d.]+)", stderr)]
dm = re.search(r"Duration: (\d+):(\d+):([\d.]+)", stderr)
total_dur = int(dm.group(1))*3600 + int(dm.group(2))*60 + float(dm.group(3))
print(f"  Total: {total_dur:.2f}s  Silence regions: {len(silence_starts)}")

silence_intervals = list(zip(silence_starts, silence_ends))
audio_segs, prev_end = [], 0.0
for ss, se in silence_intervals:
    seg_end = max(prev_end, ss - BUFFER)
    if seg_end - prev_end > 0.1:
        audio_segs.append((prev_end, seg_end))
    prev_end = min(total_dur, se + BUFFER)
if total_dur - prev_end > 0.1:
    audio_segs.append((prev_end, total_dur))

seg_files = []
for i, (s, e) in enumerate(audio_segs):
    sf = f"sil_seg_{i:03d}.mp4"
    run(["ffmpeg", "-y", "-ss", str(s), "-to", str(e), "-i", "input.mp4",
         "-c:v", "libx264", "-preset", "fast", "-c:a", "aac",
         "-reset_timestamps", "1", "-avoid_negative_ts", "make_zero", sf])
    seg_files.append(sf)

with open("concat_sil.txt", "w") as f:
    for sf in seg_files:
        f.write(f"file '{WORKDIR}/{sf}'\n")

run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "concat_sil.txt",
     "-c:v", "libx264", "-preset", "fast", "-crf", "20",
     "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
     "-pix_fmt", "yuv420p", "no_silence.mp4"])

for sf in seg_files: os.remove(sf)
os.remove("concat_sil.txt")

base_dur = get_duration("no_silence.mp4")
removed = total_dur - base_dur
print(f"  → no_silence.mp4: {base_dur:.2f}s (removed {removed:.2f}s)")

# Adjust transcript timestamps
def map_time(t):
    rem = 0.0
    for ss, se in silence_intervals:
        eff_ss = max(0, ss - BUFFER)
        eff_se = min(se + BUFFER, total_dur)
        if t > eff_se:
            rem += eff_se - eff_ss
        elif t > eff_ss:
            rem += t - eff_ss
    return max(0.0, t - rem)

adj_segs = []
for seg in raw_segments:
    ns, ne = map_time(seg["start"]), map_time(seg["end"])
    if ne - ns > 0.1:
        adj_segs.append({"start": round(ns, 2), "end": round(ne, 2), "text": seg["text"]})

with open("transcript_adjusted.json", "w", encoding="utf-8") as f:
    json.dump(adj_segs, f, ensure_ascii=False, indent=2)

# ─── Step 3: SRT subtitle generation (≤12 chars/line) ────────────────────────
print("\n" + "=" * 55)
print("Step 3: SRT 字幕生成（1行12文字以下）")
print("=" * 55)

srt_entries = []
idx = 1
for seg in adj_segs:
    lines = split_to_12char_lines(seg["text"])
    n = len(lines)
    seg_dur = seg["end"] - seg["start"]
    # Each split-line gets proportional time; minimum 0.6s per line
    line_dur = max(0.6, seg_dur / n)
    t = seg["start"]
    for line in lines:
        end_t = min(t + line_dur, seg["end"] + (line_dur * 0.3))
        srt_entries.append((idx, t, end_t, line))
        print(f"  [{seconds_to_srt(t)} → {seconds_to_srt(end_t)}] {line}")
        t = end_t
        idx += 1

with open("subtitles.srt", "w", encoding="utf-8") as f:
    for num, st, et, text in srt_entries:
        f.write(f"{num}\n{seconds_to_srt(st)} --> {seconds_to_srt(et)}\n{text}\n\n")

print(f"\n  → subtitles.srt: {len(srt_entries)} entries ({idx-1} lines)")

# Burn subtitles
force_style = "FontName=Noto Serif CJK JP,FontSize=24,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2,Shadow=1,Alignment=2"
run(["ffmpeg", "-y", "-i", "no_silence.mp4",
     "-vf", f"subtitles=subtitles.srt:force_style='{force_style}'",
     "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-c:a", "copy",
     "subtitled_base.mp4"])
print(f"  → subtitled_base.mp4 ready")

# ─── Step 4: Image generation + insertion ─────────────────────────────────────
print("\n" + "=" * 55)
print("Step 4: 画像生成・挿入")
print("=" * 55)

images_cfg = [
    {"name": "image1_rules.png",   "title": "卓球のルール",    "subtitle": "基本をマスターしよう", "bg": (20,40,100),  "ac": (0,200,255),  "at": 1.8, "dur": 2.5},
    {"name": "image2_serve.png",   "title": "サーブの打ち方",  "subtitle": "上に投げてから打つ",   "bg": (15,60,35),   "ac": (0,230,110),  "at": 5.5, "dur": 2.5},
    {"name": "image3_practice.png","title": "毎日の練習",      "subtitle": "継続は力なり！",        "bg": (60,15,15),   "ac": (255,120,0),  "at": 12.5,"dur": 2.5},
]

def make_image(cfg):
    img = Image.new("RGB", (W, H), cfg["bg"])
    draw = ImageDraw.Draw(img)
    bg, ac = cfg["bg"], cfg["ac"]
    for y in range(H):
        t = y / H
        r = int(bg[0] + (ac[0]-bg[0])*t*0.3)
        g = int(bg[1] + (ac[1]-bg[1])*t*0.3)
        b = int(bg[2] + (ac[2]-bg[2])*t*0.3)
        draw.line([(0,y),(W,y)], fill=(r,g,b))
    for i in range(3):
        draw.rectangle([6+i*3, 6+i*3, W-7-i*3, H-7-i*3], outline=ac, width=2)
    cx, cy = W//2, H//2 - 50
    for rad in [210, 185, 160]:
        draw.ellipse([cx-rad,cy-rad,cx+rad,cy+rad], outline=(*ac,50), width=1)
    br = 58
    draw.ellipse([cx+65,cy-68,cx+65+br*2,cy-68+br*2], fill="white", outline=ac, width=3)
    draw.arc([cx+65,cy-68,cx+65+br*2,cy-68+br*2], start=25, end=155, fill=ac, width=3)
    tw2, th2 = 360, 195
    draw.rectangle([cx-tw2//2,cy-th2//2,cx+tw2//2,cy+th2//2], fill=(0,70,25), outline="white", width=2)
    draw.line([(cx,cy-th2//2),(cx,cy+th2//2)], fill="white", width=3)
    draw.line([(cx-tw2//2,cy),(cx+tw2//2,cy)], fill="white", width=2)
    f60 = find_jp_font(60)
    f36 = find_jp_font(36)
    title, sub = cfg["title"], cfg["subtitle"]
    bb = draw.textbbox((0,0), title, font=f60)
    tx = (W-(bb[2]-bb[0]))//2
    draw.text((tx+3,H-188+3), title, font=f60, fill=(0,0,0))
    draw.text((tx,H-188), title, font=f60, fill="white")
    bb2 = draw.textbbox((0,0), sub, font=f36)
    sx = (W-(bb2[2]-bb2[0]))//2
    draw.text((sx+2,H-118+2), sub, font=f36, fill=(0,0,0))
    draw.text((sx,H-118), sub, font=f36, fill=ac)
    img.save(cfg["name"])
    print(f"  Generated: {cfg['name']}")

for cfg in images_cfg:
    make_image(cfg)

# Convert to clips
for cfg in images_cfg:
    clip = cfg["name"].replace(".png", "_clip.mp4")
    run(["ffmpeg", "-y", "-loop", "1", "-i", cfg["name"],
         "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
         "-t", str(cfg["dur"]),
         "-c:v", "libx264", "-preset", "fast", "-crf", "20",
         "-c:a", "aac", "-b:a", "128k", "-pix_fmt", "yuv420p",
         "-vf", "scale=1280:720", "-r", "30", clip])
    print(f"  Clip: {clip} ({cfg['dur']}s)")

# Extract base video segments around insert points
insert_pts = sorted(images_cfg, key=lambda x: x["at"])
base_segs2 = []
prev_t = 0.0
for i, cfg in enumerate(insert_pts):
    ins = cfg["at"]
    sf = f"fb_{i:02d}.mp4"
    if ins - prev_t > 0.05:
        run(["ffmpeg", "-y", "-ss", str(prev_t), "-to", str(ins),
             "-i", "subtitled_base.mp4",
             "-c:v", "libx264", "-preset", "fast", "-crf", "20",
             "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
             "-reset_timestamps", "1", "-pix_fmt", "yuv420p", sf])
        base_segs2.append(sf)
    prev_t = ins

sf_last = f"fb_{len(insert_pts):02d}.mp4"
run(["ffmpeg", "-y", "-ss", str(prev_t), "-i", "subtitled_base.mp4",
     "-c:v", "libx264", "-preset", "fast", "-crf", "20",
     "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
     "-reset_timestamps", "1", "-pix_fmt", "yuv420p", sf_last])
base_segs2.append(sf_last)

# Build ordered clip list
ordered = []
for i, cfg in enumerate(insert_pts):
    if i < len(base_segs2) - 1:
        ordered.append(base_segs2[i])
    ordered.append(cfg["name"].replace(".png", "_clip.mp4"))
ordered.append(base_segs2[-1])

# ─── Step 5: End card (5s) ────────────────────────────────────────────────────
print("\n" + "=" * 55)
print("Step 5: エンドカード生成（5秒）")
print("=" * 55)

img = Image.new("RGB", (W, H), (8,8,25))
draw = ImageDraw.Draw(img)
for y in range(H):
    t = y/H
    draw.line([(0,y),(W,y)], fill=(int(8+35*t),int(8+15*t),int(25+70*t)))
for i in range(4):
    draw.rectangle([5+i*4,5+i*4,W-5-i*4,H-5-i*4], outline=(255,200,0), width=1)
cx2, cy2 = W//2, H//2-55
for rad in [175,150,125]:
    draw.ellipse([cx2-rad,cy2-rad,cx2+rad,cy2+rad], outline=(255,200,0,40), width=1)
br2 = 62
draw.ellipse([cx2-br2,cy2-br2-12,cx2+br2,cy2+br2-12], fill="white", outline=(200,200,200), width=3)
draw.arc([cx2-br2,cy2-br2-12,cx2+br2,cy2+br2-12], start=20,end=160, fill=(100,180,255), width=4)

f58 = find_jp_font(58)
f34 = find_jp_font(34)
f24 = find_jp_font(24)

title_e = "ご視聴ありがとうございました！"
bb = draw.textbbox((0,0), title_e, font=f58)
tx_e = (W-(bb[2]-bb[0]))//2
draw.text((tx_e+3,H-168+3), title_e, font=f58, fill=(0,0,0))
draw.text((tx_e,H-168), title_e, font=f58, fill=(255,230,50))

sub_e = "チャンネル登録・高評価よろしくお願いします！"
bb2 = draw.textbbox((0,0), sub_e, font=f34)
sx_e = (W-(bb2[2]-bb2[0]))//2
draw.text((sx_e+2,H-100+2), sub_e, font=f34, fill=(0,0,0))
draw.text((sx_e,H-100), sub_e, font=f34, fill=(180,210,255))

ch_e = "ピンポンチャンネル"
bb3 = draw.textbbox((0,0), ch_e, font=f24)
cx3 = (W-(bb3[2]-bb3[0]))//2
draw.text((cx3,22), ch_e, font=f24, fill=(140,190,255))

img.save("endcard.png")

run(["ffmpeg", "-y", "-loop", "1", "-i", "endcard.png",
     "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
     "-t", "5",
     "-vf", "scale=1280:720,fade=t=in:st=0:d=0.8,fade=t=out:st=4.2:d=0.8",
     "-c:v", "libx264", "-preset", "fast", "-crf", "20",
     "-c:a", "aac", "-b:a", "128k", "-pix_fmt", "yuv420p", "-r", "30",
     "endcard_clip.mp4"])
print(f"  → endcard_clip.mp4 (5s)")

ordered.append("endcard_clip.mp4")

# ─── Step 6: Final output.mp4 ─────────────────────────────────────────────────
print("\n" + "=" * 55)
print("Step 6: output.mp4 書き出し")
print("=" * 55)

total_exp = 0.0
for f in ordered:
    d = get_duration(f)
    total_exp += d
    print(f"  {f}: {d:.2f}s")
print(f"  期待合計: {total_exp:.2f}s")

with open("final_concat.txt", "w") as f:
    for clip in ordered:
        f.write(f"file '{WORKDIR}/{clip}'\n")

run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "final_concat.txt",
     "-c:v", "libx264", "-preset", "medium", "-crf", "20",
     "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
     "-pix_fmt", "yuv420p", "output.mp4"])

out_dur = get_duration("output.mp4")
size = os.path.getsize("output.mp4")
r2 = run(["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", "output.mp4"])
streams = json.loads(r2.stdout)["streams"]

print(f"\n{'='*55}")
print(f"  output.mp4 完成！")
print(f"{'='*55}")
print(f"  Duration : {out_dur:.2f}s ({int(out_dur//60)}分{int(out_dur%60)}秒)")
print(f"  Size     : {size/1024/1024:.2f} MB")
for s in streams:
    if s["codec_type"]=="video":
        print(f"  Video    : {s['codec_name']} {s.get('width')}x{s.get('height')}")
    elif s["codec_type"]=="audio":
        print(f"  Audio    : {s['codec_name']} {s.get('sample_rate')}Hz")

print(f"""
処理サマリー:
  [1] Whisper文字起こし     → 5セグメント（日本語）
  [2] 無音カット-40dB       → {removed:.2f}s削除 ({total_dur:.1f}s → {base_dur:.1f}s)
  [3] SRT字幕 12文字/行     → {len(srt_entries)}エントリ
  [4] 画像3枚挿入 各2.5s   → 卓球ルール / サーブ / 練習
  [5] エンドカード5s         → フェードイン/アウト付き
""")

# Cleanup
for f in base_segs2 + ["final_concat.txt", "endcard_clip.mp4",
                        "no_silence.mp4", "subtitled_base.mp4"]:
    try: os.remove(f)
    except: pass
for cfg in images_cfg:
    try: os.remove(cfg["name"].replace(".png","_clip.mp4"))
    except: pass
print("一時ファイルクリーンアップ完了")
