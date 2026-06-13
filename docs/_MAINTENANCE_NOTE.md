# ⚠️ ランディングページは再び「整備中」に戻しています（最新: 2026-06-13）

**全4言語ページを「整備中」ページに戻しました。** 理由: v1.1.0（Mac版 mlx-whisper / Metal GPU）で、
実際の会話音声に対して Whisper の幻聴（無音・小音量区間に「ご視聴ありがとうございました」を繰り返す）が
出る件があり、**ちゃんと検証が済むまで公開を保留**するため。

> 補足: この幻聴は Whisper モデル（特に large-v3）と音声品質（小音量・遠距離・2人会話）に由来する既知挙動で、
> mlx 固有のバグではない（旧 openai-whisper でも同様に起きうる）。エンジン自体は合成音声・動画で正常動作を確認済み。
> 対処の方向: モデル変更（large-v3-turbo / medium）、音量正規化、幻聴抑制パラメータ（condition_on_previous_text=False 等）。

## 今の状態

| ファイル | 今の中身 | 復帰用マスター（DLページ） |
|----------|----------|----------------------------|
| `docs/index.html`（日本語） | 🛠 整備中 | `docs/index.full.html` |
| `docs/en.html` | 🛠 Under maintenance | `docs/en.full.html` |
| `docs/ko.html` | 🛠 정비 중 | `docs/ko.full.html` |
| `docs/zh.html` | 🛠 维护中 | `docs/zh.full.html` |

- 整備中ページには「お急ぎの方は GitHub から →」リンクを掲載、`noindex` で検索除外、Search Console認証は維持。
- `*.full.html` は **Mac/Windows両方のDLボタンを持つ元のフルページ**（無変更で温存）。

## 復帰のしかた（検証OK後）

整備中をやめてDLページに戻すには:

```bash
cd ~/tools/video_editor
for f in index en ko zh; do cp docs/$f.full.html docs/$f.html; done
git commit -am "ランディングページを通常版に復帰（4言語）"
git push
```

Windowsだけ「調整中」にして公開したい場合は、復帰後に各 `*.html` の Windowsボタン
（`<a class="btn btn-win" href="...-Windows.zip">Windows</a>`）を
無効スパン `<span class="btn btn-win btn-disabled">Windows（調整中）</span>` に差し替える（CSSに `.btn-disabled { opacity:.45; pointer-events:none; }` を追加）。

## 経緯

2026-06-13: 整備中化 → Mac mini側で v1.0.10 / v1.1.0 を検証・公開 → サイトを一旦DLページに復帰（Windowsのみ調整中）→
v1.1.0(mlx) の実音声での幻聴が判明し、**検証完了まで再び全面「整備中」に戻した**。
