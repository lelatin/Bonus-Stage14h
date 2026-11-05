#!/usr/bin/env python3
"""Lit sources.json (chaînes YouTube), récupère les dernières vidéos longues (hors Shorts) de chaque
chaîne via les flux Atom officiels de YouTube, et écrit data.json, lu par index.html.
Aucune dépendance externe, aucune clé d'API."""
import json, re, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

UA = {"User-Agent": "Mozilla/5.0 (compatible; bonusstage/2.0)", "Accept-Language": "fr-FR,fr;q=0.9",
      "Cookie": "CONSENT=YES+1; SOCS=CAI"}
PER_SOURCE = 12   # vidéos gardées par chaîne (modifiable par chaîne avec "count" dans sources.json)
MAX_TOTAL = 120   # nombre total de vidéos écrites dans data.json
NS = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015",
      "m": "http://search.yahoo.com/mrss/"}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
        return r.read()


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def channel_id(handle):
    """Retrouve l'identifiant UC… d'une chaîne à partir de son @pseudo."""
    page = get("https://www.youtube.com/@" + handle.lstrip("@")).decode("utf-8", "replace")
    for pat in (r'"externalId":"(UC[\w-]{22})"', r'rel="canonical" href="https://www\.youtube\.com/channel/(UC[\w-]{22})"',
                r'"channelId":"(UC[\w-]{22})"'):
        m = re.search(pat, page)
        if m:
            return m.group(1)
    raise ValueError("identifiant de chaîne introuvable pour @" + handle)


def read_channel(src, cid):
    # UULF… = playlist « vidéos » de la chaîne, sans les Shorts ni les directs
    urls = ["https://www.youtube.com/feeds/videos.xml?playlist_id=UULF" + cid[2:],
            "https://www.youtube.com/feeds/videos.xml?channel_id=" + cid]
    root = None
    for u in urls:
        try:
            root = ET.fromstring(get(u))
            break
        except Exception:
            continue
    if root is None:
        raise RuntimeError("flux illisible")
    out = []
    for e in root.findall("a:entry", NS):
        vid = e.findtext("yt:videoId", namespaces=NS)
        link = e.find("a:link", NS)
        if not vid or (link is not None and "/shorts/" in link.get("href", "")):
            continue
        stats = e.find("m:group/m:community/m:statistics", NS)
        views = int(stats.get("views")) if stats is not None and stats.get("views", "").isdigit() else None
        item = {"title": (e.findtext("a:title", namespaces=NS) or "").strip(),
                "link": "https://www.youtube.com/watch?v=" + vid,
                "date": e.findtext("a:published", namespaces=NS),
                "source": src["name"], "category": src.get("category", ""), "video": vid,
                "image": "https://i.ytimg.com/vi/%s/hq720.jpg" % vid}
        if views is not None:
            item["views"] = views
        out.append(item)
    out.sort(key=lambda a: a["date"] or "", reverse=True)
    return out[: src.get("count", PER_SOURCE)]


def main():
    sources, old = load("sources.json", []), load("data.json", {})
    ids = {s["name"]: s.get("channel_id") for s in old.get("sources", [])}
    articles, meta = [], []
    for src in sources:
        name, cid = src["name"], src.get("channel_id") or ids.get(src["name"])
        try:
            cid = cid or channel_id(src["handle"])
            items = read_channel(src, cid)
            print("OK  ", name, len(items))
        except Exception as ex:
            print("ERR ", name, ex)
            items = [a for a in old.get("articles", []) if a.get("source") == name]  # on garde l'ancien contenu
        articles += items
        meta.append({"name": name, "category": src.get("category", ""), "handle": src["handle"], "channel_id": cid, "url": "https://www.youtube.com/@" + src["handle"].lstrip("@")})
    seen, uniq = set(), []
    for a in sorted(articles, key=lambda a: a["date"] or "", reverse=True):
        if a["video"] not in seen:
            seen.add(a["video"]); uniq.append(a)
    data = {"updated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "sources": meta, "articles": uniq[:MAX_TOTAL]}
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(len(data["articles"]), "vidéos")


if __name__ == "__main__":
    main()
