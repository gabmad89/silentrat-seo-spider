---
name: silentrat-seo-audit
description: Rastrea una web con el crawler SilentRat (alternativa open source a Screaming Frog) y entrega una auditoría SEO priorizada con dashboard HTML, Excel y resumen. Úsalo cuando pidan auditar el SEO de una web, rastrear un sitio, buscar enlaces rotos, errores 404, titles o meta descriptions duplicados, H1, canonicals o analizar un CSV exportado por SilentRat.
---

# SilentRat SEO Audit

Crawler SEO completo (el motor de SilentRat) más una capa de análisis que convierte el rastreo en una lista de incidencias priorizadas: críticos, avisos y mejoras.

Proyecto: https://github.com/gabmad89/silentrat-seo-spider

## Archivos

- `scripts/seo_spider.py`: motor de rastreo de SilentRat, el mismo que usa la app de escritorio.
- `scripts/audit.py`: rastrea, aplica las reglas SEO y genera los informes.
- `assets/report_template.html`: plantilla del dashboard interactivo. `audit.py` la rellena con los datos.

## Flujo

### 1. Prepara la petición

Necesitas la URL de inicio. Si no la dan, pídela. Opciones útiles:

| Petición | Argumentos |
|---|---|
| Web pequeña o mediana (por defecto) | `--max 500` |
| Web grande / "rastréalo entero" | `--max 5000` (avisa de que tardará más) |
| Servidor lento o compartido | `--delay 0.5 --threads 2` |
| Solo una sección | `--include "/blog/"` o `--exclude "\?|/tag/"` |
| Desde el sitemap | `--mode sitemap` con la URL del sitemap.xml |
| Lista de URLs concretas | `--mode list --list-file urls.txt` |
| CSV de la app de escritorio | `--from-csv ruta/al/archivo.csv` (sin rastreo) |

Rastrea solo webs del usuario o que tenga permiso para auditar. El crawler respeta robots.txt por defecto; no uses `--no-robots` salvo que el usuario lo pida para su propia web.

### 2. Instala dependencias y ejecuta

```bash
pip install requests beautifulsoup4 lxml openpyxl --break-system-packages -q
python <ruta-del-skill>/scripts/audit.py https://ejemplo.com --max 500 --out-dir silentrat_out
```

El script imprime el progreso, la puntuación de salud y el recuento por incidencia. Tarda de segundos a unos minutos según el tamaño. Si la herramienta de shell tiene límite de tiempo, baja `--max` o ejecútalo en segundo plano.

### 3. Si sale `NETWORK_BLOCKED` (código de salida 2)

El entorno de Claude no tiene permiso para salir a esa web. Díselo al usuario en una frase y explícale cómo activarlo: en la configuración de Claude, apartado de capacidades, hay que permitir el acceso a la red para **todos los dominios** (en planes de empresa lo decide un administrador). Como alternativa, puede rastrear con la app de escritorio de SilentRat, exportar el CSV y subirlo aquí para analizarlo con `--from-csv`. No intentes saltarte el bloqueo por otras vías.

### 4. Lee los resultados y responde

Lee `silentrat_out/audit.md`. Responde en el idioma del usuario con:

1. **La puntuación de salud** (0–100) y el número de URLs rastreadas.
2. **Las 3–5 acciones con más impacto**, en orden: primero los críticos y luego los avisos que afectan a más URLs. Para cada una: qué pasa, cuántas URLs, 1–3 URLs de ejemplo y cómo arreglarlo de forma concreta.
3. Una línea sobre las mejoras menores, sin enumerarlas todas.

No pegues el informe entero en el chat: para eso están los archivos.

### 5. Entrega los archivos

En `silentrat_out/`:

- `report.html`: dashboard interactivo (salud, incidencias, tabla filtrable y detalle por URL). Es el entregable principal. Funciona sin conexión.
- `crawl.xlsx`: Excel con las hojas Overview, Internal, Resources, External y Duplicates.
- `crawl.csv`: todas las columnas. Se puede abrir en la app de escritorio o en el visor online.
- `audit.md` / `audit.json`: resumen e incidencias en formato legible y para máquinas.
- `sitemap.xml`: las páginas indexables con estado 200, listo para subir.

Entrégalos con la herramienta de archivos del entorno. Si existe la herramienta Artifact y el usuario quiere compartir el dashboard, puedes publicar `report.html` como artefacto (quita el doctype y las etiquetas html/head/body que añade el script, porque Artifact pone su propio esqueleto).

## Reglas de auditoría

Puntuación: cada URL empieza en 100 y pierde 40 por incidencia crítica, 15 por aviso y 3 por mejora (mínimo 0). La salud de la web es la media.

- **Críticos**: 4xx, 5xx, sin respuesta, sin `<title>`, contenido mixto y recursos rotos.
- **Avisos**: cadenas de redirección (2 o más saltos), titles o descriptions duplicados, title de más de 60 caracteres, sin meta description, sin H1, contenido duplicado exacto, imágenes sin alt, sin HTTPS, sin viewport, respuesta de más de 1 s y enlaces externos rotos.
- **Mejoras**: enlaces a redirecciones, title de menos de 30 caracteres, description de más de 160 o menos de 70, varios H1, menos de 300 palabras, sin canonical, sin lang, sin datos estructurados, más de 3 clics de profundidad, noindex y canonicalizadas.

Las reglas de `audit.py` y las de la plantilla HTML son las mismas. Si cambias una, cambia la otra.

## Notas

- `--render` (renderizado de JavaScript) necesita Chrome o Edge con Selenium, que no suelen estar en el entorno de Claude. Úsalo solo si `which google-chrome chromium` encuentra un navegador. Para webs hechas con React o Vue sin renderizado en servidor, avisa de que sin `--render` el contenido puede salir vacío.
- Core Web Vitals reales: la app de escritorio los mide en local. Desde el skill solo se tiene el tiempo de respuesta (`response_ms`).
