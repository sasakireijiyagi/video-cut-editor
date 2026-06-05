# EasyTranscribe / おまかせ文字起こし

[日本語](README.md) ｜ [中文](README.zh.md) ｜ [한국어](README.ko.md)

A local tool for video transcription, trimming, and subtitle burning.  
Fully local · Free · No service shutdown risk. Mac / Windows supported.

---

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20515527.svg)](https://doi.org/10.5281/zenodo.20515527)

If this tool is useful to you, please give it a **[⭐ Star](https://github.com/sasakireijiyagi/video-cut-editor)** — it really helps!

This tool is developed and maintained by a researcher at Kyushu University in his spare time.
It has now reached users around the world.
If it has helped your research or work, **even a small donation — the price of a coffee — would be a huge encouragement** ☕  
Click the **❤ Support Development** button in the top-right corner of the app.

---

## What it does

```
Open video → Auto-transcribe (Whisper) → Uncheck unwanted segments → Export with ffmpeg
```

- **Transcribe** lecture or meeting videos with [OpenAI Whisper](https://github.com/openai/whisper) — **100 languages supported**
- **Edit** SRT segments — trim start/end times, edit text, fine-tune with ◀/▶ nudge buttons
- **Split** a segment at any character position; **merge** multiple segments into one
- **Cut** selected segments and combine into one file or export separately
- **Burn subtitles** directly into the video (bold Gothic font, white text, black outline)
- **Batch transcription** — queue multiple files and add more while processing
- **Vertical video** (9:16) — auto-detects and switches to vertical layout

---

## Supported transcription languages — 100 languages

Whisper supports **100 languages** for transcription. The app's language selector offers 13 major languages + auto-detect.

| Region | Languages |
|--------|-----------|
| East Asia | Japanese · Chinese (Mandarin & Cantonese) · Korean |
| Southeast Asia | Indonesian · Malay · Thai · Vietnamese · Tagalog · Javanese · Khmer · Lao · Burmese |
| South Asia | Hindi · Bengali · Urdu · Tamil · Telugu · Gujarati · Marathi · Punjabi · Nepali · Sinhala |
| Middle East / Central Asia | Arabic · Persian · Hebrew · Turkish · Kazakh · Uzbek · Azerbaijani · Georgian · Armenian |
| Europe (West) | English · Spanish · French · German · Italian · Portuguese · Dutch · Swedish · Norwegian · Danish · Finnish · Polish · Czech · Hungarian · Romanian · Greek |
| Europe (East) | Russian · Ukrainian · Bulgarian · Serbian · Croatian · Slovak · Slovenian · Macedonian · Belarusian · Lithuanian · Latvian · Estonian |
| Africa | Swahili · Hausa · Yoruba · Somali · Amharic · Shona · Lingala · Malagasy |
| Others | Welsh · Icelandic · Maori · Hawaiian · Latin · Sanskrit · and more |

---

## Requirements

- [Anaconda](https://www.anaconda.com/download) or [Miniconda](https://docs.conda.io/en/latest/miniconda.html)
- Internet connection (first-time setup only)

---

## Setup — Mac

Double-click **「セットアップ.command」** in the distribution folder.  
A terminal will open and run setup automatically. Press Enter when done.

> **Auto-installed (skipped if already present):**
> - Homebrew
> - ffmpeg
> - Whisper

> **"Developer cannot be verified" message?**  
> Right-click the file → Open → Open.

## Setup — Windows

### 1. Install ffmpeg

Download a prebuilt binary from [ffmpeg.org](https://ffmpeg.org/download.html), extract to `C:\ffmpeg`, and add `C:\ffmpeg\bin` to your system PATH.

### 2. Install Whisper

```bat
pip install openai-whisper
```

### 3. Install PyQt6

```bat
pip install PyQt6
```

### 4. Launch

```bat
python editor.py
```

---

## Launch — Mac

After setup, double-click **`EasyTranscribe.app`**.

---

## How to use

**① Open a video**  
Click "Open Video…". If a `.srt` file with the same name exists in the same folder, it loads automatically.  
Vertical video (height > width) is detected automatically and the layout switches to vertical.

**② Transcribe**  
Click "🎙 Transcribe". When done, segments appear in the table on the right.

**③ Review & edit segments**  
- Click a row to preview that segment (auto-stops at end)
- Double-click the text column to edit inline
- Double-click start/end time columns to edit directly (`HH:MM:SS,mmm` format)
- Use **◀ / ▶ buttons** to nudge start/end times by 100ms or 500ms
- **Right-click → Split row…** — click a character position to split; time is auto-calculated proportionally
- **Right-click → Merge selected rows** — select consecutive rows and merge into one
- All edits support **Ctrl+Z** undo / **Ctrl+Y** redo
- **Ctrl+H** opens Find & Replace
- **✂ Filler Cut** removes filler words in one click — list is fully customizable
- **Save SRT** overwrites the original SRT file with your edits

**④ Uncheck unwanted segments**  
Uncheck rows you want to cut. The total selected duration is shown in real time.

**⑤ Export**  
Choose output settings and click "▶ Cut with ffmpeg".

---

## Output options

| Option | Description |
|--------|-------------|
| Combine into one file | Joins selected segments into a single video |
| Export separately | Saves each segment as an individual file |
| Re-encode | Enables precise cuts (slower) |
| Burn subtitles | Renders subtitles into the video (see below) |
| Output folder | Choose where to save |

---

## Subtitle burning

Check **"Burn subtitles"** in the output settings to embed subtitles directly into the video.

- Font: bold Gothic (Hiragino Kaku Gothic ProN on Mac)
- Style: white text, black outline, bottom-center
- Font size is adjustable (default 52px landscape / 36px portrait)
- **▶ Preview** renders just the selected segment so you can check before exporting

> **⚠️ ffmpeg libass requirement**  
> Subtitle burning requires an **ffmpeg built with libass**. Homebrew's default `ffmpeg` (recent versions) no longer bundles libass, so subtitle burning alone may fail.  
> If so, install a libass-enabled build:  
> ```
> brew tap homebrew-ffmpeg/ffmpeg
> brew install homebrew-ffmpeg/ffmpeg/ffmpeg --with-libass
> ```  
> All other features (transcription, cutting, EAF export) work fine without libass.

---

## Batch transcription

Click **"📂 Batch Transcription"** to transcribe multiple videos at once.

1. Add files or a folder
2. Choose model, language, and silence settings
3. Click ▶ Start

- Current file is shown in real time: `Processing [2/5]: lecture03.mp4`
- **You can add more files while processing** — they join the queue immediately

---

## Keyboard shortcuts

**SRT table**

| Key | Action |
|-----|--------|
| ↓ / ↑ | Move to next/previous row and play |
| X | Toggle check on current row |
| D | Enter text edit mode |
| Escape | Exit edit mode |
| S | Open split dialog |
| Z | Merge with previous row |
| C | Merge with next row |

**General**

| Shortcut | Action |
|----------|--------|
| Ctrl+Z | Undo |
| Ctrl+Y | Redo |
| Ctrl+H | Open Find & Replace |

---

## Whisper models

| Model | Accuracy | Speed | Notes |
|-------|----------|-------|-------|
| large-v3 ★ | ◎ Best | Slow | Recommended |
| medium ★ | ○ | Normal | |
| small ★ | △ | Fast | |
| base ★ | △ | Fastest | |
| turbo | ○ | Fast | Downloads on first use |

**★** = already downloaded locally.  
Models without ★ download automatically on first use (large-v3 ≈ 3 GB).  
Running on CPU: expect **3–10× real-time** processing.

---

## Notes

- Original video files are never modified
- "Save SRT" **overwrites** the original SRT — back it up if needed
- Re-transcribing a video overwrites the existing SRT

---

## Disclaimer

This is experimental software for research and educational use. No warranty is provided. The author is not responsible for any damages arising from its use.

---

## License

[MIT License](LICENSE) © 2025 Reiji Sasaki  
Free to use, modify, and distribute. Please retain the copyright notice.

---

## Feedback & Bug Reports

Feel free to share how you use it, suggestions, or bug reports via **[GitHub Issues](https://github.com/sasakireijiyagi/video-cut-editor/issues)**. English or Japanese, either is fine.
