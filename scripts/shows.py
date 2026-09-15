# -*- coding: utf-8 -*-
"""prompts/<番組ID>.md の front matter を読んで番組一覧を返す。
使い方:
  python3 shows.py matrix [YYYY-MM-DD]   … その日に放送する番組IDの JSON 配列(GitHub Actions の matrix 用)
  python3 shows.py all                    … 全番組IDの JSON 配列
  python3 shows.py get <番組ID> <キー>      … 設定値を1つ表示(配列は空白区切り)
  python3 shows.py json <番組ID>           … 設定を JSON で表示
front matter は YAML のごく単純な部分集合(key: value / key: [a, b] / "..." )だけを扱う。
外部ライブラリ不要。
"""
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

PROMPTS = Path(__file__).resolve().parent.parent / "prompts"
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DEFAULTS = {
    "title": "",
    "description": "",
    "speakers": ["Nana"],
    "days": DAYS,
    "chars": [1500, 2000],
    "category": "Education",
    "color": "#3f6fb5",
    "pub_hour": 6,
    "collector": "",      # 素材収集スクリプト(例: scripts/collect_crypto.py)。空なら収集なし
    "fresh_hours": 24,    # 収集スクリプトに渡す鮮度(時間)
}


def _value(raw: str):
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        items = [i.strip().strip('"').strip("'") for i in raw[1:-1].split(",")]
        items = [i for i in items if i]
        return [int(i) if re.fullmatch(r"-?\d+", i) else i for i in items]
    if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
        return raw[1:-1]
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    return raw


def split_front_matter(text: str):
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.S)
    if not m:
        return {}, text
    cfg = {}
    for line in m.group(1).splitlines():
        line = line.split(" #", 1)[0].rstrip()   # 行末コメント
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        cfg[k.strip()] = _value(v)
    return cfg, m.group(2)


def load(show: str) -> dict:
    path = PROMPTS / f"{show}.md"
    if not path.exists():
        raise SystemExit(f"prompts/{show}.md が無い")
    cfg, body = split_front_matter(path.read_text(encoding="utf-8"))
    out = dict(DEFAULTS)
    out.update(cfg)
    out["id"] = show
    out["body"] = body.strip()
    if isinstance(out["speakers"], str):
        out["speakers"] = [out["speakers"]]
    if isinstance(out["days"], str):
        out["days"] = [out["days"]]
    out["days"] = [str(d).lower()[:3] for d in out["days"]]
    if not out["title"]:
        raise SystemExit(f"prompts/{show}.md の front matter に title が無い")
    return out


def all_ids():
    ids = []
    for p in sorted(PROMPTS.glob("*.md")):
        if p.name.startswith("_") or p.name.lower() == "readme.md":
            continue
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", p.stem):
            print(f"警告: 番組IDに使えない名前なので無視: {p.name}(英小文字・数字・ハイフンのみ)", file=sys.stderr)
            continue
        ids.append(p.stem)
    return ids


def due(day: date):
    wd = DAYS[day.weekday()]
    return [s for s in all_ids() if wd in load(s)["days"]]


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "matrix":
        d = datetime.strptime(sys.argv[2], "%Y-%m-%d").date() if len(sys.argv) > 2 else date.today()
        print(json.dumps(due(d)))
    elif cmd == "all":
        print(json.dumps(all_ids()))
    elif cmd == "get":
        v = load(sys.argv[2])[sys.argv[3]]
        print(" ".join(str(x) for x in v) if isinstance(v, list) else v)
    elif cmd == "json":
        cfg = load(sys.argv[2])
        cfg.pop("body")
        print(json.dumps(cfg, ensure_ascii=False, indent=1))
    else:
        sys.exit(__doc__)
