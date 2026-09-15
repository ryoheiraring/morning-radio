# -*- coding: utf-8 -*-
"""Claude に渡すプロンプトを組み立てる。
使い方: python3 build_prompt.py <番組ID> <YYYY-MM-DD> <出力先> [ダイジェスト.md]
  = prompts/<番組ID>.md の本文 + prompts/_common.md(字数を埋め込み) + 今日の日付 + 放送済みテーマ一覧
放送済みテーマ一覧は radio/<番組ID>/*/テーマ.txt(無ければ meta.json のタイトル)から全期間ぶん集める。
"""
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import shows  # noqa: E402

WEEKDAY_JA = ["月", "火", "水", "木", "金", "土", "日"]

show_id, day, out = sys.argv[1], sys.argv[2], Path(sys.argv[3])
digest = Path(sys.argv[4]) if len(sys.argv) > 4 else None
cfg = shows.load(show_id)
d = datetime.strptime(day, "%Y-%m-%d")
lo, hi = cfg["chars"]

common = (shows.PROMPTS / "_common.md").read_text(encoding="utf-8")
common = common.replace("{CHARS_LO}", f"{lo:,}").replace("{CHARS_HI}", f"{hi:,}")

past = []
for ep in sorted(Path(f"radio/{show_id}").glob("*/")):
    if not ep.is_dir() or ep.name.startswith("_"):
        continue
    t = ep / "テーマ.txt"
    if t.exists():
        for line in t.read_text(encoding="utf-8").splitlines():
            if "|||" in line:
                past.append(f"{ep.name}  {line.split('|||')[0].strip()}")
        continue
    m = ep / "meta.json"
    if m.exists():
        past.append(f"{ep.name}  {json.loads(m.read_text(encoding='utf-8')).get('title', '')}")

speakers = " / ".join(cfg["speakers"])
parts = [
    cfg["body"],
    "",
    common,
    "",
    "---",
    "",
    f"## 今日の放送情報",
    f"- 番組名: {cfg['title']}",
    f"- 放送日: {d.year}年{d.month}月{d.day}日({WEEKDAY_JA[d.weekday()]}曜日)",
    f"- この番組の話者: {speakers}(これ以外の話者タグは使わない)",
    f"- 読み上げ文字数: {lo:,}〜{hi:,}字",
    "",
    "## 放送済みテーマ一覧(これらは扱わない)",
]
if past:
    parts += [f"- {p}" for p in past[-300:]]
else:
    parts.append("(まだ放送はありません。第1回です)")
if digest and digest.exists():
    parts += ["", "---", "", "## 今日の素材(ダイジェスト)", "",
              "★ 台本の事実・数字はすべてこのダイジェストの範囲内で書くこと。無い項目は飛ばす。", "",
              digest.read_text(encoding="utf-8")]

out.parent.mkdir(parents=True, exist_ok=True)
out.write_text("\n".join(parts) + "\n", encoding="utf-8")
print(f"プロンプト作成: {out} ({len(past)}件の放送済みテーマを添付)")
