# -*- coding: utf-8 -*-
"""radio/<番組ID>/*/meta.json から docs/<番組ID>/feed.xml(ポッドキャストRSS)を生成し、
docs/index.html(番組一覧ページ)と、無ければ docs/<番組ID>/artwork.png も作る。
使い方: python3 make_feed.py <番組ID>          … その番組のフィードを更新(+index.html を再生成)
        python3 make_feed.py --all             … 全番組
番組名・説明・カテゴリは prompts/<番組ID>.md の front matter から取る。
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parent))
import shows  # noqa: E402

JST = timezone(timedelta(hours=9))
repo = os.environ.get("GITHUB_REPOSITORY", "ryoheiraring/morning-radio")
owner, name = repo.split("/")
PAGES = f"https://{owner}.github.io/{name}"
AUTHOR = os.environ.get("PODCAST_AUTHOR", owner)
DAY_JA = {"mon": "月", "tue": "火", "wed": "水", "thu": "木", "fri": "金", "sat": "土", "sun": "日"}


def rfc2822(date_str: str, hour: int) -> str:
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(hour=hour, tzinfo=JST)
    return dt.strftime("%a, %d %b %Y %H:%M:%S %z")


def hms(sec: int) -> str:
    return f"{sec // 3600}:{sec % 3600 // 60:02d}:{sec % 60:02d}"


def days_label(days):
    if len(days) == 7:
        return "毎朝"
    return "毎週" + "・".join(DAY_JA.get(d, d) for d in days) + "曜"


def artwork(show_id: str, cfg: dict):
    """1400×1400 のアートワークを Pillow で作る(無ければ作らない。Pillow が無くても落ちない)"""
    out = Path(f"docs/{show_id}/artwork.png")
    if out.exists():
        return
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("Pillow が無いのでアートワークは作らない(後で pip install pillow して再実行すれば作られる)")
        return
    color = cfg.get("color", "#3f6fb5").lstrip("#")
    rgb = tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))
    img = Image.new("RGB", (1400, 1400), rgb)
    d = ImageDraw.Draw(img)
    # うっすら円を置いて単色より少しラジオらしく
    for r, a in ((900, 18), (700, 24), (500, 30)):
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(overlay).ellipse((700 - r, 700 - r, 700 + r, 700 + r), fill=(255, 255, 255, a))
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    d = ImageDraw.Draw(img)
    font = None
    for cand in ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
                 "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                 "C:/Windows/Fonts/meiryob.ttc", "C:/Windows/Fonts/YuGothB.ttc", "C:/Windows/Fonts/msgothic.ttc"):
        if Path(cand).exists():
            try:
                font = ImageFont.truetype(cand, 110)
                break
            except Exception:
                pass
    title = cfg["title"].split("〜")[0].strip()
    lines = [title[i:i + 7] for i in range(0, len(title), 7)][:3]
    if font:
        total_h = len(lines) * 140
        y = 700 - total_h // 2
        for ln in lines:
            w = d.textlength(ln, font=font)
            d.text(((1400 - w) / 2, y), ln, fill="white", font=font)
            y += 140
        small = ImageFont.truetype(font.path, 48)
        d.text((80, 1400 - 140), "AI RADIO / " + days_label(cfg["days"]), fill=(255, 255, 255), font=small)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, optimize=True)
    print(f"artwork 作成: {out}")


def build_feed(show_id: str):
    cfg = shows.load(show_id)
    episodes = [json.loads(p.read_text(encoding="utf-8"))
                for p in sorted(Path(f"radio/{show_id}").glob("*/meta.json"), reverse=True)]
    items = []
    for e in episodes:
        items.append(f"""    <item>
      <title>{escape(e["title"])}</title>
      <description>{escape(e["description"])}</description>
      <pubDate>{rfc2822(e["date"], cfg["pub_hour"])}</pubDate>
      <guid isPermaLink="false">{escape(e["url"])}</guid>
      <enclosure url="{escape(e["url"])}" length="{e["size_bytes"]}" type="audio/mpeg"/>
      <itunes:duration>{hms(e["duration_sec"])}</itunes:duration>
      <itunes:explicit>false</itunes:explicit>
    </item>""")
    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{escape(cfg["title"])}</title>
    <link>{PAGES}/</link>
    <description>{escape(cfg["description"])}</description>
    <language>ja</language>
    <atom:link href="{PAGES}/{show_id}/feed.xml" rel="self" type="application/rss+xml"/>
    <itunes:author>{escape(AUTHOR)}</itunes:author>
    <itunes:image href="{PAGES}/{show_id}/artwork.png"/>
    <itunes:category text="{escape(cfg["category"])}"/>
    <itunes:explicit>false</itunes:explicit>
{chr(10).join(items)}
  </channel>
</rss>
"""
    out = Path(f"docs/{show_id}/feed.xml")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(feed, encoding="utf-8")
    artwork(show_id, cfg)
    print(f"feed.xml 更新: {len(episodes)}エピソード → {out}")


def build_index():
    rows = []
    for sid in shows.all_ids():
        cfg = shows.load(sid)
        n = len(list(Path(f"radio/{sid}").glob("*/meta.json")))
        url = f"{PAGES}/{sid}/feed.xml"
        rows.append(f"""<div class="show">
  <img src="{sid}/artwork.png" alt="" onerror="this.style.visibility='hidden'">
  <div>
    <strong>{escape(cfg["title"])}</strong>({days_label(cfg["days"])}・{"／".join(cfg["speakers"])}・{n}回)<br>
    <small>{escape(cfg["description"])}</small><br>
    <code>{url}</code><br>
    <a class="btn" href="pktc://subscribe/{owner}.github.io/{name}/{sid}/feed.xml">Pocket Casts で登録</a>
    <a class="btn alt" href="{url}">RSS</a>
  </div>
</div>""")
    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>毎朝ラジオ</title>
<style>
  body {{ font-family: sans-serif; max-width: 680px; margin: 2rem auto; padding: 0 1rem; line-height: 1.7; color: #222; }}
  .show {{ display: flex; gap: 1rem; align-items: flex-start; margin: 1.5rem 0; }}
  .show img {{ width: 96px; height: 96px; border-radius: 12px; flex: none; }}
  code {{ background: #f0f0f0; padding: 2px 6px; border-radius: 4px; word-break: break-all; font-size: .85em; }}
  .btn {{ display: inline-block; margin: .5rem .3rem 0 0; padding: .5rem 1rem; background: #1a73e8; color: #fff; border-radius: 8px; text-decoration: none; font-weight: bold; font-size: .9em; }}
  .btn.alt {{ background: #666; }}
</style>
</head>
<body>
<h1>毎朝ラジオ</h1>
<p>AI が毎朝自動生成する 5 分のポッドキャスト。フィードURLをポッドキャストアプリに登録すると自動で届きます。</p>
{chr(10).join(rows)}
<p><small>台本は Claude、音声は AivisSpeech(Nana: morioki / Sou: fumifumi)。AI 生成のため誤りを含む可能性があります。</small></p>
</body>
</html>
"""
    Path("docs").mkdir(exist_ok=True)
    Path("docs/index.html").write_text(html, encoding="utf-8")
    Path("docs/.nojekyll").touch()
    print("index.html 更新")


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "--all"
    targets = shows.all_ids() if arg == "--all" else [arg]
    for sid in targets:
        build_feed(sid)
    build_index()
