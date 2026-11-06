#!/usr/bin/env python3
"""Lit sources.json (chaînes YouTube), récupère leurs dernières vidéos (hors Shorts) et écrit data.json, lu par index.html.

Deux méthodes :
  1. l'API officielle YouTube Data v3 (fiable depuis GitHub Actions), si la variable YOUTUBE_API_KEY est définie ;
  2. à défaut, les flux RSS de YouTube (gratuits, mais souvent bloqués ou instables depuis les serveurs GitHub).
Aucune dépendance externe."""
import email.utils, html, json, os, re, time, urllib.error, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
      "Accept-Language": "fr-FR,fr;q=0.9", "Cookie": "CONSENT=YES+1; SOCS=CAI"}
API_KEY = os.environ.get("YOUTUBE_API_KEY", "").strip()
PER_SOURCE = 10     # vidéos gardées par chaîne (modifiable par chaîne avec "count" dans sources.json)
MAX_TOTAL = 40      # nombre total de vidéos écrites dans data.json
NEWS_PER_SITE = 15  # articles gardés par site d'actualités (news_sources.json)
MIN_SECONDS = 180   # sous cette durée, on considère que c'est un Short (appliqué seulement si la playlist « sans Shorts » est indisponible)
NS = {"c": "http://purl.org/rss/1.0/modules/content/", "a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015", "m": "http://search.yahoo.com/mrss/"}


def get(url, tries=3):
    """Télécharge une URL ; réessaie avec une pause croissante."""
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
                return r.read()
        except Exception as ex:
            last = ex
            if isinstance(ex, urllib.error.HTTPError) and ex.code in (400, 401, 403) and "googleapis" in url:
                break  # clé invalide / quota : inutile de réessayer
            time.sleep(2 * (i + 1))
    raise last


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


# ---------- méthode 1 : API officielle ----------
def api(endpoint, **params):
    params["key"] = API_KEY
    try:
        return json.loads(get("https://www.googleapis.com/youtube/v3/%s?%s" % (endpoint, urllib.parse.urlencode(params)), tries=2))
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read())["error"]["message"]
        except Exception:
            detail = ""
        raise RuntimeError("API %s %s" % (e.code, detail))


def seconds(iso):
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 0
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return ((d * 24 + h) * 60 + mi) * 60 + s


def read_api(src, cid):
    ids, strict, errors = [], False, []
    for prefix in ("UULF", "UU"):  # UULF = vidéos sans Shorts ; UU = toutes les mises en ligne
        try:
            r = api("playlistItems", part="contentDetails", playlistId=prefix + cid[2:], maxResults=30)
        except RuntimeError as ex:
            errors.append("%s → %s" % (prefix, ex)); continue
        ids = [i["contentDetails"]["videoId"] for i in r.get("items", [])]
        if ids:
            strict = prefix == "UU"
            break
        errors.append(prefix + " → vide")
    if not ids:
        raise RuntimeError(" ; ".join(errors))
    out = []
    for x in api("videos", part="snippet,contentDetails,statistics", id=",".join(ids), maxResults=50).get("items", []):
        sn, dur = x["snippet"], seconds(x["contentDetails"].get("duration"))
        if sn.get("liveBroadcastContent") in ("live", "upcoming") or dur < (MIN_SECONDS if strict else 60):
            continue
        item = {"title": sn["title"].strip(), "link": "https://www.youtube.com/watch?v=" + x["id"], "date": sn["publishedAt"],
                "source": src["name"], "category": src.get("category", ""), "video": x["id"],
                "image": "https://i.ytimg.com/vi/%s/hq720.jpg" % x["id"], "duration": dur}
        views = x.get("statistics", {}).get("viewCount")
        if views:
            item["views"] = int(views)
        out.append(item)
    out.sort(key=lambda a: a["date"], reverse=True)
    return out[: src.get("count", PER_SOURCE)]


# ---------- méthode 2 : flux RSS ----------
def parse(root, src):
    out = []
    for e in root.findall("a:entry", NS):
        vid = e.findtext("yt:videoId", namespaces=NS)
        link = e.find("a:link", NS)
        if not vid or (link is not None and "/shorts/" in link.get("href", "")):
            continue
        stats = e.find("m:group/m:community/m:statistics", NS)
        item = {"title": (e.findtext("a:title", namespaces=NS) or "").strip(), "link": "https://www.youtube.com/watch?v=" + vid,
                "date": e.findtext("a:published", namespaces=NS), "source": src["name"], "category": src.get("category", ""),
                "video": vid, "image": "https://i.ytimg.com/vi/%s/hq720.jpg" % vid}
        if stats is not None and stats.get("views", "").isdigit():
            item["views"] = int(stats.get("views"))
        out.append(item)
    out.sort(key=lambda a: a["date"] or "", reverse=True)
    return out


def read_rss(src, cid):
    base = "https://www.youtube.com/feeds/videos.xml?"
    errors = []
    for u in (base + "playlist_id=UULF" + cid[2:], base + "playlist_id=UU" + cid[2:], base + "channel_id=" + cid):
        try:
            items = parse(ET.fromstring(get(u)), src)
        except Exception as ex:
            errors.append("%s → %s" % (u.split("=")[1][:6], ex)); continue
        if items:
            return items[: src.get("count", PER_SOURCE)]
        errors.append("%s → flux vide" % u.split("=")[1][:6])
    raise RuntimeError("RSS : " + " ; ".join(errors))


def resolve(handle):
    """Retrouve l'identifiant UC… d'une chaîne à partir de son @pseudo."""
    handle = handle.lstrip("@")
    if API_KEY:
        try:
            return api("channels", part="id", forHandle="@" + handle)["items"][0]["id"]
        except Exception:
            pass
    page = get("https://www.youtube.com/@" + handle).decode("utf-8", "replace")
    for pat in (r'"externalId":"(UC[\w-]{22})"', r'rel="canonical" href="https://www\.youtube\.com/channel/(UC[\w-]{22})"', r'"channelId":"(UC[\w-]{22})"'):
        m = re.search(pat, page)
        if m:
            return m.group(1)
    raise ValueError("identifiant introuvable pour @" + handle)


# ---------- actualités (flux RSS / Atom des sites) ----------
def clean(t):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", t or ""))).strip()


def iso(s):
    s = (s or "").strip()
    try:
        d = email.utils.parsedate_to_datetime(s)
    except Exception:
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return ""
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc).isoformat(timespec="seconds")


def parse_news(root, src):
    out = []
    for e in root.findall(".//item") or root.findall(".//a:entry", NS):
        title = clean(e.findtext("title") or e.findtext("a:title", namespaces=NS))
        link = (e.findtext("link") or "").strip()
        if not link:
            l = e.find("a:link", NS)
            link = l.get("href", "") if l is not None else ""
        date = iso(e.findtext("pubDate") or e.findtext("a:published", namespaces=NS) or e.findtext("a:updated", namespaces=NS)
                   or e.findtext("{http://purl.org/dc/elements/1.1/}date"))
        image = ""
        for tag in ("m:content", "m:thumbnail", "m:group/m:content"):
            x = e.find(tag, NS)
            if x is not None and x.get("url"):
                image = x.get("url"); break
        if not image:
            enc = e.find("enclosure")
            if enc is not None and enc.get("url") and "image" in (enc.get("type") or "image"):
                image = enc.get("url")
        if not image:
            m = re.search(r'<img[^>]+src=["\']([^"\']+)', (e.findtext("c:encoded", namespaces=NS) or "") + (e.findtext("description") or ""))
            image = m.group(1) if m else ""
        if title and link:
            out.append({"title": title, "link": link, "date": date, "source": src["name"], "image": image})
    out.sort(key=lambda a: a["date"] or "", reverse=True)
    return out


def discover(url):
    """Cherche les flux annoncés dans le <head> de la page d'accueil."""
    page = get(url).decode("utf-8", "replace")
    found = []
    for tag in re.findall(r"<link[^>]+>", page, re.I):
        if re.search(r"(rss|atom)\+xml", tag, re.I):
            m = re.search(r'href=["\']([^"\']+)', tag)
            if m:
                found.append(urllib.parse.urljoin(url, html.unescape(m.group(1))))
    return found


def read_news(src):
    errors, tried = [], set()
    candidates = list(src.get("feeds", []))
    for step in range(2):
        for u in candidates:
            if u in tried:
                continue
            tried.add(u)
            try:
                items = parse_news(ET.fromstring(get(u, tries=2)), src)
            except Exception as ex:
                errors.append("%s → %s" % (u, ex)); continue
            if items:
                return items[: src.get("count", NEWS_PER_SITE)]
            errors.append(u + " → flux vide")
        if step == 0:
            try:
                candidates = discover(src["url"])  # 2e tour : flux trouvés automatiquement
            except Exception as ex:
                errors.append("découverte → %s" % ex); break
    raise RuntimeError(" ; ".join(errors))


def main():
    sources, old = load("sources.json", []), load("data.json", {})
    ids = {s["name"]: s.get("channel_id") for s in old.get("sources", [])}
    print("Méthode :", "API YouTube" if API_KEY else "flux RSS (pas de clé YOUTUBE_API_KEY)")
    articles, meta, ok = [], [], 0
    for src in sources:
        name, cid = src["name"], src.get("channel_id") or ids.get(src["name"])
        try:
            cid = cid or resolve(src["handle"])
            try:
                items, how = (read_api(src, cid), "api") if API_KEY else (read_rss(src, cid), "rss")
            except Exception as ex:
                if not API_KEY:
                    raise
                print("     API en échec pour", name, "→", ex, "— essai en RSS")
                items, how = read_rss(src, cid), "rss"
            print("OK  ", name, len(items), "vidéos (%s)" % how)
            ok += 1
        except Exception as ex:
            print("ERR ", name, "→", ex)
            items = [a for a in old.get("articles", []) if a.get("source") == name]  # on garde l'ancien contenu
        articles += items
        meta.append({"name": name, "category": src.get("category", ""), "handle": src["handle"], "channel_id": cid,
                     "url": "https://www.youtube.com/@" + src["handle"].lstrip("@")})
        if not API_KEY:
            time.sleep(1)
    seen, uniq = set(), []
    for a in sorted(articles, key=lambda a: a["date"] or "", reverse=True):
        if a["video"] not in seen:
            seen.add(a["video"]); uniq.append(a)
    news, nmeta = [], []
    for src in load("news_sources.json", []):
        try:
            items = read_news(src)
            print("OK  ", src["name"], len(items), "articles")
        except Exception as ex:
            print("ERR ", src["name"], "→", ex)
            items = [a for a in old.get("news", []) if a.get("source") == src["name"]]  # on garde l'ancien contenu
        news += items
        nmeta.append({"name": src["name"], "url": src["url"]})
    data = {"updated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "sources": meta, "news_sources": nmeta,
            "articles": uniq[:MAX_TOTAL], "news": news}
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print("Résultat :", ok, "chaîne(s) lue(s) sur", len(sources), "—", len(data["articles"]), "vidéos")


if __name__ == "__main__":
    main()
