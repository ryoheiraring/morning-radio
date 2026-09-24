# -*- coding: utf-8 -*-
"""HEIDEL BEERE 日次報告 (radio/heidel-daily/report.md) を、そのまま読み上げ用の台本に整形する。

使い方: python3 build_heidel_daily.py <YYYY-MM-DD> <台本出力> <概要欄出力> <テーマ出力> [--last-chance]

この番組だけ Claude を使わない。研究員が書いた本文が唯一の正典で、ラジオ側は
**読み上げ用の整形だけ**を行い、内容は一切書き換えない:
  - 見出し記号 (#)・箇条書き記号・強調 (**)・リンク・コード記号を落とす
  - 「見返し用」以降 (--- 区切り) は読み上げず、概要欄(ショーノート)に回す
  - 段落ごとに「研究員: 」を付け、空行で間を作る。見出しは罫線コメントにして長めの間にする
  - 数字の丸め: 小数第3位以下の生の数値と、桁の多い数を読みやすい形にする(値は変えない)

report.md が今日ぶんでない (05:00 JST 以降に更新されていない) 場合:
  --last-chance なし … 何もせず exit 3 (本線・保険1 は静かに見送り、次の便で再確認)
  --last-chance あり … 「本日の報告は届いていません」の 1 分版を作って exit 0 (LINE 通知は呼び出し側)
"""
import datetime as _dt
import re
import sys
from pathlib import Path

JST = _dt.timezone(_dt.timedelta(hours=9))
REPORT = Path("radio/heidel-daily/report.md")
SPEAKER = "研究員"

day, dst_script, dst_desc, dst_topics = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
last_chance = "--last-chance" in sys.argv[5:]


def strip_marks(s: str) -> str:
    """読み上げに不要な記号だけを落とす(語は変えない)。"""
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)          # リンクは表示文だけ残す
    s = re.sub(r"https?://\S+", "", s)                        # 裸の URL は読まない
    s = s.replace("**", "").replace("`", "").replace("*", "")
    s = re.sub(r"^\s*[-–—•]\s*", "", s)                      # 行頭の箇条書き記号
    s = re.sub(r"[｜|]", "、", s)
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()


# 読み方だけを整える(語は変えない)。TTS が英字をそのまま読むと崩れるため
KANA = [("HEIDEL BEERE", "ハイデルベーレ"), ("Hyperliquid", "ハイパーリキッド"), ("Binance", "バイナンス"),
        ("Funding", "ファンディング"), ("API", "エーピーアイ"), ("AI", "エーアイ"), ("PSR", "ピーエスアール"),
        ("LINE", "ライン"), ("OI", "オーアイ"), ("DD", "ディーディー"), ("PC", "パソコン"),
        ("USD", "ドル"), ("BTC", "ビットコイン"), ("ETH", "イーサリアム"), ("HYPE", "ハイプ")]


def read_aloud(s: str) -> str:
    for a, b in KANA:
        s = re.sub(rf"(?<![A-Za-z]){re.escape(a)}(?![A-Za-z])", b, s)
    return s


def round_numbers(s: str) -> str:
    """値は変えずに読みやすくする: 小数は第1位まで、4桁以上の数に桁区切り。"""
    def _dec(m):
        v = float(m.group(0))
        return f"{v:.1f}".rstrip("0").rstrip(".") if abs(v) < 1000 else f"{v:,.0f}"
    s = re.sub(r"(?<![\d,.])\d+\.\d{2,}", _dec, s)            # 0.41666… → 0.4
    def _int(m):
        return f"{int(m.group(0)):,}"
    s = re.sub(r"(?<![\d,.])\d{5,}(?![\d,.])", _int, s)       # 12345 → 12,345
    return s


def to_script(body: str) -> str:
    out = []
    for raw in body.splitlines():
        line = raw.rstrip()
        if not line.strip():
            out.append("")
            continue
        m = re.match(r"^(#{1,6})\s*(.+)$", line.strip())
        if m:                                                  # 見出し → 罫線コメント(長めの間)＋読み上げ
            title = strip_marks(m.group(2))
            if m.group(1) == "#":                              # 文書タイトルは読まない
                continue
            out += ["", f"# ──{title}──", "", f"{SPEAKER}: {read_aloud(title)}。"]
            continue
        if re.fullmatch(r"[-=_]{3,}", line.strip()):
            continue
        if line.lstrip().startswith("|"):                      # 表は読み上げない(概要欄に残る)
            continue
        text = read_aloud(round_numbers(strip_marks(line)))
        if text:
            out.append(f"{SPEAKER}: {text}")
    # 連続する空行を 1 つにまとめる
    cleaned = []
    for ln in out:
        if ln == "" and (not cleaned or cleaned[-1] == ""):
            continue
        cleaned.append(ln)
    return "\n".join(cleaned).strip() + "\n"


def absent_script() -> tuple[str, str, str]:
    d = _dt.datetime.strptime(day, "%Y-%m-%d")
    s = "\n".join([
        f"{SPEAKER}: おはようございます。HEIDEL BEERE 研究員の日次報告です。",
        f"{SPEAKER}: 今日は{d.month}月{d.day}日。",
        "",
        f"{SPEAKER}: 本日の報告は届いていません。",
        f"{SPEAKER}: 研究員の締め処理が、朝の時点で報告書を出せませんでした。",
        f"{SPEAKER}: パソコン側が止まっているか、書き出しに失敗した可能性があります。",
        "",
        f"{SPEAKER}: 台帳と前向きの記録そのものは、いつもどおり残っています。",
        f"{SPEAKER}: 復旧しだい、翌朝の回で二日ぶんをまとめてお伝えします。",
        f"{SPEAKER}: 以上、本日は報告なしのお知らせでした。",
    ]) + "\n"
    desc = "\n".join([
        f"【HEIDEL BEERE 日次報告】{d.month}/{d.day} 本日の報告は届いていません",
        "",
        "研究員からの日次報告が、配信の時点で届きませんでした。",
        "パソコン側の締め処理 (run.cmd daily-report) が動いていない可能性があります。",
        "台帳と前向きの記録は残っており、復旧後の回で二日ぶんをまとめてお伝えします。",
    ]) + "\n"
    return s, desc, f"報告が届かなかった日 ||| 欠配, {day}\n"


raw = REPORT.read_text(encoding="utf-8") if REPORT.exists() else ""
fresh = bool(raw) and (day in raw.splitlines()[0] if raw.splitlines() else False)

if not fresh:
    if not last_chance:
        print(f"report.md が {day} ぶんではない (1行目: {raw.splitlines()[0] if raw else '(ファイルなし)'})。"
              "次の便で再確認するため、この回は作らない。")
        sys.exit(3)
    print("::warning::report.md が届いていないため「本日の報告は届いていません」版を配信する")
    script, desc, topics = absent_script()
    dst_script.write_text(script, encoding="utf-8")
    dst_desc.write_text(desc, encoding="utf-8")
    dst_topics.write_text(topics, encoding="utf-8")
    Path("work/absent.flag").write_text(day, encoding="utf-8")
    sys.exit(0)

# 本文 (読み上げ) と 見返し用 (ショーノート) に分ける
parts = re.split(r"\n---\n", raw, maxsplit=1)
body, notes = parts[0], (parts[1] if len(parts) > 1 else "")
script = to_script(body)
spoken = len(re.sub(r"\s", "", re.sub(r"^#.*$", "", script, flags=re.M)))
spoken -= len(SPEAKER + ":") * script.count(f"{SPEAKER}:")

title_src = ""
for ln in body.splitlines():
    if ln.startswith("## "):
        continue
    t = strip_marks(ln)
    if t and not t.startswith("#"):
        title_src = t
        break
d = _dt.datetime.strptime(day, "%Y-%m-%d")
title = f"【HEIDEL BEERE 日次報告】{d.month}/{d.day} 研究員より"
desc = "\n".join([
    title, "",
    "HEIDEL BEERE の研究員AIによる、直近24時間の締めの報告です。",
    "台本は研究員が書いた報告書そのままで、ラジオ側は読み上げ用の整形だけを行っています。",
    "", (notes.strip() or "(見返し用の記載はありません)"), "",
    "本番組は研究の進み具合の報告であり、投資助言ではありません。",
]) + "\n"

dst_script.write_text(script, encoding="utf-8")
dst_desc.write_text(desc, encoding="utf-8")
dst_topics.write_text(f"日次報告 {day} ||| 研究員, 日次報告, {day}\n", encoding="utf-8")
print(f"整形OK: 読み上げ {spoken}字 / 見返し用 {len(notes.strip())}字")
