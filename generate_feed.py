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

EXCLUDE = ["junior", "intern", "graduate", "entry level", "entry-level"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; JobFeedBot/1.0; +https://github.com/jbanos093/qa-jobs-feed)"
}

def matches(title: str, description: str = "") -> bool:
    text = (title + " " + description).lower()
    if any(ex in text for ex in EXCLUDE):
        return False
    return any(kw in text for kw in KEYWORDS)

def clean(text: str) -> str:
    text = re.sub(r'<[^>]+>', ' ', text or '')
    text = re.sub(r'\s+', ' ', text).strip()
    return html.escape(text[:400]) + ("..." if len(text) > 400 else "")

def rss_date(dt=None) -> str:
    if dt is None:
        return formatdate(usegmt=True)
    if isinstance(dt, str):
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(dt[:19], fmt).replace(tzinfo=timezone.utc)
                break
            except ValueError:
                continue
        else:
            return formatdate(usegmt=True)
    return formatdate(dt.timestamp(), usegmt=True)

# ── FUENTES ──────────────────────────────────────────────────

def fetch_remoteok() -> list:
    jobs = []
    try:
        r = requests.get("https://remoteok.com/api", headers=HEADERS, timeout=15)
        data = r.json()
        for job in data:
            if not isinstance(job, dict) or not job.get("position"):
                continue
            title = job.get("position", "")
            if not matches(title, " ".join(job.get("tags", []))):
                continue
            jobs.append({
                "title": f"{title} — {job.get('company', '')}",
                "link": job.get("url", f"https://remoteok.com/remote-jobs/{job.get('id','')}"),
                "desc": clean(job.get("description", "")),
                "date": job.get("date", ""),
                "source": "RemoteOK",
                "guid": f"remoteok-{job.get('id', title)}"
            })
    except Exception as e:
        print(f"[RemoteOK] Error: {e}")
    return jobs

def fetch_remotive() -> list:
    jobs = []
    try:
        r = requests.get(
            "https://remotive.com/api/remote-jobs?category=software-dev&limit=100",
            headers=HEADERS, timeout=15
        )
        data = r.json().get("jobs", [])
        for job in data:
            title = job.get("title", "")
            if not matches(title, job.get("candidate_required_location", "")):
                continue
            jobs.append({
                "title": f"{title} — {job.get('company_name', '')}",
                "link": job.get("url", ""),
                "desc": clean(job.get("description", "")),
                "date": job.get("publication_date", ""),
                "source": "Remotive",
                "guid": f"remotive-{job.get('id', title)}"
            })
    except Exception as e:
        print(f"[Remotive] Error: {e}")
    return jobs

def fetch_arbeitnow() -> list:
    jobs = []
    try:
        r = requests.get(
            "https://arbeitnow.com/api/job-board-api",
            headers=HEADERS, timeout=15
        )
        data = r.json().get("data", [])
        for job in data:
            title = job.get("title", "")
            if not matches(title, job.get("description", "")):
                continue
            jobs.append({
                "title": f"{title} — {job.get('company_name', '')}",
                "link": job.get("url", ""),
                "desc": clean(job.get("description", "")),
                "date": job.get("created_at", ""),
                "source": "Arbeitnow",
                "guid": f"arbeitnow-{job.get('slug', title)}"
            })
    except Exception as e:
        print(f"[Arbeitnow] Error: {e}")
    return jobs

def fetch_weworkremotely() -> list:
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
                if not matches(title, entry.get("summary", "")):
                    continue
                jobs.append({
                    "title": title,
                    "link": entry.get("link", ""),
                    "desc": clean(entry.get("summary", "")),
                    "date": entry.get("published", ""),
                    "source": "WeWorkRemotely",
                    "guid": f"wwr-{entry.get('id', title)}"
                })
        except Exception as e:
            print(f"[WWR] Error: {e}")
        time.sleep(1)
    return jobs

def fetch_jobicy() -> list:
    jobs = []
    try:
        r = requests.get(
            "https://jobicy.com/?feed=job_feed&job_categories=engineering&job_types=full-time&search_keywords=QA+Lead",
            headers=HEADERS, timeout=15
        )
        feed = feedparser.parse(r.text)
        for entry in feed.entries:
            title = entry.get("title", "")
            if not matches(title, entry.get("summary", "")):
                continue
            jobs.append({
                "title": title,
                "link": entry.get("link", ""),
                "desc": clean(entry.get("summary", "")),
                "date": entry.get("published", ""),
                "source": "Jobicy",
                "guid": f"jobicy-{entry.get('id', title)}"
            })
    except Exception as e:
        print(f"[Jobicy] Error: {e}")
    return jobs

# ── GENERAR XML ──────────────────────────────────────────────

def build_rss(jobs: list) -> str:
    seen = set()
    unique = []
    for job in jobs:
        if job["guid"] not in seen and job["link"]:
            seen.add(job["guid"])
            unique.append(job)

    # Ordenar por fecha (más recientes primero)
    unique.sort(key=lambda j: str(j.get("date", "")), reverse=True)

    items = []
    for job in unique[:80]:  # máx 80 items en el feed
        items.append(f"""
  <item>
    <title>{html.escape(job['title'])}</title>
    <link>{html.escape(job['link'])}</link>
    <description>{job['desc']} [Fuente: {job['source']}]</description>
    <pubDate>{rss_date(job['date'])}</pubDate>
    <guid isPermaLink="false">{html.escape(job['guid'])}</guid>
    <source url="{html.escape(job['link'])}">{job['source']}</source>
  </item>""")

    now = rss_date()
    count = len(unique)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>QA Jobs Feed — Jose Baños Arroyo</title>
    <link>https://Darumidas.github.io/qa-jobs-feed/</link>
    <atom:link href="https://Darumidas.github.io/qa-jobs-feed/feed.xml" rel="self" type="application/rss+xml"/>
    <description>QA Lead · Senior QA · Test Manager · SDET Lead — Remote jobs in English</description>
    <language>en</language>
    <lastBuildDate>{now}</lastBuildDate>
    <ttl>360</ttl>
    <generator>JoseAI JobFeed v1.0</generator>
    <managingEditor>jbanos093@gmail.com (Jose Banos Arroyo)</managingEditor>
    <!-- {count} jobs found -->
{''.join(items)}
  </channel>
</rss>"""

# ── MAIN ─────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Fetching jobs...")
    all_jobs = []
    all_jobs += fetch_remoteok();   print(f"  RemoteOK:       {len(all_jobs)} so far")
    all_jobs += fetch_remotive();   print(f"  Remotive:       {len(all_jobs)} so far")
    all_jobs += fetch_arbeitnow();  print(f"  Arbeitnow:      {len(all_jobs)} so far")
    all_jobs += fetch_weworkremotely(); print(f"  WeWorkRemotely: {len(all_jobs)} so far")
    all_jobs += fetch_jobicy();     print(f"  Jobicy:         {len(all_jobs)} so far")

    rss = build_rss(all_jobs)

    out_path = os.path.join(os.path.dirname(__file__), "feed.xml")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(rss)

    print(f"\nDone. {len(all_jobs)} raw jobs → feed.xml written.")
