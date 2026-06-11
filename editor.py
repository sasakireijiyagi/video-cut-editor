#!/usr/bin/env python3
"""
おまかせ文字起こし  —  SRT + 動画を読み込んでffmpegでカット出力
"""

import sys
import os
import shutil

APP_VERSION = "1.0.6"
GITHUB_REPO = "sasakireijiyagi/video-cut-editor"

# PyQt6 プラグインパスをインポート前に解決（conda 環境対応）
def _find_pyqt6_plugins() -> str:
    import glob
    if sys.platform == 'win32':
        patterns = [
            os.path.expanduser('~/anaconda3/Lib/site-packages/PyQt6/Qt6/plugins'),
            os.path.expanduser('~/miniconda3/Lib/site-packages/PyQt6/Qt6/plugins'),
            os.path.expanduser('~/miniforge3/Lib/site-packages/PyQt6/Qt6/plugins'),
            r'C:\ProgramData\anaconda3\Lib\site-packages\PyQt6\Qt6\plugins',
            r'C:\ProgramData\miniconda3\Lib\site-packages\PyQt6\Qt6\plugins',
        ]
    else:
        patterns = [
            '/opt/anaconda3/lib/python3.*/site-packages/PyQt6/Qt6/plugins',
            '/opt/miniconda3/lib/python3.*/site-packages/PyQt6/Qt6/plugins',
            os.path.expanduser('~/anaconda3/lib/python3.*/site-packages/PyQt6/Qt6/plugins'),
            os.path.expanduser('~/miniconda3/lib/python3.*/site-packages/PyQt6/Qt6/plugins'),
            os.path.expanduser('~/miniforge3/lib/python3.*/site-packages/PyQt6/Qt6/plugins'),
        ]
    for pat in patterns:
        hits = sorted(glob.glob(pat))
        if hits:
            return hits[-1]
    return ''

_p = _find_pyqt6_plugins()
if _p:
    os.environ.setdefault('QT_QPA_PLATFORM_PLUGIN_PATH', _p)
    os.environ.setdefault('QT_PLUGIN_PATH', _p)

import re
import subprocess
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QTableWidget, QTableWidgetItem, QPushButton, QCheckBox,
    QGraphicsOpacityEffect, QListWidget,
    QLabel, QFileDialog, QLineEdit, QRadioButton, QGroupBox,
    QProgressBar, QTextEdit, QHeaderView, QAbstractItemView,
    QSlider, QSizePolicy, QMessageBox, QComboBox, QDoubleSpinBox, QSpinBox,
    QDialog, QDialogButtonBox, QMenuBar, QMenu,
)
from PyQt6.QtCore import Qt, QUrl, pyqtSignal, QThread, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QKeySequence, QShortcut, QFont, QFontDatabase, QPainter, QColor
from PyQt6.QtGui import QDesktopServices, QUndoStack, QUndoCommand
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget


# ──────────────────────────────────────────────────────────────────
# 言語辞書 / String dictionary
# ──────────────────────────────────────────────────────────────────

STRINGS = {
    'ja': {
        'window_title'      : 'おまかせ文字起こし  —  by Reiji Sasaki',
        'open_video'        : '動画を開く…',
        'open_srt'          : 'SRTを開く…',
        'save_srt'          : 'SRT保存',
        'save_srt_tip'      : '編集内容をSRTファイルに上書き保存',
        'donate'            : '❤ 開発を支援する',
        'donate_tip'        : '寄付ページを開きます',
        'video_none'        : '動画: 未選択',
        'srt_none'          : 'SRT: 未選択',
        'video_label'       : '動画: {name}',
        'srt_label'         : 'SRT: {name}',
        'transcribe_label'  : '文字起こし:',
        'model_label'       : 'モデル:',
        'lang_label'        : '言語:',
        'model_tip'         : 'Whisper モデル  ★=ローカル済み（すぐ使える）',
        'lang_tip'          : '文字起こし言語',
        'transcribe_btn'    : '🎙 文字起こし実行',
        'transcribe_cancel' : '中止',
        'mark_silence'      : '[間]を記録',
        'mark_silence_tip'  : '発話間の無音区間をSRTに[間 X.X秒]として挿入する',
        'silence_suffix'    : ' 秒以上',
        'silence_tip'       : 'この秒数以上の無音を[間]として記録する',
        'output_group'      : '出力設定',
        'combine'           : '1ファイルに結合',
        'separate'          : '行ごとに別ファイル',
        'reencode'          : '再エンコード (libx264/aac) — 遅いが正確',
        'output_dir'        : '出力先:',
        'browse'            : '参照…',
        'execute'           : '▶  ffmpegカット実行',
        'cancel'            : 'キャンセル',
        'select_all'        : '全選択',
        'deselect_all'      : '全解除',
        'tbl_headers'       : ['✓', '開始', '終了', 'テキスト'],
        'count_fmt'         : '{checked} / {total} 件  |  合計 {dur}',
        'play'              : '▶ 再生',
        'pause'             : '⏸ 一時停止',
        'stop'              : '⏹ 停止',
        'menu_help'         : 'ヘルプ',
        'menu_about'        : 'このソフトウェアについて',
        'about_title'       : 'このソフトウェアについて',
        'about_donate_link' : '開発を支援する（寄付）',
        'dlg_open_video'    : '動画ファイルを選択',
        'dlg_video_filter'  : '動画・音声 (*.mp4 *.mov *.MOV *.avi *.mkv *.m4v *.webm *.mp3 *.wav *.m4a *.aac *.flac *.ogg);;すべて (*)',
        'dlg_open_srt'      : 'SRTファイルを選択',
        'dlg_srt_filter'    : 'SRT (*.srt);;すべて (*)',
        'dlg_save_srt'      : 'SRTファイルを保存',
        'dlg_output_dir'    : '出力先ディレクトリを選択',
        'err_no_video'      : '動画ファイルを開いてください',
        'err_no_segments'   : '1つ以上のセグメントを選択してください',
        'err_title'         : 'エラー',
        'done_title'        : '完了',
        'log_srt_loaded'    : 'SRT読み込み完了: {n} セグメント — {path}',
        'log_srt_saved'     : 'SRT保存: {path}',
        'log_transcribe_start': '--- 文字起こし開始: {name} ---',
        'log_transcribe_done' : '--- 文字起こし完了 → {path} ---',
        'lang_toggle'       : 'EN',
    },
    'en': {
        'window_title'      : 'おまかせ文字起こし  —  by Reiji Sasaki',
        'open_video'        : 'Open Video…',
        'open_srt'          : 'Open SRT…',
        'save_srt'          : 'Save SRT',
        'save_srt_tip'      : 'Overwrite and save edits to SRT file',
        'donate'            : '❤ Support Development',
        'donate_tip'        : 'Open donation page',
        'video_none'        : 'Video: Not selected',
        'srt_none'          : 'SRT: Not selected',
        'video_label'       : 'Video: {name}',
        'srt_label'         : 'SRT: {name}',
        'transcribe_label'  : 'Transcribe:',
        'model_label'       : 'Model:',
        'lang_label'        : 'Language:',
        'model_tip'         : 'Whisper model  ★=already downloaded',
        'lang_tip'          : 'Transcription language',
        'transcribe_btn'    : '🎙 Run Transcription',
        'transcribe_cancel' : 'Stop',
        'mark_silence'      : 'Record [Pause]',
        'mark_silence_tip'  : 'Insert [Pause X.Xs] entries for silent gaps in SRT',
        'silence_suffix'    : ' sec or more',
        'silence_tip'       : 'Record silence longer than this as [Pause]',
        'output_group'      : 'Output Settings',
        'combine'           : 'Combine into one file',
        'separate'          : 'Separate file per segment',
        'reencode'          : 'Re-encode (libx264/aac) — slower but precise',
        'output_dir'        : 'Output:',
        'browse'            : 'Browse…',
        'execute'           : '▶  Cut with ffmpeg',
        'cancel'            : 'Cancel',
        'select_all'        : 'Select All',
        'deselect_all'      : 'Deselect All',
        'tbl_headers'       : ['✓', 'Start', 'End', 'Text'],
        'count_fmt'         : '{checked} / {total} selected  |  Total {dur}',
        'play'              : '▶ Play',
        'pause'             : '⏸ Pause',
        'stop'              : '⏹ Stop',
        'menu_help'         : 'Help',
        'menu_about'        : 'About',
        'about_title'       : 'About おまかせ文字起こし',
        'about_donate_link' : 'Support Development (Donate)',
        'dlg_open_video'    : 'Select video file',
        'dlg_video_filter'  : 'Video / Audio (*.mp4 *.mov *.MOV *.avi *.mkv *.m4v *.webm *.mp3 *.wav *.m4a *.aac *.flac *.ogg);;All (*)',
        'dlg_open_srt'      : 'Select SRT file',
        'dlg_srt_filter'    : 'SRT (*.srt);;All (*)',
        'dlg_save_srt'      : 'Save SRT file',
        'dlg_output_dir'    : 'Select output directory',
        'err_no_video'      : 'Please open a video file first.',
        'err_no_segments'   : 'Please select at least one segment.',
        'err_title'         : 'Error',
        'done_title'        : 'Done',
        'log_srt_loaded'    : 'SRT loaded: {n} segments — {path}',
        'log_srt_saved'     : 'SRT saved: {path}',
        'log_transcribe_start': '--- Transcription started: {name} ---',
        'log_transcribe_done' : '--- Transcription complete → {path} ---',
        'lang_toggle'       : 'JA',
    },
}

_lang = 'ja'

def tr(key: str) -> str:
    return STRINGS[_lang].get(key, key)


# ──────────────────────────────────────────────────────────────────
# SRT utilities
# ──────────────────────────────────────────────────────────────────

@dataclass
class SRTEntry:
    index: int
    start_ms: int
    end_ms: int
    text: str
    checked: bool = True


def _ts_to_ms(ts: str) -> int:
    m = re.match(r'(\d+):(\d+):(\d+)[,.](\d+)', ts.strip())
    if not m:
        return 0
    h, mi, s, ms = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
    return h * 3_600_000 + mi * 60_000 + s * 1_000 + ms


def _ms_to_srt(ms: int) -> str:
    h, r = divmod(ms, 3_600_000)
    mi, r = divmod(r, 60_000)
    s, ms = divmod(r, 1_000)
    return f"{h:02d}:{mi:02d}:{s:02d},{ms:03d}"


def _ms_to_ffmpeg(ms: int) -> str:
    h, r = divmod(ms, 3_600_000)
    mi, r = divmod(r, 60_000)
    s, ms = divmod(r, 1_000)
    return f"{h:02d}:{mi:02d}:{s:02d}.{ms:03d}"


def _ms_to_clock(ms: int) -> str:
    h, r = divmod(ms, 3_600_000)
    mi, r = divmod(r, 60_000)
    s = r // 1_000
    return f"{h:02d}:{mi:02d}:{s:02d}"


def parse_srt(text: str) -> List[SRTEntry]:
    entries: List[SRTEntry] = []
    for block in re.split(r'\n\s*\n', text.strip()):
        lines = block.strip().splitlines()
        if len(lines) < 3:
            continue
        try:
            idx = int(lines[0].strip())
        except ValueError:
            continue
        m = re.match(r'(.+?)\s*-->\s*(.+)', lines[1])
        if not m:
            continue
        entries.append(SRTEntry(
            index=idx,
            start_ms=_ts_to_ms(m.group(1)),
            end_ms=_ts_to_ms(m.group(2)),
            text='\n'.join(lines[2:]),
        ))
    return entries


# ──────────────────────────────────────────────────────────────────
# ffmpeg worker
# ──────────────────────────────────────────────────────────────────

def _find_ffmpeg() -> str:
    # まず PATH から探す
    w = shutil.which('ffmpeg')
    if w:
        return w
    if sys.platform == 'win32':
        candidates = [
            r'C:\ffmpeg\bin\ffmpeg.exe',
            r'C:\Program Files\ffmpeg\bin\ffmpeg.exe',
            r'C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe',
            os.path.expanduser(r'~\ffmpeg\bin\ffmpeg.exe'),
        ]
    else:
        candidates = [
            '/usr/local/bin/ffmpeg',
            '/opt/homebrew/bin/ffmpeg',
        ]
    for p in candidates:
        if os.path.isfile(p):
            return p
    return 'ffmpeg'

def _find_whisper() -> str:
    w = shutil.which('whisper')
    if w:
        return w
    if sys.platform == 'win32':
        # Windows conda: Scripts/whisper.exe
        conda_bases = [
            os.path.expanduser('~/anaconda3'),
            os.path.expanduser('~/miniconda3'),
            os.path.expanduser('~/miniforge3'),
            r'C:\ProgramData\anaconda3',
            r'C:\ProgramData\miniconda3',
        ]
        for base in conda_bases:
            # envs 内を検索
            hits = sorted(Path(base).glob('envs/*/Scripts/whisper.exe'))
            if hits:
                return str(hits[0])
            w_base = Path(base) / 'Scripts' / 'whisper.exe'
            if w_base.exists():
                return str(w_base)
    else:
        conda_bases = [
            '/opt/anaconda3', '/opt/miniconda3',
            os.path.expanduser('~/anaconda3'),
            os.path.expanduser('~/miniconda3'),
            os.path.expanduser('~/miniforge3'),
            os.path.expanduser('~/mambaforge'),
        ]
        for base in conda_bases:
            hits = sorted(Path(base).glob('envs/*/bin/whisper'))
            if hits:
                return str(hits[0])
            w_base = Path(base) / 'bin' / 'whisper'
            if w_base.exists():
                return str(w_base)
    return 'whisper'

FFMPEG_BIN  = _find_ffmpeg()
WHISPER_BIN = _find_whisper()

def _is_ffmpeg_ok() -> bool:
    try:
        subprocess.run([FFMPEG_BIN, '-version'], capture_output=True, timeout=5)
        return True
    except Exception:
        return False

def _is_whisper_ok() -> bool:
    try:
        subprocess.run([WHISPER_BIN, '--help'], capture_output=True, timeout=5)
        return True
    except Exception:
        return False

class SetupDialog(QDialog):
    """ffmpeg / Whisper が見つからないときに自動インストールを提案するダイアログ"""

    def __init__(self, missing_ffmpeg: bool, missing_whisper: bool, parent=None):
        super().__init__(parent)
        self.setWindowTitle('セットアップ' if _lang == 'ja' else 'Setup')
        self.setMinimumWidth(480)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        if _lang == 'ja':
            msg = '以下のソフトウェアが見つかりませんでした。\n自動でインストールしますか？\n（インターネット接続が必要です）'
        else:
            msg = 'The following software was not found.\nInstall automatically?\n(Internet connection required)'

        layout.addWidget(QLabel(msg))

        self.chk_ffmpeg  = QCheckBox('ffmpeg')
        self.chk_whisper = QCheckBox('Whisper (openai-whisper)')
        self.chk_ffmpeg.setChecked(missing_ffmpeg)
        self.chk_whisper.setChecked(missing_whisper)
        self.chk_ffmpeg.setEnabled(missing_ffmpeg)
        self.chk_whisper.setEnabled(missing_whisper)
        layout.addWidget(self.chk_ffmpeg)
        layout.addWidget(self.chk_whisper)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setFixedHeight(140)
        self.log.setVisible(False)
        layout.addWidget(self.log)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        btns = QDialogButtonBox()
        if _lang == 'ja':
            self.btn_install = btns.addButton('インストール', QDialogButtonBox.ButtonRole.AcceptRole)
            self.btn_skip    = btns.addButton('スキップ',     QDialogButtonBox.ButtonRole.RejectRole)
        else:
            self.btn_install = btns.addButton('Install', QDialogButtonBox.ButtonRole.AcceptRole)
            self.btn_skip    = btns.addButton('Skip',    QDialogButtonBox.ButtonRole.RejectRole)
        layout.addWidget(btns)

        self.btn_install.clicked.connect(self._run_install)
        self.btn_skip.clicked.connect(self.reject)

        self._worker = None

    def _run_install(self):
        self.btn_install.setEnabled(False)
        self.btn_skip.setEnabled(False)
        self.log.setVisible(True)
        self.progress.setVisible(True)

        install_ffmpeg  = self.chk_ffmpeg.isChecked()
        install_whisper = self.chk_whisper.isChecked()

        self._worker = SetupWorker(install_ffmpeg, install_whisper)
        self._worker.log_line.connect(self._append_log)
        self._worker.finished.connect(self._on_done)
        self._worker.start()

    def _append_log(self, line: str):
        self.log.append(line)

    def _on_done(self, success: bool):
        self.progress.setVisible(False)
        self.btn_skip.setEnabled(True)
        if success:
            if sys.platform == 'win32':
                msg = 'インストール完了！PCを再起動してからアプリを起動してください。' if _lang == 'ja' else 'Installation complete! Please restart your PC, then launch the app again.'
            else:
                msg = 'インストール完了！アプリを再起動してください。' if _lang == 'ja' else 'Installation complete! Please restart the app.'
            self.log.append(msg)
            self.btn_skip.setText('閉じる' if _lang == 'ja' else 'Close')
        else:
            msg = 'エラーが発生しました。手動でインストールしてください。' if _lang == 'ja' else 'An error occurred. Please install manually.'
            self.log.append(msg)


class SetupWorker(QThread):
    log_line = pyqtSignal(str)
    finished = pyqtSignal(bool)

    def __init__(self, ffmpeg: bool, whisper: bool):
        super().__init__()
        self.do_ffmpeg  = ffmpeg
        self.do_whisper = whisper

    def run(self):
        try:
            if self.do_ffmpeg and sys.platform != 'win32':
                self.log_line.emit('Homebrewを確認中...')
                brew = shutil.which('brew')
                if not brew:
                    self.log_line.emit('Homebrewをインストール中...')
                    cmd = '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
                    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                    for line in proc.stdout:
                        self.log_line.emit(line.rstrip())
                    proc.wait()
                self.log_line.emit('ffmpegをインストール中...')
                proc = subprocess.Popen(['brew', 'install', 'ffmpeg'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                for line in proc.stdout:
                    self.log_line.emit(line.rstrip())
                proc.wait()

            if self.do_ffmpeg and sys.platform == 'win32':
                winget = shutil.which('winget')
                if winget:
                    self.log_line.emit('ffmpegをインストール中（winget）...')
                    proc = subprocess.Popen(
                        ['winget', 'install', '--id', 'Gyan.FFmpeg', '-e', '--silent'],
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                    for line in proc.stdout:
                        self.log_line.emit(line.rstrip())
                    proc.wait()
                else:
                    self.log_line.emit('wingetが見つかりません。手動でインストールしてください。')
                    self.log_line.emit('https://ffmpeg.org/download.html')

            if self.do_whisper:
                self.log_line.emit('Whisperをインストール中...')
                proc = subprocess.Popen(
                    [sys.executable, '-m', 'pip', 'install', 'openai-whisper'],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                for line in proc.stdout:
                    self.log_line.emit(line.rstrip())
                proc.wait()

            if sys.platform == 'win32' and self.do_ffmpeg:
                self.log_line.emit('')
                self.log_line.emit('⚠ Windowsの場合、PATHを反映するためにPCを再起動してください。')
            self.finished.emit(True)
        except Exception as e:
            self.log_line.emit(str(e))
            self.finished.emit(False)

_SUBTITLES_FILTER_CACHE = None

def _ffmpeg_has_subtitles() -> bool:
    """ffmpeg に subtitles フィルタ（libass）が含まれているか判定（結果をキャッシュ）"""
    global _SUBTITLES_FILTER_CACHE
    if _SUBTITLES_FILTER_CACHE is not None:
        return _SUBTITLES_FILTER_CACHE
    try:
        env = os.environ.copy()
        if sys.platform != 'win32':
            env['PATH'] = '/usr/local/bin:/opt/homebrew/bin:' + env.get('PATH', '')
        r = subprocess.run([FFMPEG_BIN, '-hide_banner', '-filters'],
                           capture_output=True, text=True, timeout=15, env=env)
        # "subtitles" フィルタ行を探す（行頭フラグの後にフィルタ名が来る）
        import re as _re
        found = bool(_re.search(r'\bsubtitles\b\s+\S+->\S+', r.stdout))
        _SUBTITLES_FILTER_CACHE = found
    except Exception:
        _SUBTITLES_FILTER_CACHE = False
    return _SUBTITLES_FILTER_CACHE


def _subtitle_unavailable_msg() -> str:
    if _lang == 'en':
        return (
            "Subtitle burning requires an ffmpeg built with libass, "
            "but the current ffmpeg does not include it.\n\n"
            "On macOS (Homebrew's default ffmpeg no longer bundles libass), "
            "install the homebrew-ffmpeg build (libass is enabled by default):\n"
            "    brew tap homebrew-ffmpeg/ffmpeg\n"
            "    brew unlink ffmpeg\n"
            "    brew install homebrew-ffmpeg/ffmpeg/ffmpeg\n\n"
            "Verify with:  ffmpeg -hide_banner -filters | grep subtitles\n\n"
            "All other features (transcription, cutting, EAF export) work without libass."
        )
    return (
        "字幕焼き込みには libass を含む ffmpeg が必要ですが、"
        "現在の ffmpeg には含まれていません。\n\n"
        "macOS の場合（Homebrew の標準 ffmpeg は libass を同梱しなくなりました）、"
        "homebrew-ffmpeg 版を導入してください（libass は標準で有効）:\n"
        "    brew tap homebrew-ffmpeg/ffmpeg\n"
        "    brew unlink ffmpeg\n"
        "    brew install homebrew-ffmpeg/ffmpeg/ffmpeg\n\n"
        "確認:  ffmpeg -hide_banner -filters | grep subtitles\n\n"
        "※ 字幕焼き込み以外の機能（文字起こし・カット・EAF書き出し等）は\n"
        "  libass がなくても問題なく使えます。"
    )

DEFAULT_FILLERS = [
    'えー', 'えーと', 'えっと', 'えと',
    'あー', 'あーと', 'あの', 'あのー', 'あのう',
    'うーん', 'うん', 'うーむ',
    'まあ', 'まー',
    'そのー', 'その',
    'なんか', 'なんかー',
    'ね', 'ねー', 'ねえ',
    'さー', 'さあ',
    'はい', 'はー',
    'んー', 'んーと',
]

# 言語コード → フィラーリスト（対応言語のみ）
FILLER_LISTS = {
    'ja': DEFAULT_FILLERS,
    'en': [
        'uh', 'um', 'er', 'erm', 'ah', 'oh',
        'like', 'you know', 'you know what i mean',
        'so', 'well', 'right', 'okay', 'ok',
        'i mean', 'basically', 'actually', 'literally',
        'kind of', 'sort of', 'anyway',
    ],
    'zh': [
        '那个', '那个那个', '就是', '就是说', '然后', '然后呢',
        '嗯', '啊', '哦', '呃', '这个', '对对对', '好',
    ],
    'ko': [
        '어', '음', '그', '그러니까', '뭐', '아',
        '이제', '그래서', '근데', '그냥', '좀',
    ],
    'es': [
        'eh', 'este', 'esta', 'o sea', 'bueno',
        'pues', 'entonces', 'osea', 'a ver',
    ],
    'fr': [
        'euh', 'bah', 'ben', 'alors', 'enfin',
        'voilà', 'quoi', 'genre', 'du coup',
    ],
    'de': [
        'äh', 'ähm', 'also', 'halt', 'ne',
        'oder', 'sozusagen', 'quasi', 'irgendwie',
    ],
    'pt': [
        'é', 'ah', 'eh', 'tipo', 'né',
        'então', 'assim', 'quer dizer', 'sabe',
    ],
}

_LANG_MAP = {
    '日本語': 'ja',
    'English': 'en',
    '中文': 'zh',
    '한국어': 'ko',
    'Español': 'es',
    'Français': 'fr',
    'Deutsch': 'de',
    'Português': 'pt',
    'Italiano': 'it',
    'Русский': 'ru',
    'العربية': 'ar',
    'Hindi हिन्दी': 'hi',
    '自動検出 / Auto': 'auto',
}


class VersionCheckWorker(QThread):
    """GitHub Releases API で最新バージョンを確認するスレッド"""
    result = pyqtSignal(str, str, str)  # (latest_tag, release_url, dmg_url)
    error  = pyqtSignal(str)

    def run(self):
        try:
            import urllib.request, json
            url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            req = urllib.request.Request(url, headers={"User-Agent": "EasyTranscribe"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read())
            tag = data.get("tag_name", "")
            html_url = data.get("html_url", f"https://github.com/{GITHUB_REPO}/releases")
            # プラットフォームに合わせたダウンロードURLを探す
            download_url = ""
            ext = ".dmg" if sys.platform == "darwin" else ".zip"
            for asset in data.get("assets", []):
                if asset.get("name", "").endswith(ext):
                    download_url = asset.get("browser_download_url", "")
                    break
            self.result.emit(tag, html_url, download_url)
        except Exception as e:
            self.error.emit(str(e))


class UpdateDownloadWorker(QThread):
    """新バージョンをダウンロード→インストール準備するスレッド（Mac/Windows対応）"""
    progress = pyqtSignal(int)   # 0-100
    finished = pyqtSignal(str)   # 新アプリのパス（Mac: _new.app / Win: _new フォルダ）
    error    = pyqtSignal(str)

    def __init__(self, download_url: str):
        super().__init__()
        self.download_url = download_url

    def run(self):
        import urllib.request, tempfile, subprocess, glob, shutil, os, zipfile

        try:
            req = urllib.request.Request(
                self.download_url, headers={"User-Agent": "EasyTranscribe"})

            if sys.platform == "darwin":
                self._run_mac(req, tempfile, subprocess, glob, shutil, os)
            else:
                self._run_win(req, tempfile, shutil, os, zipfile)

        except Exception as e:
            self.error.emit(str(e))

    # ── Mac ──────────────────────────────────────────────────────
    def _run_mac(self, req, tempfile, subprocess, glob, shutil, os):
        tmp_dmg = os.path.join(tempfile.gettempdir(), "EasyTranscribe_update.dmg")

        with urllib.request.urlopen(req) as resp, open(tmp_dmg, "wb") as f:
            import urllib.request
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    self.progress.emit(min(int(downloaded * 85 / total), 85))

        self.progress.emit(88)
        result = subprocess.run(
            ["hdiutil", "attach", tmp_dmg, "-nobrowse", "-noverify"],
            capture_output=True, text=True)
        if result.returncode != 0:
            self.error.emit(f"マウント失敗: {result.stderr}")
            return

        mount_point = None
        for line in result.stdout.splitlines():
            if "/Volumes/" in line:
                mount_point = line.split("\t")[-1].strip()
                break
        if not mount_point:
            self.error.emit("マウントポイントが見つかりません")
            return

        self.progress.emit(92)
        apps = glob.glob(os.path.join(mount_point, "*.app"))
        if not apps:
            self.error.emit("DMG内に .app が見つかりません")
            subprocess.run(["hdiutil", "detach", mount_point])
            return

        src_app = apps[0]
        current_app = self._find_current_app_mac()
        if not current_app:
            current_app = f"/Applications/{os.path.basename(src_app)}"

        tmp_new_app = current_app + "_new.app"
        if os.path.exists(tmp_new_app):
            shutil.rmtree(tmp_new_app)
        shutil.copytree(src_app, tmp_new_app)

        subprocess.run(["hdiutil", "detach", mount_point, "-quiet"])
        os.remove(tmp_dmg)

        self.progress.emit(100)
        self.finished.emit(tmp_new_app)

    def _find_current_app_mac(self) -> str:
        if hasattr(sys, "_MEIPASS"):
            parts = sys.executable.split("/")
            for i, p in enumerate(parts):
                if p.endswith(".app"):
                    return "/".join(parts[:i+1])
        return ""

    # ── Windows ──────────────────────────────────────────────────
    def _run_win(self, req, tempfile, shutil, os, zipfile):
        import urllib.request
        tmp_zip = os.path.join(tempfile.gettempdir(), "EasyTranscribe_update.zip")

        with urllib.request.urlopen(req) as resp, open(tmp_zip, "wb") as f:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    self.progress.emit(min(int(downloaded * 80 / total), 80))

        self.progress.emit(82)
        tmp_extract = os.path.join(tempfile.gettempdir(), "EasyTranscribe_update")
        if os.path.exists(tmp_extract):
            shutil.rmtree(tmp_extract)
        with zipfile.ZipFile(tmp_zip, "r") as zf:
            zf.extractall(tmp_extract)
        os.remove(tmp_zip)

        # EasyTranscribe フォルダを探す
        candidates = [
            d for d in os.listdir(tmp_extract)
            if os.path.isdir(os.path.join(tmp_extract, d))
        ]
        if not candidates:
            self.error.emit("ZIP内にフォルダが見つかりません")
            return
        src_dir = os.path.join(tmp_extract, candidates[0])

        current_dir = self._find_current_dir_win()
        if not current_dir:
            current_dir = os.path.join(os.path.expanduser("~"), "EasyTranscribe")

        new_dir = current_dir + "_new"
        if os.path.exists(new_dir):
            shutil.rmtree(new_dir)
        shutil.copytree(src_dir, new_dir)

        self.progress.emit(100)
        self.finished.emit(new_dir)

    def _find_current_dir_win(self) -> str:
        if hasattr(sys, "_MEIPASS"):
            return os.path.dirname(sys.executable)
        return ""


class FFmpegWorker(QThread):
    progress = pyqtSignal(int)
    log      = pyqtSignal(str)
    done     = pyqtSignal(bool, str)

    def __init__(self, entries: List[SRTEntry], video: str,
                 outdir: str, combine: bool, reencode: bool,
                 subtitle_burn: bool = False, font_size: int = 0,
                 font_name: str = ''):
        super().__init__()
        self.entries       = entries
        self.video         = video
        self.outdir        = outdir
        self.combine       = combine
        self.reencode      = reencode
        self.subtitle_burn = subtitle_burn
        self.font_size     = font_size  # 0 = auto
        self.font_name     = font_name  # 空文字で自動
        self._stop         = False

    def cancel(self):
        self._stop = True

    # ── 字幕フィルタ文字列を生成 ──
    def _subtitle_vf(self, srt_path: str) -> str:
        font = self.font_name.strip() if self.font_name.strip() else self._pick_font()
        size = self.font_size if self.font_size > 0 else 40
        # ASSスタイルをffmpegのforce_styleで指定
        # Alignment=2: 下中央, BorderStyle=1: 縁取り, Outline=4, Shadow=0
        style = (
            f"FontName={font},FontSize={size},Bold=1,"
            "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
            "BorderStyle=1,Outline=4,Shadow=0,Alignment=2,"
            "MarginV=30"
        )
        # srt_pathのバックスラッシュ・コロンをエスケープ（Windows対応）
        escaped = srt_path.replace('\\', '/').replace(':', '\\:')
        return f"subtitles='{escaped}':force_style='{style}'"

    @staticmethod
    def _pick_font() -> str:
        candidates = [
            'Hiragino Kaku Gothic ProN',
            'Hiragino Sans',
            'Noto Sans CJK JP Bold',
            'NotoSansCJK-Bold',
            'Yu Gothic Bold',
            'Meiryo Bold',
            'Arial Unicode MS',
        ]
        try:
            import subprocess as sp
            result = sp.run(['fc-list', ':lang=ja'], capture_output=True, text=True)
            installed = result.stdout.lower()
            for c in candidates:
                if c.lower().replace(' ', '') in installed.replace(' ', ''):
                    return c
        except Exception:
            pass
        # macOS fallback
        if sys.platform == 'darwin':
            return 'Hiragino Kaku Gothic ProN'
        return 'Arial Unicode MS'

    def run(self):
        checked = [e for e in self.entries if e.checked]
        if not checked:
            self.done.emit(False, "No segments selected." if _lang == 'en' else "選択されたセグメントがありません")
            return

        # 字幕焼き込み要求時、ffmpegにsubtitlesフィルタが無ければ中断
        if self.subtitle_burn and not _ffmpeg_has_subtitles():
            self.done.emit(False,
                'ffmpeg does not support subtitle burning (libass missing).'
                if _lang == 'en' else
                '字幕焼き込み非対応のffmpegです（libass無し）。詳細はログ参照。')
            self.log.emit(_subtitle_unavailable_msg())
            return

        # 重複除去
        seen, deduped = set(), []
        for e in checked:
            if e.index not in seen:
                seen.add(e.index)
                deduped.append(e)
        if len(deduped) != len(checked):
            self.log.emit(f"  {'Duplicate entries removed' if _lang=='en' else '重複エントリを除去'}: {len(checked)} → {len(deduped)}")
        checked = deduped

        self.log.emit(f"  {'Processing' if _lang=='en' else 'カット対象'}: {len(checked)} segments")
        os.makedirs(self.outdir, exist_ok=True)
        stem = Path(self.video).stem
        codec = (['-c:v', 'libx264', '-preset', 'fast', '-c:a', 'aac']
                 if self.reencode else ['-c', 'copy'])

        # 字幕焼き込み用: 全エントリのSRTをtmpに書き出す
        tmp_srt = None
        if self.subtitle_burn:
            import tempfile
            tmp_srt = os.path.join(self.outdir, '_tmp_sub.srt')
            lines = []
            for idx, e in enumerate(checked, 1):
                lines.append(str(idx))
                # セグメント先頭を0基準にオフセット
                lines.append(f"{_ms_to_srt(0)} --> {_ms_to_srt(e.end_ms - e.start_ms)}")
                lines.append(e.text)
                lines.append('')
            # ダミー: 実際は各セグメント個別に作る（下のループで生成）

        segs: List[str] = []
        for i, entry in enumerate(checked):
            if self._stop:
                self.done.emit(False, "Cancelled." if _lang == 'en' else "キャンセルされました")
                if tmp_srt and os.path.exists(tmp_srt):
                    os.remove(tmp_srt)
                return

            start = _ms_to_ffmpeg(entry.start_ms)
            dur   = _ms_to_ffmpeg(entry.end_ms - entry.start_ms)
            out   = os.path.join(self.outdir, f"{stem}_{entry.index:04d}.mp4")

            if self.subtitle_burn:
                # セグメント単体SRT（0基準）を一時ファイルに書く
                seg_srt = os.path.join(self.outdir, f'_seg_{entry.index:04d}.srt')
                seg_dur = entry.end_ms - entry.start_ms
                with open(seg_srt, 'w', encoding='utf-8') as f:
                    f.write(f"1\n{_ms_to_srt(0)} --> {_ms_to_srt(seg_dur)}\n{entry.text}\n\n")
                vf = self._subtitle_vf(seg_srt)
                cmd = [FFMPEG_BIN, '-y',
                       '-ss', start, '-i', self.video,
                       '-t', dur,
                       '-avoid_negative_ts', 'make_zero',
                       '-vf', vf,
                       '-c:v', 'libx264', '-preset', 'fast', '-c:a', 'aac', out]
            else:
                cmd = [FFMPEG_BIN, '-y',
                       '-ss', start, '-i', self.video,
                       '-t', dur,
                       '-avoid_negative_ts', 'make_zero',
                       *codec, out]

            self.log.emit(f"[{i+1}/{len(checked)}] seg {entry.index}  {start} + {dur}")
            proc = subprocess.run(cmd, capture_output=True, text=True)

            if self.subtitle_burn and os.path.exists(seg_srt):
                os.remove(seg_srt)

            if proc.returncode != 0:
                self.log.emit(f"  ERROR: {proc.stderr[-400:]}")
                self.done.emit(False, f"{'Error on segment' if _lang=='en' else 'セグメントでエラー'} {entry.index}")
                return

            segs.append(out)
            self.progress.emit(i + 1)

        if self.combine and len(segs) > 1:
            listfile = os.path.join(self.outdir, '_concat.txt')
            with open(listfile, 'w') as f:
                for p in segs:
                    f.write(f"file '{p}'\n")

            final = os.path.join(self.outdir, f"{stem}_combined.mp4")
            cmd = [FFMPEG_BIN, '-y', '-f', 'concat', '-safe', '0',
                   '-i', listfile, '-c', 'copy', final]
            self.log.emit("Combining..." if _lang == 'en' else "結合中...")
            proc = subprocess.run(cmd, capture_output=True, text=True)
            os.remove(listfile)
            for p in segs:
                try:
                    os.remove(p)
                except OSError:
                    pass

            if proc.returncode != 0:
                self.log.emit(f"  ERROR: {proc.stderr[-400:]}")
                self.done.emit(False, "Concat failed." if _lang == 'en' else "結合に失敗しました")
                return

            self.done.emit(True, f"{'Done' if _lang=='en' else '完了'}: {final}")
        else:
            self.done.emit(True,
                f"{'Done' if _lang=='en' else '完了'}: {len(segs)} {'file(s) saved to' if _lang=='en' else 'ファイルを'} {self.outdir}{'.' if _lang=='en' else ' に保存しました'}")


# ──────────────────────────────────────────────────────────────────
# Whisper worker
# ──────────────────────────────────────────────────────────────────

class WhisperWorker(QThread):
    log  = pyqtSignal(str)
    done = pyqtSignal(bool, str)

    def __init__(self, video: str, model: str, language: str,
                 mark_silence: bool = False, silence_sec: float = 1.0):
        super().__init__()
        self.video        = video
        self.model        = model
        self.language     = language
        self.mark_silence = mark_silence
        self.silence_ms   = int(silence_sec * 1000)
        self._proc        = None

    def cancel(self):
        if self._proc:
            self._proc.terminate()

    def run(self):
        outdir = str(Path(self.video).parent)
        cmd = [WHISPER_BIN, self.video,
               '--model', self.model,
               '--output_format', 'srt',
               '--output_dir', outdir]
        if self.language != 'auto':
            cmd += ['--language', self.language]

        self.log.emit(f"Whisper: model={self.model}  lang={self.language}")

        env = os.environ.copy()
        if sys.platform != 'win32':
            env['PATH'] = '/usr/local/bin:/opt/homebrew/bin:' + env.get('PATH', '')

        try:
            self._proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, env=env,
            )
            for line in self._proc.stdout:
                line = line.rstrip()
                if line:
                    self.log.emit(line)
            self._proc.wait()
        except Exception as exc:
            self.done.emit(False, str(exc))
            return

        if self._proc.returncode != 0:
            self.done.emit(False, f"whisper exited with error (code {self._proc.returncode})")
            return

        stem = Path(self.video).stem
        outdir_path = Path(outdir)
        srt = outdir_path / (stem + '.srt')
        if not srt.exists():
            hits = sorted(outdir_path.glob('*.srt'), key=lambda p: p.stat().st_mtime, reverse=True)
            srt = hits[0] if hits else srt

        if not srt.exists():
            self.done.emit(False, f"SRT not found: {srt}")
            return

        if self.mark_silence:
            entries = parse_srt(srt.read_text(encoding='utf-8-sig'))
            new_entries = []
            for i, entry in enumerate(entries):
                new_entries.append(entry)
                if i + 1 < len(entries):
                    gap_ms = entries[i + 1].start_ms - entry.end_ms
                    if gap_ms >= self.silence_ms:
                        label = f'[Pause  {gap_ms/1000:.1f}s]' if _lang == 'en' else f'[間  {gap_ms/1000:.1f}秒]'
                        new_entries.append(SRTEntry(
                            index=0,
                            start_ms=entry.end_ms,
                            end_ms=entries[i + 1].start_ms,
                            text=label,
                        ))
            for idx, e in enumerate(new_entries):
                e.index = idx + 1
            lines = []
            for e in new_entries:
                lines.append(str(e.index))
                lines.append(f"{_ms_to_srt(e.start_ms)} --> {_ms_to_srt(e.end_ms)}")
                lines.append(e.text)
                lines.append('')
            srt.write_text('\n'.join(lines), encoding='utf-8')
            inserted = len(new_entries) - len(entries)
            self.log.emit(f"  {'[Pause] inserted' if _lang=='en' else '[間] を挿入'}: {inserted} ({self.silence_ms/1000:.1f}{'s' if _lang=='en' else '秒'}+)")

        self.done.emit(True, str(srt))


# ──────────────────────────────────────────────────────────────────
# Batch whisper worker
# ──────────────────────────────────────────────────────────────────

class BatchWhisperWorker(QThread):
    file_started  = pyqtSignal(int, int, str)   # current, total, filename
    file_done     = pyqtSignal(int, int, bool, str)  # current, total, ok, msg
    log           = pyqtSignal(str)
    all_done      = pyqtSignal(int, int)        # success_count, total
    seg_tick      = pyqtSignal()                # whisperが1区間出力するたび（進捗の鼓動）

    def __init__(self, files: List[str], model: str, language: str,
                 mark_silence: bool, silence_sec: float):
        super().__init__()
        self.files        = files
        self.model        = model
        self.language     = language
        self.mark_silence = mark_silence
        self.silence_ms   = int(silence_sec * 1000)
        self._stop        = False
        self._proc        = None

    def cancel(self):
        self._stop = True
        if self._proc:
            self._proc.terminate()

    def add_files(self, paths: List[str]):
        """実行中に追加ファイルをキューへ積む（スレッドセーフ: list.append はGIL保護）"""
        for p in paths:
            if p not in self.files:
                self.files.append(p)

    def run(self):
        success = 0
        env     = os.environ.copy()
        if sys.platform != 'win32':
            env['PATH'] = '/usr/local/bin:/opt/homebrew/bin:' + env.get('PATH', '')

        i = 0
        while i < len(self.files):
            if self._stop:
                break
            video = self.files[i]
            total = len(self.files)  # 追加分を反映

            self.file_started.emit(i + 1, total, Path(video).name)

            outdir = str(Path(video).parent)
            cmd = [WHISPER_BIN, video,
                   '--model', self.model,
                   '--output_format', 'srt',
                   '--output_dir', outdir]
            if self.language != 'auto':
                cmd += ['--language', self.language]

            try:
                self._proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, bufsize=1, env=env)
                for line in self._proc.stdout:
                    line = line.rstrip()
                    if line:
                        self.log.emit(line)
                        if '-->' in line:        # whisperの区間出力行＝進捗の鼓動
                            self.seg_tick.emit()
                self._proc.wait()
            except Exception as exc:
                self.file_done.emit(i + 1, total, False, str(exc))
                i += 1
                continue

            if self._proc.returncode != 0:
                self.file_done.emit(i + 1, total, False,
                    f"whisper error (code {self._proc.returncode})")
                i += 1
                continue

            # SRTを探す
            stem = Path(video).stem
            srt  = Path(outdir) / (stem + '.srt')
            if not srt.exists():
                hits = sorted(Path(outdir).glob('*.srt'),
                              key=lambda p: p.stat().st_mtime, reverse=True)
                srt  = hits[0] if hits else srt

            if not srt.exists():
                self.file_done.emit(i + 1, total, False, f"SRT not found: {srt}")
                i += 1
                continue

            # [間] 挿入
            if self.mark_silence:
                entries = parse_srt(srt.read_text(encoding='utf-8-sig'))
                new_entries = []
                for j, entry in enumerate(entries):
                    new_entries.append(entry)
                    if j + 1 < len(entries):
                        gap_ms = entries[j + 1].start_ms - entry.end_ms
                        if gap_ms >= self.silence_ms:
                            label = (f'[Pause  {gap_ms/1000:.1f}s]'
                                     if _lang == 'en' else f'[間  {gap_ms/1000:.1f}秒]')
                            new_entries.append(SRTEntry(0, entry.end_ms,
                                entries[j + 1].start_ms, label))
                for idx, e in enumerate(new_entries):
                    e.index = idx + 1
                lines = []
                for e in new_entries:
                    lines.append(str(e.index))
                    lines.append(f"{_ms_to_srt(e.start_ms)} --> {_ms_to_srt(e.end_ms)}")
                    lines.append(e.text)
                    lines.append('')
                srt.write_text('\n'.join(lines), encoding='utf-8')

            success += 1
            self.file_done.emit(i + 1, total, True, str(srt))
            i += 1

        self.all_done.emit(success, len(self.files))


# ──────────────────────────────────────────────────────────────────
# Batch dialog
# ──────────────────────────────────────────────────────────────────

class BatchDialog(QDialog):
    def __init__(self, parent=None, model: str = 'large-v3',
                 language: str = '日本語',
                 mark_silence: bool = False, silence_sec: float = 1.0):
        super().__init__(parent)
        self.setWindowTitle('バッチ文字起こし' if _lang == 'ja' else 'Batch Transcription')
        self.setMinimumSize(700, 500)
        self._worker: Optional[BatchWhisperWorker] = None
        self._default_model    = model
        self._default_language = language
        self._default_silence  = mark_silence
        self._default_silence_sec = silence_sec
        self._build()

    def _build(self):
        vbox = QVBoxLayout(self)

        # ── ファイルリスト ──
        lbl = QLabel('動画ファイル一覧:' if _lang == 'ja' else 'Video files:')
        vbox.addWidget(lbl)

        self.file_list = QListWidget()
        self.file_list.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection)
        vbox.addWidget(self.file_list)

        btn_row = QHBoxLayout()
        self.btn_add     = QPushButton('ファイルを追加…' if _lang == 'ja' else 'Add Files…')
        self.btn_add_dir = QPushButton('フォルダを追加…' if _lang == 'ja' else 'Add Folder…')
        self.btn_remove  = QPushButton('削除' if _lang == 'ja' else 'Remove')
        self.btn_clear   = QPushButton('全クリア' if _lang == 'ja' else 'Clear All')
        self.btn_add.setToolTip('Cmd+クリックで複数選択できます' if _lang == 'ja' else 'Cmd+click to select multiple')
        self.btn_add.clicked.connect(self._add_files)
        self.btn_add_dir.clicked.connect(self._add_folder)
        self.btn_remove.clicked.connect(self._remove_selected)
        self.btn_clear.clicked.connect(self.file_list.clear)
        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_add_dir)
        btn_row.addWidget(self.btn_remove)
        btn_row.addWidget(self.btn_clear)
        btn_row.addStretch()
        vbox.addLayout(btn_row)

        # ── 設定 ──
        cfg = QHBoxLayout()
        cfg.addWidget(QLabel('モデル:' if _lang == 'ja' else 'Model:'))
        self.cmb_model = QComboBox()
        cache_dir = Path.home() / '.cache' / 'whisper'
        cached = {p.stem for p in cache_dir.glob('*.pt')} if cache_dir.is_dir() else set()
        for m in ['large-v3','large-v3-turbo','turbo','medium','small','base','tiny']:
            self.cmb_model.addItem(f'★ {m}' if m in cached else m)
        # デフォルトモデルを選択
        stem = self._default_model
        for i in range(self.cmb_model.count()):
            if stem in self.cmb_model.itemText(i):
                self.cmb_model.setCurrentIndex(i)
                break
        cfg.addWidget(self.cmb_model)
        cfg.addSpacing(12)
        cfg.addWidget(QLabel('言語:' if _lang == 'ja' else 'Language:'))
        self.cmb_lang = QComboBox()
        self.cmb_lang.addItems(list(_LANG_MAP.keys()))
        self.cmb_lang.setCurrentText(self._default_language)
        cfg.addWidget(self.cmb_lang)
        cfg.addSpacing(12)
        self.chk_silence = QCheckBox('[間]を記録' if _lang == 'ja' else 'Record [Pause]')
        self.chk_silence.setChecked(self._default_silence)
        self.spn_silence = QDoubleSpinBox()
        self.spn_silence.setRange(0.5, 10.0)
        self.spn_silence.setSingleStep(0.5)
        self.spn_silence.setValue(self._default_silence_sec)
        self.spn_silence.setSuffix(' 秒以上' if _lang == 'ja' else ' sec+')
        cfg.addWidget(self.chk_silence)
        cfg.addWidget(self.spn_silence)
        cfg.addStretch()
        vbox.addLayout(cfg)

        # ── 進捗 ──
        self.lbl_current = QLabel('')
        self.lbl_current.setVisible(False)
        vbox.addWidget(self.lbl_current)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        self.progress.setRange(0, 1000)
        # 淡い色の細いバーが、実際の進み具合に合わせてじわっと前進するだけ
        self.progress.setStyleSheet(
            "QProgressBar { border: none; border-radius: 3px; background: #e8e8e8; }"
            "QProgressBar::chunk { border-radius: 3px; background: #a9c0d8; }"
        )
        self._cur_file  = 0
        self._cur_total = 1
        self._creep     = 0.0
        vbox.addWidget(self.progress)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(140)
        vbox.addWidget(self.log)

        # ── 実行ボタン ──
        exec_row = QHBoxLayout()
        self.btn_start  = QPushButton('▶ 実行' if _lang == 'ja' else '▶ Start')
        self.btn_cancel = QPushButton('中止' if _lang == 'ja' else 'Stop')
        self.btn_cancel.setEnabled(False)
        f = self.btn_start.font()
        f.setPointSize(13)
        self.btn_start.setFont(f)
        self.btn_start.clicked.connect(self._start)
        self.btn_cancel.clicked.connect(self._cancel)
        exec_row.addWidget(self.btn_start)
        exec_row.addWidget(self.btn_cancel)
        exec_row.addStretch()
        vbox.addLayout(exec_row)

    def _add_files(self):
        start = getattr(self, '_last_dir', str(Path.home() / 'Downloads'))
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            'ファイルを選択（Cmd+クリックで複数選択）' if _lang == 'ja' else 'Select files (Cmd+click for multiple)',
            start,
            '動画・音声 (*.mp4 *.mov *.MOV *.avi *.mkv *.m4v *.mp3 *.wav *.m4a *.aac *.flac *.ogg);;すべて (*)' if _lang == 'ja'
            else 'Video / Audio (*.mp4 *.mov *.MOV *.avi *.mkv *.m4v *.mp3 *.wav *.m4a *.aac *.flac *.ogg);;All (*)')
        if paths:
            self._last_dir = str(Path(paths[0]).parent)
        self._append_paths(paths)

    def _add_folder(self):
        start = getattr(self, '_last_dir', str(Path.home() / 'Downloads'))
        folder = QFileDialog.getExistingDirectory(
            self,
            'フォルダを選択' if _lang == 'ja' else 'Select folder',
            start)
        if not folder:
            return
        self._last_dir = folder
        exts = {'.mp4', '.mov', '.MOV', '.avi', '.mkv', '.m4v', '.mp3', '.wav', '.m4a', '.aac', '.flac', '.ogg'}
        paths = [str(p) for p in sorted(Path(folder).iterdir())
                 if p.suffix in exts]
        self._append_paths(paths)

    def _append_paths(self, paths):
        existing = {self.file_list.item(i).text()
                    for i in range(self.file_list.count())}
        new_paths = [p for p in paths if p not in existing]
        for p in new_paths:
            self.file_list.addItem(p)
        if new_paths and self._worker and self._worker.isRunning():
            self._worker.add_files(new_paths)
            self._cur_total = self.file_list.count()
            self._update_progress()

    def _remove_selected(self):
        for item in self.file_list.selectedItems():
            self.file_list.takeItem(self.file_list.row(item))

    def _start(self):
        files = [self.file_list.item(i).text()
                 for i in range(self.file_list.count())]
        if not files:
            QMessageBox.warning(self,
                'エラー' if _lang == 'ja' else 'Error',
                'ファイルを追加してください' if _lang == 'ja' else 'Please add files.')
            return

        model = self.cmb_model.currentText().lstrip('★ ')
        lang  = _LANG_MAP.get(self.cmb_lang.currentText(), 'ja')

        self._worker = BatchWhisperWorker(
            files, model, lang,
            self.chk_silence.isChecked(),
            self.spn_silence.value())
        self._worker.file_started.connect(self._on_file_started)
        self._worker.file_done.connect(self._on_file_done)
        self._worker.seg_tick.connect(self._on_seg_tick)
        self._worker.log.connect(self.log.append)
        self._worker.all_done.connect(self._on_all_done)

        self.progress.setRange(0, 1000)
        self.progress.setValue(0)
        self._creep = 0.0
        self.progress.setVisible(True)
        self.lbl_current.setVisible(True)
        self.btn_start.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.btn_remove.setEnabled(False)
        self.btn_clear.setEnabled(False)
        self._batch_start_time = None
        self._file_start_time  = None
        self._worker.start()

    def _cancel(self):
        if self._worker:
            self._worker.cancel()
        self.btn_cancel.setEnabled(False)

    def _update_progress(self):
        # 全体進捗 = (完了ファイル数 + 処理中ファイルのじわ進み) / 総数
        cur, total = self._cur_file, max(self._cur_total, 1)
        overall = ((cur - 1) + self._creep) / total if cur > 0 else 0.0
        self.progress.setValue(max(0, min(1000, int(overall * 1000))))

    def _on_seg_tick(self):
        # whisperが1区間出すたびに、現ファイル分(上限0.95)へ向けてじわっと前進
        self._creep += (0.95 - self._creep) * 0.06
        self._update_progress()

    def _on_file_started(self, current: int, total: int, name: str):
        import time
        self._cur_file  = current
        self._cur_total = total
        self._creep     = 0.0
        self._update_progress()
        if self._batch_start_time is None:
            self._batch_start_time = time.time()
        self._file_start_time = time.time()
        label = (f'処理中 [{current}/{total}]: {name}'
                 if _lang == 'ja' else f'Processing [{current}/{total}]: {name}')
        self.lbl_current.setText(label)
        self.log.append(f"\n[{current}/{total}] {name}")

    def _on_file_done(self, current: int, total: int, ok: bool, msg: str):
        import time
        # このファイルを完了扱いにしてバーを確定的に前進
        self._cur_file  = current
        self._cur_total = total
        self._creep     = 1.0
        self._update_progress()
        status = '✓' if ok else '✗'
        self.log.append(f"  {status} {msg}")

        # 残り時間を推定
        if self._batch_start_time and current > 0:
            elapsed   = time.time() - self._batch_start_time
            avg_per   = elapsed / current
            remaining = avg_per * (total - current)
            if remaining >= 3600:
                r_str = f'{int(remaining//3600)}時間{int((remaining%3600)//60)}分' if _lang == 'ja' else f'{int(remaining//3600)}h {int((remaining%3600)//60)}m'
            elif remaining >= 60:
                r_str = f'約{int(remaining//60)}分' if _lang == 'ja' else f'~{int(remaining//60)} min'
            else:
                r_str = f'約{int(remaining)}秒' if _lang == 'ja' else f'~{int(remaining)} sec'

            if current < total:
                eta = f'  残り推定: {r_str}' if _lang == 'ja' else f'  Est. remaining: {r_str}'
                current_text = self.lbl_current.text().split('  残り')[0].split('  Est.')[0]
                self.lbl_current.setText(current_text + eta)

    def _on_all_done(self, success: int, total: int):
        self.btn_start.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.btn_remove.setEnabled(True)
        self.btn_clear.setEnabled(True)
        # 完了＝バー満杯
        self.progress.setRange(0, 1000)
        self.progress.setValue(1000)
        self.lbl_current.setVisible(False)
        msg = (f"完了: {success}/{total} ファイル処理しました"
               if _lang == 'ja' else f"Done: {success}/{total} files processed.")
        self.log.append(f"\n{'='*40}\n{msg}")
        QMessageBox.information(self,
            '完了' if _lang == 'ja' else 'Done', msg)


# ──────────────────────────────────────────────────────────────────
# Find & Replace dialog
# ──────────────────────────────────────────────────────────────────

class FillerCutDialog(QDialog):
    def __init__(self, srt_table, parent=None, transcribe_lang: str = 'ja'):
        super().__init__(parent)
        self.srt_table = srt_table
        self.transcribe_lang = transcribe_lang
        self.setWindowTitle('フィラーカット' if _lang == 'ja' else 'Filler Cut')
        self.setMinimumWidth(420)
        self._build()

    def _build(self):
        vbox = QVBoxLayout(self)

        fillers = FILLER_LISTS.get(self.transcribe_lang)
        supported = fillers is not None
        if not supported:
            fillers = []

        # 対応言語バッジ
        lang_names = {
            'ja': '日本語', 'en': 'English', 'zh': '中文', 'ko': '한국어',
            'es': 'Español', 'fr': 'Français', 'de': 'Deutsch', 'pt': 'Português',
        }
        lang_name = lang_names.get(self.transcribe_lang, self.transcribe_lang)
        if supported:
            badge = QLabel(f'✅ {lang_name} のフィラーリストを使用中'
                           if _lang == 'ja' else
                           f'✅ Using filler list for {lang_name}')
            badge.setStyleSheet('color: #2a7a2a; font-weight: bold;')
        else:
            badge = QLabel(f'⚠️ {lang_name} は未対応です。フィラー語を手動で入力してください。'
                           if _lang == 'ja' else
                           f'⚠️ {lang_name} is not supported. Enter filler words manually.')
            badge.setStyleSheet('color: #a05000; font-weight: bold;')
        badge.setWordWrap(True)
        vbox.addWidget(badge)

        lbl = QLabel(
            '以下のテキストと完全一致するセグメントのチェックを外します。\n'
            '1行1ワード。追加・削除・編集して自由にカスタマイズできます。'
            if _lang == 'ja' else
            'Uncheck segments that exactly match the words below.\n'
            'One word per line. You can add, delete, or edit to customize the list.'
        )
        lbl.setWordWrap(True)
        vbox.addWidget(lbl)

        self.txt_fillers = QTextEdit()
        self.txt_fillers.setPlainText('\n'.join(fillers))
        self.txt_fillers.setMaximumHeight(200)
        vbox.addWidget(self.txt_fillers)

        self.lbl_result = QLabel('')
        self.lbl_result.setStyleSheet('color: green;')
        vbox.addWidget(self.lbl_result)

        btn_row = QHBoxLayout()
        btn_apply = QPushButton('適用' if _lang == 'ja' else 'Apply')
        btn_close = QPushButton('閉じる' if _lang == 'ja' else 'Close')
        btn_apply.clicked.connect(self._apply)
        btn_close.clicked.connect(self.close)
        btn_row.addWidget(btn_apply)
        btn_row.addWidget(btn_close)
        btn_row.addStretch()
        vbox.addLayout(btn_row)

    @staticmethod
    def _normalize(text: str) -> str:
        """句読点・空白を除去して比較用テキストを返す"""
        return text.strip().rstrip('、。，．,. \t　')

    def _apply(self):
        fillers = {line.strip() for line in
                   self.txt_fillers.toPlainText().splitlines() if line.strip()}
        count = 0
        self.srt_table.tbl.blockSignals(True)
        for row, entry in enumerate(self.srt_table.entries):
            if self._normalize(entry.text) in fillers:
                entry.checked = False
                item = self.srt_table.tbl.item(row, 0)
                if item:
                    item.setCheckState(Qt.CheckState.Unchecked)
                count += 1
        self.srt_table.tbl.blockSignals(False)
        self.srt_table._update_count()
        msg = f'{count} 件のフィラーを解除しました' if _lang == 'ja' \
              else f'{count} filler(s) unchecked.'
        self.lbl_result.setText(msg)


class FindReplaceDialog(QDialog):
    def __init__(self, srt_table, parent=None):
        super().__init__(parent)
        self.srt_table   = srt_table
        self._matches: List[int] = []  # マッチした行インデックス
        self._match_idx  = -1
        self.setWindowTitle('検索と置換' if _lang == 'ja' else 'Find & Replace')
        self.setMinimumWidth(420)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self._build()

    def _build(self):
        grid = QVBoxLayout(self)

        # 検索
        r1 = QHBoxLayout()
        r1.addWidget(QLabel('検索:' if _lang == 'ja' else 'Find:'))
        self.txt_find = QLineEdit()
        self.txt_find.setPlaceholderText('検索するテキスト' if _lang == 'ja' else 'Search text')
        self.txt_find.textChanged.connect(self._on_find_changed)
        r1.addWidget(self.txt_find)
        grid.addLayout(r1)

        # 置換
        r2 = QHBoxLayout()
        r2.addWidget(QLabel('置換:' if _lang == 'ja' else 'Replace:'))
        self.txt_replace = QLineEdit()
        self.txt_replace.setPlaceholderText('置換後のテキスト' if _lang == 'ja' else 'Replacement text')
        r2.addWidget(self.txt_replace)
        grid.addLayout(r2)

        # オプション
        opt = QHBoxLayout()
        self.chk_case = QCheckBox('大文字小文字を区別' if _lang == 'ja' else 'Case sensitive')
        self.lbl_status = QLabel('')
        self.lbl_status.setStyleSheet('color: #555;')
        opt.addWidget(self.chk_case)
        opt.addStretch()
        opt.addWidget(self.lbl_status)
        grid.addLayout(opt)

        # ボタン
        btn_row = QHBoxLayout()
        self.btn_prev    = QPushButton('◀ 前へ' if _lang == 'ja' else '◀ Prev')
        self.btn_next    = QPushButton('次へ ▶' if _lang == 'ja' else 'Next ▶')
        self.btn_replace = QPushButton('置換' if _lang == 'ja' else 'Replace')
        self.btn_all     = QPushButton('一括置換' if _lang == 'ja' else 'Replace All')
        self.btn_prev.clicked.connect(self._prev)
        self.btn_next.clicked.connect(self._next)
        self.btn_replace.clicked.connect(self._replace_one)
        self.btn_all.clicked.connect(self._replace_all)
        for b in (self.btn_prev, self.btn_next, self.btn_replace, self.btn_all):
            btn_row.addWidget(b)
        btn_row.addStretch()
        grid.addLayout(btn_row)

    # ── ロジック ──────────────────────────────────

    def _search_text(self) -> str:
        return self.txt_find.text()

    def _find_matches(self) -> List[int]:
        needle = self._search_text()
        if not needle:
            return []
        case = Qt.CaseSensitivity.CaseSensitive if self.chk_case.isChecked() \
               else Qt.CaseSensitivity.CaseInsensitive
        result = []
        for i, entry in enumerate(self.srt_table.entries):
            haystack = entry.text if self.chk_case.isChecked() else entry.text.lower()
            n        = needle if self.chk_case.isChecked() else needle.lower()
            if n in haystack:
                result.append(i)
        return result

    def _on_find_changed(self):
        self._matches  = self._find_matches()
        self._match_idx = 0 if self._matches else -1
        self._update_status()
        self._highlight()

    def _update_status(self):
        if not self._search_text():
            self.lbl_status.setText('')
        elif not self._matches:
            self.lbl_status.setText('見つかりません' if _lang == 'ja' else 'No matches')
            self.lbl_status.setStyleSheet('color: red;')
        else:
            pos = self._match_idx + 1 if self._match_idx >= 0 else '?'
            self.lbl_status.setText(f'{pos} / {len(self._matches)}件')
            self.lbl_status.setStyleSheet('color: #555;')

    def _highlight(self):
        tbl = self.srt_table.tbl
        # 全行のハイライトをリセット
        for row in range(tbl.rowCount()):
            for col in range(tbl.columnCount()):
                item = tbl.item(row, col)
                if item:
                    item.setBackground(Qt.GlobalColor.transparent)
        # マッチ行をハイライト
        for row in self._matches:
            for col in range(tbl.columnCount()):
                item = tbl.item(row, col)
                if item:
                    item.setBackground(Qt.GlobalColor.yellow)
        # 現在のマッチを強調
        if self._matches and self._match_idx >= 0:
            cur_row = self._matches[self._match_idx]
            tbl.scrollToItem(tbl.item(cur_row, 3))
            tbl.selectRow(cur_row)

    def _next(self):
        if not self._matches:
            self._matches = self._find_matches()
        if not self._matches:
            return
        self._match_idx = (self._match_idx + 1) % len(self._matches)
        self._update_status()
        self._highlight()

    def _prev(self):
        if not self._matches:
            self._matches = self._find_matches()
        if not self._matches:
            return
        self._match_idx = (self._match_idx - 1) % len(self._matches)
        self._update_status()
        self._highlight()

    def _replace_one(self):
        if not self._matches or self._match_idx < 0:
            return
        row   = self._matches[self._match_idx]
        entry = self.srt_table.entries[row]
        needle  = self._search_text()
        replace = self.txt_replace.text()
        if self.chk_case.isChecked():
            entry.text = entry.text.replace(needle, replace)
        else:
            import re as _re
            entry.text = _re.sub(_re.escape(needle), replace, entry.text,
                                  flags=_re.IGNORECASE)
        # テーブル表示を更新
        self.srt_table.tbl.blockSignals(True)
        item = self.srt_table.tbl.item(row, 3)
        if item:
            item.setText(entry.text.replace('\n', ' '))
        self.srt_table.tbl.blockSignals(False)
        # 再検索
        self._on_find_changed()

    def _replace_all(self):
        needle  = self._search_text()
        replace = self.txt_replace.text()
        if not needle:
            return
        count = 0
        import re as _re
        self.srt_table.tbl.blockSignals(True)
        for i, entry in enumerate(self.srt_table.entries):
            if self.chk_case.isChecked():
                if needle in entry.text:
                    entry.text = entry.text.replace(needle, replace)
                    count += 1
            else:
                new_text = _re.sub(_re.escape(needle), replace, entry.text,
                                   flags=_re.IGNORECASE)
                if new_text != entry.text:
                    entry.text = new_text
                    count += 1
            item = self.srt_table.tbl.item(i, 3)
            if item:
                item.setText(entry.text.replace('\n', ' '))
        self.srt_table.tbl.blockSignals(False)
        msg = f'{count} 件置換しました' if _lang == 'ja' else f'Replaced {count} item(s).'
        self.lbl_status.setText(msg)
        self.lbl_status.setStyleSheet('color: green;')
        self._matches = []
        self._match_idx = -1
        self._highlight()

    def closeEvent(self, event):
        # ダイアログを閉じたらハイライトをクリア
        self._matches = []
        self._highlight()
        super().closeEvent(event)


# ──────────────────────────────────────────────────────────────────
# Undo command for SRT text edits
# ──────────────────────────────────────────────────────────────────

class NudgeTimeCommand(QUndoCommand):
    def __init__(self, srt_table, row: int, col: int, delta_ms: int):
        label = '開始' if col == 1 else '終了'
        sign  = f'+{delta_ms}ms' if delta_ms > 0 else f'{delta_ms}ms'
        super().__init__(f"{label}微調整 {sign} (行 {row + 1})")
        self.srt_table = srt_table
        self.row       = row
        self.col       = col
        self.delta_ms  = delta_ms

    def _apply(self, delta: int):
        entry = self.srt_table.entries[self.row]
        if self.col == 1:
            entry.start_ms = max(0, entry.start_ms + delta)
            ms = entry.start_ms
        else:
            entry.end_ms = max(0, entry.end_ms + delta)
            ms = entry.end_ms
        self.srt_table.tbl.blockSignals(True)
        item = self.srt_table.tbl.item(self.row, self.col)
        if item:
            item.setText(_ms_to_srt(ms))
        self.srt_table.tbl.blockSignals(False)

    def redo(self):
        self._apply(self.delta_ms)

    def undo(self):
        self._apply(-self.delta_ms)


class EditTimeCommand(QUndoCommand):
    def __init__(self, srt_table, row: int, col: int, old_ms: int, new_ms: int):
        label = '開始時間' if col == 1 else '終了時間'
        super().__init__(f"{label}編集 (行 {row + 1})")
        self.srt_table = srt_table
        self.row    = row
        self.col    = col
        self.old_ms = old_ms
        self.new_ms = new_ms

    def _apply(self, ms: int):
        entry = self.srt_table.entries[self.row]
        if self.col == 1:
            entry.start_ms = ms
        else:
            entry.end_ms = ms
        self.srt_table.tbl.blockSignals(True)
        item = self.srt_table.tbl.item(self.row, self.col)
        if item:
            item.setText(_ms_to_srt(ms))
            item.setBackground(Qt.GlobalColor.transparent)
        self.srt_table.tbl.blockSignals(False)
        self.srt_table._update_count()

    def redo(self):
        self._apply(self.new_ms)

    def undo(self):
        self._apply(self.old_ms)


class EditTextCommand(QUndoCommand):
    def __init__(self, srt_table, row: int, old_text: str, new_text: str):
        super().__init__(f"テキスト編集 (行 {row + 1})")
        self.srt_table = srt_table
        self.row       = row
        self.old_text  = old_text
        self.new_text  = new_text

    def redo(self):
        self.srt_table.entries[self.row].text = self.new_text
        self.srt_table.tbl.blockSignals(True)
        item = self.srt_table.tbl.item(self.row, 3)
        if item:
            item.setText(self.new_text)
        self.srt_table.tbl.blockSignals(False)

    def undo(self):
        self.srt_table.entries[self.row].text = self.old_text
        self.srt_table.tbl.blockSignals(True)
        item = self.srt_table.tbl.item(self.row, 3)
        if item:
            item.setText(self.old_text)
        self.srt_table.tbl.blockSignals(False)


# ──────────────────────────────────────────────────────────────────
# Split / Merge commands
# ──────────────────────────────────────────────────────────────────

class SplitCommand(QUndoCommand):
    def __init__(self, srt_table, row: int, text_a: str, text_b: str, split_ms: int):
        super().__init__(f"分割 (行 {row + 1})" if _lang == 'ja' else f"Split (row {row + 1})")
        self.srt_table = srt_table
        self.row       = row
        self.text_a    = text_a
        self.text_b    = text_b
        self.split_ms  = split_ms

    def redo(self):
        st = self.srt_table
        orig = st.entries[self.row]
        entry_a = SRTEntry(orig.index,     orig.start_ms, self.split_ms, self.text_a, orig.checked)
        entry_b = SRTEntry(orig.index + 1, self.split_ms, orig.end_ms,   self.text_b, orig.checked)
        st.entries[self.row] = entry_a
        st.entries.insert(self.row + 1, entry_b)
        _reindex(st.entries)
        st._repopulate()

    def undo(self):
        st = self.srt_table
        orig_a = st.entries[self.row]
        orig_b = st.entries[self.row + 1]
        merged = SRTEntry(orig_a.index, orig_a.start_ms, orig_b.end_ms,
                          self.text_a + (' ' if self.text_a and self.text_b else '') + self.text_b,
                          orig_a.checked)
        st.entries[self.row] = merged
        del st.entries[self.row + 1]
        _reindex(st.entries)
        st._repopulate()


class MergeCommand(QUndoCommand):
    def __init__(self, srt_table, rows: List[int]):
        super().__init__(f"統合 ({len(rows)}行)" if _lang == 'ja' else f"Merge ({len(rows)} rows)")
        self.srt_table   = srt_table
        self.rows        = sorted(rows)
        # 元のエントリを保存
        self.saved       = [srt_table.entries[r].__class__(
                                srt_table.entries[r].index,
                                srt_table.entries[r].start_ms,
                                srt_table.entries[r].end_ms,
                                srt_table.entries[r].text,
                                srt_table.entries[r].checked)
                            for r in self.rows]

    def redo(self):
        st    = self.srt_table
        first = self.rows[0]
        texts = ' '.join(st.entries[r].text for r in self.rows)
        merged = SRTEntry(st.entries[first].index,
                          st.entries[first].start_ms,
                          st.entries[self.rows[-1]].end_ms,
                          texts, st.entries[first].checked)
        # 後ろから削除
        for r in reversed(self.rows[1:]):
            del st.entries[r]
        st.entries[first] = merged
        _reindex(st.entries)
        st._repopulate()

    def undo(self):
        st    = self.srt_table
        first = self.rows[0]
        # 1行を元の複数行に戻す
        del st.entries[first]
        for i, e in enumerate(self.saved):
            st.entries.insert(first + i, SRTEntry(e.index, e.start_ms, e.end_ms, e.text, e.checked))
        _reindex(st.entries)
        st._repopulate()


def _make_eaf(entries: List['SRTEntry'], video_path: str, tier_name: str) -> str:
    """SRTエントリからELAN EAF形式のXML文字列を生成する"""
    import xml.etree.ElementTree as ET
    from datetime import datetime, timezone, timedelta

    now = datetime.now(timezone(timedelta(hours=9))).strftime('%Y-%m-%dT%H:%M:%S+09:00')
    video_name = Path(video_path).name
    video_url  = Path(video_path).as_uri()

    # タイムスロットとアノテーションを構築
    time_slots = []
    annotations = []
    for i, e in enumerate(entries):
        ts1_id = f'ts{i*2+1}'
        ts2_id = f'ts{i*2+2}'
        ann_id = f'a{i+1}'
        time_slots.append((ts1_id, e.start_ms))
        time_slots.append((ts2_id, e.end_ms))
        annotations.append((ann_id, ts1_id, ts2_id, e.text))

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<ANNOTATION_DOCUMENT AUTHOR="" DATE="{now}" FORMAT="3.0" VERSION="3.0"',
        '    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"',
        '    xsi:noNamespaceSchemaLocation="http://www.mpi.nl/tools/elan/EAFv3.0.xsd">',
        f'    <HEADER MEDIA_FILE="" TIME_UNITS="milliseconds">',
        f'        <MEDIA_DESCRIPTOR MEDIA_URL="{video_url}" MIME_TYPE="video/mp4"',
        f'            RELATIVE_MEDIA_URL="{video_name}"/>',
        '    </HEADER>',
        '    <TIME_ORDER>',
    ]
    for ts_id, ts_val in time_slots:
        lines.append(f'        <TIME_SLOT TIME_SLOT_ID="{ts_id}" TIME_VALUE="{ts_val}"/>')
    lines.append('    </TIME_ORDER>')
    lines.append(f'    <TIER LINGUISTIC_TYPE_REF="default-lt" TIER_ID="{tier_name}">')
    for ann_id, ts1, ts2, text in annotations:
        safe_text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
        lines += [
            '        <ANNOTATION>',
            f'            <ALIGNABLE_ANNOTATION ANNOTATION_ID="{ann_id}"',
            f'                TIME_SLOT_REF1="{ts1}" TIME_SLOT_REF2="{ts2}">',
            f'                <ANNOTATION_VALUE>{safe_text}</ANNOTATION_VALUE>',
            '            </ALIGNABLE_ANNOTATION>',
            '        </ANNOTATION>',
        ]
    lines += [
        '    </TIER>',
        '    <LINGUISTIC_TYPE GRAPHIC_REFERENCES="false" LINGUISTIC_TYPE_ID="default-lt" TIME_ALIGNABLE="true"/>',
        '    <CONSTRAINT DESCRIPTION="Time subdivision of parent annotation\'s time interval, no time gaps allowed within this interval" STEREOTYPE="Time_Subdivision"/>',
        '    <CONSTRAINT DESCRIPTION="Symbolic subdivision of a parent annotation. Annotations referring to the same parent are ordered" STEREOTYPE="Symbolic_Subdivision"/>',
        '    <CONSTRAINT DESCRIPTION="1-1 association with a parent annotation" STEREOTYPE="Symbolic_Association"/>',
        '    <CONSTRAINT DESCRIPTION="Time alignment of 2-3 child annotation" STEREOTYPE="Included_In"/>',
        '</ANNOTATION_DOCUMENT>',
    ]
    return '\n'.join(lines)


def _reindex(entries: List['SRTEntry']):
    for i, e in enumerate(entries):
        e.index = i + 1


# ──────────────────────────────────────────────────────────────────
# Split dialog
# ──────────────────────────────────────────────────────────────────

class SplitDialog(QDialog):
    def __init__(self, entry: 'SRTEntry', parent=None):
        super().__init__(parent)
        self.entry = entry
        self.setWindowTitle('行を分割' if _lang == 'ja' else 'Split Segment')
        self.setMinimumWidth(480)
        self._build()

    def _build(self):
        vbox = QVBoxLayout(self)

        # 説明
        vbox.addWidget(QLabel('テキストをクリックして分割位置を選択してください。'
                              if _lang == 'ja' else
                              'Click in the text to choose the split point.'))

        # テキスト表示（クリックで分割点を選ぶ）
        self.txt = QTextEdit()
        self.txt.setPlainText(self.entry.text)
        self.txt.setMaximumHeight(80)
        self.txt.setReadOnly(False)
        self.txt.cursorPositionChanged.connect(self._on_cursor)
        vbox.addWidget(self.txt)

        # プレビュー
        self.lbl_preview = QLabel('')
        self.lbl_preview.setWordWrap(True)
        vbox.addWidget(self.lbl_preview)

        # 分割時間
        hbox = QHBoxLayout()
        hbox.addWidget(QLabel('分割時間:' if _lang == 'ja' else 'Split time:'))
        self.spn_split = QDoubleSpinBox()
        dur_sec = (self.entry.end_ms - self.entry.start_ms) / 1000
        self.spn_split.setRange(self.entry.start_ms / 1000, self.entry.end_ms / 1000)
        self.spn_split.setDecimals(3)
        self.spn_split.setSingleStep(0.1)
        mid = (self.entry.start_ms + self.entry.end_ms) / 2000
        self.spn_split.setValue(mid)
        self.spn_split.setSuffix(' 秒' if _lang == 'ja' else ' sec')
        self.spn_split.valueChanged.connect(self._on_time_changed)
        hbox.addWidget(self.spn_split)
        hbox.addStretch()
        vbox.addLayout(hbox)

        # ボタン
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        vbox.addWidget(btns)

        self._update_preview()

    def _on_cursor(self):
        cursor = self.txt.textCursor()
        pos    = cursor.position()
        text   = self.txt.toPlainText()
        total  = max(len(text), 1)
        ratio  = pos / total
        dur_ms = self.entry.end_ms - self.entry.start_ms
        split_ms = self.entry.start_ms + int(dur_ms * ratio)
        self.spn_split.blockSignals(True)
        self.spn_split.setValue(split_ms / 1000)
        self.spn_split.blockSignals(False)
        self._split_pos = pos
        self._update_preview()

    def _on_time_changed(self):
        self._update_preview()

    def _update_preview(self):
        cursor = self.txt.textCursor()
        pos    = cursor.position()
        text   = self.txt.toPlainText()
        part_a = text[:pos].strip()
        part_b = text[pos:].strip()
        t      = self.spn_split.value()
        self.lbl_preview.setText(
            f'前半: 「{part_a}」  ({_ms_to_srt(self.entry.start_ms)} → {_ms_to_srt(int(t*1000))})\n'
            f'後半: 「{part_b}」  ({_ms_to_srt(int(t*1000))} → {_ms_to_srt(self.entry.end_ms)})'
        )

    def result_values(self):
        cursor = self.txt.textCursor()
        pos    = cursor.position()
        text   = self.txt.toPlainText()
        text_a = text[:pos].strip()
        text_b = text[pos:].strip()
        split_ms = int(self.spn_split.value() * 1000)
        return text_a, text_b, split_ms


# ──────────────────────────────────────────────────────────────────
# SRT table widget
# ──────────────────────────────────────────────────────────────────

class SRTTable(QWidget):
    row_activated = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.entries: List[SRTEntry] = []
        self.undo_stack = QUndoStack(self)
        self._build()

    def insert_playback_controls(self, widget):
        """再生コントロールを「全選択」行と「ステップ」行の間に差し込む"""
        # vbox の index: 0=bar(全選択行), 1=nudge_bar(ステップ行)...
        self._vbox.insertWidget(1, widget)

    def _build(self):
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(2)          # 全選択/再生/ステップ各行の行間を詰める
        self._vbox = vbox

        bar = QHBoxLayout()
        self.btn_all  = QPushButton(tr('select_all'))
        self.btn_none = QPushButton(tr('deselect_all'))
        self.btn_find   = QPushButton('🔍 検索・置換' if _lang == 'ja' else '🔍 Find & Replace')
        self.btn_filler = QPushButton('✂ フィラーカット' if _lang == 'ja' else '✂ Filler Cut')
        self.lbl_count  = QLabel("")
        self.btn_all.clicked.connect(self._all)
        self.btn_none.clicked.connect(self._none)
        self.btn_find.clicked.connect(self._open_find_replace)
        self.btn_filler.clicked.connect(self._open_filler_cut)
        bar.addWidget(self.btn_all)
        bar.addWidget(self.btn_none)
        bar.addWidget(self.btn_find)
        bar.addWidget(self.btn_filler)
        bar.addStretch()
        bar.addWidget(self.lbl_count)
        vbox.addLayout(bar)

        # 微調整ツールバー
        nudge_bar = QHBoxLayout()
        nudge_bar.setSpacing(2)
        self._nudge_step = 100  # ms

        lbl_step = QLabel('ステップ:' if _lang == 'ja' else 'Step:')
        self.rdo_100 = QRadioButton('100ms')
        self.rdo_500 = QRadioButton('500ms')
        self.rdo_100.setChecked(True)
        self.rdo_100.toggled.connect(lambda on: setattr(self, '_nudge_step', 100) if on else None)
        self.rdo_500.toggled.connect(lambda on: setattr(self, '_nudge_step', 500) if on else None)

        lbl_start = QLabel('開始:' if _lang == 'ja' else 'Start:')
        self.btn_s_back = QPushButton('◀')
        self.btn_s_fwd  = QPushButton('▶')
        self.btn_s_back.setFixedWidth(32)
        self.btn_s_fwd.setFixedWidth(32)
        self.btn_s_back.setToolTip('開始時間を戻す' if _lang == 'ja' else 'Move start earlier')
        self.btn_s_fwd.setToolTip('開始時間を進める' if _lang == 'ja' else 'Move start later')
        self.btn_s_back.clicked.connect(lambda: self._nudge(1, -1))
        self.btn_s_fwd.clicked.connect(lambda: self._nudge(1, +1))

        lbl_end = QLabel('終了:' if _lang == 'ja' else 'End:')
        self.btn_e_back = QPushButton('◀')
        self.btn_e_fwd  = QPushButton('▶')
        self.btn_e_back.setFixedWidth(32)
        self.btn_e_fwd.setFixedWidth(32)
        self.btn_e_back.setToolTip('終了時間を戻す' if _lang == 'ja' else 'Move end earlier')
        self.btn_e_fwd.setToolTip('終了時間を進める' if _lang == 'ja' else 'Move end later')
        self.btn_e_back.clicked.connect(lambda: self._nudge(2, -1))
        self.btn_e_fwd.clicked.connect(lambda: self._nudge(2, +1))

        for w in (lbl_step, self.rdo_100, self.rdo_500,
                  lbl_start, self.btn_s_back, self.btn_s_fwd,
                  lbl_end,   self.btn_e_back, self.btn_e_fwd):
            nudge_bar.addWidget(w)
        nudge_bar.addStretch()
        vbox.addLayout(nudge_bar)

        self.tbl = QTableWidget(0, 4)
        self.tbl.setHorizontalHeaderLabels(tr('tbl_headers'))
        hh = self.tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl.setAlternatingRowColors(True)
        self.tbl.itemSelectionChanged.connect(self._on_sel)
        self.tbl.itemChanged.connect(self._on_changed)
        self.tbl.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tbl.customContextMenuRequested.connect(self._on_context_menu)
        vbox.addWidget(self.tbl)

        # Undo / Redo ショートカット
        QShortcut(QKeySequence('Ctrl+Z'), self).activated.connect(self.undo_stack.undo)
        QShortcut(QKeySequence('Ctrl+Y'), self).activated.connect(self.undo_stack.redo)

        # 再生・チェック操作ショートカット
        QShortcut(QKeySequence('X'), self).activated.connect(self._toggle_check)
        QShortcut(QKeySequence('Down'), self).activated.connect(self._next_row)
        QShortcut(QKeySequence('Up'), self).activated.connect(self._prev_row)
        QShortcut(QKeySequence('Z'), self).activated.connect(self._merge_prev)
        QShortcut(QKeySequence('C'), self).activated.connect(self._merge_next)
        QShortcut(QKeySequence('S'), self).activated.connect(lambda: self._split_row(self.tbl.currentRow()))
        QShortcut(QKeySequence('D'), self).activated.connect(self._enter_edit_mode)

    def retranslate(self):
        self.btn_all.setText(tr('select_all'))
        self.btn_none.setText(tr('deselect_all'))
        self.btn_find.setText('🔍 検索・置換' if _lang == 'ja' else '🔍 Find & Replace')
        self.btn_filler.setText('✂ フィラーカット' if _lang == 'ja' else '✂ Filler Cut')
        self.tbl.setHorizontalHeaderLabels(tr('tbl_headers'))
        self._update_count()

    def _open_find_replace(self):
        dlg = FindReplaceDialog(self, self.window())
        dlg.show()

    def _open_filler_cut(self):
        # メインウィンドウの文字起こし言語設定を取得
        win = self.window()
        lang_code = 'ja'
        if hasattr(win, 'cmb_lang'):
            lang_code = _LANG_MAP.get(win.cmb_lang.currentText(), 'ja')
        dlg = FillerCutDialog(self, win, transcribe_lang=lang_code)
        dlg.exec()

    def load(self, entries: List[SRTEntry]):
        self.entries = entries
        self._repopulate()

    def _repopulate(self):
        self.tbl.blockSignals(True)
        self.tbl.setRowCount(len(self.entries))
        for row, e in enumerate(self.entries):
            cb = QTableWidgetItem()
            cb.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            cb.setCheckState(Qt.CheckState.Checked if e.checked else Qt.CheckState.Unchecked)
            self.tbl.setItem(row, 0, cb)

            for col, val in [(1, _ms_to_srt(e.start_ms)), (2, _ms_to_srt(e.end_ms))]:
                item = QTableWidgetItem(val)
                item.setToolTip('HH:MM:SS,mmm 形式で編集できます')
                self.tbl.setItem(row, col, item)

            self.tbl.setItem(row, 3, QTableWidgetItem(e.text.replace('\n', ' ')))

        self.tbl.blockSignals(False)
        self._update_count()

    def _on_changed(self, item: QTableWidgetItem):
        row = item.row()
        if row >= len(self.entries):
            return
        if item.column() == 0:
            self.entries[row].checked = (item.checkState() == Qt.CheckState.Checked)
            self._update_count()
        elif item.column() in (1, 2):
            entry  = self.entries[row]
            old_ms = entry.start_ms if item.column() == 1 else entry.end_ms
            new_ms = _ts_to_ms(item.text())
            if new_ms == 0 and item.text().strip() not in ('00:00:00,000', '0:00:00,000'):
                # パース失敗 → 赤背景で元に戻す
                self.tbl.blockSignals(True)
                item.setText(_ms_to_srt(old_ms))
                item.setBackground(QColor('#ffcccc'))
                self.tbl.blockSignals(False)
                QTimer.singleShot(1200, lambda: item.setBackground(Qt.GlobalColor.transparent))
            elif new_ms != old_ms:
                cmd = EditTimeCommand(self, row, item.column(), old_ms, new_ms)
                self.undo_stack.push(cmd)
        elif item.column() == 3:
            old_text = self.entries[row].text
            new_text = item.text()
            if old_text != new_text:
                cmd = EditTextCommand(self, row, old_text, new_text)
                self.undo_stack.push(cmd)

    def _enter_edit_mode(self):
        row = self.tbl.currentRow()
        if row < 0 or row >= len(self.entries):
            return
        item = self.tbl.item(row, 3)
        if item:
            self.tbl.setCurrentItem(item)
            self.tbl.editItem(item)

    def _merge_prev(self):
        row = self.tbl.currentRow()
        if row <= 0 or row >= len(self.entries):
            return
        self._merge_rows([row - 1, row])

    def _merge_next(self):
        row = self.tbl.currentRow()
        if row < 0 or row >= len(self.entries) - 1:
            return
        self._merge_rows([row, row + 1])

    def _toggle_check(self):
        row = self.tbl.currentRow()
        if row < 0 or row >= len(self.entries):
            return
        entry = self.entries[row]
        entry.checked = not entry.checked
        self.tbl.blockSignals(True)
        item = self.tbl.item(row, 0)
        if item:
            item.setCheckState(Qt.CheckState.Checked if entry.checked else Qt.CheckState.Unchecked)
        self.tbl.blockSignals(False)
        self._update_count()

    def _next_row(self):
        row = self.tbl.currentRow()
        next_row = min(row + 1, self.tbl.rowCount() - 1)
        self.tbl.setCurrentCell(next_row, 0)
        self.row_activated.emit(next_row)

    def _prev_row(self):
        row = self.tbl.currentRow()
        prev_row = max(row - 1, 0)
        self.tbl.setCurrentCell(prev_row, 0)
        self.row_activated.emit(prev_row)

    def _nudge(self, col: int, direction: int):
        row = self.tbl.currentRow()
        if row < 0 or row >= len(self.entries):
            return
        delta = direction * self._nudge_step
        cmd = NudgeTimeCommand(self, row, col, delta)
        self.undo_stack.push(cmd)

    def _on_sel(self):
        if self.tbl.selectedItems():
            self.row_activated.emit(self.tbl.currentRow())

    def _all(self):
        self._set_all(True)

    def _none(self):
        self._set_all(False)

    def _set_all(self, checked: bool):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        self.tbl.blockSignals(True)
        for row in range(self.tbl.rowCount()):
            item = self.tbl.item(row, 0)
            if item:
                item.setCheckState(state)
                self.entries[row].checked = checked
        self.tbl.blockSignals(False)
        self._update_count()

    def _on_context_menu(self, pos):
        selected_rows = sorted({idx.row() for idx in self.tbl.selectedIndexes()})
        menu = QMenu(self)
        act_split = menu.addAction('✂ 行を分割…' if _lang == 'ja' else '✂ Split row…')
        act_merge = menu.addAction('⊕ 選択行を統合' if _lang == 'ja' else '⊕ Merge selected rows')
        act_split.setEnabled(len(selected_rows) == 1)
        act_merge.setEnabled(len(selected_rows) >= 2)
        action = menu.exec(self.tbl.viewport().mapToGlobal(pos))
        if action == act_split and selected_rows:
            self._split_row(selected_rows[0])
        elif action == act_merge and len(selected_rows) >= 2:
            self._merge_rows(selected_rows)

    def _split_row(self, row: int):
        entry = self.entries[row]
        dlg = SplitDialog(entry, self.window())
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        text_a, text_b, split_ms = dlg.result_values()
        if not text_a and not text_b:
            return
        if split_ms <= entry.start_ms or split_ms >= entry.end_ms:
            QMessageBox.warning(self.window(),
                'エラー' if _lang == 'ja' else 'Error',
                '分割時間が範囲外です' if _lang == 'ja' else 'Split time is out of range.')
            return
        cmd = SplitCommand(self, row, text_a, text_b, split_ms)
        self.undo_stack.push(cmd)

    def _merge_rows(self, rows: List[int]):
        # 連続行チェック
        if rows != list(range(rows[0], rows[-1] + 1)):
            QMessageBox.warning(self.window(),
                'エラー' if _lang == 'ja' else 'Error',
                '連続した行を選択してください' if _lang == 'ja' else 'Please select consecutive rows.')
            return
        cmd = MergeCommand(self, rows)
        self.undo_stack.push(cmd)

    def _update_count(self):
        total       = len(self.entries)
        checked     = sum(1 for e in self.entries if e.checked)
        duration_ms = sum(e.end_ms - e.start_ms for e in self.entries if e.checked)
        h, r  = divmod(duration_ms, 3_600_000)
        mi, r = divmod(r, 60_000)
        s     = r // 1_000
        dur_str = f"{h:02d}:{mi:02d}:{s:02d}" if h else f"{mi:02d}:{s:02d}"
        self.lbl_count.setText(tr('count_fmt').format(checked=checked, total=total, dur=dur_str))


# ──────────────────────────────────────────────────────────────────
# Video player widget
# ──────────────────────────────────────────────────────────────────

class VideoPlayer(QWidget):
    def __init__(self):
        super().__init__()
        self._seg_end: Optional[int] = None
        self._build()
        self._setup_player()

    def _build(self):
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(0, 0, 0, 0)

        self.video_widget = QVideoWidget()
        self.video_widget.setMinimumSize(400, 240)
        self.video_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        vbox.addWidget(self.video_widget)

        # セグメント文字表示は画面に出さない（時刻は再生バー、本文は右の表に表示）
        # レイアウトに加えないことで動画が下までいっぱいになり、右のSRT表と下辺が揃う
        self.lbl_seg = QLabel("", self)
        self.lbl_seg.setVisible(False)

        # 再生コントロールは1つのウィジェットにまとめ、右側のSRT表の上に配置する
        # （動画の下に置くと縦が詰まったとき隠れてしまうため）
        self.controls_widget = QWidget()
        cbar = QHBoxLayout(self.controls_widget)
        cbar.setContentsMargins(0, 0, 0, 0)
        self.btn_play  = QPushButton(tr('play'))
        self.btn_pause = QPushButton(tr('pause'))
        self.btn_stop  = QPushButton(tr('stop'))
        self.btn_play.clicked.connect(self._play)
        self.btn_pause.clicked.connect(self._pause)
        self.btn_stop.clicked.connect(self._stop)
        self.lbl_time = QLabel("--:--:-- / --:--:--")
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.sliderMoved.connect(self._seek)
        cbar.addWidget(self.btn_play)
        cbar.addWidget(self.btn_pause)
        cbar.addWidget(self.btn_stop)
        cbar.addWidget(self.lbl_time)
        cbar.addWidget(self.slider, stretch=1)

    def retranslate(self):
        self.btn_play.setText(tr('play'))
        self.btn_pause.setText(tr('pause'))
        self.btn_stop.setText(tr('stop'))

    def _setup_player(self):
        self.player = QMediaPlayer()
        self.audio  = QAudioOutput()
        self.player.setAudioOutput(self.audio)
        self.player.setVideoOutput(self.video_widget)
        self.player.positionChanged.connect(self._on_pos)
        self.player.durationChanged.connect(self._on_dur)
        self.player.errorOccurred.connect(
            lambda _err, msg: self.lbl_seg.setText(f"Player error: {msg}"))

    def load(self, path: str):
        self.player.setSource(QUrl.fromLocalFile(path))
        self._seg_end = None

    def play_segment(self, entry: SRTEntry):
        self._seg_end = entry.end_ms
        self.player.setPosition(entry.start_ms)
        self.player.play()
        self.lbl_seg.setText(
            f"{_ms_to_srt(entry.start_ms)}  →  {_ms_to_srt(entry.end_ms)}\n"
            f"{entry.text[:120]}")

    def _play(self):
        self.player.play()

    def _pause(self):
        self.player.pause()

    def _stop(self):
        self._seg_end = None
        self.player.stop()

    def _seek(self, pos: int):
        self.player.setPosition(pos)

    def _on_pos(self, pos: int):
        self.slider.setValue(pos)
        dur = self.player.duration()
        self.lbl_time.setText(f"{_ms_to_clock(pos)} / {_ms_to_clock(dur)}")
        if self._seg_end is not None and pos >= self._seg_end:
            self.player.pause()
            self._seg_end = None

    def _on_dur(self, dur: int):
        self.slider.setRange(0, dur)


# ──────────────────────────────────────────────────────────────────
# Main window
# ──────────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.video_path: Optional[str] = None
        self.srt_path:   Optional[str] = None
        self.worker: Optional[FFmpegWorker] = None
        self.whisper_worker: Optional[WhisperWorker] = None
        self.setWindowTitle(tr('window_title'))
        self.setMinimumSize(1100, 700)
        self._build()
        self._build_menu()
        QShortcut(QKeySequence('Ctrl+H'), self).activated.connect(
            self.srt_tbl._open_find_replace)

    def _build(self):
        root = QWidget()
        self.setCentralWidget(root)
        vbox = QVBoxLayout(root)

        # ── ファイル選択バー ──────────────────────────
        bar = QHBoxLayout()
        self.btn_video    = QPushButton(tr('open_video'))
        self.btn_srt      = QPushButton(tr('open_srt'))
        self.lbl_video    = QLabel(tr('video_none'))
        self.lbl_srt      = QLabel(tr('srt_none'))
        self.btn_save_srt = QPushButton(tr('save_srt'))
        self.btn_save_srt.setEnabled(False)
        self.btn_save_srt.setToolTip(tr('save_srt_tip'))
        self.btn_export_eaf = QPushButton('EAF書き出し' if _lang == 'ja' else 'Export EAF')
        self.btn_export_eaf.setEnabled(False)
        self.btn_export_eaf.setToolTip('ELAN用EAFファイルを書き出す' if _lang == 'ja' else 'Export as ELAN EAF file')
        self.btn_export_eaf.clicked.connect(self._export_eaf)
        self.btn_close_video = QPushButton('✕')
        self.btn_close_video.setFixedWidth(28)
        self.btn_close_video.setEnabled(False)
        self.btn_close_video.setToolTip('動画を閉じて初期状態に戻す' if _lang == 'ja' else 'Close video and reset')
        self.btn_video.clicked.connect(self._open_video)
        self.btn_srt.clicked.connect(self._open_srt)
        self.btn_save_srt.clicked.connect(self._save_srt)
        self.btn_close_video.clicked.connect(self._reset)

        self.btn_lang = QPushButton(tr('lang_toggle'))
        self.btn_lang.setFlat(True)
        self.btn_lang.setStyleSheet("font-weight: bold; font-size: 12px;")
        self.btn_lang.setToolTip("Switch language / 言語切り替え")
        self.btn_lang.clicked.connect(self._toggle_lang)

        self.btn_donate = QPushButton(tr('donate'))
        self.btn_donate.setStyleSheet("color: #c0392b; font-size: 11px;")
        self.btn_donate.setFlat(True)
        self.btn_donate.setToolTip(tr('donate_tip'))
        self.btn_donate.clicked.connect(self._open_donate)

        for w in (self.btn_video, self.lbl_video, self.btn_close_video, self.btn_srt, self.lbl_srt, self.btn_save_srt, self.btn_export_eaf):
            bar.addWidget(w)
        bar.addStretch()
        bar.addWidget(self.btn_lang)
        bar.addSpacing(8)
        bar.addWidget(self.btn_donate)
        vbox.addLayout(bar)

        # ── Whisper 文字起こし行 ──────────────────────
        w_bar = QHBoxLayout()
        self.lbl_transcribe = QLabel(tr('transcribe_label'))
        w_bar.addWidget(self.lbl_transcribe)

        self.cmb_model = QComboBox()
        self.cmb_model.setMinimumWidth(180)
        self.cmb_model.setToolTip(tr('model_tip'))
        self._populate_models()

        self.cmb_lang = QComboBox()
        self.cmb_lang.addItems(list(_LANG_MAP.keys()))
        self.cmb_lang.setToolTip(tr('lang_tip'))

        self.btn_transcribe = QPushButton(tr('transcribe_btn'))
        self.btn_transcribe.setEnabled(False)
        self.btn_transcribe.clicked.connect(self._transcribe)

        self.btn_transcribe_cancel = QPushButton(tr('transcribe_cancel'))
        self.btn_transcribe_cancel.setEnabled(False)
        self.btn_transcribe_cancel.clicked.connect(self._cancel_transcribe)

        self.btn_batch = QPushButton('📂 バッチ文字起こし' if _lang == 'ja' else '📂 Batch Transcription')
        self.btn_batch.setToolTip('複数の動画ファイルをまとめて文字起こしする' if _lang == 'ja'
                                  else 'Transcribe multiple video files at once')
        self.btn_batch.clicked.connect(self._open_batch)

        self.chk_mark_silence = QCheckBox(tr('mark_silence'))
        self.chk_mark_silence.setToolTip(tr('mark_silence_tip'))

        self.spn_silence = QDoubleSpinBox()
        self.spn_silence.setRange(0.5, 10.0)
        self.spn_silence.setSingleStep(0.5)
        self.spn_silence.setValue(1.0)
        self.spn_silence.setSuffix(tr('silence_suffix'))
        self.spn_silence.setToolTip(tr('silence_tip'))

        self.lbl_model = QLabel(tr('model_label'))
        self.lbl_lang  = QLabel(tr('lang_label'))
        w_bar.addWidget(self.lbl_model)
        w_bar.addWidget(self.cmb_model)
        w_bar.addWidget(self.lbl_lang)
        w_bar.addWidget(self.cmb_lang)
        w_bar.addWidget(self.btn_transcribe)
        w_bar.addWidget(self.btn_transcribe_cancel)
        w_bar.addSpacing(8)
        w_bar.addWidget(self.btn_batch)
        w_bar.addSpacing(16)
        w_bar.addWidget(self.chk_mark_silence)
        w_bar.addWidget(self.spn_silence)
        w_bar.addStretch()
        vbox.addLayout(w_bar)

        # ── スプリッター ─────────────────────────────
        self.spl = QSplitter(Qt.Orientation.Horizontal)

        self.player = VideoPlayer()
        self.spl.addWidget(self.player)

        self.srt_tbl = SRTTable()
        self.srt_tbl.row_activated.connect(self._on_row)
        self.spl.addWidget(self.srt_tbl)

        # 再生コントロールを右側（全選択行とステップ行の間）に配置
        self.srt_tbl.insert_playback_controls(self.player.controls_widget)

        self.spl.setSizes([500, 600])
        vbox.addWidget(self.spl, stretch=1)

        # ── 出力設定 ──────────────────────────────────
        self.grp_output = QGroupBox(tr('output_group'))
        gv = QVBoxLayout(self.grp_output)
        gv.setContentsMargins(10, 6, 10, 6)   # 出力設定の上下余白を詰める
        gv.setSpacing(4)

        r1 = QHBoxLayout()
        self.rb_combine   = QRadioButton(tr('combine'))
        self.rb_separate  = QRadioButton(tr('separate'))
        self.rb_combine.setChecked(True)
        self.chk_reencode = QCheckBox(tr('reencode'))
        r1.addWidget(self.rb_combine)
        r1.addWidget(self.rb_separate)
        r1.addSpacing(24)
        r1.addWidget(self.chk_reencode)
        r1.addStretch()
        gv.addLayout(r1)

        r_sub = QHBoxLayout()
        self.chk_burn_sub = QCheckBox('字幕を焼き込む' if _lang == 'ja' else 'Burn subtitles')
        self.chk_burn_sub.setToolTip('選択セグメントの字幕を映像に焼き込みます（再エンコード）'
                                     if _lang == 'ja' else
                                     'Burn subtitles into video (re-encodes)')
        lbl_fsize = QLabel('フォントサイズ:' if _lang == 'ja' else 'Font size:')
        self.spn_font_size = QSpinBox()
        self.spn_font_size.setRange(20, 120)
        self.spn_font_size.setValue(40)
        self.spn_font_size.setSuffix(' px')
        self.spn_font_size.setToolTip('0にすると自動' if _lang == 'ja' else 'Auto if 0')

        lbl_font = QLabel('フォント:' if _lang == 'ja' else 'Font:')
        self.txt_font = QLineEdit()
        self.txt_font.setPlaceholderText('空欄で自動 / Auto if empty')
        self.txt_font.setFixedWidth(200)
        self.txt_font.setToolTip(
            '空欄で言語に応じて自動選択。アラビア語など特殊文字は手動でフォント名を入力してください。'
            if _lang == 'ja' else
            'Leave blank for auto-selection. For Arabic, Hindi, etc., enter the font name manually.'
        )

        self.btn_sub_preview = QPushButton('▶ プレビュー' if _lang == 'ja' else '▶ Preview')
        self.btn_sub_preview.setToolTip('選択行1セグメントだけ焼き込んで確認'
                                        if _lang == 'ja' else
                                        'Render selected segment for preview')
        self.btn_sub_preview.clicked.connect(self._preview_subtitle)

        def _toggle_sub_ui(checked):
            lbl_fsize.setEnabled(checked)
            self.spn_font_size.setEnabled(checked)
            lbl_font.setEnabled(checked)
            self.txt_font.setEnabled(checked)
            self.btn_sub_preview.setEnabled(checked)
            # オンにした瞬間、ffmpegが字幕焼き込み非対応なら即警告
            if checked and not _ffmpeg_has_subtitles():
                QMessageBox.warning(
                    self,
                    '字幕焼き込み非対応のffmpeg' if _lang == 'ja' else 'ffmpeg without subtitle support',
                    _subtitle_unavailable_msg())
        self.chk_burn_sub.toggled.connect(_toggle_sub_ui)
        _toggle_sub_ui(False)

        r_sub.addWidget(self.chk_burn_sub)
        r_sub.addSpacing(16)
        r_sub.addWidget(lbl_fsize)
        r_sub.addWidget(self.spn_font_size)
        r_sub.addSpacing(16)
        r_sub.addWidget(lbl_font)
        r_sub.addWidget(self.txt_font)
        r_sub.addSpacing(16)
        r_sub.addWidget(self.btn_sub_preview)
        r_sub.addStretch()
        gv.addLayout(r_sub)

        r2 = QHBoxLayout()
        self.lbl_output_dir = QLabel(tr('output_dir'))
        self.txt_dir = QLineEdit(str(Path.home() / "Downloads"))
        self.btn_dir = QPushButton(tr('browse'))
        self.btn_dir.clicked.connect(self._browse_dir)
        r2.addWidget(self.lbl_output_dir)
        r2.addWidget(self.txt_dir)
        r2.addWidget(self.btn_dir)
        gv.addLayout(r2)
        vbox.addWidget(self.grp_output)

        # ── 実行行 ────────────────────────────────────
        exec_row = QHBoxLayout()
        self.btn_exec   = QPushButton(tr('execute'))
        self.btn_cancel = QPushButton(tr('cancel'))
        f = self.btn_exec.font()
        f.setPointSize(13)
        self.btn_exec.setFont(f)
        self.btn_cancel.setEnabled(False)
        self.btn_exec.clicked.connect(self._execute)
        self.btn_cancel.clicked.connect(self._cancel)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        exec_row.addWidget(self.btn_exec)
        exec_row.addWidget(self.btn_cancel)
        exec_row.addWidget(self.progress, stretch=1)
        vbox.addLayout(exec_row)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(90)
        vbox.addWidget(self.log)

    # ── 言語切り替え ──────────────────────────────────

    def _open_batch(self):
        dlg = BatchDialog(
            self,
            model=self.cmb_model.currentText().lstrip('★ '),
            language=self.cmb_lang.currentText(),
            mark_silence=self.chk_mark_silence.isChecked(),
            silence_sec=self.spn_silence.value(),
        )
        dlg.exec()

    def _open_donate(self):
        import urllib.parse as up
        if _lang == 'en':
            to   = "jbzkeiri1@jimu.kyushu-u.ac.jp"
            subj = "Donation request for Reiji Sasaki (Kyushu University)"
            body = (
                "Dear Accounting Division,\n\n"
                "I would like to make a donation in support of the research activities "
                "of Reiji Sasaki (Graduate School of Human-Environment Studies, "
                "Clinical Psychology).\n\n"
                "Could you please provide me with the necessary information and "
                "procedures to complete the donation?\n\n"
                "Thank you very much.\n\n"
                "---\n"
                "Name:\n"
                "Email:\n"
                "Donation amount (JPY):\n"
            )
            mailto = f"mailto:{to}?subject={up.quote(subj)}&body={up.quote(body).replace('%0A','%0D%0A')}"
            QDesktopServices.openUrl(QUrl(mailto))
        else:
            QDesktopServices.openUrl(QUrl("https://donate.sasakireijiyagi.com/"))

    def _toggle_lang(self):
        global _lang
        _lang = 'en' if _lang == 'ja' else 'ja'
        self.retranslate()

    def retranslate(self):
        self.setWindowTitle(tr('window_title'))
        self.btn_video.setText(tr('open_video'))
        self.btn_srt.setText(tr('open_srt'))
        self.btn_save_srt.setText(tr('save_srt'))
        self.btn_save_srt.setToolTip(tr('save_srt_tip'))
        self.btn_lang.setText(tr('lang_toggle'))
        self.btn_donate.setText(tr('donate'))
        self.btn_donate.setToolTip(tr('donate_tip'))
        self.lbl_transcribe.setText(tr('transcribe_label'))
        self.lbl_model.setText(tr('model_label'))
        self.lbl_lang.setText(tr('lang_label'))
        self.cmb_model.setToolTip(tr('model_tip'))
        self.cmb_lang.setToolTip(tr('lang_tip'))
        self.btn_transcribe.setText(tr('transcribe_btn'))
        self.btn_transcribe_cancel.setText(tr('transcribe_cancel'))
        self.btn_batch.setText('📂 バッチ文字起こし' if _lang == 'ja' else '📂 Batch Transcription')
        self.chk_mark_silence.setText(tr('mark_silence'))
        self.chk_mark_silence.setToolTip(tr('mark_silence_tip'))
        self.spn_silence.setSuffix(tr('silence_suffix'))
        self.spn_silence.setToolTip(tr('silence_tip'))
        self.grp_output.setTitle(tr('output_group'))
        self.rb_combine.setText(tr('combine'))
        self.rb_separate.setText(tr('separate'))
        self.chk_reencode.setText(tr('reencode'))
        self.lbl_output_dir.setText(tr('output_dir'))
        self.btn_dir.setText(tr('browse'))
        self.btn_exec.setText(tr('execute'))
        self.btn_cancel.setText(tr('cancel'))
        # 動画・SRTラベルは現在のファイル名を保持
        if self.video_path:
            self.lbl_video.setText(tr('video_label').format(name=Path(self.video_path).name))
        else:
            self.lbl_video.setText(tr('video_none'))
        if self.srt_path:
            self.lbl_srt.setText(tr('srt_label').format(name=Path(self.srt_path).name))
        else:
            self.lbl_srt.setText(tr('srt_none'))
        # サブウィジェット
        self.player.retranslate()
        self.srt_tbl.retranslate()
        # メニュー再構築
        self.menuBar().clear()
        self._build_menu()

    # ── スロット ──────────────────────────────────────

    @staticmethod
    def _probe_size(path: str):
        """ffprobeで (width, height) を返す。失敗時は (0, 0)。"""
        ffprobe = shutil.which('ffprobe') or FFMPEG_BIN.replace('ffmpeg', 'ffprobe')
        try:
            r = subprocess.run(
                [ffprobe, '-v', 'error', '-select_streams', 'v:0',
                 '-show_entries', 'stream=width,height',
                 '-of', 'csv=s=x:p=0', path],
                capture_output=True, text=True, timeout=10)
            w, h = r.stdout.strip().split('x')
            return int(w), int(h)
        except Exception:
            return 0, 0

    def _open_video(self):
        path, _ = QFileDialog.getOpenFileName(
            self, tr('dlg_open_video'),
            str(Path.home() / "Downloads"),
            tr('dlg_video_filter'))
        if not path:
            return
        self.video_path = path
        self.srt_path   = None
        self.lbl_video.setText(tr('video_label').format(name=Path(path).name))
        self.lbl_srt.setText(tr('srt_none'))
        self.srt_tbl.load([])
        self.btn_save_srt.setEnabled(False)
        self.player.load(path)
        self.btn_transcribe.setEnabled(True)
        self.btn_close_video.setEnabled(True)
        self.btn_export_eaf.setEnabled(True)

        # 縦動画判定 → レイアウト・フォントサイズを自動調整
        w, h = self._probe_size(path)
        is_vertical = h > w > 0
        if is_vertical:
            self.spl.setOrientation(Qt.Orientation.Vertical)
            self.spl.setSizes([400, 400])
            self.spn_font_size.setValue(36)
            self.log.append('縦動画を検出: レイアウトを縦並びに変更' if _lang == 'ja'
                            else 'Vertical video detected: switched to vertical layout')
        else:
            self.spl.setOrientation(Qt.Orientation.Horizontal)
            self.spl.setSizes([500, 600])
            self.spn_font_size.setValue(40)

        for ext in ('.srt', '.SRT'):
            candidate = Path(path).with_suffix(ext)
            if candidate.exists():
                self._load_srt(str(candidate))
                break

    def _open_srt(self):
        start = (str(Path(self.video_path).parent)
                 if self.video_path else str(Path.home()))
        path, _ = QFileDialog.getOpenFileName(
            self, tr('dlg_open_srt'), start, tr('dlg_srt_filter'))
        if path:
            self._load_srt(path)

    def _load_srt(self, path: str):
        try:
            text = Path(path).read_text(encoding='utf-8-sig')
        except Exception as exc:
            QMessageBox.critical(self, tr('err_title'), f"SRT error:\n{exc}")
            return
        entries = parse_srt(text)
        self.srt_tbl.load(entries)
        self.srt_path = path
        self.lbl_srt.setText(tr('srt_label').format(name=Path(path).name))
        self.btn_save_srt.setEnabled(True)
        self.log.append(tr('log_srt_loaded').format(n=len(entries), path=path))

    def _save_srt(self):
        path = self.srt_path
        if not path:
            path, _ = QFileDialog.getSaveFileName(
                self, tr('dlg_save_srt'), str(Path.home()), tr('dlg_srt_filter'))
            if not path:
                return
            self.srt_path = path

        lines = []
        for e in self.srt_tbl.entries:
            lines.append(str(e.index))
            lines.append(f"{_ms_to_srt(e.start_ms)} --> {_ms_to_srt(e.end_ms)}")
            lines.append(e.text)
            lines.append('')

        try:
            Path(path).write_text('\n'.join(lines), encoding='utf-8')
        except Exception as exc:
            QMessageBox.critical(self, tr('err_title'), f"Save failed:\n{exc}")
            return

        self.lbl_srt.setText(tr('srt_label').format(name=Path(path).name))
        self.log.append(tr('log_srt_saved').format(path=path))

    def _on_row(self, row: int):
        if row < len(self.srt_tbl.entries):
            self.player.play_segment(self.srt_tbl.entries[row])

    def _preview_subtitle(self):
        if not self.video_path:
            QMessageBox.warning(self, tr('err_title'), tr('err_no_video'))
            return
        row = self.srt_tbl.tbl.currentRow()
        entries = self.srt_tbl.entries
        if row < 0 or row >= len(entries):
            QMessageBox.warning(self, tr('err_title'),
                '行を選択してください' if _lang == 'ja' else 'Please select a row.')
            return
        if not _ffmpeg_has_subtitles():
            QMessageBox.warning(
                self,
                '字幕焼き込み非対応のffmpeg' if _lang == 'ja' else 'ffmpeg without subtitle support',
                _subtitle_unavailable_msg())
            return
        entry = entries[row]
        import tempfile
        outdir = tempfile.mkdtemp()
        preview_out = os.path.join(outdir, 'subtitle_preview.mp4')
        seg_srt     = os.path.join(outdir, 'preview.srt')
        seg_dur     = entry.end_ms - entry.start_ms
        with open(seg_srt, 'w', encoding='utf-8') as f:
            f.write(f"1\n{_ms_to_srt(0)} --> {_ms_to_srt(seg_dur)}\n{entry.text}\n\n")

        worker = FFmpegWorker(
            [entry], self.video_path, outdir,
            combine=False, reencode=False,
            subtitle_burn=True, font_size=self.spn_font_size.value(),
            font_name=self.txt_font.text(),
        )
        vf  = worker._subtitle_vf(seg_srt)
        start = _ms_to_ffmpeg(entry.start_ms)
        dur   = _ms_to_ffmpeg(seg_dur)
        cmd = [FFMPEG_BIN, '-y',
               '-ss', start, '-i', self.video_path,
               '-t', dur, '-avoid_negative_ts', 'make_zero',
               '-vf', vf,
               '-c:v', 'libx264', '-preset', 'fast', '-c:a', 'aac',
               preview_out]
        self.log.append('プレビュー生成中…' if _lang == 'ja' else 'Generating preview…')
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            self.log.append(f"ERROR: {proc.stderr[-300:]}")
            return
        # プレビューをデフォルトアプリで開く
        if sys.platform == 'darwin':
            subprocess.Popen(['open', preview_out])
        elif sys.platform == 'win32':
            os.startfile(preview_out)
        else:
            subprocess.Popen(['xdg-open', preview_out])
        self.log.append(f"{'Preview:' if _lang=='en' else 'プレビュー:'} {preview_out}")

    def _export_eaf(self):
        if not self.video_path:
            QMessageBox.warning(self, tr('err_title'), tr('err_no_video'))
            return
        entries = self.srt_tbl.entries
        if not entries:
            QMessageBox.warning(self, tr('err_title'),
                'SRTが読み込まれていません' if _lang == 'ja' else 'No SRT loaded.')
            return

        # ティア名（発話者名）を入力
        from PyQt6.QtWidgets import QInputDialog
        tier, ok = QInputDialog.getText(
            self,
            'EAF書き出し' if _lang == 'ja' else 'Export EAF',
            'ティア名（発話者名など）:' if _lang == 'ja' else 'Tier name (e.g. speaker name):',
            text='発話' if _lang == 'ja' else 'utterance'
        )
        if not ok:
            return
        tier = tier.strip() or ('発話' if _lang == 'ja' else 'utterance')

        # 保存先を選択
        default = str(Path(self.video_path).with_suffix('.eaf'))
        path, _ = QFileDialog.getSaveFileName(
            self,
            'EAFファイルを保存' if _lang == 'ja' else 'Save EAF file',
            default, 'ELAN EAF (*.eaf);;すべて (*)')
        if not path:
            return

        try:
            eaf_text = _make_eaf(entries, self.video_path, tier)
            Path(path).write_text(eaf_text, encoding='utf-8')
            self.log.append(f"{'EAF書き出し完了' if _lang == 'ja' else 'EAF exported'}: {path}")
        except Exception as exc:
            QMessageBox.critical(self, tr('err_title'), str(exc))

    def _reset(self):
        self.video_path = None
        self.srt_path   = None
        self.player.player.stop()
        self.player.load('')
        self.srt_tbl.load([])
        self.lbl_video.setText(tr('video_none'))
        self.lbl_srt.setText(tr('srt_none'))
        self.btn_save_srt.setEnabled(False)
        self.btn_export_eaf.setEnabled(False)
        self.btn_close_video.setEnabled(False)
        self.btn_transcribe.setEnabled(False)
        self.log.append('--- ' + ('リセットしました' if _lang == 'ja' else 'Reset.') + ' ---')

    def _browse_dir(self):
        d = QFileDialog.getExistingDirectory(
            self, tr('dlg_output_dir'), self.txt_dir.text())
        if d:
            self.txt_dir.setText(d)

    def _execute(self):
        if not self.video_path:
            QMessageBox.warning(self, tr('err_title'), tr('err_no_video'))
            return
        entries = self.srt_tbl.entries
        count = sum(1 for e in entries if e.checked)
        if count == 0:
            QMessageBox.warning(self, tr('err_title'), tr('err_no_segments'))
            return

        self.progress.setRange(0, count)
        self.progress.setValue(0)
        self.progress.setVisible(True)

        self.worker = FFmpegWorker(
            entries,
            self.video_path,
            self.txt_dir.text(),
            self.rb_combine.isChecked(),
            self.chk_reencode.isChecked(),
            subtitle_burn=self.chk_burn_sub.isChecked(),
            font_size=self.spn_font_size.value(),
            font_name=self.txt_font.text(),
        )
        self.worker.progress.connect(self.progress.setValue)
        self.worker.log.connect(self.log.append)
        self.worker.done.connect(self._on_done)
        self.btn_exec.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.worker.start()

    def _populate_models(self):
        cache_dir = Path.home() / '.cache' / 'whisper'
        cached = set()
        if cache_dir.is_dir():
            cached = {p.stem for p in cache_dir.glob('*.pt')}

        all_models = [
            'large-v3', 'large-v3-turbo', 'turbo',
            'medium', 'small', 'base', 'tiny',
            'large-v2', 'large-v1',
        ]
        default_idx = 0
        for i, m in enumerate(all_models):
            label = f'★ {m}' if m in cached else m
            self.cmb_model.addItem(label)
            if m in cached and default_idx == 0:
                default_idx = i
        self.cmb_model.setCurrentIndex(default_idx)

    def _transcribe(self):
        model = self.cmb_model.currentText().lstrip('★ ')
        lang  = _LANG_MAP.get(self.cmb_lang.currentText(), 'ja')

        self.whisper_worker = WhisperWorker(
            self.video_path, model, lang,
            mark_silence=self.chk_mark_silence.isChecked(),
            silence_sec=self.spn_silence.value(),
        )
        self.whisper_worker.log.connect(self.log.append)
        self.whisper_worker.done.connect(self._on_transcription_done)

        self.btn_transcribe.setEnabled(False)
        self.btn_transcribe_cancel.setEnabled(True)
        self.btn_exec.setEnabled(False)
        self.log.append(tr('log_transcribe_start').format(name=Path(self.video_path).name))
        self.whisper_worker.start()

    def _cancel_transcribe(self):
        if self.whisper_worker:
            self.whisper_worker.cancel()
        self.btn_transcribe_cancel.setEnabled(False)

    def _on_transcription_done(self, ok: bool, result: str):
        self.btn_transcribe.setEnabled(True)
        self.btn_transcribe_cancel.setEnabled(False)
        self.btn_exec.setEnabled(True)
        if ok:
            self.log.append(tr('log_transcribe_done').format(path=result))
            self._load_srt(result)
        else:
            self.log.append(f"Whisper error: {result}")
            QMessageBox.warning(self, "Whisper", result)

    def _cancel(self):
        if self.worker:
            self.worker.cancel()

    def _on_done(self, ok: bool, msg: str):
        self.btn_exec.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.progress.setVisible(False)
        self.log.append(msg)
        fn = QMessageBox.information if ok else QMessageBox.warning
        fn(self, tr('done_title') if ok else tr('err_title'), msg)

    def _build_menu(self):
        file_menu = self.menuBar().addMenu('ファイル' if _lang == 'ja' else 'File')
        open_action = file_menu.addAction('動画を開く…' if _lang == 'ja' else 'Open Video…')
        open_action.triggered.connect(self._open_video)
        close_action = file_menu.addAction('動画を閉じる' if _lang == 'ja' else 'Close Video')
        close_action.triggered.connect(self._reset)

        help_menu = self.menuBar().addMenu(tr('menu_help'))
        usage_action = help_menu.addAction('使い方を見る' if _lang == 'ja' else 'How to use')
        usage_action.triggered.connect(lambda: QDesktopServices.openUrl(
            QUrl('https://github.com/sasakireijiyagi/video-cut-editor#readme')))
        help_menu.addSeparator()
        about_action = help_menu.addAction(tr('menu_about'))
        about_action.triggered.connect(self._show_about)

    def _show_about(self):
        dlg = QDialog(self)
        dlg.setWindowTitle(tr('about_title'))
        dlg.setMinimumWidth(400)
        layout = QVBoxLayout(dlg)
        layout.setSpacing(12)

        brand = QLabel("<p style='text-align:center; font-size:22px;'>ヤギ製作所</p>")
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(brand)

        title = QLabel("<h2>おまかせ文字起こし</h2>")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        info = QLabel(
            "<p style='text-align:center;'>"
            "Reiji Sasaki<br>"
            "九州大学大学院 臨床心理学講座<br>"
            "Kyushu University, Clinical Psychology"
            "</p>"
        )
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info)

        star_lbl = QLabel(
            "<p style='text-align:center; font-size:13px;'>"
            "役に立ったら "
            "<a href='https://github.com/sasakireijiyagi/video-cut-editor'>⭐ Star</a>"
            " をつけてもらえると励みになります！"
            "</p>"
        )
        star_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        star_lbl.setOpenExternalLinks(True)
        layout.addWidget(star_lbl)

        links = QLabel(
            "<p style='text-align:center;'>"
            "<a href='https://sasakireijiyagi.github.io/video-cut-editor/'>ダウンロードページ</a>"
            "　｜　"
            "<a href='https://github.com/sasakireijiyagi/video-cut-editor'>GitHub</a>"
            "　｜　"
            "<a href='https://github.com/sasakireijiyagi/video-cut-editor/issues'>💬 感想・バグ報告</a>"
            "　｜　"
            f"<a href='https://donate.sasakireijiyagi.com/'>{tr('about_donate_link')}</a>"
            "</p>"
        )
        links.setAlignment(Qt.AlignmentFlag.AlignCenter)
        links.setOpenExternalLinks(True)
        layout.addWidget(links)

        # バージョン表示 & アップデート
        from PyQt6.QtWidgets import QProgressBar
        ver_lbl = QLabel(f"<p style='text-align:center; color:#888; font-size:11px;'>v{APP_VERSION}</p>")
        ver_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(ver_lbl)

        progress_bar = QProgressBar()
        progress_bar.setRange(0, 100)
        progress_bar.setTextVisible(True)
        progress_bar.hide()
        layout.addWidget(progress_bar)

        check_btn = QPushButton("アップデートを確認")
        check_btn.setFixedWidth(180)
        check_btn_wrap = QWidget()
        check_btn_layout = QHBoxLayout(check_btn_wrap)
        check_btn_layout.setContentsMargins(0, 0, 0, 0)
        check_btn_layout.addStretch()
        check_btn_layout.addWidget(check_btn)
        check_btn_layout.addStretch()
        layout.addWidget(check_btn_wrap)

        def _do_update(dmg_url, new_tag):
            """ダウンロード→インストール"""
            check_btn.hide()
            progress_bar.show()
            progress_bar.setValue(0)

            worker = UpdateDownloadWorker(dmg_url)
            worker.progress.connect(progress_bar.setValue)

            def _on_finished(new_path):
                import subprocess, os
                progress_bar.hide()
                ver_lbl.setText(
                    "<p style='text-align:center; color:#2a8a55; font-size:11px;'>"
                    "インストール完了！再起動します…</p>"
                )
                if sys.platform == "darwin":
                    # Mac: シェルスクリプトで _new.app に差し替えて再起動
                    current_app = new_path.replace("_new.app", ".app")
                    script = (
                        f'#!/bin/bash\n'
                        f'sleep 1\n'
                        f'rm -rf "{current_app}"\n'
                        f'mv "{new_path}" "{current_app}"\n'
                        f'open "{current_app}"\n'
                    )
                    script_path = "/tmp/easytranscribe_update.sh"
                    with open(script_path, "w") as f:
                        f.write(script)
                    os.chmod(script_path, 0o755)
                    subprocess.Popen(["bash", script_path])
                else:
                    # Windows: バッチファイルで _new フォルダに差し替えて再起動
                    current_dir = new_path.replace("_new", "")
                    exe_name = "EasyTranscribe.exe"
                    new_exe = os.path.join(new_path, exe_name)
                    script = (
                        f'@echo off\n'
                        f'timeout /t 2 /nobreak >nul\n'
                        f'rmdir /s /q "{current_dir}"\n'
                        f'move "{new_path}" "{current_dir}"\n'
                        f'start "" "{os.path.join(current_dir, exe_name)}"\n'
                    )
                    script_path = os.path.join(os.environ.get("TEMP", "C:\\Temp"),
                                               "easytranscribe_update.bat")
                    with open(script_path, "w") as f:
                        f.write(script)
                    subprocess.Popen(["cmd", "/c", script_path],
                                     creationflags=subprocess.CREATE_NO_WINDOW
                                     if hasattr(subprocess, "CREATE_NO_WINDOW") else 0)
                QApplication.quit()

            def _on_error(msg):
                progress_bar.hide()
                ver_lbl.setText(
                    f"<p style='text-align:center; color:#e63946; font-size:11px;'>"
                    f"失敗: {msg}</p>"
                )
                check_btn.show()

            worker.finished.connect(_on_finished)
            worker.error.connect(_on_error)
            dlg._update_worker = worker
            worker.start()

        def _check_version():
            check_btn.setEnabled(False)
            check_btn.setText("確認中…")
            worker = VersionCheckWorker()

            def _on_result(tag, url, dmg_url):
                latest = tag.lstrip("v")
                if latest and latest > APP_VERSION:
                    ver_lbl.setText(
                        f"<p style='text-align:center; color:#e63946; font-size:11px;'>"
                        f"v{latest} が利用可能！</p>"
                    )
                    if dmg_url:
                        check_btn.setText(f"v{latest} にアップデート")
                        check_btn.setEnabled(True)
                        check_btn.clicked.disconnect()
                        check_btn.clicked.connect(lambda: _do_update(dmg_url, latest))
                    else:
                        ver_lbl.setOpenExternalLinks(True)
                        ver_lbl.setText(
                            f"<p style='text-align:center; color:#e63946; font-size:11px;'>"
                            f"<a href='{url}'>v{latest} をダウンロード</a></p>"
                        )
                        check_btn.hide()
                else:
                    ver_lbl.setText(
                        f"<p style='text-align:center; color:#2a8a55; font-size:11px;'>"
                        f"v{APP_VERSION}（最新です）</p>"
                    )
                    check_btn.hide()

            def _on_error(msg):
                ver_lbl.setText(
                    "<p style='text-align:center; color:#888; font-size:11px;'>確認に失敗しました</p>"
                )
                check_btn.setEnabled(True)
                check_btn.setText("アップデートを確認")

            worker.result.connect(_on_result)
            worker.error.connect(_on_error)
            dlg._ver_worker = worker
            worker.start()

        check_btn.clicked.connect(_check_version)

        btn = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        btn.accepted.connect(dlg.accept)
        layout.addWidget(btn)

        dlg.exec()


# ──────────────────────────────────────────────────────────────────
# Splash screen
# ──────────────────────────────────────────────────────────────────

class SplashScreen(QWidget):
    finished = pyqtSignal()

    def __init__(self, font_id: int):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.SplashScreen |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(640, 380)

        # 中央に配置
        screen = QApplication.primaryScreen().geometry()
        self.move((screen.width() - 640) // 2, (screen.height() - 380) // 2)

        # フォント設定
        if font_id >= 0:
            families = QFontDatabase.applicationFontFamilies(font_id)
            self._font_family = families[0] if families else 'Hiragino Mincho ProN'
        else:
            self._font_family = 'Hiragino Mincho ProN'

        # フェードエフェクト
        self._effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._effect)
        self._effect.setOpacity(0.0)

        # フェードイン → 保持 → フェードアウト
        self._anim_in = QPropertyAnimation(self._effect, b'opacity')
        self._anim_in.setDuration(800)
        self._anim_in.setStartValue(0.0)
        self._anim_in.setEndValue(1.0)
        self._anim_in.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._anim_in.finished.connect(self._hold)

        self._anim_out = QPropertyAnimation(self._effect, b'opacity')
        self._anim_out.setDuration(800)
        self._anim_out.setStartValue(1.0)
        self._anim_out.setEndValue(0.0)
        self._anim_out.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._anim_out.finished.connect(self._done)

    def start(self):
        self.show()
        self._anim_in.start()

    def _hold(self):
        QTimer.singleShot(1500, self._anim_out.start)

    def _done(self):
        self.close()
        self.finished.emit()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 背景：白・角丸
        painter.setBrush(QColor('#ffffff'))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), 12, 12)

        # ヤギ製作所
        f1 = QFont(self._font_family, 72)
        painter.setFont(f1)
        painter.setPen(QColor('#2c2c2c'))
        painter.drawText(self.rect().adjusted(0, -40, 0, 0),
                         Qt.AlignmentFlag.AlignCenter, 'ヤギ製作所')

        # 佐々木玲仁研究室
        f2 = QFont(self._font_family, 18)
        painter.setFont(f2)
        painter.setPen(QColor('#555555'))
        painter.drawText(self.rect().adjusted(0, 140, 0, 0),
                         Qt.AlignmentFlag.AlignCenter, '佐々木玲仁研究室')


# ──────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("おまかせ文字起こし")

    # Klee One フォントを読み込む
    font_path = str(Path(__file__).parent / 'fonts' / 'HinaMincho-Regular.ttf')
    font_id = QFontDatabase.addApplicationFont(font_path)

    # スプラッシュ画面
    splash = SplashScreen(font_id)
    win    = MainWindow()

    def _show_main():
        win.show()

    def _after_splash():
        missing_ffmpeg  = not _is_ffmpeg_ok()
        missing_whisper = not _is_whisper_ok()
        if missing_ffmpeg or missing_whisper:
            dlg = SetupDialog(missing_ffmpeg, missing_whisper)
            dlg.exec()
        _show_main()

    splash.finished.connect(_after_splash)
    splash.start()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
