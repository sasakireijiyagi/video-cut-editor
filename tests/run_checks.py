#!/usr/bin/env python3
"""リリース前の退行チェック。

使い方:
    <PyQt6の入ったpython> tests/run_checks.py

数秒で終わる。1つでも落ちたらリリースしないこと。

ここにあるのは 2026-09-01〜02 の一連の不具合対応で実際に踏んだ退行の
再現テスト。多視点のAI点検（30分・高コスト）が捕まえたものを，
数秒で再検査できる形に固定したもの。新しい種類の穴はこのテストでは
見つからないので，大きな変更のときは別途点検を回すこと。

whisper 本体は使わない。偽エンジン（Pythonスクリプト）が
--output-dir に SRT を書く挙動だけを模す。動画・音声ファイルも使わない。
mac / Windows の両方で走る（CI は両ランナーでこれを回してからビルドする）。
"""
import importlib.util
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# CI（GitHub Actions の mac/windows ランナー）でも走るように:
# - 画面なしで Qt を動かす
# - Windows のコンソールで日本語が UnicodeEncodeError にならないようにする
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

REPO = Path(__file__).resolve().parent.parent
EDITOR = REPO / 'editor.py'

PASS = 0
FAIL = 0


def check(name, cond, detail=''):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f'  ok  {name}')
    else:
        FAIL += 1
        print(f'  NG  {name}  {detail}')


def load_editor():
    sys.argv = ['editor.py']
    spec = importlib.util.spec_from_file_location('ed', str(EDITOR))
    m = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(m)
    except SystemExit:
        pass
    return m


# ─────────────────────────────────────────────────────────────
print('== 起動 ==')

# v1.2.9 の退行: _ver_key の定義位置が使用箇所より後ろにあり，
# conda が無く ~/Library/Python/3.*/bin/whisper がある環境（=アプリ内
# セットアップが pip install --user で作る状態）で NameError 起動不能。
# 開発機は conda があって再現しないため，環境を差し替えて検査する。
if sys.platform == 'darwin':
    with tempfile.TemporaryDirectory() as fake_home:
      bindir = Path(fake_home) / 'Library' / 'Python' / '3.11' / 'bin'
      bindir.mkdir(parents=True)
      (bindir / 'whisper').write_text('#!/bin/sh\n', encoding='utf-8')
      (bindir / 'whisper').chmod(0o755)
      r = subprocess.run(
          [sys.executable, '-c',
           'import importlib.util,sys\n'
           'sys.argv=["editor.py"]\n'
           f'spec=importlib.util.spec_from_file_location("ed", r"{EDITOR}")\n'
           'm=importlib.util.module_from_spec(spec)\n'
           'try: spec.loader.exec_module(m)\n'
           'except SystemExit: pass\n'
           'print("IMPORTED")'],
          env={**os.environ, 'HOME': fake_home,
               'PATH': '/usr/bin:/bin:/usr/sbin:/sbin'},
          capture_output=True, text=True, timeout=120)
      check('conda無し + user-site whisper ありで起動できる',
            'IMPORTED' in r.stdout, (r.stderr or '')[-200:])

m = load_editor()
# 以降の節が _build_transcribe_cmd を差し替えるので、本物をここで退避しておく
_REAL_BUILD_CMD = m._build_transcribe_cmd
from PyQt6.QtWidgets import QApplication          # noqa: E402
app = QApplication.instance() or QApplication([])

# ─────────────────────────────────────────────────────────────
print('== バージョン比較（更新確認） ==')
# 文字列比較だと "1.2.11" > "1.2.9" が False で，全利用者に更新が届かない
k = m._ver_key
check("1.2.9 → 1.2.11 を更新ありと判定", k('1.2.11') > k('1.2.9'))
check("1.2.3 → 1.2.11 を更新ありと判定", k('1.2.11') > k('1.2.3'))
check("同一版を更新なしと判定", not (k('1.2.11') > k('1.2.11')))
check("3.9 < 3.10（Python探索の並び）", k('3.9') < k('3.10'))

# ─────────────────────────────────────────────────────────────
print('== 文字起こしワーカー（偽エンジン） ==')

work = Path(tempfile.mkdtemp(prefix='easytranscribe-test-'))
os.chdir(work)
FAKE = work / 'fake_engine.py'   # sh でなく Python: Windows でも同じに動かすため

_FAKE_TEMPLATE = '''import sys, pathlib
out = {out!r}
if out:
    (pathlib.Path(sys.argv[1]) / out).write_text(
        "1\\n00:00:00,000 --> 00:00:01,000\\n新しい機械出力\\n\\n",
        encoding="utf-8")
sys.exit({rc})
'''


def setup_engine(out_name, rc=0):
    """mlx を模す: 渡された --output-dir(argv[1]) に out_name で書く。
    out_name を切り詰めた名前にすれば mlx のドット切り詰めを再現できる。"""
    FAKE.write_text(_FAKE_TEMPLATE.format(out=out_name, rc=rc), encoding='utf-8')
    m._build_transcribe_cmd = lambda a, mo, l, od, **kw: (
        [sys.executable, str(FAKE), od], 'mlx')
    m._media_duration = lambda v: 1.0


def run_single(video):
    w = m.WhisperWorker(video, 'large-v3-turbo', 'ja')
    res = {}
    w.done.connect(lambda ok, msg: res.update(ok=ok, msg=msg))
    w.log.connect(lambda s: None)
    w.run()
    return res


def reset(files):
    for p in work.iterdir():
        if p.is_file() and p != FAKE:
            p.unlink()
    for name, content in files.items():
        (work / name).write_text(content, encoding='utf-8')


V = 'Screen Recording 2026-01-15 at 09.30.00.mov'   # macOS 画面収録の既定名
S = 'Screen Recording 2026-01-15 at 09.30.00.srt'   # 正規名
T = 'Screen Recording 2026-01-15 at 09.30.srt'      # mlx が切り詰める名前

# (1) 退避の空振り退行: mlx が切り詰め名で出しても，正規名で確定し
#     既存の編集済みSRTは .backup.srt に退避されること
reset({V: 'd', S: '編集した逐語録'})
setup_engine(T)
r = run_single(str(work / V))
bak = list(work.glob('*backup*'))
check('ドット入り名: 正規名に出力される',
      r.get('ok') and (work / S).read_text(encoding='utf-8').startswith('1'))
check('ドット入り名: 編集済みSRTが退避される',
      bak and '編集した逐語録' in bak[0].read_text(encoding='utf-8'))

# (2) 旧版の遺産（切り詰め名に編集済みSRT）を壊さないこと
reset({V: 'd', T: '旧版時代の逐語録'})
setup_engine(T)
r = run_single(str(work / V))
check('切り詰め名の遺産が無傷', (work / T).read_text(encoding='utf-8') == '旧版時代の逐語録')
check('新出力は正規名', (work / S).exists())

# (3) 中止(rc≠0): 利用者のフォルダに一切触れないこと
reset({V: 'd', S: '編集した逐語録'})
setup_engine(T, rc=143)
r = run_single(str(work / V))
check('中止: 失敗と報告', r.get('ok') is False)
check('中止: 既存SRTが無傷（退避もされない）',
      (work / S).read_text(encoding='utf-8') == '編集した逐語録'
      and not list(work.glob('*backup*')))

# (4) mlx が何も出さず exit 0（ファイル単位の例外を握りつぶす挙動）:
#     成功扱いにせず，別のSRTも掴まないこと
reset({V: 'd', S: '編集した逐語録'})
setup_engine(None, rc=0)
r = run_single(str(work / V))
check('無出力 exit0: 失敗と報告', r.get('ok') is False)
check('無出力 exit0: 既存SRTが無傷', (work / S).read_text(encoding='utf-8') == '編集した逐語録')

# (5) 隣の動画のSRTを掴まないこと（a.mp4 の a.srt がある所で a.b.mp4 を処理）
reset({'a.mp4': 'd', 'a.srt': 'a.mp4の逐語録', 'a.b.mp4': 'd'})
setup_engine('a.srt')   # mlx は a.b → a に切り詰める
r = run_single(str(work / 'a.b.mp4'))
check('隣接動画のSRTが無傷', (work / 'a.srt').read_text(encoding='utf-8') == 'a.mp4の逐語録')
check('出力は a.b.srt', (work / 'a.b.srt').exists())

# (6) 書き出しOFFの .txt/.csv を退避しないこと（CSVはコーディング成果物）
reset({'会議.mp4': 'd', '会議.srt': '編集済み',
       '会議.csv': 'コーディング済み', '会議.txt': 'メモ'})
setup_engine('会議.srt')
r = run_single(str(work / '会議.mp4'))
check('書き出しOFFのCSVが無傷', (work / '会議.csv').read_text(encoding='utf-8') == 'コーディング済み')
check('書き出しOFFのTXTが無傷', (work / '会議.txt').read_text(encoding='utf-8') == 'メモ')

# (7) 退避が効かない環境でもフェイルクローズすること:
#     退避が空振りしたら上書きせず，今回の結果は .new.srt として残す
reset({'会議.mp4': 'd', '会議.srt': '編集した逐語録'})
setup_engine('会議.srt')
_orig_backup = m._backup_existing_outputs
m._backup_existing_outputs = lambda *a, **kw: []   # 退避が全滅する環境を模す
try:
    r = run_single(str(work / '会議.mp4'))
finally:
    m._backup_existing_outputs = _orig_backup
check('退避不能: 失敗と報告（成功と偽らない）', r.get('ok') is False)
check('退避不能: 編集済みSRTが無傷', (work / '会議.srt').read_text(encoding='utf-8') == '編集した逐語録')
news = list(work.glob('*.new*.srt'))
check('退避不能: 今回の結果は .new.srt として残る',
      news and news[0].read_text(encoding='utf-8').startswith('1'))
check('退避不能: 文言が上書き中止を説明', '上書きを中止' in r.get('msg', ''))

# (7b) 巻き戻せなかったものがあるとき「元のまま」と言わないこと（文言の整合）
reset({'会議.mp4': 'd', '会議.srt': '編集した逐語録'})
setup_engine('会議.srt')
_orig_backup = m._backup_existing_outputs
_orig_roll = m._rollback_backups
m._backup_existing_outputs = lambda *a, **kw: []
m._rollback_backups = lambda *a, **kw: [(work / '会議.backup.srt', work / '会議.srt')]
try:
    r = run_single(str(work / '会議.mp4'))
finally:
    m._backup_existing_outputs = _orig_backup
    m._rollback_backups = _orig_roll
check('文言整合: 巻き戻し失敗時に「元のまま」と言わない',
      '元のまま' not in r.get('msg', ''))
check('文言整合: 改名を実名で案内', 'という名前になっています' in r.get('msg', ''))

# (8) 書き出し先に書けない（読み取り専用フォルダ）:
#     利用者のファイルに触れず，完成品の在り処を知らせること
# 救い出し先(Path.home()/Desktop)が本物のデスクトップに向かないよう HOME を偽装する
fake_home = work / 'fakehome2'
(fake_home / 'Desktop').mkdir(parents=True, exist_ok=True)
sub = work / 'rodir'
sub.mkdir(exist_ok=True)
(sub / '会議.mp4').write_text('d', encoding='utf-8')
(sub / '会議.srt').write_text('編集した逐語録', encoding='utf-8')
setup_engine('会議.srt')
if os.name != 'nt':   # Windows の chmod はフォルダへの書き込みを防げない
    os.chmod(sub, 0o555)
    _home = os.environ.get('HOME')
    os.environ['HOME'] = str(fake_home)
    try:
        r = run_single(str(sub / '会議.mp4'))
    finally:
        if _home is None:
            os.environ.pop('HOME', None)   # Windows では未設定が普通
        else:
            os.environ['HOME'] = _home
        os.chmod(sub, 0o755)
    check('読取専用: 失敗と報告', r.get('ok') is False)
    check('読取専用: 既存SRTが無傷（退避もされない）',
          (sub / '会議.srt').read_text(encoding='utf-8') == '編集した逐語録'
          and not list(sub.glob('*backup*')))
    salvaged = list((fake_home / 'Desktop').glob('*.srt'))
    check('読取専用: 完成品をデスクトップへ救い出す',
          salvaged and salvaged[0].read_text(encoding='utf-8').startswith('1'))
    check('読取専用: 救い出し先を文言で知らせる', '保存しました' in r.get('msg', ''))
else:
    print('  --  読取専用フォルダの検査は POSIX のみ')

# (9) 幹が極端に長い名前（退避名だけが上限を超える）:
#     例外がワーカーの外へ抜けてアプリごと落ちないこと
if os.name == 'nt':
    # 幹を縮めると「普通に成功する」だけのシナリオになり検査が成立しない。
    # Windows のパス長は MAX_PATH という別問題なので，この検査ごとスキップする
    print('  --  超長名の検査は POSIX のみ（Windows は MAX_PATH の別問題になるため）')
else:
    long_stem = 'x' * 250
    reset({long_stem + '.mov': 'd', long_stem + '.srt': '編集した逐語録'})
    setup_engine(long_stem + '.srt')
    _home = os.environ.get('HOME')
    os.environ['HOME'] = str(fake_home)
    try:
        r = run_single(str(work / (long_stem + '.mov')))
        escaped = False
    except Exception:
        escaped = True
    finally:
        if _home is None:
            os.environ.pop('HOME', None)
        else:
            os.environ['HOME'] = _home
    check('超長名: 例外がワーカーの外へ抜けない', not escaped)
    check('超長名: 失敗と報告', not escaped and r.get('ok') is False)
    check('超長名: 既存SRTが無傷',
          (work / (long_stem + '.srt')).read_text(encoding='utf-8') == '編集した逐語録')

# (10) 退避が「一部だけ」失敗（CSVがロック中＝Excelで開いたまま等）:
#      退避済みのSRTを巻き戻し，利用者のファイルを元のままにすること
if sys.platform == 'darwin':
    reset({'会議.mp4': 'd', '会議.srt': '編集した逐語録', '会議.csv': 'コーディング済み'})
    setup_engine('会議.srt')
    subprocess.run(['chflags', 'uchg', str(work / '会議.csv')])
    try:
        w = m.WhisperWorker(str(work / '会議.mp4'), 'large-v3-turbo', 'ja',
                            export_csv=True)
        r = {}
        w.done.connect(lambda ok, msg: r.update(ok=ok, msg=msg))
        w.log.connect(lambda s: None)
        w.run()
    finally:
        subprocess.run(['chflags', 'nouchg', str(work / '会議.csv')])
    check('部分退避失敗: 失敗と報告', r.get('ok') is False)
    check('部分退避失敗: SRTが元の名前・元の内容に巻き戻る',
          (work / '会議.srt').read_text(encoding='utf-8') == '編集した逐語録')
    check('部分退避失敗: 退避の残骸(.backup)が残らない',
          not list(work.glob('会議.backup*')))
    check('部分退避失敗: 今回の結果は .new.srt に保全',
          any(p.read_text(encoding='utf-8').startswith('1') for p in work.glob('会議.new*.srt')))
    check('部分退避失敗: 文言が原因のファイルを実名で挙げる',
          '会議.csv' in r.get('msg', ''))
else:
    print('  --  部分退避失敗（chflags）は macOS のみ検査')

# (11) 確定(os.replace)が失敗（容量切れ等）:
#      巻き戻して .new.srt に保全し，.part を残さないこと
reset({'会議.mp4': 'd', '会議.srt': '編集した逐語録'})
setup_engine('会議.srt')
_orig_replace = os.replace
def _raise_on_dest(a, b):
    if str(b).endswith('会議.srt'):
        raise OSError(28, 'No space left on device')
    return _orig_replace(a, b)
os.replace = _raise_on_dest
try:
    r = run_single(str(work / '会議.mp4'))
finally:
    os.replace = _orig_replace
check('確定失敗: 失敗と報告', r.get('ok') is False)
check('確定失敗: SRTが元の名前・元の内容に巻き戻る',
      (work / '会議.srt').read_text(encoding='utf-8') == '編集した逐語録')
check('確定失敗: 結果は .new.srt に保全',
      any(p.read_text(encoding='utf-8').startswith('1') for p in work.glob('会議.new*.srt')))
check('確定失敗: .part の残骸が残らない', not list(work.glob('*.part')))
check('確定失敗: 保全先を文言で知らせる', 'として保存しています' in r.get('msg', ''))

# (12) 一括の完了表示: 失敗したファイルの実名が本文に載ること
t = m._batch_summary_text(1, 2, [('ng.mp4', 'エラーの1行目\n詳細')])
check('完了文: 件数', '1/2' in t)
check('完了文: 失敗ファイルの実名', 'ng.mp4' in t)
check('完了文: 理由の1行目', 'エラーの1行目' in t and '詳細' not in t)
dlg = m.BatchDialog(model='large-v3-turbo', language='日本語')
dlg._update_progress = lambda: None   # UI更新は本題でない
dlg._update_detail   = lambda: None
dlg._batch_start_time = None
dlg._on_file_started(1, 2, 'ng.mp4')
dlg._on_file_done(1, 2, False, 'だめでした')
check('完了文: ダイアログが失敗を実名で貯める',
      dlg._failures == [('ng.mp4', 'だめでした')])

# ─────────────────────────────────────────────────────────────
print('== 一括ワーカー ==')
# 成功と「無出力 exit0」の失敗を正しく区別して数えること
reset({'ok.mp4': 'd', 'ng.mp4': 'd', 'ok.srt': '既存の編集'})
FAKE.write_text(
    'import sys, pathlib\n'
    'if sys.argv[2].endswith("ok.mp4"):\n'
    '    (pathlib.Path(sys.argv[1]) / "ok.srt").write_text(\n'
    '        "1\\n00:00:00,000 --> 00:00:01,000\\n出力\\n\\n", encoding="utf-8")\n'
    'sys.exit(0)\n', encoding='utf-8')
m._build_transcribe_cmd = lambda a, mo, l, od, **kw: ([sys.executable, str(FAKE), od, a], 'mlx')
w = m.BatchWhisperWorker([str(work / 'ok.mp4'), str(work / 'ng.mp4')],
                         'large-v3-turbo', 'ja', False, 1.0)
results = []
w.file_done.connect(lambda i, t, ok, msg: results.append((i, ok)))
w.all_done.connect(lambda s, t: results.append(('all', s, t)))
w.log.connect(lambda s: None)
w.run()
check('一括: 1本目成功', (1, True) in results)
check('一括: 無出力の2本目は失敗', (2, False) in results)
check('一括: 集計 1/2', ('all', 1, 2) in results)
check('一括: 既存の編集が退避されている',
      (work / 'ok.backup.srt').exists()
      and (work / 'ok.backup.srt').read_text(encoding='utf-8') == '既存の編集')

# ─────────────────────────────────────────────────────────────
print('\n== 誤操作よけ（ホイールで設定が変わらない） ==')
# 閉じているコンボの上でホイールを回すと、Qt の既定では選択が無言で
# 変わる。起こす言語が変わったまま文字起こしされると、別の文字体系で
# 書き取られて「文字化け」に見える。実際に報告が1件あった。
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt6.QtWidgets import QApplication, QComboBox, QSpinBox, QDoubleSpinBox
from PyQt6.QtGui import QWheelEvent
from PyQt6.QtCore import QPointF, QPoint, Qt as _Qt

_app = QApplication.instance() or QApplication([])


def _spin_wheel(widget, clicks=3):
    """トラックパッドの2本指スクロール相当を送る。"""
    for _ in range(clicks):
        _app.sendEvent(widget, QWheelEvent(
            QPointF(10, 10), QPointF(10, 10), QPoint(0, 0), QPoint(0, -120),
            _Qt.MouseButton.NoButton, _Qt.KeyboardModifier.NoModifier,
            _Qt.ScrollPhase.NoScrollPhase, False))


# まず「この検査が本当に鳴るか」を素の QComboBox で確かめる。
# 鳴らない検査を置くと、守れていないのに通ったように見える。
_bare = QComboBox()
_bare.addItems(['日本語', '英語', '中国語', '韓国語'])
_bare.setCurrentIndex(0)
_spin_wheel(_bare)
check('検査そのものが効いている（素のコンボは実際に変わる）',
      _bare.currentText() != '日本語',
      f'素のQComboBoxが変わらない＝この検査は何も見ていない（{_bare.currentText()}）')

for _cls_name, _items, _label in [
    ('NoWheelComboBox', ['日本語', '英語', '中国語', '韓国語'], 'コンボ'),
]:
    _w = getattr(m, _cls_name)()
    _w.addItems(_items)
    _w.setCurrentIndex(0)
    _spin_wheel(_w)
    check(f'{_label}: ホイールで選択が変わらない', _w.currentText() == _items[0],
          f'{_items[0]} → {_w.currentText()}')

_s = m.NoWheelSpinBox(); _s.setRange(0, 100); _s.setValue(20)
_spin_wheel(_s)
check('スピンボックス: ホイールで値が変わらない', _s.value() == 20, f'20 → {_s.value()}')

_d = m.NoWheelDoubleSpinBox(); _d.setRange(0.0, 10.0); _d.setValue(1.0)
_spin_wheel(_d)
check('スピンボックス（小数）: ホイールで値が変わらない', _d.value() == 1.0, f'1.0 → {_d.value()}')

# 設定を変える部品が素のクラスのまま残っていないか（置き換え漏れの検出）。
# 文字列一致だと QComboBox(self) や addWidget(QComboBox()) を見逃すので、
# クラス定義行と QSS 文字列を除いた上で正規表現で探す。
import re
_src_lines = EDITOR.read_text(encoding='utf-8').split('\n')
_bare_uses = []
for _i, _ln in enumerate(_src_lines, 1):
    if _ln.startswith('class NoWheel'):
        continue
    if re.search(r'(?<![\w.])(?<!NoWheel)Q(?:ComboBox|SpinBox|DoubleSpinBox)\s*\(', _ln):
        _bare_uses.append(f'{_i}: {_ln.strip()[:60]}')
check('素のコンボ／スピンを生成している箇所がない', not _bare_uses,
      '; '.join(_bare_uses))

# やり過ぎの検出。キーボードでの選択が殺されていないこと。
# setCurrentIndex() は API 呼び出しでイベントを通らないため、
# keyPressEvent を潰しても必ず通ってしまう。実際にキーを送ること。
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtCore import QEvent as _QEvent


def _send_key(widget, key):
    widget.setFocus()
    _app.sendEvent(widget, QKeyEvent(
        _QEvent.Type.KeyPress, key, _Qt.KeyboardModifier.NoModifier))


# まずこの検査が鳴るかを、キーも殺したクラスで確かめる
class _DeadCombo(m.NoWheelComboBox):
    def keyPressEvent(self, e):
        e.ignore()


_dead = _DeadCombo(); _dead.addItems(['日本語', '英語', '中国語']); _dead.setCurrentIndex(0)
_send_key(_dead, _Qt.Key.Key_Down)
check('検査そのものが効いている（キーを殺すと下キーが通らない）',
      _dead.currentText() == '日本語',
      'キーを殺しても値が変わった＝この検査は何も見ていない')

_k = m.NoWheelComboBox(); _k.addItems(['日本語', '英語', '中国語']); _k.setCurrentIndex(0)
_send_key(_k, _Qt.Key.Key_Down)
check('コンボ: 下キーでの選択は従来どおり効く', _k.currentText() == '英語',
      f'日本語 → {_k.currentText()}')

_ks = m.NoWheelSpinBox(); _ks.setRange(0, 100); _ks.setValue(20)
_send_key(_ks, _Qt.Key.Key_Up)
check('スピンボックス: 上キーでの増減は従来どおり効く', _ks.value() == 21,
      f'20 → {_ks.value()}')

# ─────────────────────────────────────────────────────────────
print('\n== 幻聴よけ（無音が多い録音を既定でオン） ==')
# Whisper は冒頭や無音区間に定型句（「以上で終わります」など）を湧かせる。
# 抑制のフラグは --word-timestamps True とセットでないと効かない。

_w = m.MainWindow()
check('主画面: 「無音が多い録音」が既定でオン',
      _w.chk_silent_recording.isChecked(),
      '既定がオフだと，利用者は幻聴を1回踏むまで選択肢に気づけない')

# 既定の状態で，抑制のフラグが実際にコマンドへ乗るか（両エンジン）
for _eng_name, _model in [('mlx', 'large-v3'), ('openai', 'large-v3')]:
    _cmd, _ = _REAL_BUILD_CMD(
        'a.mp4', _model, 'ja', '/tmp',
        silent_recording=_w.chk_silent_recording.isChecked())
    _joined = ' '.join(_cmd)
    _has_thr = 'hallucination-silence-threshold' in _joined or 'hallucination_silence_threshold' in _joined
    _has_wts = 'word-timestamps' in _joined or 'word_timestamps' in _joined
    check(f'既定の状態で幻聴抑制のフラグが乗る（{_eng_name}）', _has_thr, _joined)
    # しきい値は単語単位の時刻が無いと効かない。片方だけ付けても意味がない
    check(f'単語単位の時刻もセットで乗る（{_eng_name}）', _has_wts, _joined)
    break   # エンジンはこの環境で決まるので1回でよい

# 切ったときは乗らないこと（利用者が外せること）
_cmd_off, _ = _REAL_BUILD_CMD('a.mp4', 'large-v3', 'ja', '/tmp',
                              silent_recording=False)
check('チェックを外せば従来どおりフラグは乗らない',
      'hallucination' not in ' '.join(_cmd_off), ' '.join(_cmd_off))

# 一括処理の画面が主画面の状態を引き継ぐか
_dlg = m.BatchDialog(None, model='large-v3', language='日本語',
                     mark_silence=False, silence_sec=1.0, fill_gaps=False,
                     fill_mode='label', export_txt=False, export_csv=False,
                     silent_recording=_w.chk_silent_recording.isChecked())
check('一括処理: 主画面の状態を引き継ぐ', _dlg.chk_silent_rec.isChecked())

# ─────────────────────────────────────────────────────────────
os.chdir('/')
import shutil as _sh
_sh.rmtree(work, ignore_errors=True)

print()
print(f'結果: {PASS} 合格 / {FAIL} 不合格')
sys.exit(1 if FAIL else 0)
