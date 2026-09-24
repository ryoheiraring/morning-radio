---
title: HEIDEL BEERE 日次報告
description: HEIDEL BEERE の研究員AIが、直近24時間の締めとして書いた日次報告を、そのまま読み上げる約15分。試した仮説の結果、落ちた理由、生きている候補、判断待ち、今日の予定の5項目。研究の進み具合の報告であり、投資助言ではありません。
speakers: [研究員]
days: [mon, tue, wed, thu, fri, sat, sun]
chars: [800, 7000]
category: Business
color: "#2f5d50"
builder: scripts/build_heidel_daily.py
duration_sec: [45, 1500]
---
この番組は Claude で台本を書きません。研究員AI が書いた `radio/heidel-daily/report.md` が唯一の正典で、
`scripts/build_heidel_daily.py` が読み上げ用の整形 (記号除去・数字の丸め・段落の区切り) だけを行います。
内容を書き換えないため、このファイルの本文はプロンプトとしては使われません。

## この番組の流れ

1. PC 側 (`C:\Users\ryohe\neu-researcher`) が毎朝 05:00 JST に `run.cmd daily-report` を実行
2. 研究員が直近24時間の材料 (台帳・forward 記録・その日に受けた指示) から報告書を書く
3. `radio/heidel-daily/report.md` と `archive/<日付>.md` に push
4. このリポジトリの 05:30 の本線が report.md を整形して配信 (届いていなければ 06:30 / 07:30 で再確認)
5. それでも届かなければ「本日の報告は届いていません」の1分版を配信し、LINE に通知

## 報告書の中身 (研究員側 `researcher/daily_report.py` が定める)

一、昨日の結果 ／ 二、落ちた理由の掘り下げ ／ 三、生きている候補の状態 ／ 四、判断待ち ／ 五、今日の予定
本文の後の `---` 以降は「見返し用」で、読み上げず概要欄 (ショーノート) に載ります。
