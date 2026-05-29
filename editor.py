#!/usr/bin/env python3
"""
Video Cut Editor  —  SRT + 動画を読み込んでffmpegでカット出力
"""

import sys
import os
import shutil

# PyQt6 プラグインパスをインポート前に解決（conda 環境対応）
def _find_pyqt6_plugins() -> str:
    import glob
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
    QLabel, QFileDialog, QLineEdit, QRadioButton, QGroupBox,
    QProgressBar, QTextEdit, QHeaderView, QAbstractItemView,
    QSlider, QSizePolicy, QMessageBox, QComboBox, QDoubleSpinBox,
)
from PyQt6.QtCore import Qt, QUrl, pyqtSignal, QThread
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget


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
    """HH:MM:SS.mmm  (for -ss / -t)"""
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

class FFmpegWorker(QThread):
    progress = pyqtSignal(int)        # 完了セグメント数
    log      = pyqtSignal(str)
    done     = pyqtSignal(bool, str)  # (成功, メッセージ)

    def __init__(self, entries: List[SRTEntry], video: str,
                 outdir: str, combine: bool, reencode: bool):
        super().__init__()
        self.entries  = entries
        self.video    = video
        self.outdir   = outdir
        self.combine  = combine
        self.reencode = reencode
        self._stop    = False

    def cancel(self):
        self._stop = True

    def run(self):
        checked = [e for e in self.entries if e.checked]
        if not checked:
            self.done.emit(False, "選択されたセグメントがありません")
            return

        # 同一インデックスの重複を除去
        seen = set()
        deduped = []
        for e in checked:
            if e.index not in seen:
                seen.add(e.index)
                deduped.append(e)
        if len(deduped) != len(checked):
            self.log.emit(f"  重複エントリを除去: {len(checked)} → {len(deduped)} 件")
        checked = deduped

        self.log.emit(f"  カット対象: {len(checked)} セグメント")
        os.makedirs(self.outdir, exist_ok=True)
        stem = Path(self.video).stem

        codec = (['-c:v', 'libx264', '-preset', 'fast', '-c:a', 'aac']
                 if self.reencode else ['-c', 'copy'])

        segs: List[str] = []
        for i, entry in enumerate(checked):
            if self._stop:
                self.done.emit(False, "キャンセルされました")
                return

            start  = _ms_to_ffmpeg(entry.start_ms)
            dur    = _ms_to_ffmpeg(entry.end_ms - entry.start_ms)
            out    = os.path.join(self.outdir, f"{stem}_{entry.index:04d}.mp4")

            cmd = [FFMPEG_BIN, '-y',
                   '-ss', start, '-i', self.video,
                   '-t', dur,
                   '-avoid_negative_ts', 'make_zero',
                   *codec, out]

            self.log.emit(f"[{i+1}/{len(checked)}] seg {entry.index}  {start} + {dur}")
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode != 0:
                self.log.emit(f"  ERROR: {proc.stderr[-400:]}")
                self.done.emit(False, f"セグメント {entry.index} でエラーが発生しました")
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
            self.log.emit("結合中...")
            proc = subprocess.run(cmd, capture_output=True, text=True)
            os.remove(listfile)
            for p in segs:
                try:
                    os.remove(p)
                except OSError:
                    pass

            if proc.returncode != 0:
                self.log.emit(f"  ERROR: {proc.stderr[-400:]}")
                self.done.emit(False, "結合に失敗しました")
                return

            self.done.emit(True, f"完了: {final}")
        else:
            self.done.emit(True, f"完了: {len(segs)} ファイルを {self.outdir} に保存しました")


# ──────────────────────────────────────────────────────────────────
# Whisper worker
# ──────────────────────────────────────────────────────────────────

def _find_ffmpeg() -> str:
    for p in ['/usr/local/bin/ffmpeg', '/opt/homebrew/bin/ffmpeg']:
        if os.path.isfile(p):
            return p
    return shutil.which('ffmpeg') or 'ffmpeg'

def _find_whisper() -> str:
    w = shutil.which('whisper')
    if w:
        return w
    for base in ['/opt/anaconda3', '/opt/miniconda3',
                 os.path.expanduser('~/anaconda3'),
                 os.path.expanduser('~/miniconda3'),
                 os.path.expanduser('~/miniforge3'),
                 os.path.expanduser('~/mambaforge')]:
        hits = sorted(Path(base).glob('envs/*/bin/whisper'))
        if hits:
            return str(hits[0])
        w_base = Path(base) / 'bin' / 'whisper'
        if w_base.exists():
            return str(w_base)
    return 'whisper'

FFMPEG_BIN  = _find_ffmpeg()
WHISPER_BIN = _find_whisper()

_LANG_MAP = {
    '日本語': 'ja',
    'English': 'en',
    '中文': 'zh',
    '한국어': 'ko',
    '自動検出': 'auto',
}

class WhisperWorker(QThread):
    log  = pyqtSignal(str)
    done = pyqtSignal(bool, str)  # (成功, SRTパス or エラーメッセージ)

    def __init__(self, video: str, model: str, language: str,
                 mark_silence: bool = False, silence_sec: float = 1.0):
        super().__init__()
        self.video         = video
        self.model         = model
        self.language      = language
        self.mark_silence  = mark_silence
        self.silence_ms    = int(silence_sec * 1000)
        self._proc         = None

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

        self.log.emit(f"Whisper 開始: model={self.model}  lang={self.language}")

        # whisper が内部で ffmpeg を呼ぶので PATH に追加しておく
        env = os.environ.copy()
        env['PATH'] = '/usr/local/bin:' + env.get('PATH', '')

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
            self.done.emit(False, f"whisper がエラーで終了しました (code {self._proc.returncode})")
            return

        # 出力SRTを探す
        stem = Path(self.video).stem
        outdir_path = Path(outdir)
        self.log.emit(f"  SRTを探しています: {outdir_path / (stem + '.srt')}")

        # 1. 期待パスで探す
        srt = outdir_path / (stem + '.srt')
        # 2. glob で拾う（whisper がファイル名を変える場合に備えて）
        if not srt.exists():
            hits = sorted(outdir_path.glob('*.srt'), key=lambda p: p.stat().st_mtime, reverse=True)
            self.log.emit(f"  glob結果: {[str(p) for p in hits]}")
            srt = hits[0] if hits else srt

        if not srt.exists():
            self.done.emit(False, f"SRTが見つかりませんでした: {srt}")
            return

        # ── [間] 挿入後処理 ──────────────────────────────
        if self.mark_silence:
            entries = parse_srt(srt.read_text(encoding='utf-8-sig'))
            new_entries = []
            for i, entry in enumerate(entries):
                new_entries.append(entry)
                if i + 1 < len(entries):
                    gap_ms = entries[i + 1].start_ms - entry.end_ms
                    if gap_ms >= self.silence_ms:
                        new_entries.append(SRTEntry(
                            index=0,
                            start_ms=entry.end_ms,
                            end_ms=entries[i + 1].start_ms,
                            text=f'[間  {gap_ms / 1000:.1f}秒]',
                        ))
            # 連番振り直し
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
            self.log.emit(f"  [間] を {inserted} 箇所挿入しました（{self.silence_ms/1000:.1f}秒以上）")

        self.done.emit(True, str(srt))


# ──────────────────────────────────────────────────────────────────
# SRT table widget
# ──────────────────────────────────────────────────────────────────

class SRTTable(QWidget):
    row_activated = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.entries: List[SRTEntry] = []
        self._build()

    def _build(self):
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(0, 0, 0, 0)

        bar = QHBoxLayout()
        btn_all  = QPushButton("全選択")
        btn_none = QPushButton("全解除")
        self.lbl_count = QLabel("0 / 0 件選択")
        btn_all.clicked.connect(self._all)
        btn_none.clicked.connect(self._none)
        bar.addWidget(btn_all)
        bar.addWidget(btn_none)
        bar.addStretch()
        bar.addWidget(self.lbl_count)
        vbox.addLayout(bar)

        self.tbl = QTableWidget(0, 4)
        self.tbl.setHorizontalHeaderLabels(['✓', '開始', '終了', 'テキスト'])
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
        vbox.addWidget(self.tbl)

    # public API ───────────────────────────────

    def load(self, entries: List[SRTEntry]):
        self.entries = entries
        self._repopulate()

    # private ──────────────────────────────────

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
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
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
        elif item.column() == 3:
            self.entries[row].text = item.text()

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

    def _update_count(self):
        total        = len(self.entries)
        checked      = sum(1 for e in self.entries if e.checked)
        duration_ms  = sum(e.end_ms - e.start_ms for e in self.entries if e.checked)
        h, r  = divmod(duration_ms, 3_600_000)
        mi, r = divmod(r, 60_000)
        s     = r // 1_000
        dur_str = f"{h:02d}:{mi:02d}:{s:02d}" if h else f"{mi:02d}:{s:02d}"
        self.lbl_count.setText(f"{checked} / {total} 件  |  合計 {dur_str}")


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
        self.video_widget.setMinimumSize(400, 280)
        self.video_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        vbox.addWidget(self.video_widget)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.sliderMoved.connect(self._seek)
        vbox.addWidget(self.slider)

        self.lbl_time = QLabel("--:--:-- / --:--:--")
        self.lbl_time.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vbox.addWidget(self.lbl_time)

        bar = QHBoxLayout()
        self.btn_play  = QPushButton("▶ 再生")
        self.btn_pause = QPushButton("⏸ 一時停止")
        self.btn_stop  = QPushButton("⏹ 停止")
        self.btn_play.clicked.connect(self._play)
        self.btn_pause.clicked.connect(self._pause)
        self.btn_stop.clicked.connect(self._stop)
        for b in (self.btn_play, self.btn_pause, self.btn_stop):
            bar.addWidget(b)
        bar.addStretch()
        vbox.addLayout(bar)

        self.lbl_seg = QLabel("")
        self.lbl_seg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_seg.setWordWrap(True)
        self.lbl_seg.setStyleSheet("color: #555; font-size: 11px;")
        vbox.addWidget(self.lbl_seg)

    def _setup_player(self):
        self.player = QMediaPlayer()
        self.audio  = QAudioOutput()
        self.player.setAudioOutput(self.audio)
        self.player.setVideoOutput(self.video_widget)
        self.player.positionChanged.connect(self._on_pos)
        self.player.durationChanged.connect(self._on_dur)
        self.player.errorOccurred.connect(
            lambda _err, msg: self.lbl_seg.setText(f"プレーヤーエラー: {msg}"))

    # public API ───────────────────────────────

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

    # private ──────────────────────────────────

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
        self.setWindowTitle("Video Cut Editor")
        self.setMinimumSize(1100, 700)
        self._build()

    def _build(self):
        root = QWidget()
        self.setCentralWidget(root)
        vbox = QVBoxLayout(root)

        # ── ファイル選択バー ──────────────────────────
        bar = QHBoxLayout()
        self.btn_video = QPushButton("動画を開く…")
        self.btn_srt   = QPushButton("SRTを開く…")
        self.lbl_video = QLabel("動画: 未選択")
        self.lbl_srt   = QLabel("SRT: 未選択")
        self.btn_save_srt = QPushButton("SRT保存")
        self.btn_save_srt.setEnabled(False)
        self.btn_save_srt.setToolTip("編集内容をSRTファイルに上書き保存")
        self.btn_video.clicked.connect(self._open_video)
        self.btn_srt.clicked.connect(self._open_srt)
        self.btn_save_srt.clicked.connect(self._save_srt)
        for w in (self.btn_video, self.lbl_video, self.btn_srt, self.lbl_srt, self.btn_save_srt):
            bar.addWidget(w)
        bar.addStretch()
        vbox.addLayout(bar)

        # ── Whisper 文字起こし行 ──────────────────────
        w_bar = QHBoxLayout()
        w_bar.addWidget(QLabel("文字起こし:"))

        self.cmb_model = QComboBox()
        self.cmb_model.setMinimumWidth(180)
        self.cmb_model.setToolTip("Whisper モデル  ★=ローカル済み（すぐ使える）")
        self._populate_models()

        self.cmb_lang = QComboBox()
        self.cmb_lang.addItems(list(_LANG_MAP.keys()))
        self.cmb_lang.setToolTip("文字起こし言語")

        self.btn_transcribe = QPushButton("🎙 文字起こし実行")
        self.btn_transcribe.setEnabled(False)
        self.btn_transcribe.clicked.connect(self._transcribe)

        self.btn_transcribe_cancel = QPushButton("中止")
        self.btn_transcribe_cancel.setEnabled(False)
        self.btn_transcribe_cancel.clicked.connect(self._cancel_transcribe)

        self.chk_mark_silence = QCheckBox("[間]を記録")
        self.chk_mark_silence.setToolTip("発話間の無音区間をSRTに[間 X.X秒]として挿入する")

        self.spn_silence = QDoubleSpinBox()
        self.spn_silence.setRange(0.5, 10.0)
        self.spn_silence.setSingleStep(0.5)
        self.spn_silence.setValue(1.0)
        self.spn_silence.setSuffix(" 秒以上")
        self.spn_silence.setToolTip("この秒数以上の無音を[間]として記録する")

        w_bar.addWidget(QLabel("モデル:"))
        w_bar.addWidget(self.cmb_model)
        w_bar.addWidget(QLabel("  言語:"))
        w_bar.addWidget(self.cmb_lang)
        w_bar.addWidget(self.btn_transcribe)
        w_bar.addWidget(self.btn_transcribe_cancel)
        w_bar.addSpacing(16)
        w_bar.addWidget(self.chk_mark_silence)
        w_bar.addWidget(self.spn_silence)
        w_bar.addStretch()
        vbox.addLayout(w_bar)

        # ── スプリッター（SRTテーブル | ビデオプレーヤー） ──
        spl = QSplitter(Qt.Orientation.Horizontal)

        self.player = VideoPlayer()
        spl.addWidget(self.player)

        self.srt_tbl = SRTTable()
        self.srt_tbl.row_activated.connect(self._on_row)
        spl.addWidget(self.srt_tbl)

        spl.setSizes([500, 600])
        vbox.addWidget(spl, stretch=1)

        # ── 出力設定 ──────────────────────────────────
        grp = QGroupBox("出力設定")
        gv  = QVBoxLayout(grp)

        r1 = QHBoxLayout()
        self.rb_combine  = QRadioButton("1ファイルに結合")
        self.rb_separate = QRadioButton("行ごとに別ファイル")
        self.rb_combine.setChecked(True)
        self.chk_reencode = QCheckBox("再エンコード (libx264/aac) — 遅いが正確")
        r1.addWidget(self.rb_combine)
        r1.addWidget(self.rb_separate)
        r1.addSpacing(24)
        r1.addWidget(self.chk_reencode)
        r1.addStretch()
        gv.addLayout(r1)

        r2 = QHBoxLayout()
        r2.addWidget(QLabel("出力先:"))
        self.txt_dir = QLineEdit(str(Path.home() / "Downloads"))
        self.btn_dir = QPushButton("参照…")
        self.btn_dir.clicked.connect(self._browse_dir)
        r2.addWidget(self.txt_dir)
        r2.addWidget(self.btn_dir)
        gv.addLayout(r2)
        vbox.addWidget(grp)

        # ── 実行行 ────────────────────────────────────
        exec_row = QHBoxLayout()
        self.btn_exec   = QPushButton("▶  ffmpegカット実行")
        self.btn_cancel = QPushButton("キャンセル")
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

    # ── スロット ──────────────────────────────────────

    def _open_video(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "動画ファイルを選択",
            str(Path.home() / "Downloads"),
            "動画 (*.mp4 *.mov *.MOV *.avi *.mkv *.m4v *.webm);;すべて (*)")
        if not path:
            return
        self.video_path = path
        self.lbl_video.setText(f"動画: {Path(path).name}")
        self.player.load(path)
        self.btn_transcribe.setEnabled(True)
        # 同名 .srt を自動検出
        for ext in ('.srt', '.SRT'):
            candidate = Path(path).with_suffix(ext)
            if candidate.exists():
                self._load_srt(str(candidate))
                break

    def _open_srt(self):
        start = (str(Path(self.video_path).parent)
                 if self.video_path else str(Path.home()))
        path, _ = QFileDialog.getOpenFileName(
            self, "SRTファイルを選択", start, "SRT (*.srt);;すべて (*)")
        if path:
            self._load_srt(path)

    def _load_srt(self, path: str):
        try:
            text = Path(path).read_text(encoding='utf-8-sig')
        except Exception as exc:
            QMessageBox.critical(self, "エラー", f"SRT読み込みエラー:\n{exc}")
            return
        entries = parse_srt(text)
        self.srt_tbl.load(entries)
        self.srt_path = path
        self.lbl_srt.setText(f"SRT: {Path(path).name}")
        self.btn_save_srt.setEnabled(True)
        self.log.append(f"SRT読み込み完了: {len(entries)} セグメント — {path}")

    def _save_srt(self):
        path = self.srt_path
        if not path:
            path, _ = QFileDialog.getSaveFileName(
                self, "SRTファイルを保存", str(Path.home()), "SRT (*.srt)")
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
            QMessageBox.critical(self, "エラー", f"保存失敗:\n{exc}")
            return

        self.lbl_srt.setText(f"SRT: {Path(path).name}")
        self.log.append(f"SRT保存: {path}")

    def _on_row(self, row: int):
        if row < len(self.srt_tbl.entries):
            self.player.play_segment(self.srt_tbl.entries[row])

    def _browse_dir(self):
        d = QFileDialog.getExistingDirectory(
            self, "出力先ディレクトリを選択", self.txt_dir.text())
        if d:
            self.txt_dir.setText(d)

    def _execute(self):
        if not self.video_path:
            QMessageBox.warning(self, "エラー", "動画ファイルを開いてください")
            return
        entries = self.srt_tbl.entries
        count = sum(1 for e in entries if e.checked)
        if count == 0:
            QMessageBox.warning(self, "エラー", "1つ以上のセグメントを選択してください")
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
        self.log.append(f"--- 文字起こし開始: {Path(self.video_path).name} ---")
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
            self.log.append(f"--- 文字起こし完了 → {result} ---")
            self._load_srt(result)
        else:
            self.log.append(f"文字起こしエラー: {result}")
            QMessageBox.warning(self, "Whisper エラー", result)

    def _cancel(self):
        if self.worker:
            self.worker.cancel()

    def _on_done(self, ok: bool, msg: str):
        self.btn_exec.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.progress.setVisible(False)
        self.log.append(msg)
        fn = QMessageBox.information if ok else QMessageBox.warning
        fn(self, "完了" if ok else "エラー", msg)


# ──────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Video Cut Editor")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
