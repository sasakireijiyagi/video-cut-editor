# ℹ️ ランディングページの状態メモ（最新: 2026-06-13）

**サイトは通常のダウンロードページに復帰済み**です。v1.0.10・v1.1.0 の検証・公開が済んだため、
「整備中」ページから元のダウンロードページに戻しました。
ただし **Windowsのダウンロードだけ「調整中」表示**にして一時的に伏せています。

## 今の状態

| ファイル | 今の中身 | 復帰用マスター |
|----------|----------|----------------|
| `docs/index.html`（日本語） | 通常DLページ・Mac公開／**Windows（調整中）** | `docs/index.full.html` |
| `docs/en.html` | 同上（Windows under adjustment） | `docs/en.full.html` |
| `docs/ko.html` | 同上（Windows 조정 중） | `docs/ko.full.html` |
| `docs/zh.html` | 同上（Windows 调整中） | `docs/zh.full.html` |

- **Mac**: Apple Silicon DMG を通常どおりダウンロード可。
- **Windows**: ダウンロードボタンを無効化し「調整中」ラベル（CSSクラス `btn-disabled`）に置換。`.zip` リンクは外している。
- noindex は外れた（通常ページに戻ったので検索インデックス対象）。Search Console認証タグは維持。
- `*.full.html` は **Windows有効のままの元ページ** ＝ 将来Windowsを再開するときのマスター（無変更で温存）。

## なぜ Windows だけ「調整中」か

v1.1.0 で **Mac版だけ mlx-whisper（Metal GPU）に載せ替えて高速化**した（large-v3 が約11倍速）。
Windows版は従来どおり openai-whisper（CPU）で遅く、かつ Windows実機での動作確認ができていないため、
当面ダウンロードを伏せている。Windowsの faster-whisper 化（whisper-ctranslate2、CPUでも数倍速）は
**Phase 2** として保留中。

## Windows を再開するとき（Phase 2 完了後）

全ページを Windows有効のマスターに戻す（＝Macも含め元のフルページに戻る）：

```bash
cd ~/tools/video_editor
for f in index en ko zh; do cp docs/$f.full.html docs/$f.html; done
git commit -am "ランディング: Windowsダウンロードを再開（4言語）"
git push
```

Windowsボタンだけ手早く戻したい場合は、各 `*.html` の
`<span class="btn btn-win btn-disabled" ...>Windows（調整中）</span>` を
元の `<a class="btn btn-win" href="...releases/latest/download/EasyTranscribe-Windows.zip">Windows</a>` に戻すだけでもよい。

## 経緯

2026-06-13、複数プロジェクト同時進行のため一旦ダウンロードサイトを「整備中」ページに差し替え →
同日中に Mac mini 側で **v1.0.10**（バッチ進捗の見える化＋Dropboxダウンロード表示）と
**v1.1.0**（Mac版を mlx-whisper / Metal GPU 化）を検証・リリース →
復帰条件が満たされたのでサイトを通常版に復帰（Windowsのみ調整中）。
