#!/usr/bin/env python3
"""Lit sources.json, récupère les derniers articles de chaque site (via son flux RSS/Atom)
et écrit data.json, lu par index.html. Aucune dépendance externe."""
import json, re, html, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

UA = {"User-Agent": "Mozilla/5.0 (compatible; hebdo14h/1.0)"}
PER_SOURCE = 10   # articles gardés par site (modifiable par site avec "count" dans sources.json)
OG_LIMIT = 10     # nb max de pages ouvertes par site pour trouver une image


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
        return r.read()


def find_feed(src):
    """Utilise 'feed' s'il est donné, sinon le détecte depuis la page d'accueil."""
    if src.get("feed"):
        return src["feed"]
    site = src["site"]
    try:
        page = get(site).decode("utf-8", "replace")
        for tag in re.findall(r"<link[^>]+>", page, re.I):
            if re.search(r"alternate", tag, re.I) and re.search(r"(rss|atom)\+xml", tag, re.I):
                h = re.search(r'href=["\']([^"\']+)', tag)
                if h:
                    return urllib.parse.urljoin(site, html.unescape(h.group(1)))
    except Exception:
        pass
    for p in ("/feed/", "/feed", "/rss", "/rss.xml", "/feed.xml", "/spip.php?page=backend"):
        try:
            head = get(urllib.parse.urljoin(site, p))[:2000].decode("utf-8", "replace")
            if "<rss" in head or "<feed" in head:
                return urllib.parse.urljoin(site, p)
        except Exception:
            continue
    raise RuntimeError("aucun flux trouvé (ajoute \"feed\": \"URL\" dans sources.json)")


def name(e):
    return e.tag.split("}")[-1]


def text(e):
    return (e.text or "").strip() if e is not None else ""


def parse_date(s):
    for f in (parsedate_to_datetime, lambda x: datetime.fromisoformat(x.replace("Z", "+00:00"))):
        try:
            d = f(s)
            return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)
        except Exception:
            pass
    return datetime.now(timezone.utc)


def og_image(url):
    try:
        page = get(url).decode("utf-8", "replace")[:200000]
        m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', page, re.I) \
            or re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image', page, re.I)
        return html.unescape(m.group(1)) if m else ""
    except Exception:
        return ""


def read_feed(src):
    root = ET.fromstring(get(find_feed(src)))
    out, og_used = [], 0
    for it in [e for e in root.iter() if name(e) in ("item", "entry")][:src.get("count", PER_SOURCE)]:
        title = link = date = img = body = ""
        cats = []
        for c in it:
            n = name(c)
            if n == "title":
                title = html.unescape(re.sub(r"<[^>]+>", "", text(c) or "".join(c.itertext()))).strip()
            elif n == "link":
                if c.get("rel") == "enclosure" and "image" in (c.get("type") or ""):
                    img = img or c.get("href", "")
                elif c.get("href") and c.get("rel", "alternate") == "alternate":
                    link = c.get("href")
                elif text(c):
                    link = text(c)
            elif n in ("pubDate", "published", "updated", "date"):
                date = date or text(c)
            elif n == "category":
                cats.append(html.unescape(c.get("term") or text(c)))
            elif n in ("thumbnail", "content", "enclosure") and c.get("url") and \
                    (n == "thumbnail" or "image" in (c.get("type") or c.get("medium") or "image")):
                img = img or c.get("url")
            elif n in ("encoded", "description", "summary", "content"):
                body += "".join(c.itertext())
        if not img:
            m = re.search(r'<img[^>]+src=["\']([^"\']+)', html.unescape(body), re.I)
            img = m.group(1) if m else ""
        if not img and og_used < OG_LIMIT and link:
            og_used += 1
            img = og_image(link)
        if title and link:
            cat = next((c.strip() for c in cats if c.strip()), "Actu")
            out.append({"title": title, "link": link, "image": urllib.parse.urljoin(link, img) if img else "",
                        "date": parse_date(date).isoformat(), "source": src["name"],
                        "category": cat[:1].upper() + cat[1:]})
    return out


HEBDO = {"channel": "https://www.youtube.com/@Origatube", "channel_id": "", "match": "hebdo"}  # mot recherché dans le titre des vidéos


def read_hebdo(previous):
    """Dernière vidéo "L'HEBDO" d'Origami. Si aucune plus récente n'est trouvée, on garde la précédente."""
    try:
        cid = HEBDO["channel_id"]
        if not cid:
            req = urllib.request.Request(HEBDO["channel"], headers={**UA, "Cookie": "CONSENT=YES+1", "Accept-Language": "fr-FR,fr;q=0.9"})
            page = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace")
            m = re.search(r'"(?:channelId|externalId|browseId)":"(UC[\w-]{22})"', page) or re.search(r"channel/(UC[\w-]{22})", page)
            cid = m.group(1)
        feed = ET.fromstring(get("https://www.youtube.com/feeds/videos.xml?channel_id=" + cid))
        vids = []
        for e in feed:
            if name(e) != "entry":
                continue
            d = {name(c): text(c) for c in e}
            if d.get("videoId") and d.get("title"):
                vids.append({"id": d["videoId"], "title": d["title"], "date": parse_date(d.get("published", "")).isoformat(),
                             "link": "https://www.youtube.com/watch?v=" + d["videoId"]})
        picks = [v for v in vids if HEBDO["match"] in v["title"].lower()]
        if picks:
            best = max(picks, key=lambda v: v["date"])
            if not previous or best["date"] > previous["date"]:
                return best
        return previous or (vids[0] if vids else None)
    except Exception as e:
        print("L'HEBDO: ÉCHEC –", e)
        return previous


def main():
    sources = json.load(open("sources.json", encoding="utf-8"))
    articles, seen = [], set()
    for s in sources:
        try:
            got = read_feed(s)
            print(f"{s['name']}: {len(got)} articles")
            for a in got:
                if a["link"] not in seen:
                    seen.add(a["link"])
                    articles.append(a)
        except Exception as e:
            print(f"{s['name']}: ÉCHEC – {e}")
    articles.sort(key=lambda a: a["date"], reverse=True)
    try:
        previous = json.load(open("data.json", encoding="utf-8")).get("hebdo")
    except Exception:
        previous = None
    hebdo = read_hebdo(previous)
    json.dump({"updated": datetime.now(timezone.utc).isoformat(),
               "sources": [{"name": s["name"], "color": s.get("color", "#334155")} for s in sources],
               "hebdo": hebdo, "articles": articles}, open("data.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
