# ℹ️ ランディングページの状態メモ（最新: 2026-06-13）

**サイトは通常のダウンロードページで公開中**です。v1.1.1（Mac版 mlx-whisper / Metal GPU ＋幻聴ループ修正）の
検証が済んだため、整備中ページから元のDLページに戻しました。
**Windowsのダウンロードだけ「調整中」表示**にして当面伏せています。

## 今の状態

| ファイル | 今の中身 | 復帰用マスター |
|----------|----------|----------------|
| `docs/index.html`（日本語） | 通常DLページ・Mac公開／**Windows（調整中）** | `docs/index.full.html` |
| `docs/en.html` | 同上（Windows under adjustment） | `docs/en.full.html` |
| `docs/ko.html` | 同上（Windows 조정 중） | `docs/ko.full.html` |
| `docs/zh.html` | 同上（Windows 调整中） | `docs/zh.full.html` |

- **Mac**: `releases/latest/download/EasyTranscribe-Mac-AppleSilicon.dmg`（= v1.1.1）を通常どおりDL可。
- **Windows**: ボタンを無効化し「調整中」ラベル（`btn-disabled`）に置換。`.zip` リンクは外している。
- noindex は外れ（通常ページ）、Search Console認証は維持。`*.full.html` は Windows有効の元ページ（温存）。

## リリース状況（参考）

- **v1.1.1 = 公開latest**（Mac mlx GPU ＋ `condition_on_previous_text=False` による幻聴ループ修正入り）。既存ユーザーのアプリ内アップデータもこれを拾う。
- **v1.1.0 = ドラフト（非公開）**。幻聴修正前のビルドなので隠したまま。タグ・コードは残存。
- Windows は中身は従来どおり openai-whisper（CPU）。faster-whisper 化は **Phase 2** で保留。

## Windows を再開するとき（Phase 2 完了後）

```bash
cd ~/tools/video_editor
for f in index en ko zh; do cp docs/$f.full.html docs/$f.html; done
git commit -am "ランディング: Windowsダウンロードを再開（4言語）"
git push
```

Windowsボタンだけ手早く戻すなら、各 `*.html` の
`<span class="btn btn-win btn-disabled">Windows（調整中）</span>` を
元の `<a class="btn btn-win" href="...-Windows.zip">Windows</a>` に戻す（CSSに `.btn-disabled` 追加済み）。

## 経緯

2026-06-13: 整備中化 → v1.0.10 / v1.1.0 を検証・公開 → サイトをDLページに復帰（Win調整中）→
v1.1.0(mlx) で実会話に「なるほど」等の繰り返しループ幻聴が判明 → v1.1.0をドラフト化＆サイトを再び整備中に →
`condition_on_previous_text=False` で修正、実会話25分で全編正常を確認 →
**v1.1.1 を公開し、サイトをDLページ（Mac公開/Win調整中）に復帰**。
