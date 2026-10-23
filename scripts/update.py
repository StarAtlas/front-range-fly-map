#!/usr/bin/env python3
"""Refresh data/live.json from the Rocky Mountain Anglers and Front Range Anglers river reports.

Pulls only structured facts: report dates, Front Range Anglers' flow / water temp / clarity /
guide rating, and both shops' fly lists. If a page can't be fetched or parsed, that source keeps
its previous values, so a site redesign never blanks the map.

Usage:  python scripts/update.py            # writes data/live.json
        python scripts/update.py --dry-run  # prints the result instead
"""
import json, re, sys, time, datetime as dt
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "live.json"
UA = "FrontRangeFlyMap/1.0 (personal fishing map; checks once a day)"
PAUSE = 2  # seconds between requests, to be polite

RMA = {  # river key -> slug on rockymtanglers.com/river-reports/<slug>/
    "poudre": "cache-la-poudre-river", "bigt": "big-thompson-river", "rmnp": "rmnp-2",
    "stvrain": "st-vrain-2", "boulder": "boulder-creek", "sboulder": "south-boulder-creek",
    "clear": "clear-creek", "platte": "south-platte-river",
}
FRA = {  # river key -> slug on frontrangeanglers.com/pages/<slug>
    "bigt": "big-thompson-river", "rmnp": "rocky-mountain-national-park", "stvrain": "st-vrain-creek",
    "boulder": "boulder-creek", "sboulder": "south-boulder-creek", "clear": "clear-creek",
    "bear": "bear-creek",
}
RMA_URL = "https://rockymtanglers.com/river-reports/{}/"
FRA_URL = "https://frontrangeanglers.com/pages/{}"

# Common spellings in the reports -> the names the map uses
FIXES = [
    (r"\bMirco\b", "Micro"), (r"\bDuracel\b", "Duracell"), (r"\bGasonlina\b", "Gasolina"),
    (r"\bAutum\b", "Autumn"), (r"\bWooly\b", "Woolly"), (r"\bSkulpzilla\b", "Sculpzilla"),
    (r"\bPhe?a?sie T\b", "Pheasant Tail"), (r"\bPerdigone\b", "Perdigon"), (r"\bHares Ear\b", "Hare’s Ear"),
    (r"\bGriffiths\b", "Griffith’s"), (r"\bHippy\b", "Hippie"), (r"\bExtend Body\b", "Extended Body"),
    (r"\bJohn[’']s\b", "John"), (r"\bRS2s\b", "RS2"), (r"\bNymh\b", "Nymph"), (r"\bCheeseman\b", "Cheesman"),
    (r"\b2 Bit\b", "Two-Bit"), (r"\bJuans\b", "Juan’s"), (r"\bMayers\b", "Mayer’s"), (r"\bGuides Choice\b", "Guide’s Choice"),
]
STREAMER = re.compile(r"bugger|dungeon|gonga|sculpzilla|slump|sparkle minnow|thin mint|zonker|splendor|goldie|"
                      r"geisha|meat whistle|pocket dweller|envy|barely legal|rusty trombone", re.I)
SIZE = re.compile(r"#\s*(\d{1,3})\s*(?:[-–]\s*#?\s*(\d{1,3}))?")


def tidy(name):
    name = re.sub(r"\s+", " ", name).strip(" .;:-–")
    name = name.replace("'", "’")
    for pat, rep in FIXES:
        name = re.sub(pat, rep, name)
    return name[:1].upper() + name[1:] if name else name


def fetch(url):
    r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    return r.text


def page_text(html):
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript", "iframe"]):
        t.decompose()
    root = soup.find("main") or soup.body or soup
    text = root.get_text("\n")
    return re.sub(r"[ \t ]+", " ", text)


# ---------------- Rocky Mountain Anglers ----------------
def parse_rma(html):
    text = page_text(html)
    i = text.find("Recommended Flies")
    j = text.find("River Report", i if i >= 0 else 0)
    if i < 0 or j < 0:
        raise ValueError("RMA layout changed: headings not found")
    flies_txt = text[i + len("Recommended Flies"):j].replace("\n", " ")
    parts = re.split(r"\b(DRIES|DRY FLIES|NYMPHS|STREAMERS)\s*:", flies_txt, flags=re.I)
    flies = []
    for k in range(1, len(parts) - 1, 2):
        label = parts[k].lower()
        t = "d" if label.startswith("dr") else "s" if label.startswith("st") else "n"
        prev = None
        for raw in parts[k + 1].split(","):
            raw = raw.strip()
            if not raw:
                continue
            m = SIZE.search(raw)
            size = ""
            if m:
                size = m.group(1) + ("–" + m.group(2) if m.group(2) else "")
                raw = (raw[:m.start()] + raw[m.end():]).strip()
            name = tidy(raw)
            if not name:  # a size that drifted after a stray comma, e.g. "Flashback Pheasie T, #12-18"
                if prev is not None and not prev["z"]:
                    prev["z"] = size
                continue
            prev = {"n": name, "z": size, "t": t}
            flies.append(prev)
    report = text[j:j + 400]
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4}|\d{2})\b", report)
    if not m:
        raise ValueError("RMA report date not found")
    mo, day, yr = int(m.group(1)), int(m.group(2)), int(m.group(3))
    yr = yr + 2000 if yr < 100 else yr
    return {"iso": dt.date(yr, mo, day).isoformat(), "flies": flies}


# ---------------- Front Range Anglers ----------------
def split_list(s):
    items = [x.strip() for x in s.split(",") if x.strip()]
    out = []
    for n, it in enumerate(items):
        it = re.sub(r"^(and|&)\s+", "", it)
        it = re.sub(r"^(a|an)\s+", "", it)
        pair = re.match(r"^(.*\S)\s+Adult and Emerger$", it, re.I)  # "AR's BWO Adult and Emerger"
        if pair:
            out += [pair.group(1) + " Adult", pair.group(1) + " Emerger"]
            continue
        if n == len(items) - 1 and re.search(r"\s+and\s+", it):
            article = re.search(r"\s+and\s+an?\s+", it)
            a, b = re.split(r"\s+and\s+(?:an?\s+)?", it, maxsplit=1)
            if article or len(b.split()) > 1:  # "Remote Control and a RS-2", "Grumpy Frumpy and Chubby Chernobyl"
                out += [a, b]
                continue
        out.append(it)
    return [tidy(x) for x in out if tidy(x)]


def parse_fra(html):
    text = page_text(html)
    m = re.search(r"\b(\d{1,2})-(\d{1,2})-(20\d{2})\b", text)
    if not m:
        raise ValueError("FRA report date not found")
    iso = dt.date(int(m.group(3)), int(m.group(1)), int(m.group(2))).isoformat()
    flat = text.replace("\n", " ")
    dry = re.search(r"For (?:dry fly selection|dry flies|dries)\s*,?\s*(?:use|start with|try)\s+(.+?)\.(?:\s|$)", flat, re.I)
    sub = re.search(r"For (?:nymphs|subsurface[^,]*?)\s*,?\s*(?:use|start with|try)\s+(.+?)\.(?:\s|$)", flat, re.I)
    flies = []
    if dry:
        flies += [{"n": n, "z": "", "t": "d"} for n in split_list(dry.group(1))]
    if sub:
        flies += [{"n": n, "z": "", "t": "s" if STREAMER.search(n) else "n"} for n in split_list(sub.group(1))]

    def field(label):
        f = re.search(label + r"\s*:\s*([^\n]+)", text, re.I)
        return re.sub(r"\s+", " ", f.group(1)).strip(" -") if f else None

    rating = re.search(r"Guide Rating\s*(\d)\s*/\s*5", text)
    bits = [field("Flow Level"), field("Water Temperature"), field("Water Clarity"),
            f"guide rating {rating.group(1)}/5" if rating else None]
    gauge = " · ".join(b for b in bits if b)
    return {"iso": iso, "flies": flies, "gauge": gauge}


# ---------------- main ----------------
def main(dry_run=False):
    prev = json.loads(OUT.read_text()) if OUT.exists() else {"rivers": {}}
    rivers = prev.get("rivers", {})
    log = []
    jobs = [("RMA", rk, RMA_URL.format(s), parse_rma) for rk, s in RMA.items()] + \
           [("FRA", rk, FRA_URL.format(s), parse_fra) for rk, s in FRA.items()]
    for src, rk, url, parser in jobs:
        r = rivers.setdefault(rk, {"reports": [], "flies": {}, "gauge": []})
        old = next((x for x in r["reports"] if x["src"] == src), None)
        try:
            data = parser(fetch(url))
            if len(data["flies"]) < 5:
                raise ValueError(f"only {len(data['flies'])} flies parsed")
            if old and old.get("iso") and data["iso"] < old["iso"]:
                raise ValueError("page shows an older date than we already have")
            rep = {"src": src, "iso": data["iso"], "url": url, "ok": True}
            r["reports"] = [x for x in r["reports"] if x["src"] != src] + [rep]
            r["flies"][src] = data["flies"]
            if src == "FRA" and data.get("gauge"):
                r["gauge"] = [{"src": "FRA", "text": data["gauge"]}]
            log.append(f"ok    {src} {rk:9} {data['iso']}  {len(data['flies'])} flies")
        except Exception as e:  # keep last good data for this source
            if old:
                old["ok"] = False
            log.append(f"KEPT  {src} {rk:9} previous data ({e})")
        time.sleep(PAUSE)
    out = {"updated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "rivers": rivers}
    print("\n".join(log))
    if dry_run:
        print(json.dumps(out, indent=1, ensure_ascii=False)[:3000])
        return
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    if not any(l.startswith("ok") for l in log):
        sys.exit("No source updated; check the log above.")


if __name__ == "__main__":
    main(dry_run="--dry-run" in sys.argv)
