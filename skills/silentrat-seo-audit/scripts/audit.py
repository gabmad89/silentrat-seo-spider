#!/usr/bin/env python3
"""
SilentRat SEO Audit — crawl a site with the SilentRat engine and turn the raw
crawl into a prioritized list of SEO issues.

Usage
  python audit.py https://example.com [--max 500] [--out-dir silentrat_out]
  python audit.py --from-csv crawl.csv  [--out-dir silentrat_out]

Outputs (in --out-dir)
  crawl.csv      every crawled URL with ~60 SEO columns (same format as the desktop app)
  crawl.xlsx     Excel workbook: Overview, Internal, Resources, External, Duplicates
  sitemap.xml    indexable 200 pages (crawl mode only)
  audit.json     machine-readable issues, counts and affected URLs
  audit.md       human summary, ordered by severity
  report.html    standalone interactive dashboard (open in any browser)

The issue rules here mirror the ones in assets/report_template.html, so the
dashboard and the Markdown summary always agree.
"""

import argparse
import csv
import json
import os
import sys
import time
from collections import defaultdict
from dataclasses import asdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

SEVERITY_ORDER = {"critical": 0, "warning": 1, "notice": 2}
SEVERITY_ES = {"critical": "Crítico", "warning": "Aviso", "notice": "Mejora"}

# id, severity, title (es), why it matters + how to fix (es), required columns
RULES = [
    ("http_4xx", "critical", "Páginas con error 4xx",
     "Enlaces internos que llevan a páginas que no existen. Corrige o redirige (301) la URL y actualiza los enlaces que apuntan a ella.",
     ["status_code"]),
    ("http_5xx", "critical", "Páginas con error 5xx",
     "El servidor falla al servir estas URLs. Google deja de rastrearlas si persiste. Revisa los logs del servidor.",
     ["status_code"]),
    ("conn_error", "critical", "URLs que no responden",
     "Timeout, DNS o SSL fallido. Comprueba que la URL carga desde fuera y que el certificado es válido.",
     ["status_code"]),
    ("missing_title", "critical", "Sin etiqueta <title>",
     "El title es el factor on-page más importante y el texto azul del resultado en Google. Añade uno único por página.",
     ["title", "status_code", "content_type"]),
    ("mixed_content", "critical", "Contenido mixto (HTTP en HTTPS)",
     "Recursos cargados por HTTP dentro de una página HTTPS. El navegador los bloquea o marca la página como no segura.",
     ["mixed_content"]),
    ("redirect_chain", "warning", "Cadenas de redirecciones",
     "Dos o más saltos antes de llegar al destino. Diluye autoridad y ralentiza. Redirige directamente a la URL final.",
     ["redirect_chain"]),
    ("dup_title", "warning", "Titles duplicados",
     "Varias páginas compiten por la misma búsqueda (canibalización). Escribe un title distinto para cada una.",
     ["title"]),
    ("title_long", "warning", "Title de más de 60 caracteres",
     "Google lo cortará con '…'. Pon la palabra clave y el mensaje principal al inicio.",
     ["title_len"]),
    ("missing_desc", "warning", "Sin meta description",
     "Google inventará el fragmento del resultado. Una buena descripción mejora el CTR.",
     ["meta_description"]),
    ("dup_desc", "warning", "Meta descriptions duplicadas",
     "Resultados idénticos en Google para páginas distintas. Personaliza cada una.",
     ["meta_description"]),
    ("missing_h1", "warning", "Sin H1",
     "El H1 indica a Google y al usuario de qué trata la página. Añade uno con la palabra clave principal.",
     ["h1_count"]),
    ("dup_content", "warning", "Contenido duplicado exacto",
     "Páginas con el mismo HTML de contenido. Unifícalas o usa canonical hacia la versión principal.",
     ["content_hash"]),
    ("img_no_alt", "warning", "Imágenes sin texto alt",
     "Pierdes tráfico de Google Imágenes y accesibilidad. Describe cada imagen en su atributo alt.",
     ["images_no_alt"]),
    ("not_https", "warning", "Páginas sin HTTPS",
     "HTTPS es factor de ranking y Chrome marca HTTP como 'No seguro'. Fuerza HTTPS con una 301.",
     ["is_https"]),
    ("no_viewport", "warning", "Sin meta viewport",
     "La página no se adapta al móvil. Google indexa primero la versión móvil.",
     ["viewport"]),
    ("slow", "warning", "Respuesta lenta (>1 s)",
     "El servidor tarda más de un segundo en responder. Afecta a Core Web Vitals y al presupuesto de rastreo.",
     ["response_ms"]),
    ("redirect_3xx", "notice", "Enlaces internos a redirecciones",
     "Enlazas a URLs que redirigen. Cambia el enlace a la URL final para ahorrar un salto.",
     ["status_code"]),
    ("title_short", "notice", "Title de menos de 30 caracteres",
     "Desaprovechas espacio en el resultado de Google. Añade beneficio o ubicación.",
     ["title_len"]),
    ("desc_long", "notice", "Meta description de más de 160 caracteres",
     "Se cortará en el resultado. Resume el mensaje en ~150 caracteres.",
     ["meta_desc_len"]),
    ("desc_short", "notice", "Meta description de menos de 70 caracteres",
     "Muy corta para convencer. Añade beneficio y llamada a la acción.",
     ["meta_desc_len"]),
    ("multi_h1", "notice", "Varios H1",
     "No penaliza, pero diluye el foco. Deja un H1 y pasa el resto a H2.",
     ["h1_count"]),
    ("thin_content", "notice", "Contenido escaso (<300 palabras)",
     "Páginas indexables con poco texto. Amplía o considera noindex si no aportan.",
     ["word_count"]),
    ("missing_canonical", "notice", "Sin etiqueta canonical",
     "Sin canonical, parámetros y variantes de la URL pueden indexarse como duplicados.",
     ["canonical_status"]),
    ("no_lang", "notice", "Sin atributo lang en <html>",
     "Ayuda a Google y a lectores de pantalla a identificar el idioma.",
     ["lang"]),
    ("no_schema", "notice", "Sin datos estructurados",
     "Schema.org (JSON-LD) permite resultados enriquecidos: estrellas, FAQ, eventos, cursos…",
     ["structured_data_count"]),
    ("deep", "notice", "Profundidad mayor de 3 clics",
     "Cuanto más lejos de la home, menos autoridad y rastreo recibe. Enlázala desde páginas más altas.",
     ["crawl_depth"]),
    ("noindex", "notice", "Marcadas como noindex",
     "No aparecerán en Google. Comprueba que es intencionado.",
     ["indexability_status"]),
    ("canonicalized", "notice", "Canonicalizadas a otra URL",
     "Google indexará la URL del canonical, no esta. Verifica que es lo que quieres.",
     ["canonical_status"]),
]
RULE_BY_ID = {r[0]: r for r in RULES}
EXTRA_RULES = {
    "broken_resource": ("critical", "Recursos rotos (imágenes, CSS, JS)",
                        "Archivos que la página intenta cargar y fallan. Rompen el diseño o la funcionalidad."),
    "broken_external": ("warning", "Enlaces externos rotos",
                        "Enlaces salientes a páginas que ya no existen. Mala experiencia y señal de abandono."),
}


def _int(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def _float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def evaluate(pages):
    """pages: list of dicts (string values, CSV-style). Returns {rule_id: [urls]}."""
    cols = set()
    for p in pages:
        cols.update(k for k, v in p.items())
    present = lambda req: all(c in cols for c in req)

    def is_html(p):
        return "html" in (p.get("content_type") or "").lower()

    def ok200(p):
        c = _int(p.get("status_code"))
        return 200 <= c < 300

    def indexable(p):
        return (p.get("indexable") or "").startswith("Indexable")

    hits = defaultdict(list)

    # duplicate groups (HTML 200 pages only)
    groups = {"title": defaultdict(list), "meta_description": defaultdict(list),
              "content_hash": defaultdict(list)}
    for p in pages:
        if is_html(p) and ok200(p):
            for f in groups:
                v = (p.get(f) or "").strip()
                if v:
                    groups[f][v].append(p["url"])
    dup_urls = {f: {u for urls in g.values() if len(urls) > 1 for u in urls}
                for f, g in groups.items()}

    for p in pages:
        url = p.get("url", "")
        code = _int(p.get("status_code"))
        html = is_html(p)
        h200 = html and ok200(p)
        idx = h200 and indexable(p)

        def add(rid, cond):
            if cond and present(RULE_BY_ID[rid][4]):
                hits[rid].append(url)

        add("http_4xx", 400 <= code < 500)
        add("http_5xx", code >= 500)
        add("conn_error", code == 0)
        add("redirect_3xx", 300 <= code < 400)
        add("redirect_chain", (p.get("redirect_chain") or "").count("->") >= 2)
        add("missing_title", h200 and not (p.get("title") or "").strip())
        add("mixed_content", _int(p.get("mixed_content")) > 0)
        add("dup_title", h200 and url in dup_urls["title"])
        add("title_long", h200 and _int(p.get("title_len")) > 60)
        add("title_short", h200 and 0 < _int(p.get("title_len")) < 30)
        add("missing_desc", idx and not (p.get("meta_description") or "").strip())
        add("dup_desc", h200 and url in dup_urls["meta_description"])
        add("desc_long", h200 and _int(p.get("meta_desc_len")) > 160)
        add("desc_short", h200 and 0 < _int(p.get("meta_desc_len")) < 70)
        add("missing_h1", idx and _int(p.get("h1_count")) == 0)
        add("multi_h1", h200 and _int(p.get("h1_count")) > 1)
        add("dup_content", h200 and url in dup_urls["content_hash"])
        add("thin_content", idx and _int(p.get("word_count")) < 300)
        add("img_no_alt", h200 and _int(p.get("images_no_alt")) > 0)
        add("not_https", h200 and p.get("is_https") == "No")
        add("no_viewport", h200 and not (p.get("viewport") or "").strip())
        add("no_lang", h200 and not (p.get("lang") or "").strip())
        add("slow", ok200(p) and _int(p.get("response_ms")) > 1000)
        add("missing_canonical", idx and p.get("canonical_status") == "Missing")
        add("canonicalized", h200 and p.get("canonical_status") == "Canonicalized")
        add("noindex", h200 and p.get("indexability_status") == "noindex")
        add("no_schema", idx and _int(p.get("structured_data_count")) == 0)
        add("deep", h200 and _int(p.get("crawl_depth")) > 3)
    return dict(hits)


PENALTY = {"critical": 40, "warning": 15, "notice": 3}


def health_score(pages, hits):
    """Average page score. Each page starts at 100 and loses 40 per critical issue,
    15 per warning and 3 per improvement (floor 0). Same formula as the dashboard."""
    if not pages:
        return 0
    per_page = defaultdict(int)
    for rid, urls in hits.items():
        for u in urls:
            per_page[u] += PENALTY[RULE_BY_ID[rid][1]]
    total = sum(max(0, 100 - per_page.get(p.get("url", ""), 0)) for p in pages)
    return round(total / len(pages))


def build_audit(pages, domain, resources=None, external=None, meta=None):
    hits = evaluate(pages)
    issues = []
    for rid, sev, title, fix, _req in RULES:
        urls = hits.get(rid, [])
        if urls:
            issues.append({"id": rid, "severity": sev, "title": title, "fix": fix,
                           "count": len(urls), "urls": urls})
    if resources:
        broken = [r for r in resources if _int(r.get("status_code")) == 0 or _int(r.get("status_code")) >= 400]
        if broken:
            sev, title, fix = EXTRA_RULES["broken_resource"]
            issues.append({"id": "broken_resource", "severity": sev, "title": title, "fix": fix,
                           "count": len(broken),
                           "urls": [f"{r['url']}  (en {r.get('source', '?')}, {r.get('status_code')})" for r in broken]})
    if external:
        broken = [(u, c) for u, c in external.items() if _int(c) == 0 or _int(c) >= 400]
        if broken:
            sev, title, fix = EXTRA_RULES["broken_external"]
            issues.append({"id": "broken_external", "severity": sev, "title": title, "fix": fix,
                           "count": len(broken), "urls": [f"{u}  ({c})" for u, c in broken]})
    issues.sort(key=lambda i: (SEVERITY_ORDER[i["severity"]], -i["count"]))

    html200 = [p for p in pages if "html" in (p.get("content_type") or "").lower()
               and 200 <= _int(p.get("status_code")) < 300]
    score = health_score(pages, hits)

    codes = {"2xx": 0, "3xx": 0, "4xx": 0, "5xx": 0, "error": 0}
    for p in pages:
        c = _int(p.get("status_code"))
        key = "error" if c == 0 else f"{c // 100}xx"
        if key in codes:
            codes[key] += 1
    return {
        "tool": "SilentRat SEO Audit",
        "domain": domain,
        "generated": time.strftime("%Y-%m-%d %H:%M"),
        "meta": meta or {},
        "totals": {"urls": len(pages), "html_200": len(html200),
                   "indexable": sum(1 for p in html200 if (p.get("indexable") or "").startswith("Indexable")),
                   "codes": codes,
                   "critical": sum(i["count"] for i in issues if i["severity"] == "critical"),
                   "warning": sum(i["count"] for i in issues if i["severity"] == "warning"),
                   "notice": sum(i["count"] for i in issues if i["severity"] == "notice")},
        "score": score,
        "issues": issues,
    }


def write_markdown(audit, path, max_urls=10):
    t = audit["totals"]
    L = [f"# Auditoría SEO — {audit['domain']}", "",
         f"_Generado con SilentRat el {audit['generated']}_", "",
         f"**Salud SEO: {audit['score']}/100** (media por URL: −40 por crítico, −15 por aviso, −3 por mejora)", "",
         f"- URLs rastreadas: {t['urls']} · HTML 200: {t['html_200']} · Indexables: {t['indexable']}",
         f"- Códigos: 2xx {t['codes']['2xx']} · 3xx {t['codes']['3xx']} · 4xx {t['codes']['4xx']} · "
         f"5xx {t['codes']['5xx']} · sin respuesta {t['codes']['error']}",
         f"- Incidencias: {t['critical']} críticas · {t['warning']} avisos · {t['notice']} mejoras", ""]
    if not audit["issues"]:
        L.append("No se han encontrado problemas. 🎉")
    current = None
    for i in audit["issues"]:
        if i["severity"] != current:
            current = i["severity"]
            L += ["", f"## {SEVERITY_ES[current]}", ""]
        L += [f"### {i['title']} — {i['count']}", "", i["fix"], ""]
        for u in i["urls"][:max_urls]:
            L.append(f"- {u}")
        if i["count"] > max_urls:
            L.append(f"- … y {i['count'] - max_urls} más (ver crawl.xlsx / report.html)")
        L.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))


def write_html(audit, pages, path):
    tpl_path = os.path.join(HERE, "..", "assets", "report_template.html")
    with open(tpl_path, encoding="utf-8") as f:
        tpl = f.read()
    keep = ["url", "status_code", "content_type", "indexable", "indexability_status", "title",
            "title_len", "meta_description", "meta_desc_len", "h1", "h1_count", "canonical",
            "canonical_status", "lang", "viewport", "word_count", "size_kb", "images",
            "images_no_alt", "internal_links", "external_links", "inlinks", "is_https",
            "mixed_content", "structured_data", "structured_data_count", "content_hash",
            "redirect_to", "redirect_chain", "response_ms", "crawl_depth", "error"]
    slim = [{k: p.get(k, "") for k in keep if k in p} for p in pages]
    extra = [i for i in audit["issues"] if i["id"] not in RULE_BY_ID]
    payload = {"domain": audit["domain"], "generated": audit["generated"],
               "pages": slim, "extraIssues": extra}
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    html = tpl.replace("/*__SILENTRAT_DATA__*/null", data)
    if not html.lstrip().lower().startswith("<!doctype"):
        html = ('<!doctype html>\n<html lang="es"><head><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width, initial-scale=1"></head><body>\n'
                + html + "\n</body></html>")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main():
    ap = argparse.ArgumentParser(description="SilentRat SEO Audit")
    ap.add_argument("url", nargs="?", help="Start URL (or sitemap URL with --mode sitemap)")
    ap.add_argument("--from-csv", help="Analyze an existing SilentRat CSV instead of crawling")
    ap.add_argument("--out-dir", default="silentrat_out")
    ap.add_argument("--max", type=int, default=500, help="Max URLs to crawl (default 500)")
    ap.add_argument("--threads", type=int, default=5)
    ap.add_argument("--delay", type=float, default=0.0)
    ap.add_argument("--mode", choices=["spider", "list", "sitemap"], default="spider")
    ap.add_argument("--list-file", default="")
    ap.add_argument("--include", default="")
    ap.add_argument("--exclude", default="")
    ap.add_argument("--render", action="store_true", help="Render JavaScript (needs Chrome)")
    ap.add_argument("--no-robots", action="store_true")
    ap.add_argument("--no-resources", action="store_true")
    a = ap.parse_args()

    os.makedirs(a.out_dir, exist_ok=True)
    out = lambda name: os.path.join(a.out_dir, name)
    resources = external = None

    if a.from_csv:
        pages = read_csv(a.from_csv)
        if not pages:
            sys.exit("El CSV está vacío.")
        from urllib.parse import urlparse
        domain = urlparse(pages[0].get("url", "")).netloc or "sitio"
        meta = {"source": os.path.basename(a.from_csv)}
    else:
        if not a.url:
            ap.error("Indica una URL o --from-csv")
        url = a.url if a.url.startswith(("http://", "https://")) else "https://" + a.url
        from seo_spider import SeoSpider
        seeds = []
        if a.mode == "list" and a.list_file:
            with open(a.list_file, encoding="utf-8") as f:
                seeds = [ln.strip() for ln in f if ln.strip()]
        sp = SeoSpider(start_url=url, max_urls=a.max, delay=a.delay, threads=a.threads,
                       respect_robots=not a.no_robots, check_resources=not a.no_resources,
                       include_pattern=a.include, exclude_pattern=a.exclude,
                       mode=a.mode, seed_urls=seeds, render_js=a.render)
        sp.on_status = lambda *x: None
        t0 = time.time()
        import contextlib, io
        print(f"[SilentRat] Rastreando {url} (máx. {a.max} URLs)…", flush=True)
        with contextlib.redirect_stdout(io.StringIO()):  # the engine logs one line per URL
            sp.crawl()
        elapsed = round(time.time() - t0, 1)
        pages = [{k: ("" if v is None else str(v)) for k, v in asdict(r).items()}
                 for r in sp.results.values()]
        resources = [asdict(r) for r in sp.resources.values()]
        external = dict(sp.external_checked)
        domain = sp.domain
        meta = {"start_url": url, "max": a.max, "mode": a.mode, "seconds": elapsed}

        sp.export_csv(out("crawl.csv"))
        try:
            sp.export_xlsx(out("crawl.xlsx"))
        except ImportError:
            print("[aviso] openpyxl no instalado: se omite crawl.xlsx")
        n = sp.generate_sitemap(out("sitemap.xml"))
        meta["sitemap_urls"] = n

        # Everything failed with a proxy/network error → tell the caller clearly.
        if pages and all(_int(p["status_code"]) == 0 for p in pages):
            err = pages[0].get("error", "")
            print("\n[ERROR DE RED] No se pudo descargar ninguna URL.")
            print("Detalle:", err[:300])
            if "403" in err and "proxy" in err.lower():
                print("NETWORK_BLOCKED: el entorno bloquea este dominio. "
                      "Hay que permitir el acceso a la red (todos los dominios) en la configuración de Claude.")
            sys.exit(2)

    audit = build_audit(pages, domain, resources, external, meta)
    with open(out("audit.json"), "w", encoding="utf-8") as f:
        json.dump(audit, f, ensure_ascii=False, indent=2)
    write_markdown(audit, out("audit.md"))
    write_html(audit, pages, out("report.html"))

    t = audit["totals"]
    print(f"\nSilentRat · {domain} · salud {audit['score']}/100")
    print(f"URLs {t['urls']} · HTML 200 {t['html_200']} · críticos {t['critical']} · "
          f"avisos {t['warning']} · mejoras {t['notice']}")
    for i in audit["issues"]:
        print(f"  [{i['severity']:8}] {i['count']:5}  {i['title']}")
    print(f"\nArchivos en {os.path.abspath(a.out_dir)}")


if __name__ == "__main__":
    main()
