# ⚠️ ランディングページは現在「整備中ページ」に差し替え中

2026-06-13、ダウンロードサイトを一時的にお休みにして「整備中です、ちょっと待ってて」という
シンプルなページに差し替えました。落ち着いたら（v1.0.10の検証・公開が済んだら）元に戻します。

## 今の状態

| ファイル | 今の中身 | 元のフルページのバックアップ |
|----------|----------|------------------------------|
| `docs/index.html` | 🛠 整備中（日本語） | `docs/index.full.html` |
| `docs/en.html`    | 🛠 Under maintenance | `docs/en.full.html` |
| `docs/ko.html`    | 🛠 정비 중 | `docs/ko.full.html` |
| `docs/zh.html`    | 🛠 维护中 | `docs/zh.full.html` |

- 整備中ページには「お急ぎの方は GitHub から →」リンク（リポジトリのトップへ）を掲載
- `<meta name="robots" content="noindex">` を入れて、整備中ページが検索結果に出ないようにしている
- Google Search Console認証タグ（google-site-verification）は維持しているので、認証は外れない

## 元のフルページ（`*.full.html`）の中身＝復帰したらこうなる

元のランディングページは、こういう構成だった（復帰するとこれが戻る）：

- **ヒーロー**: アプリアイコン＋「おまかせ文字起こし / EasyTranscribe」＋キャッチコピー
- **ダウンロードボタン2つ**: 「Mac」(Apple Silicon DMG) と「Windows」(zip)
  - URLは `releases/latest/download/EasyTranscribe-Mac-AppleSilicon.dmg` と `...-Windows.zip`
  - ※Intel版は廃止済み（ボタンも無し）
- **ダウンロード数表示**: `downloads.json` を fetch して「Downloads NN」と表示（毎朝JST9時に自動更新）
- **使い方リンク**: README へ
- **折りたたみ注記**: 「Macで『開いていません』と表示されたら」→ 未署名アプリのGatekeeper対処（システム設定→プライバシーとセキュリティ→このまま開く）
- **寄付ボタン**: donate.sasakireijiyagi.com へ
- **スクリーンショット**（screenshot.png）
- **機能一覧**（Features グリッド6項目）
- **引用（Citation）**: Sasaki, R. (2026). EasyTranscribe [Computer software]. DOI: 10.5281/zenodo.20515527
- **フッター**: GitHub / README / MIT License / 佐々木玲仁（ヤギ製作所）リンク
  ＋「Claude（Anthropic）の支援を受けて開発」の透明性表記
- **言語切替バー**: 日本語 | English | 한국어 | 中文（4言語相互リンク）
- SEOメタタグ・OGP・Twitterカード・canonical 一式

実物を見たい場合は `docs/index.full.html` をブラウザで開けば、そのまま元のページが見られる。

## 復帰のしかた（4言語まとめて一発）

落ち着いたら、これで全ページを通常版に戻せる：

```bash
cd ~/tools/video_editor
for f in index en ko zh; do cp docs/$f.full.html docs/$f.html; done
git commit -am "ランディングページを通常版に復帰（4言語）"
git push
```

GitHub Pages反映に1〜2分。反映後はブラウザを Cmd+Shift+R で強制リロードして確認。
（戻したあと `*.full.html` のバックアップは消してもいいし、残しておいてもいい）

## なぜ休止したか

いろいろなプロジェクトが同時進行していて、まずバッチ進捗改善（コミット 8bda342）の検証と
v1.0.10リリースを落ち着いてやりたいため。サイトの集客より先に中身を固める判断。
急ぎのユーザーはGitHubから直接ダウンロードできるので実害はない。
