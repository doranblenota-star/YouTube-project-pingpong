# video-edit — 動画編集オートメーションパイプライン

ユーザーが `/video-edit` を呼び出したとき、または「動画を編集して」「input.mp4 を処理して」などと指示されたときに起動する。

## 実行手順（順番どおりに実行すること）

作業ディレクトリ: `/home/user/YouTube-project-pingpong`

### 前提：依存ツールの自動インストール
以下がなければ自動インストールする。
```bash
apt-get install -y ffmpeg espeak-ng fonts-noto-cjk imagemagick 2>/dev/null
pip3 install openai-whisper faster-whisper Pillow 2>/dev/null
```

---

### Step 1 — Whisper 文字起こし（日本語）
`input.mp4` を Whisper で文字起こしする。

- `faster-whisper` の tiny モデルを優先して使用。
- ネットワーク制限でモデルのダウンロードが失敗した場合は、音声の内容をもとにテキストを手動で用意する。
- 結果は `transcript.json` に保存する（フォーマット: `[{"start": 0.0, "end": 4.0, "text": "..."}]`）。

---

### Step 2 — 無音区間カット（-40dB 以下を削除）
`ffmpeg silencedetect` を使い `-40dB` 以下が `0.5s` 以上続く区間を検出してカットする。

- バッファ 0.15s を設定してクリップしないようにする。
- カット後の動画を `no_silence.mp4` として出力。
- タイムスタンプのずれを `transcript_adjusted.json` に反映する。
- `-reset_timestamps 1` を使ってタイムスタンプをリセットする。

---

### Step 3 — SRT 字幕生成・焼き付け

#### 字幕テキスト分割ルール（厳守）
- **1行は最大12文字以下**
- 文脈・意味の区切りを優先して分割する
  - 句読点（。、！？）で分割
  - 助詞（は、が、を、に、で、と）の後で分割
  - それでも12字を超える場合は意味の切れ目で強制分割

例:
```
× こんにちは。今日はピンポンの編集をご紹介します。
↓
○ こんにちは。
○ 今日は
○ ピンポンの編集を
○ ご紹介します。
```

#### SRT 生成
- `subtitles.srt` に出力
- 各セグメントの表示時間を分割行数に応じて調整（1行 ≒ 0.8s を目安）

#### 字幕焼き付け
```
force_style='FontName=Noto Serif CJK JP,FontSize=22,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2,Shadow=1,Alignment=2'
```
出力: `with_subtitles.mp4`

---

### Step 4 — 内容に応じた画像3枚を生成・挿入

#### 画像生成（PIL / Pillow を使用）
各画像は 1280×720px、内容：
1. **ルール解説画像** — 動画前半の内容に合わせた解説
2. **テクニック画像** — 中盤のポイントを強調
3. **まとめ画像** — 後半の要点

各画像の要素:
- グラデーション背景
- 卓球テーブル／ボールのシルエット装飾
- 日本語タイトル（60px Noto CJK Bold）
- サブタイトル（36px）
- 装飾ボーダー

#### 動画への挿入
- 各画像を 2.5 秒のクリップに変換（サイレント音声付き）
- `-reset_timestamps 1` で各セグメントを抽出してから連結
- 連結は ffmpeg concat demuxer を使用

出力: `with_images.mp4`

---

### Step 5 — 5秒エンドカード追加

エンドカード画像（1280×720px）の要素:
- グラデーション背景（濃紺→深い青）
- ゴールドボーダー（多重）
- ピンポン卓球テーブルのシルエット
- メインテキスト: 「ご視聴ありがとうございました！」（58px 黄色）
- サブテキスト: 「チャンネル登録・高評価よろしくお願いします！」（34px 水色）
- チャンネル名（上部）

エフェクト: フェードイン 0.8s、フェードアウト 0.8s  
出力クリップ: 5秒

---

### Step 6 — output.mp4 として書き出し

最終連結順序:
```
base[0→t1] → image1(2.5s) → base[t1→t2] → image2(2.5s) → base[t2→t3] → image3(2.5s) → base[t3→end] → endcard(5s)
```

エンコード設定:
- Video: libx264, preset=medium, crf=20
- Audio: aac, 128k, 44100Hz
- `-movflags +faststart`（Web最適化）

出力: `output.mp4`

---

## エラー処理方針
- ネットワーク制限でモデルDLが失敗 → 既知テキストで代替
- ffmpeg concat のタイムスタンプ問題 → `-reset_timestamps 1` で各セグメントを再エンコード
- 日本語フォントが見つからない → `apt-get install fonts-noto-cjk` を実行
- 一時ファイルはパイプライン完了後にクリーンアップ

## 完了条件
`output.mp4` が存在し、以下を満たすこと:
- Duration: input から無音削除 + 画像3枚（各2.5s）+ エンドカード5s
- 解像度: 1280×720
- 日本語字幕が焼き付けられている
- 3枚の画像クリップが挿入されている
- エンドカードで終わる

完了後は `git add -A && git commit` して `origin claude/video-editing-automation-S7ek6` にプッシュする。
