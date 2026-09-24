# 番組の追加・変更はこのフォルダだけ

`prompts/<番組ID>.md` を1つ置くと、翌朝からその番組が自動で作られ、
`https://<ユーザー名>.github.io/<リポジトリ名>/<番組ID>/feed.xml` で配信される。
ワークフローや他のスクリプトは触らなくてよい(番組一覧は毎朝このフォルダから自動で組み立てる)。

## ファイルの形

先頭に `---` で囲った設定(front matter)、その下に台本の指示(自由文)を書く。

```markdown
---
title: 番組名(ポッドキャストアプリに出る名前)
description: 番組の一言説明(RSSの説明文)
speakers: [Nana]            # 台本に登場する話者。Nana のみ / [Nana, Sou] の掛け合い
days: [mon, tue, wed, thu, fri, sat, sun]   # 放送する曜日。週1なら [sat]
chars: [1500, 2000]         # 読み上げ文字数の許容範囲(約5分)
category: Education         # Apple Podcasts のカテゴリ名(英語)
color: "#3f6fb5"            # アートワークの色
collector: scripts/collect_crypto.py   # (任意)素材収集スクリプト。毎朝 <出力md> <鮮度時間> を引数に実行され、
                                        #  出力がプロンプト末尾に「今日の素材」として付く。無ければ収集なし
fresh_hours: 24             # (任意)収集スクリプトに渡す鮮度(時間)
ledger: covered.md          # (任意)放送済み台帳。radio/<番組ID>/covered.md に毎回1行追記し、次回のプロンプトに丸ごと添付
builder: scripts/xxx.py     # (任意)台本を直接作るスクリプト。指定すると Claude を呼ばない(heidel-daily 方式)
duration_sec: [150, 720]    # (任意)公開してよい音声の長さ(秒)
attach_reports: 3           # (任意)研究員の日次報告の直近 N 日ぶんをプロンプトに添付
---
(ここから下が、Claude に渡す番組固有の指示。テーマ・語り口・構成など)
```

- 番組IDは英小文字・数字・ハイフンのみ(フォルダ名・URLになる)
- `_` で始まるファイル(`_common.md`)は共通ルールで、番組としては扱われない
- 共通ルール(出力形式・話者タグ・字数の数え方)は `_common.md` にあり、全番組に自動で付く
- 声の設定(どの話者にどのAivisSpeechモデルを使うか)は `voices.json`
