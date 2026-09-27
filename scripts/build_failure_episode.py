# -*- coding: utf-8 -*-
"""配信に失敗した日の「1分エピソード」を作る。Claude も素材も使わない (失敗しているので使えない)。

使い方: python3 build_failure_episode.py <番組ID> <YYYY-MM-DD> <理由コード> <台本出力> <概要欄出力> <テーマ出力>

理由コード (どの段で失敗したかを、聞いて分かる日本語に直す):
  script    台本の生成に失敗した (Claude の呼び出し・品質検査)
  report    研究員の報告書が届かなかった (heidel-daily)
  material  素材の収集に失敗した (collector)
  audio     音声合成に失敗した
  publish   配信 (Release / RSS) に失敗した
  other     それ以外
"""
import datetime as _dt
import sys
from pathlib import Path

WHY = {
    "script": ("台本の生成に失敗しました",
               "原稿を書く工程が、決められた回数のやり直しでも通りませんでした。"),
    "report": ("研究員からの報告書が届きませんでした",
               "パソコン側の締め処理が、配信の時点で報告書を出せていませんでした。"),
    "material": ("素材の収集に失敗しました",
                 "番組のもとになる情報を、外部から取り込めませんでした。"),
    "audio": ("音声の合成に失敗しました",
              "原稿はできていましたが、声に変換する工程で止まりました。"),
    "publish": ("配信の最後の工程で失敗しました",
                "音声はできていましたが、配信の手続きが完了しませんでした。"),
    "other": ("配信に失敗しました", "原因は自動では特定できませんでした。"),
}
TITLES = {
    "psychology": ("毎朝の心理学レッスン", "Nana"),
    "behavioral-economics": ("毎朝の行動経済学", "Nana"),
    "evolution": ("人類の進化", "Nana"),
    "crypto-morning": ("暗号資産朝刊", "Nana"),
    "trade-edge": ("エッジの見つけ方", "Nana"),
    "heidel-daily": ("HEIDEL BEERE 日次報告", "研究員"),
}

show, day, code = sys.argv[1], sys.argv[2], sys.argv[3]
dst_script, dst_desc, dst_topics = (Path(p) for p in sys.argv[4:7])
title, speaker = TITLES.get(show, (show, "Nana"))
headline, detail = WHY.get(code, WHY["other"])
d = _dt.datetime.strptime(day, "%Y-%m-%d")

script = "\n".join([
    f"{speaker}: おはようございます。{title}です。",
    f"{speaker}: 今日は{d.month}月{d.day}日。",
    "",
    f"{speaker}: 本日の配信は失敗しました。",
    f"{speaker}: 原因は、{headline}。",
    f"{speaker}: {detail}",
    "",
    f"{speaker}: 番組の記録そのものは残っています。",
    f"{speaker}: 復旧しだい、次の回で通常どおりお届けします。",
    f"{speaker}: 本日は、お知らせのみで失礼します。",
]) + "\n"

desc = "\n".join([
    f"【{title}】{d.month}/{d.day} 本日の配信は失敗しました",
    "",
    f"本日の配信は失敗しました。原因は{headline}。",
    detail,
    "",
    "この回は自動生成のお知らせです。復旧後の回で通常の内容に戻ります。",
    f"詳細は GitHub Actions の実行ログ (morning-radio / {day}) を確認してください。",
]) + "\n"

dst_script.write_text(script, encoding="utf-8")
dst_desc.write_text(desc, encoding="utf-8")
dst_topics.write_text(f"配信失敗 ({code}) ||| 失敗, {code}, {day}\n", encoding="utf-8")
print(f"失敗エピソードを作成: {show} {day} 理由={code} ({headline})")
