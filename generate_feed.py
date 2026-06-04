"""
QA Jobs RSS Feed Generator — Jose Baños Arroyo
Fuentes: RemoteOK, Remotive, Arbeitnow, WeWorkRemotely, Himalayas,
         Google News RSS, Google Alerts RSS (custom)
Output: feed.xml + feed_all.xml → publicado en GitHub Pages
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
    "qa", "quality assurance", "tester", "test engineer", "sdet", "scrum", "agile",
    "automation engineer", "delivery manager", "product owner",
    "engineering manager", "agile coach", "release manager", "devops"
]

EXCLUDE = ["junior", "intern", "graduate", "entry level", "entry-level", "trainee"]

# Tags que identifican una oferta como remota
REMOTE_TAGS = [
    "remote", "remote-first", "remote work", "remotework", "work from home",
    "wfh", "fully remote", "100% remote", "distributed", "worldwide",
    "anywhere", "global", "trabajo remoto", "teletrabajo"
]
# Ubicaciones presenciales aceptadas
ONSITE_OK = ["madrid", "spain", "españa", "barcelona"]
# Ubicaciones a descartar (solo si no hay tag remoto)
LOCATIONS_BAD = [
    "berlin", "munich", "münchen", "hamburg", "frankfurt", "cologne", "köln",
    "germany", "deutschland", "paris", "lyon", "france", "amsterdam", "rotterdam",
    "netherlands", "zürich", "zurich", "geneva", "switzerland", "london",
    "manchester", "united kingdom", "uk only", "new york", "san francisco",
    "los angeles", "chicago", "toronto", "vancouver", "canada",
    "on-site only", "onsite only", "in-office only", "office required"
]

# ── TÍTULOS COLUMNA A — Job Titles sheet ─────────────────────
COLUMN_A_TITLES = [
    "Test Lead", "QA Lead", "Test Automation Lead", "Senior QA Engineer",
    "Senior Test Engineer", "QA Tech Lead", "Test Manager", "QA Manager",
    "Scrum Master", "Delivery Manager", "Agile Lead", "IT Manager",
    "Engineering Manager", "Quality Lead", "Test Delivery Lead", "Agile Coach",
]

# Queries simples por título — sin site: (devuelve páginas agrupadas, no ofertas individuales)
# Google News encuentra ofertas publicadas en múltiples fuentes
def build_google_queries() -> list:
    queries = []
    for title in COLUMN_A_TITLES:
        queries.append(f'"{title}" remote job opening')
        queries.append(f'"{title}" "work from home" hiring')
        queries.append(f'"{title}" Madrid oferta empleo')
    return queries

GOOGLE_NEWS_QUERIES = build_google_queries()

# ── GOOGLE ALERTS RSS — pega aquí tus URLs ───────────────────
# Cómo obtenerlas: google.com/alerts → crea alerta → "Mostrar opciones"
# → Enviar a: "Feed RSS" → copia la URL
GOOGLE_ALERTS_URLS = [
    # Pega aquí tus URLs de Google Alerts:
    # "https://www.google.com/alerts/feeds/TU_ID/ALERTA_ID",
]

# ── INDEED RSS — feed directo por título ─────────────────────
def fetch_indeed_rss() -> list:
    """Indeed RSS — un feed por título de columna A."""
    jobs = []
    seen = set()
    for title in COLUMN_A_TITLES:
        for location in ["Remote", "Madrid"]:
            try:
                import urllib.parse
                url = (
                    f"https://www.indeed.com/rss?q={urllib.parse.quote(title)}"
                    f"&l={urllib.parse.quote(location)}&sort=date&fromage=14"
                )
                feed = feedparser.parse(url)
                for entry in feed.entries:
                    uid = entry.get("id") or entry.get("link", "")
                    if uid in seen or not entry.get("link"):
                        continue
                    seen.add(uid)
                    jobs.append({
                        "title": f"{entry.get('title', '')}",
                        "link":  entry.get("link", ""),
                        "desc":  clean(entry.get("summary", "")),
                        "date":  entry.get("published", ""),
                        "source": f"Indeed 📋 ({location})",
                        "guid":  f"indeed-{uid}"
                    })
                time.sleep(0.5)
            except Exception as e:
                print(f"[Indeed] Error ({title}/{location}): {e}")
    return jobs

def location_ok(location: str, tags: str = "", description: str = "") -> bool:
    """True si remoto o Madrid/España. False si presencial en ciudad no deseada."""
    combined = (location + " " + tags + " " + description[:800]).lower()
    if any(r in combined for r in REMOTE_TAGS):
        return True
    if any(o in combined for o in ONSITE_OK):
        return True
    if any(b in combined for b in LOCATIONS_BAD):
        return False
    return True  # sin info → aceptar

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
    jobs = []
    try:
        r = requests.get("https://arbeitnow.com/api/job-board-api", headers=HEADERS, timeout=15)
        data = r.json().get("data", [])
        for job in data:
            title = job.get("title", "")
            tags  = " ".join(job.get("tags", []))
            loc   = job.get("location", "")
            is_remote = job.get("remote", False) or "remote" in tags.lower()
            if not matches(title, job.get("description", ""), broad):
                continue
            if not is_remote and not location_ok(loc, tags, job.get("description", "")):
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


def fetch_himalayas(broad=False) -> list:
    """Himalayas.app — 100% remote jobs"""
    jobs = []
    queries = KEYWORDS[:8] if not broad else ["qa", "test", "scrum", "agile", "sdet"]
    seen = set()
    for q in queries:
        try:
            r = requests.get(
                f"https://himalayas.app/jobs/api?q={requests.utils.quote(q)}&limit=20",
                headers=HEADERS, timeout=15
            )
            if r.status_code != 200:
                continue
            for job in r.json().get("jobs", []):
                title = job.get("title", "")
                uid   = job.get("id") or job.get("slug") or title
                if uid in seen:
                    continue
                if not matches(title, job.get("description", ""), broad):
                    continue
                seen.add(uid)
                jobs.append({
                    "title": f"{title} — {job.get('company', {}).get('name', '')}",
                    "link": job.get("applicationUrl") or job.get("url") or "",
                    "desc": clean(job.get("description", "")),
                    "date": job.get("createdAt", ""),
                    "source": "Himalayas 🌐",
                    "guid": f"himalayas-{uid}"
                })
            time.sleep(0.5)
        except Exception as e:
            print(f"[Himalayas] Error ({q}): {e}")
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

def fetch_tecnoempleo() -> list:
    """Tecnoempleo — portal español, sin auth, RSS directo."""
    jobs = []
    seen = set()
    for title in COLUMN_A_TITLES:
        try:
            import urllib.parse
            url = f"https://www.tecnoempleo.com/ofertas-trabajo/rss.php?te={urllib.parse.quote(title)}&pais=es"
            feed = feedparser.parse(url)
            for entry in feed.entries:
                uid = entry.get("id") or entry.get("link", "")
                if uid in seen or not entry.get("link"):
                    continue
                seen.add(uid)
                jobs.append({
                    "title": entry.get("title", ""),
                    "link":  entry.get("link", ""),
                    "desc":  clean(entry.get("summary", "")),
                    "date":  entry.get("published", ""),
                    "source": "Tecnoempleo 📍",
                    "guid":  f"tecno-{uid}"
                })
            time.sleep(0.4)
        except Exception as e:
            print(f"[Tecnoempleo] Error ({title}): {e}")
    return jobs


def fetch_adzuna(app_id: str, app_key: str) -> list:
    """Adzuna — agrega Glassdoor, Reed, Totaljobs y +300 sitios.
    Busca: remote worldwide (vía UK que tiene el mayor mercado EN)
           + presencial Madrid/España."""
    if not app_id or not app_key:
        return []

    import urllib.parse
    jobs = []
    seen = set()

    # Combinaciones: (país, where, label)
    searches = [
        ("gb", "Remote",  "🌐 Remote"),   # UK como proxy de remote EN mundial
        ("es", "Madrid",  "📍 Madrid"),
        ("es", "Spain",   "📍 Spain"),
    ]

    for country, where, label in searches:
        for title in COLUMN_A_TITLES:
            try:
                url = (
                    f"https://api.adzuna.com/v1/api/jobs/{country}/search/1"
                    f"?app_id={app_id}&app_key={app_key}"
                    f"&what={urllib.parse.quote(title)}"
                    f"&where={urllib.parse.quote(where)}"
                    f"&results_per_page=10"
                    f"&sort_by=date"
                    f"&content-type=application/json"
                )
                r = requests.get(url, headers=HEADERS, timeout=15)
                if r.status_code != 200:
                    continue
                for job in r.json().get("results", []):
                    uid = str(job.get("id", ""))
                    if uid in seen:
                        continue
                    seen.add(uid)
                    job_title = job.get("title", "")
                    company   = job.get("company", {}).get("display_name", "")
                    jobs.append({
                        "title": f"{job_title} — {company} [{label}]",
                        "link":  job.get("redirect_url", ""),
                        "desc":  clean(job.get("description", "")),
                        "date":  job.get("created", ""),
                        "source": "Adzuna 🔗",
                        "guid":  f"adzuna-{uid}"
                    })
                time.sleep(0.3)
            except Exception as e:
                print(f"[Adzuna] Error ({title}/{where}): {e}")
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

def fetch_google_rss() -> list:
    """Lee Google News RSS + Google Alerts RSS.
    No aplica filtro de keywords — Google ya filtra por la query.
    Sí aplica filtro de ubicación."""
    jobs = []
    seen = set()

    # Google News RSS
    for query in GOOGLE_NEWS_QUERIES:
        try:
            import urllib.parse
            url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=en&gl=US&ceid=US:en"
            feed = feedparser.parse(url)
            for entry in feed.entries:
                title = entry.get("title", "")
                link  = entry.get("link", "")
                uid   = entry.get("id") or link
                if uid in seen or not link:
                    continue
                summary = entry.get("summary", "")
                # Filtro ubicación: acepta remote/Madrid, descarta ciudades no deseadas
                if not location_ok(title, "", summary):
                    continue
                seen.add(uid)
                jobs.append({
                    "title": title,
                    "link": link,
                    "desc": clean(summary),
                    "date": entry.get("published", ""),
                    "source": "Google News 🔍",
                    "guid": f"gnews-{uid}"
                })
            time.sleep(0.8)
        except Exception as e:
            print(f"[Google News] Error ({query[:30]}): {e}")

    # Google Alerts RSS (URLs custom del usuario)
    for url in GOOGLE_ALERTS_URLS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                title = entry.get("title", "")
                link  = entry.get("link", "")
                uid   = entry.get("id") or link
                if uid in seen or not link:
                    continue
                if not location_ok(title, "", entry.get("summary", "")):
                    continue
                seen.add(uid)
                jobs.append({
                    "title": title,
                    "link": link,
                    "desc": clean(entry.get("summary", "")),
                    "date": entry.get("published", ""),
                    "source": "Google Alerts 🔔",
                    "guid": f"galert-{uid}"
                })
        except Exception as e:
            print(f"[Google Alerts] Error ({url[:40]}): {e}")

    return jobs


if __name__ == "__main__":
    base = os.path.dirname(__file__)

    print("Fetching jobs (filtered)...")
    filtered = []
    filtered += fetch_remoteok(broad=False)
    filtered += fetch_remotive(broad=False)
    filtered += fetch_arbeitnow(broad=False)
    filtered += fetch_weworkremotely(broad=False)
    filtered += fetch_jobicy(broad=False)
    filtered += fetch_himalayas(broad=False)
    print(f"  Job boards: {len(filtered)} jobs")

    google = fetch_google_rss()
    print(f"  Google RSS:   {len(google)} results")

    indeed = fetch_indeed_rss()
    print(f"  Indeed RSS:   {len(indeed)} results")

    tecno = fetch_tecnoempleo()
    print(f"  Tecnoempleo:  {len(tecno)} results")

    # Adzuna — activo si hay claves en variables de entorno
    adzuna = fetch_adzuna(
        os.environ.get("ADZUNA_APP_ID", ""),
        os.environ.get("ADZUNA_APP_KEY", "")
    )
    print(f"  Adzuna:       {len(adzuna)} results")

    filtered += google + indeed + tecno + adzuna
    print(f"  Filtered total: {len(filtered)} jobs")

    print("Fetching jobs (all market)...")
    broad_jobs = []
    broad_jobs += fetch_remoteok(broad=True)
    broad_jobs += fetch_remotive(broad=True)
    broad_jobs += fetch_arbeitnow(broad=True)
    broad_jobs += fetch_weworkremotely(broad=True)
    broad_jobs += fetch_jobicy(broad=True)
    broad_jobs += fetch_himalayas(broad=True)
    broad_jobs += google + indeed + tecno + adzuna
    print(f"  Broad: {len(broad_jobs)} jobs")

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
        broad_jobs,
        title="QA Jobs — All Market (Jose Baños)",
        filename="feed_all.xml",
        description="All QA · Agile · Testing · Automation remote jobs — broad market view",
        limit=300
    )
    with open(os.path.join(base, "feed_all.xml"), "w", encoding="utf-8") as f:
        f.write(rss_broad)

    print(f"\nDone. feed.xml ({len(filtered)} jobs) + feed_all.xml ({len(broad_jobs)} jobs)")
