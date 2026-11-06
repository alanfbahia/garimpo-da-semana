"""Bundle site/ into one self-contained preview.html (CSS, JS and data inlined)."""
import json
import re
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
site = root / "site"
html = (site / "index.html").read_text(encoding="utf-8")
css = (site / "assets" / "style.css").read_text(encoding="utf-8")
js = (site / "assets" / "app.js").read_text(encoding="utf-8")
data = json.loads((site / "data" / "products.json").read_text(encoding="utf-8"))

html = re.sub(r"<!--CSP-->.*?<!--/CSP-->", "", html, flags=re.S)
html = re.sub(r"<!--STYLE-->.*?<!--/STYLE-->", lambda m: "<style>\n" + css + "\n</style>", html, flags=re.S)
payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
html = re.sub(r"<!--DATA-->.*?<!--/DATA-->", lambda m: "<script>window.__GARIMPO_DATA__ = " + payload + ";</script>", html, flags=re.S)
html = re.sub(r"<!--SCRIPT-->.*?<!--/SCRIPT-->", lambda m: "<script>\n" + js + "\n</script>", html, flags=re.S)
html = html.replace('href="politica-privacidade.html"', 'href="#canal"')

out = root / "build" / "preview.html"
out.write_text(html, encoding="utf-8")
print(out, len(html))
