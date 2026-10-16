# SilentRat 🐀 — SEO Spider

A **fully standalone desktop SEO crawler with no URL limit**, inspired by Screaming Frog,
with its own branding and code. It ships with a full GUI, **JavaScript rendering**,
**custom extraction**, **structured data**, **locally measured Core Web Vitals**,
**Spider/List/Sitemap modes**, and **Excel export**. It can also be packaged as a single
Windows `.exe` that doesn't require Python.

---

## 1. Run from Python

```
pip install -r requirements.txt
python silentrat.py          # or double-click SilentRat.bat
```

## 2. Standalone executable (Windows)

Download `SilentRat.exe` from the [Releases](../../releases) page, or build it yourself
(see [Building the `.exe`](#building-the-exe)). Double-click to run. **No Python needed**:
a single self-contained file (~95 MB, bundling the JS rendering engine and Excel export)
that runs on any Windows 10/11 machine.

> **Antivirus:** because it's a PyInstaller-packaged `.exe`, some antivirus tools may flag
> it as "unknown" the first time (a typical false positive). Add an exception if needed.
>
> **JS rendering:** requires **Chrome or Edge** to be installed (used in headless mode).

## 3. Command line (advanced)

```
python seo_spider.py https://example.com --threads 8 --sitemap-out sitemap.xml
python seo_spider.py https://example.com --render                 # render JS
python seo_spider.py https://example.com --mode sitemap           # crawl the site's sitemap
python seo_spider.py x --mode list --list-file urls.txt           # crawl a list of URLs
python seo_spider.py https://example.com --psi-key YOUR_API_KEY   # PageSpeed Core Web Vitals
python seo_spider.py https://example.com --include "/blog/" --exclude "/tag/"
```

---

## Features

### Crawling
- **No URL limit** (Max = 0), configurable multithreading, crawl depth, and inlinks
- **Modes: Spider · URL List · XML Sitemap**
  - Sitemap mode accepts a `sitemap.xml` URL **or just the domain**: the sitemap is
    auto-discovered through `robots.txt` or common paths (`/sitemap_index.xml`,
    `/sitemap.xml`, `/wp-sitemap.xml`, ...)
  - Recursive sitemap indexes, gzipped sitemaps (`.xml.gz`), and image/video entries skipped
- `robots.txt` support (can be turned off), **regex include/exclude**, configurable
  User-Agent and delay

### Per-URL data
- Status codes, redirect chains, response time, HTML size
- Title, Meta Description, Meta Keywords, H1, H2
- Canonical + diagnostics, meta robots, X-Robots-Tag, indexability + reason
- Hreflang, rel next/prev, lang, viewport, charset, word count, text ratio
- Internal/external links and outlinks, images missing `alt`

### Advanced features
- 🟢 **JavaScript rendering**: headless Chrome/Edge; crawls SPAs and JS-driven content
- 🟢 **Custom extraction**: up to 5 **CSS / XPath / Regex** extractors
- 🟢 **Structured data**: JSON-LD / Schema.org (types) + Microdata detection
- 🟢 **Duplicates**: titles, descriptions, H1s, and **exact content (hash)**
- 🟢 **Local Core Web Vitals**: FCP, LCP, CLS, TTFB, and Load measured with the headless
  browser during JS rendering. **No API or key required**
- 🟢 **Resources**: CSS/JS/images with status codes + broken **external links**
- 🟢 **Mixed content** (HTTP on HTTPS pages)

### Output
- **Excel export (.xlsx)**: one sheet per tab + an Overview sheet
- **CSV export** (full report, UTF-8)
- **`sitemap.xml` generation** from the indexable 200 URLs

---

## Interface: 19 tabs

`Overview · Internal · Response Codes · Page Titles · Meta Description · Meta Keywords ·
H1 · H2 · Images · Canonicals · Directives · Hreflang · Structured Data · Custom Extraction ·
Web Vitals · Security · Resources · External · Duplicates`

- Live table, text filter, sorting by column
- Color coding: black OK · amber redirect · red error · purple noindex
- Status bar with counters + a status code chart on Overview
- Buttons: **Start · Stop · Config · Export · Sitemap · Clear**

### Defaults
Resource checks and external link checks are on by default, and the **5 extractors** are
ready to use (just enter their expressions in Config). **JS rendering is off by default**
for speed, since it opens a browser per URL. Turn it on in **Config** for JS-heavy sites
and to measure Web Vitals.

### Settings (Config button)
User-Agent · delay · include/exclude regex · check resources/external links ·
**JS rendering + wait time** · **5 extractors (name/type/CSS/XPath/Regex expression)**.

> **Web Vitals** (FCP/LCP/CLS/TTFB/Load) are measured locally by the headless browser
> while it renders. **The PageSpeed API is not used** and no key is needed.

---

## Project structure

```
seo-spider/
├── silentrat.py         ← GUI
├── seo_spider.py        ← engine (CLI + GUI)
├── make_icon.py         ← icon generator
├── silentrat.ico        ← icon
├── SilentRat.bat        ← launcher for the Python version
├── SilentRat.spec       ← PyInstaller build spec
├── requirements.txt
└── README.md
```

## Building the `.exe`

```
pip install pyinstaller
python -m PyInstaller --onefile --windowed --name SilentRat --icon silentrat.ico ^
  --add-data "silentrat.ico;." --collect-all selenium --collect-submodules openpyxl ^
  --hidden-import lxml._elementpath silentrat.py
```

The executable is written to `dist\SilentRat.exe`.

## Responsible use
Only crawl sites **you own** or have permission to crawl. Use a delay and fewer threads
on small servers. `robots.txt` is respected by default. JS rendering opens headless
browsers (slower and more resource-intensive), so use it only when a site needs it.
