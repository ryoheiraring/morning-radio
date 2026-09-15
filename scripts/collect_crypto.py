# -*- coding: utf-8 -*-
"""暗号資産朝刊の素材(ダイジェスト)を集める。CoinGecko API(無料・キー不要)+公式RSS。標準ライブラリのみ。
使い方: python3 collect_crypto.py <出力digest.md> [鮮度=24(時間)]
方針:
  ・項目ごとに独立して取得し、取れなかった項目は「取得失敗」と書いて飛ばす(番組はある分だけで作る)
  ・ニュースは配信から <鮮度> 時間以内のものだけ(古い記事を今日の出来事として読まない)
  ・1項目も取れなければ exit 2(素材ゼロで台本を書かせない)
"""
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

JST = timezone(timedelta(hours=9))
NOW = datetime.now(JST)
out_path = sys.argv[1]
FRESH_H = int(sys.argv[2]) if len(sys.argv) > 2 else 24
UA = {"User-Agent": "Mozilla/5.0 (morning-radio digest bot)"}

COINS = ["bitcoin", "ethereum", "solana", "ripple", "binancecoin", "dogecoin", "cardano"]
NEWS_FEEDS = [
    ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
    ("Cointelegraph", "https://cointelegraph.com/rss"),
    ("The Block", "https://www.theblock.co/rss.xml"),
    ("Decrypt", "https://decrypt.co/feed"),
    ("CoinPost", "https://coinpost.jp/?feed=rss2"),
]
REG_WORDS = re.compile(
    r"SEC|CFTC|ETF|regulat|規制|金融庁|法案|bill\b|lawsuit|訴訟|court|裁判|ban\b|禁止|approv|承認|"
    r"Treasury|財務省|central bank|中央銀行|Fed\b|FRB|日銀|MiCA|stablecoin|ステーブルコイン|税|tax\b|"
    r"BlackRock|Fidelity|機関投資家|institution", re.I)

sections = []      # (見出し, 本文行リスト)
failed = []


def get(url, timeout=25):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()


def gj(url):
    return json.loads(get(url))


def fmt_usd(v):
    if v is None:
        return "不明"
    if v >= 1e12:
        return f"{v/1e12:.2f}兆ドル"
    if v >= 1e9:
        return f"{v/1e8:,.0f}億ドル"
    if v >= 1000:
        return f"{v:,.0f}ドル"
    return f"{v:.2f}ドル"


def pct(v):
    return "不明" if v is None else f"{v:+.1f}%"


# ── 1. 市況 ──────────────────────────────────────────────
try:
    lines = []
    mk = gj("https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids=" + ",".join(COINS)
            + "&order=market_cap_desc&price_change_percentage=24h,7d")
    for c in mk:
        lines.append(f"- {c['name']}({c['symbol'].upper()}): {fmt_usd(c['current_price'])} / "
                     f"24時間 {pct(c.get('price_change_percentage_24h_in_currency'))} / "
                     f"7日 {pct(c.get('price_change_percentage_7d_in_currency'))} / "
                     f"時価総額 {fmt_usd(c['market_cap'])}")
    try:
        g = gj("https://api.coingecko.com/api/v3/global")["data"]
        lines.append(f"- 暗号資産全体の時価総額: {fmt_usd(g['total_market_cap']['usd'])}"
                     f"(24時間 {pct(g.get('market_cap_change_percentage_24h_usd'))})、"
                     f"BTCドミナンス {g['market_cap_percentage']['btc']:.1f}%、ETH {g['market_cap_percentage']['eth']:.1f}%")
    except Exception as e:
        lines.append(f"- (全体時価総額は取得失敗: {e})")
    try:
        f = gj("https://api.alternative.me/fng/?limit=2")["data"]
        lines.append(f"- Fear & Greed 指数: {f[0]['value']}({f[0]['value_classification']})、"
                     f"前日 {f[1]['value']}({f[1]['value_classification']})")
    except Exception as e:
        lines.append(f"- (Fear & Greed は取得失敗: {e})")
    sections.append(("1. 市況(CoinGecko・取得時刻 " + NOW.strftime("%m/%d %H:%M JST") + ")", lines))
except Exception as e:
    failed.append(f"市況: {e}")

# ── 2. ニュース / 3. 規制・機関 ──────────────────────────
news, reg = [], []
feed_ok = 0
for name, url in NEWS_FEEDS:
    try:
        root = ET.fromstring(get(url))
        feed_ok += 1
        for it in root.iter("item"):
            title = (it.findtext("title") or "").strip()
            date_s = it.findtext("pubDate") or it.findtext("{http://purl.org/dc/elements/1.1/}date") or ""
            try:
                dt = parsedate_to_datetime(date_s)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            except Exception:
                try:
                    dt = datetime.fromisoformat(date_s.replace("Z", "+00:00"))
                except Exception:
                    continue
            age_h = (NOW - dt.astimezone(JST)).total_seconds() / 3600
            if not title or age_h > FRESH_H or age_h < -1:
                continue
            desc = re.sub(r"<[^>]+>", "", it.findtext("description") or "").strip()
            desc = re.sub(r"\s+", " ", desc)[:140]
            line = f"- [{age_h:.0f}時間前・{name}] {title}" + (f" — {desc}" if desc else "")
            (reg if REG_WORDS.search(title + " " + desc) else news).append((age_h, line))
    except Exception as e:
        failed.append(f"RSS {name}: {e}")
news.sort()
reg.sort()
if news:
    sections.append((f"2. 主要ニュース(直近{FRESH_H}時間・{len(news)}本)", [l for _, l in news[:25]]))
elif feed_ok:
    failed.append("ニュース: 鮮度内の記事が0本")
if reg:
    sections.append((f"3. 規制・政策・機関投資家(直近{FRESH_H}時間・{len(reg)}本)", [l for _, l in reg[:12]]))
else:
    failed.append("規制・機関: 該当記事なし(この項目は飛ばす)")

# ── 4. トレンド・値動き上位/下位 ─────────────────────────
try:
    lines = []
    top = gj("https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=100&page=1&price_change_percentage=24h")
    top = [c for c in top if c.get("price_change_percentage_24h") is not None]
    top.sort(key=lambda c: c["price_change_percentage_24h"], reverse=True)
    lines.append("- 時価総額上位100の24時間上昇: " + "、".join(
        f"{c['name']}({c['symbol'].upper()}) {pct(c['price_change_percentage_24h'])}" for c in top[:5]))
    lines.append("- 同・下落: " + "、".join(
        f"{c['name']}({c['symbol'].upper()}) {pct(c['price_change_percentage_24h'])}" for c in top[-5:][::-1]))
    try:
        tr = gj("https://api.coingecko.com/api/v3/search/trending")["coins"][:7]
        lines.append("- CoinGecko 検索トレンド: " + "、".join(
            f"{t['item']['name']}({t['item']['symbol']}" + (f"・時価総額{t['item']['market_cap_rank']}位" if t['item'].get('market_cap_rank') else "") + ")"
            for t in tr))
    except Exception as e:
        lines.append(f"- (検索トレンドは取得失敗: {e})")
    sections.append(("4. トレンド銘柄と値動き上位・下位(CoinGecko)", lines))
except Exception as e:
    failed.append(f"トレンド: {e}")

# ── 出力 ────────────────────────────────────────────────
head = [f"# 暗号資産ダイジェスト {NOW.strftime('%Y年%m月%d日 %H:%M')}(日本時間)", ""]
body = []
for title, lines in sections:
    body += [f"## {title}"] + lines + [""]
body.append("## 収集メモ")
if failed:
    body += ["⚠ 次の項目は取得できなかった/該当なしのため、台本ではその項目を飛ばすこと:"] + [f"- {f}" for f in failed]
else:
    body.append("全項目を取得できた。")
body.append("- 「5. 今日の見返しポイント」は素材ではなく、上の項目から台本側でまとめる")
open(out_path, "w", encoding="utf-8").write("\n".join(head + body) + "\n")
print(f"ダイジェスト: 取得 {len(sections)}項目 / 失敗 {len(failed)}件 → {out_path}")
for f in failed:
    print("  ⚠", f)
if not sections:
    print("素材が1項目も取れなかったので中止", file=sys.stderr)
    sys.exit(2)
