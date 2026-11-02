"""Write the latest YouTube videos into README.md between the YOUTUBE markers.

Same approach as the website (lib/youtube.ts): RSS feed first, then the
channel's public Videos tab when the feed is down. Shorts are skipped.
Standard library only.
"""
import datetime as dt
import html
import json
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET

CHANNEL_ID = "UCdq_o3VrzAfpifcNWoUgetA"
CHANNEL_URL = "https://www.youtube.com/@awdevrethought"
FEED_URL = f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}"
LIMIT = 3
PER_ROW = 3
README = os.path.join(os.path.dirname(__file__), "..", "..", "README.md")
START, END = "<!-- YOUTUBE:START -->", "<!-- YOUTUBE:END -->"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "en"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode()


def from_feed():
    ns = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}
    root = ET.fromstring(get(FEED_URL))
    videos = []
    for e in root.findall("a:entry", ns):
        link = e.find("a:link", ns).get("href", "")
        if "/shorts/" in link:
            continue
        videos.append({
            "id": e.findtext("yt:videoId", "", ns),
            "title": e.findtext("a:title", "Untitled", ns),
            "date": e.findtext("a:published", "", ns)[:10],
        })
    return videos


def find_lockups(node, out):
    if isinstance(node, list):
        for n in node:
            find_lockups(n, out)
    elif isinstance(node, dict):
        for k, v in node.items():
            if k == "lockupViewModel":
                out.append(v)
            else:
                find_lockups(v, out)
    return out


def relative_to_date(text):
    m = re.search(r"(\d+)\s*([a-z]+?)s?\s+ago", text, re.I)
    days = {
        "s": 0, "sec": 0, "second": 0, "m": 0, "min": 0, "minute": 0, "h": 0, "hr": 0, "hour": 0,
        "d": 1, "day": 1, "w": 7, "wk": 7, "week": 7, "mo": 30, "month": 30, "y": 365, "yr": 365, "year": 365,
    }
    if not m or m.group(2).lower() not in days:
        return ""
    return (dt.date.today() - dt.timedelta(days=int(m.group(1)) * days[m.group(2).lower()])).isoformat()


def from_videos_page():
    page = get(f"{CHANNEL_URL}/videos")
    m = re.search(r"var ytInitialData = (\{.*?\});</script>", page, re.S)
    if not m:
        raise RuntimeError("videos page had no data")
    videos = []
    for l in find_lockups(json.loads(m.group(1)), []):
        if not l.get("contentId") or l.get("contentType") != "LOCKUP_CONTENT_TYPE_VIDEO":
            continue
        meta = l.get("metadata", {}).get("lockupMetadataViewModel", {})
        rows = meta.get("metadata", {}).get("contentMetadataViewModel", {}).get("metadataRows", [])
        parts = [p.get("text", {}).get("content", "") for r in rows for p in r.get("metadataParts", [])]
        videos.append({
            "id": l["contentId"],
            "title": meta.get("title", {}).get("content", "Untitled"),
            "date": relative_to_date(next((t for t in parts if "ago" in t.lower()), "")),
        })
    return videos


def latest():
    for source in (from_feed, from_videos_page):
        try:
            videos = source()[:LIMIT]
            if videos:
                return videos
        except Exception as e:  # noqa: BLE001 - fall through to the next source
            print(f"{source.__name__} failed: {e}", file=sys.stderr)
    return []


def thumbnail(video_id):
    """Widescreen thumbnail when YouTube has one (no black bars), else the 16:9 medium one."""
    url = f"https://i.ytimg.com/vi/{video_id}/hq720.jpg"
    try:
        urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=15)
        return url
    except Exception:  # noqa: BLE001
        return f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg"


def render(videos):
    cells = []
    for v in videos:
        url = f"https://www.youtube.com/watch?v={v['id']}"
        title = html.escape(v["title"])
        date = f"<br/><code>{v['date'].replace('-', '.')}</code>" if v["date"] else ""
        cells.append(
            f'    <td width="33%" valign="top">\n'
            f'      <a href="{url}"><img src="{thumbnail(v["id"])}" alt="{title}" width="100%"/></a>\n'
            f'      <a href="{url}"><b>{title}</b></a>{date}\n'
            f'    </td>'
        )
    rows = ["  <tr>\n" + "\n".join(cells[i:i + PER_ROW]) + "\n  </tr>" for i in range(0, len(cells), PER_ROW)]
    return "<table>\n" + "\n".join(rows) + "\n</table>"


if __name__ == "__main__":
    videos = latest()
    if not videos:
        sys.exit("No videos found; README left unchanged")
    readme = open(README).read()
    if START not in readme or END not in readme:
        sys.exit("YOUTUBE markers not found in README.md")
    block = f"{START}\n{render(videos)}\n{END}"
    readme = re.sub(re.escape(START) + r".*?" + re.escape(END), lambda _: block, readme, flags=re.S)
    open(README, "w").write(readme)
    print(f"wrote {len(videos)} videos")
