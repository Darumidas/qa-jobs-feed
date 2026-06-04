"""
QA Jobs RSS Feed Generator — Jose Baños Arroyo
Fuentes: RemoteOK, Remotive, Arbeitnow, WeWorkRemotely
Output: feed.xml (RSS 2.0) → publicado en GitHub Pages
"""

import requests
import feedparser
import json
import re
from datetime import datetime, timezone
from email.utils import formatdate
import time
import html
import os

# ── KEYWORDS a buscar (case insensitive) ─────────────────────
KEYWORDS = [
    # Col A — Sogeti titles
    "test lead", "qa lead", "test automation lead", "senior qa engineer",
    "senior test engineer", "qa tech lead", "test manager", "qa manager",
    "scrum master", "delivery manager", "agile lead", "engineering manager",
    "quality lead", "test delivery lead", "agile coach",
    # Col C — Sopra titles
    "qa automation engineer", "test automation engineer", "qa engineer",
    "software test engineer", "quality engineer", "quality manager",
    "release manager", "sdet",
    # Variantes generales
    "senior qa", "lead qa", "head of qa", "head of quality", "principal qa",
    "staff qa", "staff test", "qa automation lead", "senior sdet"
]

KEYWORDS_BROAD = [
    "qa", "quality assurance", "test", "sdet", "scrum", "agile",
    "automation engineer", "delivery manager", "product owner",
    "engineering manager", "agile coach", "release manager"
]

EXCLUDE = ["junior", "intern", "graduate", "entry level", "entry-level", "trainee"]

# Ubicaciones aceptadas: remote o Madrid/España
LOCATIONS_OK  = ["remote", "worldwide", "anywhere", "global", "madrid", "spain", "españa", "distributed"]
# Ciudades/países a descartar si la oferta no dice remote
LOCATIONS_BAD = [
    "berlin", "munich", "münchen", "hamburg", "frankfurt", "cologne", "köln", "germany", "deutschland",
    "paris", "france", "amsterdam", "netherlands", "zürich", "zurich", "switzerland",
    "london", "united kingdom", "uk only", "new york", "san francisco", "toronto",
    "on-site", "onsite", "in-office", "office only"
]

def location_ok(location: str, description: str = "") -> bool:
    """Devuelve True si la oferta es remota o está en Madrid/España."""
    loc = (location + " " + description[:500]).lower()
    # Si menciona una ubicación buena → OK
    if any(l in loc for l in LOCATIONS_OK):
        return True
    # Si menciona una ubicación mala sin remote → descarta
    if any(l in loc for l in LOCATIONS_BAD):
        return False
    # Sin info de ubicación → aceptar (la mayoría son remote)
    return True

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; JobFeedBot/1.0; +https://github.com/jbanos093/qa-jobs-feed)"
}

def matches(title: str, description: str = "", broad: bool = False) -> bool:
    text = (title + " " + description).lower()
    if any(ex in text for ex in EXCLUDE):
        return False
    kw_list = KEYWORDS_BROAD if broad else KEYWORDS
    return any(kw in text for kw in kw_list)

def clean(text: str) -> str:
    text = re.sub(r'<[^>]+>', ' ', text or '')
    text = re.sub(r'\s+', ' ', text).strip()
    return html.escape(text[:400]) + ("..." if len(text) > 400 else "")

def rss_date(dt=None) -> str:
    if dt is None:
        return formatdate(usegmt=True)
    if isinstance(dt, (int, float)):
        return formatdate(float(dt), usegmt=True)
    if isinstance(dt, str) and dt:
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(dt[:19], fmt).replace(tzinfo=timezone.utc)
                return formatdate(dt.timestamp(), usegmt=True)
            except ValueError:
                continue
    if isinstance(dt, datetime):
        return formatdate(dt.timestamp(), usegmt=True)
    return formatdate(usegmt=True)

# ── FUENTES ──────────────────────────────────────────────────

def fetch_remoteok(broad=False) -> list:
    # RemoteOK = 100% remote por definición, no hace falta filtrar ubicación
    jobs = []
    try:
        r = requests.get("https://remoteok.com/api", headers=HEADERS, timeout=15)
        data = r.json()
        for job in data:
            if not isinstance(job, dict) or not job.get("position"):
                continue
            title = job.get("position", "")
            if not matches(title, " ".join(job.get("tags", [])), broad):
                continue
            jobs.append({
                "title": f"{title} — {job.get('company', '')}",
                "link": job.get("url", f"https://remoteok.com/remote-jobs/{job.get('id','')}"),
                "desc": clean(job.get("description", "")),
                "date": job.get("date", ""),
                "source": "RemoteOK 🌐",
                "guid": f"remoteok-{job.get('id', title)}"
            })
    except Exception as e:
        print(f"[RemoteOK] Error: {e}")
    return jobs

def fetch_remotive(broad=False) -> list:
    # Remotive = 100% remote
    jobs = []
    try:
        r = requests.get(
            "https://remotive.com/api/remote-jobs?category=software-dev&limit=100",
            headers=HEADERS, timeout=15
        )
        data = r.json().get("jobs", [])
        for job in data:
            title = job.get("title", "")
            if not matches(title, job.get("candidate_required_location", ""), broad):
                continue
            jobs.append({
                "title": f"{title} — {job.get('company_name', '')}",
                "link": job.get("url", ""),
                "desc": clean(job.get("description", "")),
                "date": job.get("publication_date", ""),
                "source": "Remotive 🌐",
                "guid": f"remotive-{job.get('id', title)}"
            })
    except Exception as e:
        print(f"[Remotive] Error: {e}")
    return jobs

def fetch_arbeitnow(broad=False) -> list:
    # Arbeitnow mezcla remote y presencial → filtrar por ubicación
    jobs = []
    try:
        r = requests.get(
            "https://arbeitnow.com/api/job-board-api",
            headers=HEADERS, timeout=15
        )
        data = r.json().get("data", [])
        for job in data:
            title = job.get("title", "")
            if not matches(title, job.get("description", ""), broad):
                continue
            loc = job.get("location", "")
            is_remote = job.get("remote", False)
            if not is_remote and not location_ok(loc, job.get("description", "")):
                continue
            loc_label = "🌐 Remote" if is_remote else f"📍 {loc}"
            jobs.append({
                "title": f"{title} — {job.get('company_name', '')} [{loc_label}]",
                "link": job.get("url", ""),
                "desc": clean(job.get("description", "")),
                "date": job.get("created_at", ""),
                "source": "Arbeitnow",
                "guid": f"arbeitnow-{job.get('slug', title)}"
            })
    except Exception as e:
        print(f"[Arbeitnow] Error: {e}")
    return jobs

def fetch_weworkremotely(broad=False) -> list:
    # WeWorkRemotely = 100% remote
    jobs = []
    urls = [
        "https://weworkremotely.com/categories/remote-programming-jobs.rss",
        "https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss",
    ]
    for url in urls:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                title = entry.get("title", "")
                if not matches(title, entry.get("summary", ""), broad):
                    continue
                jobs.append({
                    "title": title,
                    "link": entry.get("link", ""),
                    "desc": clean(entry.get("summary", "")),
                    "date": entry.get("published", ""),
                    "source": "WeWorkRemotely 🌐",
                    "guid": f"wwr-{entry.get('id', title)}"
                })
        except Exception as e:
            print(f"[WWR] Error: {e}")
        time.sleep(1)
    return jobs

def fetch_jobicy(broad=False) -> list:
    jobs = []
    try:
        r = requests.get(
            "https://jobicy.com/?feed=job_feed&job_categories=engineering&job_types=full-time&search_keywords=QA+Lead",
            headers=HEADERS, timeout=15
        )
        feed = feedparser.parse(r.text)
        for entry in feed.entries:
            title = entry.get("title", "")
            summary = entry.get("summary", "")
            if not matches(title, summary, broad):
                continue
            if not location_ok("", summary):
                continue
            jobs.append({
                "title": title,
                "link": entry.get("link", ""),
                "desc": clean(summary),
                "date": entry.get("published", ""),
                "source": "Jobicy 🌐",
                "guid": f"jobicy-{entry.get('id', title)}"
            })
    except Exception as e:
        print(f"[Jobicy] Error: {e}")
    return jobs

# ── GENERAR XML ──────────────────────────────────────────────

def build_rss(jobs: list, title: str, filename: str, description: str, limit: int = 150) -> str:
    seen = set()
    unique = []
    for job in jobs:
        if job["guid"] not in seen and job["link"]:
            seen.add(job["guid"])
            unique.append(job)

    unique.sort(key=lambda j: str(j.get("date", "")), reverse=True)

    items = []
    for job in unique[:limit]:
        items.append(f"""
  <item>
    <title>{html.escape(job['title'])}</title>
    <link>{html.escape(job['link'])}</link>
    <description>{job['desc']} [{job['source']}]</description>
    <pubDate>{rss_date(job['date'])}</pubDate>
    <guid isPermaLink="false">{html.escape(job['guid'])}</guid>
  </item>""")

    now = rss_date()
    base = "https://darumidas.github.io/qa-jobs-feed"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{html.escape(title)}</title>
    <link>{base}/</link>
    <atom:link href="{base}/{filename}" rel="self" type="application/rss+xml"/>
    <description>{html.escape(description)}</description>
    <language>en</language>
    <lastBuildDate>{now}</lastBuildDate>
    <ttl>240</ttl>
    <generator>JoseAI JobFeed v2.0</generator>
    <!-- {len(unique)} jobs -->
{''.join(items)}
  </channel>
</rss>"""

# ── MAIN ─────────────────────────────────────────────────────

if __name__ == "__main__":
    base = os.path.dirname(__file__)

    print("Fetching jobs (filtered)...")
    filtered = []
    filtered += fetch_remoteok(broad=False)
    filtered += fetch_remotive(broad=False)
    filtered += fetch_arbeitnow(broad=False)
    filtered += fetch_weworkremotely(broad=False)
    filtered += fetch_jobicy(broad=False)
    print(f"  Filtered: {len(filtered)} jobs")

    print("Fetching jobs (all market)...")
    broad = []
    broad += fetch_remoteok(broad=True)
    broad += fetch_remotive(broad=True)
    broad += fetch_arbeitnow(broad=True)
    broad += fetch_weworkremotely(broad=True)
    broad += fetch_jobicy(broad=True)
    print(f"  Broad: {len(broad)} jobs")

    # Feed filtrado — títulos exactos de tu Job Titles sheet
    rss_filtered = build_rss(
        filtered,
        title="QA Jobs — Filtered (Jose Baños)",
        filename="feed.xml",
        description="QA Lead · Test Lead · Test Manager · Scrum Master · Senior QA — Remote, English",
        limit=150
    )
    with open(os.path.join(base, "feed.xml"), "w", encoding="utf-8") as f:
        f.write(rss_filtered)

    # Feed amplio — todo el mercado QA/tech/agile
    rss_broad = build_rss(
        broad,
        title="QA Jobs — All Market (Jose Baños)",
        filename="feed_all.xml",
        description="All QA · Agile · Testing · Automation remote jobs — broad market view",
        limit=300
    )
    with open(os.path.join(base, "feed_all.xml"), "w", encoding="utf-8") as f:
        f.write(rss_broad)

    print(f"\nDone. feed.xml ({len(filtered)} jobs) + feed_all.xml ({len(broad)} jobs)")
