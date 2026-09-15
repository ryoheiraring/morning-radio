# -*- coding: utf-8 -*-
"""暗号資産朝刊の素材(ダイジェスト)を集める。無料・キー不要の公開データのみ、標準ライブラリだけで動く。
使い方: python3 collect_crypto.py <出力digest.md> [鮮度=24(時間)]

項目(番組の構成に対応):
  1. 市況        CoinGecko(BTC/ETH/BNB/HYPE + 全体時価総額) + alternative.me(Fear & Greed)
  2. Binance     公式アナウンス API(新規上場 / 上場廃止 / アクティビティ(Launchpool・Alpha・HODLer) / 重要なお知らせ)
  3. Hyperliquid 公式 info API(出来高・HYPE・新規Perp=前回との差分) + DeFiLlama(手数料) + HypurrScan(HIP-3 Perp デプロイ)
  4. Web3ニュース 公式RSS(CoinDesk/Cointelegraph/The Block/Decrypt/CoinPost)。規制・ハッキング・資金調達・アップデートを優先
  5. 注目日程     FOMC(年間予定表) + Binance アナウンス内の今後の日付
方針:
  ・項目ごとに独立して取得し、取れなかった項目は「収集メモ」に書いて飛ばす(番組はある分だけで作る)
  ・ニュース・アナウンスは配信から <鮮度> 時間以内のものだけ
  ・pump.fun 系ミームコインの話題は除外
  ・1項目も取れなければ exit 2(素材ゼロで台本を書かせない)
新規Perp検出のため、Hyperliquid の銘柄一覧を radio/crypto-morning/_hl_universe.json に保存して翌朝と比較する。
"""
import json
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

JST = timezone(timedelta(hours=9))
NOW = datetime.now(JST)
out_path = sys.argv[1]
FRESH_H = int(sys.argv[2]) if len(sys.argv) > 2 else 24
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128 Safari/537.36",
      "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9"}
STATE = Path("radio/crypto-morning/_hl_universe.json")

COINS = ["bitcoin", "ethereum", "binancecoin", "hyperliquid"]
NEWS_FEEDS = [
    ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
    ("Cointelegraph", "https://cointelegraph.com/rss"),
    ("The Block", "https://www.theblock.co/rss.xml"),
    ("Decrypt", "https://decrypt.co/feed"),
    ("CoinPost", "https://coinpost.jp/?feed=rss2"),
]
# Web3ニュースの優先度付け(項目4)。ヒット数が多いほど上位
PRIORITY = {
    "規制": re.compile(r"SEC|CFTC|ETF|regulat|規制|金融庁|法案|bill\b|lawsuit|訴訟|court|裁判|ban\b|禁止|approv|承認|Treasury|MiCA|stablecoin|ステーブルコイン|tax\b|税制|Fed\b|FRB|日銀", re.I),
    "ハッキング": re.compile(r"hack|exploit|breach|drain|stolen|ハッキング|不正|流出|盗難|攻撃|脆弱性|rug", re.I),
    "資金調達": re.compile(r"rais(e|es|ed|ing)|funding round|series [a-c]|valuation|資金調達|調達|IPO|acqui|買収", re.I),
    "アップデート": re.compile(r"upgrade|mainnet|launch|hard fork|proposal|governance|v2|v3|アップグレード|メインネット|ハードフォーク|提案", re.I),
}
EXCLUDE = re.compile(r"pump\.?fun|pumpfun|pump fun|bonk\.fun|letsbonk", re.I)
FOMC_2026 = ["2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17", "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09"]  # 声明発表日(米国時間)

sections = []      # (見出し, 本文行リスト)
failed = []


def get(url, data=None, timeout=25, retries=3):
    """GET/POST。Binance などは同じ URL でも時々 400 を返すので少し待って再試行する"""
    last = None
    for i in range(retries):
        try:
            hdr = dict(UA)
            if data is not None:
                hdr["Content-Type"] = "application/json"
            req = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None, headers=hdr)
            return urllib.request.urlopen(req, timeout=timeout).read()
        except Exception as e:
            last = e
            time.sleep(2 + i * 2)
    raise last


def gj(url, data=None):
    return json.loads(get(url, data))


def fmt_usd(v):
    if v is None:
        return "不明"
    if v >= 1e12:
        return f"{v/1e12:.2f}兆ドル"
    if v >= 1e8:
        return f"{v/1e8:,.0f}億ドル"
    if v >= 1e6:
        return f"{v/1e4:,.0f}万ドル"
    if v >= 1000:
        return f"{v:,.0f}ドル"
    return f"{v:.2f}ドル"


def pct(v):
    return "不明" if v is None else f"{v:+.1f}%"


def age_hours(dt):
    return (NOW - dt.astimezone(JST)).total_seconds() / 3600


def fresh(dt):
    return -1 <= age_hours(dt) <= FRESH_H


# ── 1. 市況 ──────────────────────────────────────────────
try:
    lines = []
    mk = gj("https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids=" + ",".join(COINS)
            + "&order=market_cap_desc&price_change_percentage=24h,7d")
    for c in mk:
        lines.append(f"- {c['name']}({c['symbol'].upper()}): {fmt_usd(c['current_price'])} / "
                     f"24時間 {pct(c.get('price_change_percentage_24h_in_currency'))} / "
                     f"7日 {pct(c.get('price_change_percentage_7d_in_currency'))} / "
                     f"時価総額 {fmt_usd(c['market_cap'])}(順位{c.get('market_cap_rank')}) / "
                     f"24時間出来高 {fmt_usd(c.get('total_volume'))}")
    if not mk:
        raise RuntimeError("CoinGecko が空の応答")
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
    lines.append("- ※「なぜ動いたか」は、項目4のニュースや項目2・3の出来事の中に理由がある場合だけ結びつける。素材に理由が無ければ「はっきりした材料は見当たらない」と言う")
    sections.append((f"1. 市況(CoinGecko・取得時刻 {NOW.strftime('%m/%d %H:%M')} JST)", lines))
except Exception as e:
    failed.append(f"1. 市況: {e}")

# ── 2. Binance の動き ──────────────────────────────────────
BINANCE_CATS = [  # (catalogId, 表示名, pageSize, タイトル絞り込み)
    (48, "新規上場", 20, None),
    (161, "上場廃止", 10, None),
    (93, "Launchpool・Alpha・エアドロップ", 20, re.compile(r"Launchpool|Launchpad|Alpha|HODLer|Megadrop|Airdrop", re.I)),
    (49, "重要なお知らせ", 10, re.compile(r"Important|Notice|Update|Suspend|Support|Introduc|Launch|Will|Delist|Risk", re.I)),
]
binance_upcoming = []
try:
    lines = []
    got_any_cat = False
    for cat, label, size, pat in BINANCE_CATS:
        try:
            d = gj(f"https://www.binance.com/bapi/composite/v1/public/cms/article/list/query?type=1&pageNo=1&pageSize={size}&catalogId={cat}")
            got_any_cat = True
            arts = []
            for c in d["data"]["catalogs"]:
                for a in c["articles"]:
                    dt = datetime.fromtimestamp(a["releaseDate"] / 1000, tz=timezone.utc)
                    title = a["title"].strip()
                    if not fresh(dt) or EXCLUDE.search(title):
                        continue
                    if pat and not pat.search(title):
                        continue
                    arts.append((age_hours(dt), title))
                    for m in re.finditer(r"(20\d\d-\d\d-\d\d)", title):   # 今後の日付は項目5の候補にも
                        try:
                            dd = date.fromisoformat(m.group(1))
                            if 0 <= (dd - NOW.date()).days <= 7:
                                binance_upcoming.append((dd, f"Binance: {title}"))
                        except ValueError:
                            pass
            arts.sort()
            if arts:
                lines.append(f"### {label}({len(arts)}件)")
                lines += [f"- [{h:.0f}時間前] {t}" for h, t in arts[:8]]
            else:
                lines.append(f"### {label}: 直近{FRESH_H}時間の該当なし")
        except Exception as e:
            lines.append(f"### {label}: 取得失敗({e})")
        time.sleep(1.5)
    if not got_any_cat:
        raise RuntimeError("Binance アナウンス API に全カテゴリで失敗")
    if any(l.startswith("- ") for l in lines):
        lines.append("- ※ Alpha は Binance Alpha(取引所内の早期銘柄枠)。Launchpool は BNB 等を預けて新トークンを得る仕組み。台本では初出時に一言説明")
        sections.append(("2. Binance の動き(公式アナウンス)", lines))
    else:
        failed.append(f"2. Binance: 直近{FRESH_H}時間に該当するアナウンスなし(この項目は飛ばす)")
except Exception as e:
    failed.append(f"2. Binance: {e}")

# ── 3. Hyperliquid の動き ──────────────────────────────────
try:
    lines = []
    meta, ctxs = gj("https://api.hyperliquid.xyz/info", {"type": "metaAndAssetCtxs"})
    universe = [u["name"] for u in meta["universe"]]                       # ctxs と同じ並び
    listed = [u["name"] for u in meta["universe"] if not u.get("isDelisted")]
    vol = sum(float(c["dayNtlVlm"]) for c in ctxs)
    oi = sum(float(c["openInterest"]) * float(c["markPx"]) for c in ctxs if c.get("openInterest"))
    lines.append(f"- 全 Perp の24時間出来高: {fmt_usd(vol)} / 建玉(OI)合計: {fmt_usd(oi)} / 上場 Perp 数: {len(listed)}")
    top = sorted(zip(universe, ctxs), key=lambda x: float(x[1]["dayNtlVlm"]), reverse=True)[:5]
    lines.append("- 出来高上位: " + "、".join(f"{n} {fmt_usd(float(c['dayNtlVlm']))}" for n, c in top))
    hype = next((c for n, c in zip(universe, ctxs) if n == "HYPE"), None)
    if hype:
        chg = (float(hype["markPx"]) / float(hype["prevDayPx"]) - 1) * 100
        lines.append(f"- HYPE(Hyperliquid の独自トークン): {float(hype['markPx']):.2f}ドル / 24時間 {chg:+.1f}% / "
                     f"HYPE Perp 出来高 {fmt_usd(float(hype['dayNtlVlm']))} / 資金調達率(8時間) {float(hype['funding'])*100:+.4f}%")
    # 新規 Perp = 前回保存した銘柄一覧との差分
    prev = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else None
    if prev is None:
        lines.append("- 新規 Perp 上場: (初回のため前回比較なし。今日から記録を開始)")
    else:
        new = [n for n in listed if n not in set(prev.get("universe", []))]
        gone = [n for n in prev.get("universe", []) if n not in set(listed)]
        lines.append(f"- 新規 Perp 上場(前回 {prev.get('date')} 以降): " + ("、".join(new) if new else "なし")
                     + (f" / 上場廃止: {'、'.join(gone)}" if gone else ""))
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({"date": NOW.strftime("%Y-%m-%d"), "universe": listed}, ensure_ascii=False), encoding="utf-8")
    # 手数料(DeFiLlama・無料枠)
    try:
        fz = gj("https://api.llama.fi/summary/fees/hyperliquid?dataType=dailyFees")
        lines.append(f"- プロトコル手数料(DeFiLlama): 直近24時間 {fmt_usd(fz.get('total24h'))}、その前の24時間 {fmt_usd(fz.get('total48hto24h'))}"
                     f"(前日比 {pct(fz.get('change_1d'))})、直近7日 {fmt_usd(fz.get('total7d'))}")
    except Exception as e:
        lines.append(f"- (手数料は取得失敗: {e})")
    # HIP-3 の Perp デプロイ(HypurrScan)
    try:
        pa = gj("https://api.hypurrscan.io/pastAuctionsPerp")
        recent = []
        for a in pa:
            dt = datetime.fromtimestamp(a["time"] / 1000, tz=timezone.utc)
            if fresh(dt) and not a.get("error"):
                coin = a["action"].get("registerAsset", {}).get("assetRequest", {}).get("coin", "?")
                dex = a["action"].get("registerAsset", {}).get("dex", "")
                recent.append(f"{coin}({dex} dex)")
        lines.append("- HIP-3(誰でも Perp 市場を作れる仕組み)の新規デプロイ(HypurrScan): " + ("、".join(recent) if recent else "直近24時間なし"))
    except Exception as e:
        lines.append(f"- (HIP-3 デプロイは取得失敗: {e})")
    lines.append("- 大口清算: 無料の公開データ源が無いため未収集(素材に無いので台本では触れない)")
    lines.append("- HIP 提案・ガバナンス: 公開 API が無いため、項目4のニュースに出た場合のみ扱う")
    sections.append(("3. Hyperliquid の動き(公式 API・DeFiLlama・HypurrScan)", lines))
except Exception as e:
    failed.append(f"3. Hyperliquid: {e}")

# ── 4. Web3 ニュース ───────────────────────────────────────
items = []
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
            if not title or not fresh(dt):
                continue
            desc = re.sub(r"<[^>]+>", "", it.findtext("description") or "").strip()
            desc = re.sub(r"\s+", " ", desc)[:140]
            blob = title + " " + desc
            if EXCLUDE.search(blob):
                continue
            tags = [k for k, p in PRIORITY.items() if p.search(blob)]
            items.append((-len(tags), age_hours(dt), f"- [{age_hours(dt):.0f}時間前・{name}]"
                          + (f"【{'/'.join(tags)}】" if tags else "") + f" {title}" + (f" — {desc}" if desc else "")))
    except Exception as e:
        failed.append(f"4. RSS {name}: {e}")
items.sort()
if items:
    lines = [l for _, _, l in items[:20]]
    lines.append("- ※【】は機械的な分類。この中から重要度の高い3本を選ぶ(規制・ハッキング・大型資金調達・主要プロトコルのアップデートを優先)")
    sections.append((f"4. Web3 ニュース候補(直近{FRESH_H}時間・{len(items)}本、優先度順)", lines))
elif feed_ok:
    failed.append("4. Web3ニュース: 鮮度内の記事が0本")

# ── 5. 注目日程 ────────────────────────────────────────────
try:
    lines = []
    for d in FOMC_2026:
        dd = date.fromisoformat(d)
        delta = (dd - NOW.date()).days
        if 0 <= delta <= 7:
            when = "【今日】" if delta == 0 else f"(あと{delta}日)"
            lines.append(f"- FOMC(米連邦公開市場委員会)の政策発表: {dd.month}月{dd.day}日(米国時間・日本では翌日未明){when}")
            break
    for dd, t in sorted(set(binance_upcoming)):
        lines.append(f"- {dd.month}月{dd.day}日: {t}")
    if lines:
        lines.append("- ※ トークンのアンロック日程は無料の公開データ源が無いため未収集。ニュースに出た場合のみ扱う")
        sections.append(("5. 今後7日の注目日程(候補)", lines))
    else:
        failed.append("5. 注目日程: 7日以内の該当なし(項目4のニュースから注目点を1つ選ぶ)")
except Exception as e:
    failed.append(f"5. 注目日程: {e}")

# ── 出力 ────────────────────────────────────────────────
head = [f"# 暗号資産ダイジェスト {NOW.strftime('%Y年%m月%d日 %H:%M')}(日本時間)", ""]
body = []
for title, lines in sections:
    body += [f"## {title}"] + lines + [""]
body.append("## 収集メモ")
if failed:
    body += ["⚠ 次の項目は取得できなかった/該当なしのため、台本ではその項目を飛ばす(一言添えて次へ):"] + [f"- {f}" for f in failed]
else:
    body.append("全項目を取得できた。")
body.append("- 「見返し用の数字3つ」は素材ではなく、上の項目から台本側でまとめる")
Path(out_path).write_text("\n".join(head + body) + "\n", encoding="utf-8")
print(f"ダイジェスト: 取得 {len(sections)}項目 / 失敗・該当なし {len(failed)}件 → {out_path}")
for f in failed:
    print("  ⚠", f)
if not sections:
    print("素材が1項目も取れなかったので中止", file=sys.stderr)
    sys.exit(2)
