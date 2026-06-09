#!/usr/bin/env python3
"""
アプリのUIを widget.grab() で直接キャプチャするスクリプト。
ウィンドウが前面でなくても動作する。他のウィンドウと干渉しない。

使い方:
  python3 capture_screenshots.py

出力先: ~/tools/video_editor/promo_work/ss_*.png
"""

import sys
import os
import time

def _find_pyqt6_plugins():
    import glob
    patterns = [
        '/opt/anaconda3/lib/python3.*/site-packages/PyQt6/Qt6/plugins',
        '/opt/miniconda3/lib/python3.*/site-packages/PyQt6/Qt6/plugins',
        os.path.expanduser('~/anaconda3/lib/python3.*/site-packages/PyQt6/Qt6/plugins'),
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

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR  = os.path.join(BASE_DIR, 'promo_work')
os.makedirs(OUT_DIR, exist_ok=True)

DEMO_SRT_TEXT = """\
1
00:00:01,000 --> 00:00:03,500
えー、本日はお集まりいただきありがとうございます。

2
00:00:04,000 --> 00:00:06,800
あのー、まず最初に自己紹介をさせていただきます。

3
00:00:07,200 --> 00:00:10,000
私は九州大学のささきれいじと申します。

4
00:00:10,500 --> 00:00:13,200
えっと、今日は動画編集ツールについてお話しします。

5
00:00:14,000 --> 00:00:17,000
うーん、まず文字起こし機能からご説明します。

6
00:00:17,500 --> 00:00:20,500
このツールはwhisperを使って高精度な文字起こしができます。

7
00:00:21,000 --> 00:00:24,000
えー、モデルはtinyからlarge-v3まで選べます。

8
00:00:24,500 --> 00:00:27,500
あのー、フィラーカット機能も非常に便利です。
"""


def save(widget, name: str) -> str:
    path = os.path.join(OUT_DIR, name)
    pix = widget.grab()
    pix.save(path, 'PNG')
    print(f'  {name}  ({pix.width()}x{pix.height()})')
    return path


def pump(app, secs=0.3):
    """イベントループを回して描画を完了させる"""
    app.processEvents()
    time.sleep(secs)
    app.processEvents()


def run():
    app = QApplication(sys.argv)
    sys.path.insert(0, BASE_DIR)
    import editor as ed

    # ── メインウィンドウ（空の状態）──
    win = ed.MainWindow()
    win.resize(1400, 900)
    win.show()
    pump(app, 0.5)

    save(win, 'ss_main_empty.png')

    # ── デモSRTを読み込んでテーブルを埋める ──
    tmp_srt = os.path.join(OUT_DIR, '_demo.srt')
    with open(tmp_srt, 'w', encoding='utf-8') as f:
        f.write(DEMO_SRT_TEXT)

    entries = ed.parse_srt(DEMO_SRT_TEXT)
    win.srt_tbl.load(entries)
    pump(app, 0.3)

    # ── メインウィンドウ（SRT読み込み後）──
    save(win, 'ss_main.png')

    # ── SRTテーブル部分だけ ──
    save(win.srt_tbl, 'ss_table.png')

    # ── バッチダイアログ ──
    try:
        bdlg = ed.BatchDialog(parent=win)
        bdlg.resize(720, 540)
        bdlg.show()
        pump(app, 0.3)
        save(bdlg, 'ss_batch.png')
        bdlg.close()
    except Exception as e:
        print(f'  BatchDialog エラー: {e}')

    # ── フィラーカットダイアログ ──
    try:
        fdlg = ed.FillerCutDialog(srt_table=win.srt_tbl, parent=win)
        fdlg.resize(440, 380)
        fdlg.show()
        pump(app, 0.3)
        save(fdlg, 'ss_filler.png')
        fdlg.close()
    except Exception as e:
        print(f'  FillerCutDialog エラー: {e}')

    # ── 分割ダイアログ ──
    try:
        sdlg = ed.SplitDialog(parent=win)
        sdlg.show()
        pump(app, 0.3)
        save(sdlg, 'ss_split.png')
        sdlg.close()
    except Exception as e:
        print(f'  SplitDialog エラー: {e}')

    # ── 検索置換ダイアログ ──
    try:
        frdlg = ed.FindReplaceDialog(srt_table=win.srt_tbl, parent=win)
        frdlg.show()
        pump(app, 0.3)
        save(frdlg, 'ss_findreplace.png')
        frdlg.close()
    except Exception as e:
        print(f'  FindReplaceDialog エラー: {e}')

    os.remove(tmp_srt)
    print('\n完了。promo_work/ に保存しました。')
    app.quit()


if __name__ == '__main__':
    run()
