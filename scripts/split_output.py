# -*- coding: utf-8 -*-
"""Claudeの出力を 台本 / 概要欄 / テーマ台帳 に分割し、字数・話者タグ・タイトル長を検査する。
使い方: python3 split_output.py <claude出力> <台本> <概要欄> <テーマ出力> <最小字数> <最大字数> <許可する話者(空白区切り)> [厳格=1/0]
不合格なら <claude出力と同じフォルダ>/feedback.txt に修正指示を書き、exit 3。
字数は「#コメント行・話者タグ・空白を除いた、実際に読み上げられる文字数」で数える。
厳格=1(1回目)ではテーマ台帳が無いと作り直し、0(2回目以降)では警告だけにして放送を落とさない。
"""
import re
import sys
from pathlib import Path

src, dst_script, dst_desc, dst_topics = (Path(p) for p in sys.argv[1:5])
lo, hi = int(sys.argv[5]), int(sys.argv[6])
speakers = sys.argv[7].split()
strict = (sys.argv[8] if len(sys.argv) > 8 else "1") == "1"
text = src.read_text(encoding="utf-8")


def extract(name: str, required=True) -> str:
    m = re.search(rf"===\s*{name}ここから\s*===\s*\n(.*?)\n\s*===\s*{name}ここまで\s*===", text, re.S)
    if not m:
        if required:
            sys.exit(f"出力に『==={name}ここから===』〜『==={name}ここまで===』の区切りが見つからない")
        return ""
    body = m.group(1).strip()
    body = re.sub(r"^```[a-z]*\n|\n```$", "", body)  # 万一のコードフェンス除去
    return body + "\n"


script = extract("台本")
desc = extract("概要欄")
topics = extract("テーマ台帳", required=False)

# 全角コロン・スペース無し・行頭の空白も救済して「Name: 」に正規化する
tag = r"^\s*(" + "|".join(re.escape(s) for s in speakers) + r")\s*[:：]\s*"
fixed_lines = []
bad = []
for line in script.splitlines():
    if not line.strip():
        fixed_lines.append("")
        continue
    if line.lstrip().startswith("#"):
        fixed_lines.append(line.strip())
        continue
    m = re.match(tag, line)
    if not m:
        bad.append(line.strip())
        continue
    fixed_lines.append(f"{m.group(1)}: {line[m.end():].strip()}")
script = "\n".join(fixed_lines).strip() + "\n"

spoken = "\n".join(l for l in script.splitlines() if not l.startswith("#"))
spoken = re.sub(tag, "", spoken, flags=re.M)
chars = len(re.sub(r"\s", "", spoken))
title = desc.splitlines()[0].strip() if desc.strip() else ""
topic_lines = [l.strip() for l in topics.splitlines() if "|||" in l]
print(f"台本(読み上げ分) {chars}字 / タイトル {len(title)}字 / テーマ {len(topic_lines)}件: {title}")

problems = []
tags_hint = " / ".join(s + ": " for s in speakers)
if bad:
    problems.append(
        f"台本に話者タグの無い行が{len(bad)}行あった(例: {bad[0][:40]!r})。"
        f"台本の全行を {tags_hint} のどれかで始めること。"
    )
if not (lo <= chars <= hi):
    problems.append(
        f"台本の読み上げ文字数が{chars}字で、許容範囲({lo}〜{hi}字)の外だった。"
        f"{lo}〜{hi}字になるよう説明の深さ・具体例の数を調整して全体を作り直すこと。"
        "同じ話を言い換えて繰り返す水増しはしないこと。"
    )
if not title:
    problems.append("概要欄が空だった。1行目にタイトルを書くこと。")
elif len(title) > 40:
    problems.append(f"概要欄1行目のタイトルが{len(title)}字だった。40字以内に収めること。")
if not topic_lines:
    msg = ("テーマ台帳が読み取れなかった。『===テーマ台帳ここから===』〜『===テーマ台帳ここまで===』の中に"
           "『テーマ名 ||| キーワード1, キーワード2』の形で1行以上書くこと。")
    if strict:
        problems.append(msg)
    else:
        print("警告: " + msg, file=sys.stderr)
        topic_lines = [f"{title} ||| {title}"]

if problems:
    (src.parent / "feedback.txt").write_text("\n".join(problems) + "\n", encoding="utf-8")
    print("\n".join(problems), file=sys.stderr)
    sys.exit(3)

dst_script.write_text(script, encoding="utf-8")
dst_desc.write_text(desc, encoding="utf-8")
dst_topics.write_text("\n".join(topic_lines) + "\n", encoding="utf-8")
print("分割OK")
