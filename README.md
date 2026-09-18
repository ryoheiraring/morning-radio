# morning-radio — 毎朝5分の自分専用ラジオ(全自動)

[teruhikonomizu-ops/ai-radio](https://github.com/teruhikonomizu-ops/ai-radio) をフォークし、
ニュース番組から「学びの5分番組」に作り替えたもの。毎朝 GitHub Actions が
**台本(Claude・定額プラン) → 音声合成(AivisSpeech) → Podcast RSS(GitHub Pages)** まで無人で実行する。
PC 不要・API 課金なし・YouTube 出力なし。

## 番組

| 番組ID | 番組 | 放送 | 話者 |
|---|---|---|---|
| `psychology` | 毎朝の心理学レッスン | 毎朝 | Nana |
| `behavioral-economics` | 毎朝の行動経済学 | 毎朝 | Nana |
| `evolution` | 人類の進化 〜ナナとソウの土曜日〜 | 毎週土曜 | Nana / Sou |
| `crypto-morning` | 暗号資産朝刊(CoinGecko + 公式RSS、直近24時間、5項目) | 毎朝 | Nana / Sou |
| `trade-edge` | エッジの見つけ方(題材は radio/trade-edge/covered.md に記録) | 毎朝 | Nana / Sou |

フィード URL: `https://<ユーザー名>.github.io/morning-radio/<番組ID>/feed.xml`
(一覧ページ: `https://<ユーザー名>.github.io/morning-radio/`)

- **Nana**(進行役): AivisSpeech `morioki`(落ち着いた女性)
- **Sou**(解説役): AivisSpeech `fumifumi`(落ち着いた青年)
- 台本の行頭 `Nana: ` / `Sou: ` で声が切り替わる。声の割り当ては [voices.json](voices.json)

## 初期設定(やることは1つだけ)

1. 手元の PC で `claude setup-token` を実行し、表示された長いトークンをコピー
2. GitHub のリポジトリ → **Settings → Secrets and variables → Actions → New repository secret**
   - Name: `CLAUDE_CODE_OAUTH_TOKEN` / Secret: コピーしたトークン

以上。次の朝から自動で始まる(すぐ試すなら Actions タブ → morning-radio → Run workflow)。
GitHub Pages(配信元 = GitHub Actions)は作成済み。

## スケジュール

- 05:30 JST に本線、06:30 / 07:30 JST に保険(作り終えていれば数秒で skip)
- 10:17 JST に `radio-watchdog` が当日分の有無を確認し、欠けていれば自動で再実行
- GitHub の cron は混雑時に遅れることがある(6時ちょうどの保証はない)

## 番組を増やす・変える

`prompts/<番組ID>.md` を1つ足すだけ。書き方は [prompts/README.md](prompts/README.md)。
既存番組の語り口やテーマ選びを変えたいときも、そのファイルを編集するだけでよい。
全番組共通のルール(出力形式・字数の数え方など)は `prompts/_common.md`。

## 仕組み

```
GitHub Actions (毎朝・cron)
  plan  … prompts/ を読み、今日の曜日に放送する番組IDを列挙(matrix)
  build … 番組ごとに(直列):
    0. (collector がある番組のみ) 素材収集 → digest.md。取れない項目は「取得失敗」と記して飛ばす
    1. scripts/build_prompt.py   番組プロンプト + 共通ルール + 日付 + 放送済みテーマ一覧 (+ digest) → prompt.md
    2. claude -p --model sonnet  台本・概要欄・テーマ台帳を執筆(CLAUDE_CODE_OAUTH_TOKEN)
    3. scripts/split_output.py   分割・話者タグ/字数/タイトル検査(不合格なら修正指示付きで作り直し)
    4. scripts/tts_aivis.py      AivisSpeech Engine(Docker・CPU)で合成。声モデルは AivisHub から自動DL
    5. 長さ検証 → GitHub Release に mp3 を添付 → meta.json
    6. scripts/make_feed.py      docs/<番組ID>/feed.xml と index.html を再生成 → main にコミット
  pages … docs/ を GitHub Pages に配信
```

- `radio/<番組ID>/<日付>/` に 台本.txt・概要欄.txt・テーマ.txt・meta.json が残る
- テーマの重複は、過去全回の `テーマ.txt` をプロンプトに添付して避ける
- 生成済みの日は自動スキップ。`台本.txt` だけある日は音声合成から再開(手動修復の入り口)
- 作り直したい日: その日のフォルダの `meta.json` を消して手動実行(台本ごとなら `台本.txt` も消す)
- 失敗時は GitHub からオーナーへ通知メールが飛ぶ(Actions の既定動作)

## 声を変える

[voices.json](voices.json) の `model_uuid` / `speaker` / `style` を AivisHub(https://hub.aivis-project.com/)の
モデルに差し替える。`_global` で全体の速度と間(文・段落・コーナー)を調整できる。
