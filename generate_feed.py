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

# ── KEYWORDS — derivados directamente de Columna A de Job Titles ─────────
# Feed filtrado: solo matchea contra ESTOS títulos exactos en el título del puesto
# Incluye variantes mínimas (Senior X, X Lead, Head of X) pero nada genérico
KEYWORDS = [
    # Exactos columna A
    "test lead", "qa lead", "test automation lead", "senior qa engineer",
    "senior test engineer", "qa tech lead", "test manager", "qa manager",
    "scrum master", "delivery manager", "agile lead", "engineering manager",
    "quality lead", "test delivery lead", "agile coach",
    # Variantes directas aceptables (mismo rol, distinto prefijo)
    "senior test lead", "lead test engineer", "qa team lead",
    "head of qa", "head of quality", "head of testing",
    "principal test", "staff test", "qa automation lead",
    "senior scrum master", "certified scrum master",
    "senior delivery manager", "senior engineering manager",
    "senior agile", "agile delivery", "agile delivery manager",
    "testing manager", "quality assurance manager", "quality assurance lead",
    "senior quality", "quality engineering manager",
]

# Feed amplio: términos más generales para "todo el mercado"
KEYWORDS_BROAD = [
    "qa engineer", "quality assurance", "test engineer", "automation engineer",
    "sdet", "scrum master", "agile coach", "delivery manager",
    "engineering manager", "product owner", "release manager",
    "quality manager", "test analyst"
]

EXCLUDE = [
    # Seniority no deseada
    "junior", "jr.", "intern", "internship", "graduate", "entry level",
    "entry-level", "trainee", "apprentice", "associate qa", "associate test",
    # Roles de desarrollo (no QA/Agile)
    "software developer", "software engineer", "frontend developer",
    "backend developer", "full stack", "fullstack", "full-stack",
    "mobile developer", "ios developer", "android developer",
    "web developer", "react developer", "node developer",
    "python developer", "java developer", ".net developer",
    "devops engineer", "data engineer", "data scientist",
    "machine learning engineer", "ml engineer", "ai engineer",
    # Contrato/jornada no deseada
    "part-time", "part time", "freelance only", "temporary", "contract only",
    # Otros roles no relevantes
    "sales", "account executive", "account manager", "marketing manager",
    "recruiter", "hr manager", "finance manager", "designer",
    "head of office", "office manager",
    # Presencial explícito
    "on-site", "onsite", "on site", "in-office", "in office",
    "must be in office", "office-based", "no remote", "not remote",
    "presencial", "en oficina",
    # US-only
    "us citizenship required", "must be authorized to work in the u",
    "sponsorship not available", "must be located in the us",
    "us only", "united states only", "eligible to work in the us",
]

# Tags que identifican una oferta como remota
REMOTE_TAGS = [
    "remote", "remote-first", "remote work", "remotework", "work from home",
    "wfh", "fully remote", "100% remote", "distributed", "worldwide",
    "anywhere", "global", "trabajo remoto", "teletrabajo", "hybrid remote"
]
# Ubicaciones presenciales aceptadas
ONSITE_OK = ["madrid", "spain", "españa", "barcelona", "europe", "emea"]
# Ubicaciones a descartar si no hay tag remoto
LOCATIONS_BAD = [
    # USA
    "denver", "colorado", "california", "texas", "new york", "florida",
    "washington", "chicago", "boston", "seattle", "austin", "atlanta",
    "united states", "usa", ", co", ", ca", ", tx", ", ny", ", fl",
    # Canada
    "toronto", "vancouver", "canada",
    # Europa no España (solo si no es remote)
    "berlin", "munich", "münchen", "hamburg", "frankfurt", "germany", "deutschland",
    "paris", "lyon", "france", "amsterdam", "netherlands",
    "zürich", "zurich", "switzerland",
    # Presencial duro
    "on-site only", "onsite only", "in-office only", "office required", "no remote"
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
    # Grupo 1 — QA/Test roles × sitios + remote
    "https://www.google.com/alerts/feeds/10249602398417491184/11611437265442465505",
    "https://www.google.com/alerts/feeds/10249602398417491184/12178066067736602236",
    "https://www.google.com/alerts/feeds/10249602398417491184/2223651637235887985",
    "https://www.google.com/alerts/feeds/10249602398417491184/13155169726062107205",
    # Grupo 2 — Automation/Quality × sitios + remote
    "https://www.google.com/alerts/feeds/10249602398417491184/7916913769787249035",
    "https://www.google.com/alerts/feeds/10249602398417491184/10001309389220709605",
    "https://www.google.com/alerts/feeds/10249602398417491184/10713089913937078173",
    "https://www.google.com/alerts/feeds/10249602398417491184/1206722805401966609",
    # Grupo 3 — Agile/Management × sitios + remote
    "https://www.google.com/alerts/feeds/10249602398417491184/4970848268405658321",
    "https://www.google.com/alerts/feeds/10249602398417491184/3277825465328383907",
    "https://www.google.com/alerts/feeds/10249602398417491184/7916913769787249821",
    "https://www.google.com/alerts/feeds/10249602398417491184/3277825465328382919",
    # General — Madrid + Glassdoor
    "https://www.google.com/alerts/feeds/10249602398417491184/9434042950324112243",
    "https://www.google.com/alerts/feeds/10249602398417491184/395567329496222380",
    "https://www.google.com/alerts/feeds/10249602398417491184/3463153044462255800",
    "https://www.google.com/alerts/feeds/10249602398417491184/4970848268405658360",
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
    title_low = title.lower()
    # Exclusiones siempre contra el título
    if any(ex in title_low for ex in EXCLUDE):
        return False
    if broad:
        # Feed amplio: title + descripción
        return any(kw in (title_low + " " + description.lower()) for kw in KEYWORDS_BROAD)
    else:
        # Feed filtrado: SOLO el título del puesto — más preciso, evita falsos positivos
        return any(kw in title_low for kw in KEYWORDS)

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
                    f"&max_days_old=21"
                    f"&content-type=application/json"
                )
                r = requests.get(url, headers=HEADERS, timeout=15)
                if r.status_code != 200:
                    continue
                for job in r.json().get("results", []):
                    uid       = str(job.get("id", ""))
                    job_title = job.get("title", "")
                    desc      = job.get("description", "")
                    loc_raw   = job.get("location", {}).get("display_name", "")
                    if uid in seen:
                        continue
                    # Filtro de keywords y exclusiones
                    if not matches(job_title, desc):
                        continue
                    # Para España: verificar que no sea on-site fuera de Madrid
                    if country == "es":
                        loc_low = (loc_raw + " " + desc[:300]).lower()
                        spain_bad = [
                            "málaga", "malaga", "granada", "sevilla", "seville",
                            "barcelona", "valencia", "bilbao", "zaragoza",
                            "alicante", "murcia", "vigo", "on-site"
                        ]
                        if any(b in loc_low for b in spain_bad) and "remote" not in loc_low:
                            continue
                    seen.add(uid)
                    company = job.get("company", {}).get("display_name", "")
                    jobs.append({
                        "title": f"{job_title} — {company} [{label}]",
                        "link":  job.get("redirect_url", ""),
                        "desc":  clean(desc),
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

def fetch_themuse() -> list:
    """The Muse — API pública sin auth, empresas tech globales, fuerte en remote.
    Endpoint: themuse.com/api/public/jobs"""
    jobs = []
    seen = set()
    # Categorías relevantes en The Muse
    categories = ["QA & Testing", "Project Management", "Agile & Scrum"]
    levels      = ["Senior Level", "Manager", "Lead"]
    try:
        import urllib.parse
        for category in categories:
            for level in levels:
                url = (
                    f"https://www.themuse.com/api/public/jobs"
                    f"?category={urllib.parse.quote(category)}"
                    f"&level={urllib.parse.quote(level)}"
                    f"&location=Flexible+%2F+Remote"
                    f"&page=1&descending=true"
                )
                r = requests.get(url, headers=HEADERS, timeout=15)
                if r.status_code != 200:
                    continue
                for job in r.json().get("results", []):
                    uid    = str(job.get("id", ""))
                    jtitle = job.get("name", "")
                    if uid in seen or not jtitle:
                        continue
                    if not matches(jtitle, job.get("contents", "")):
                        continue
                    seen.add(uid)
                    company = job.get("company", {}).get("name", "")
                    link    = job.get("refs", {}).get("landing_page", "")
                    pub     = job.get("publication_date", "")
                    jobs.append({
                        "title": f"{jtitle} — {company} [🌐 Remote]",
                        "link":  link,
                        "desc":  clean(job.get("contents", "")),
                        "date":  pub,
                        "source": "The Muse 🌐",
                        "guid":  f"muse-{uid}"
                    })
                time.sleep(0.4)
    except Exception as e:
        print(f"[The Muse] Error: {e}")
    return jobs


def fetch_grabjobs() -> list:
    """GrabJobs — scraper de su endpoint público de búsqueda.
    Cubre España (Madrid/remote) y ofertas globales."""
    jobs = []
    seen = set()
    import urllib.parse

    searches = [
        # (keywords, country_code, location_label)
        ("QA Lead",             "spain",  "📍 Spain"),
        ("Test Manager",        "spain",  "📍 Spain"),
        ("Scrum Master",        "spain",  "📍 Spain"),
        ("QA Manager",          "spain",  "📍 Spain"),
        ("Test Lead",           "spain",  "📍 Spain"),
        ("Agile Lead",          "spain",  "📍 Spain"),
        ("Engineering Manager", "spain",  "📍 Spain"),
        ("QA Lead",             "remote", "🌐 Remote"),
        ("Test Manager",        "remote", "🌐 Remote"),
        ("Scrum Master",        "remote", "🌐 Remote"),
    ]

    for keyword, country, label in searches:
        try:
            url = (
                f"https://grabjobs.co/{country}/jobs"
                f"?search_keyword={urllib.parse.quote(keyword)}"
                f"&employment_type=full-time"
                f"&working_location={'remote' if 'Remote' in label else 'all'}"
                f"&sort_by=recent"
            )
            r = requests.get(url, headers={
                **HEADERS,
                "Accept": "application/json, text/html",
                "X-Requested-With": "XMLHttpRequest"
            }, timeout=15)

            if r.status_code != 200:
                continue

            # Intenta parsear JSON si existe
            try:
                data = r.json()
                job_list = data.get("data", data.get("jobs", []))
            except Exception:
                # Si devuelve HTML, no lo procesamos (sin BeautifulSoup)
                continue

            for job in job_list:
                uid    = str(job.get("id", "") or job.get("job_id", ""))
                jtitle = job.get("title", "") or job.get("job_title", "")
                jlink  = job.get("url", "") or job.get("job_url", "") or f"https://grabjobs.co/job/{uid}"
                if uid in seen or not jtitle:
                    continue
                if not matches(jtitle, job.get("description", "")):
                    continue
                # Descarta cerradas
                if job.get("is_closed") or job.get("status") == "closed":
                    continue
                seen.add(uid)
                company = job.get("company_name", "") or job.get("company", {}).get("name", "")
                jobs.append({
                    "title": f"{jtitle} — {company} [{label}]",
                    "link":  jlink,
                    "desc":  clean(job.get("description", "") or job.get("snippet", "")),
                    "date":  job.get("posted_at", "") or job.get("created_at", ""),
                    "source": "GrabJobs 🟣",
                    "guid":  f"grabjobs-{uid}"
                })
            time.sleep(0.5)
        except Exception as e:
            print(f"[GrabJobs] Error ({keyword}/{country}): {e}")

    print(f"  GrabJobs raw: {len(jobs)}")
    return jobs


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

    # ── Fuentes que devuelven ofertas INDIVIDUALES reales ──
    print("Fetching jobs...")
    filtered = []

    src = fetch_remoteok(broad=False);      print(f"  RemoteOK:      {len(src)}"); filtered += src
    src = fetch_remotive(broad=False);      print(f"  Remotive:      {len(src)}"); filtered += src
    src = fetch_weworkremotely(broad=False);print(f"  WWRemotely:    {len(src)}"); filtered += src
    src = fetch_himalayas(broad=False);     print(f"  Himalayas:     {len(src)}"); filtered += src
    src = fetch_arbeitnow(broad=False);     print(f"  Arbeitnow:     {len(src)}"); filtered += src
    src = fetch_jobicy(broad=False);        print(f"  Jobicy:        {len(src)}"); filtered += src
    src = fetch_tecnoempleo();              print(f"  Tecnoempleo:   {len(src)}"); filtered += src
    src = fetch_themuse();                  print(f"  The Muse:      {len(src)}"); filtered += src
    src = fetch_grabjobs();                 print(f"  GrabJobs:      {len(src)}"); filtered += src

    adzuna = fetch_adzuna(
        os.environ.get("ADZUNA_APP_ID", ""),
        os.environ.get("ADZUNA_APP_KEY", "")
    );                                      print(f"  Adzuna:        {len(adzuna)}"); filtered += adzuna

    # Google RSS y Indeed RSS eliminados — devuelven páginas de búsqueda, no ofertas individuales
    print(f"  TOTAL: {len(filtered)} jobs antes de deduplicar")

    # Feed amplio — mismas fuentes sin filtro de keywords
    print("Fetching broad market...")
    broad_jobs = []
    src = fetch_remoteok(broad=True);       broad_jobs += src
    src = fetch_remotive(broad=True);       broad_jobs += src
    src = fetch_weworkremotely(broad=True); broad_jobs += src
    src = fetch_himalayas(broad=True);      broad_jobs += src
    src = fetch_arbeitnow(broad=True);      broad_jobs += src
    src = fetch_jobicy(broad=True);         broad_jobs += src
    broad_jobs += adzuna + fetch_themuse() + fetch_grabjobs()
    print(f"  Broad total: {len(broad_jobs)}")

    # Feed filtrado — máx 50 ofertas relevantes del día
    rss_filtered = build_rss(
        filtered,
        title="QA Jobs — Filtered (Jose Baños)",
        filename="feed.xml",
        description="QA Lead · Test Lead · Test Manager · Scrum Master · Senior QA — Remote / Madrid",
        limit=50
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
