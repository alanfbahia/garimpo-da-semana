"""Builds static product pages, the Pinterest RSS feed and the sitemap from site/data/products.json.

Outputs (all under site/):
  p/<id>.html     one page per product (shareable, indexable, Pinterest-friendly)
  feed.xml        RSS 2.0 feed of current products (Pinterest "auto-publish from RSS")
  sitemap.xml     home, privacy page and every product page
"""
from __future__ import annotations

import html
import json
import re
import shutil
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
BASE = "https://garimpodasemana.com"
CHECKED = ""
FEED_SIZE = 15  # pins per weekly refresh; keeps the Pinterest account from bursting
STORE = {"shopee": "Shopee", "mercadolivre": "Mercado Livre"}
CSP = ("default-src 'self'; style-src 'self' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; "
       "img-src 'self' data: https://*.susercontent.com https://cf.shopee.com.br https://*.mlstatic.com; "
       "base-uri 'self'; form-action 'none'; frame-ancestors 'none'")
LINK_HOSTS = ("shopee.com.br", "shope.ee", "mercadolivre.com.br", "mercadolivre.com", "meli.la")


def esc(v) -> str:
    return html.escape(str(v), quote=True)


def safe_id(p: dict) -> str:
    return re.sub(r"[^A-Za-z0-9-]", "", p["id"])[:60]


def safe_link(url: str) -> str | None:
    m = re.match(r"^https://([^/]+)/", url or "")
    if not m:
        return None
    host = m.group(1).lower()
    return url if any(host == h or host.endswith("." + h) for h in LINK_HOSTS) else None


def safe_image(url: str) -> str:
    m = re.match(r"^https://([^/]+)/", url or "")
    if m and (m.group(1).endswith(".susercontent.com") or m.group(1).endswith(".mlstatic.com")
              or m.group(1) == "cf.shopee.com.br"):
        return url
    return ""


def jpg(url: str) -> str:
    """Pinterest reads JPEG reliably; both CDNs serve JPEG when the .webp suffix is dropped/changed."""
    if url.endswith(".webp"):
        return url[:-5] + (".jpg" if "mlstatic" in url else "")
    return url


def brl(v: float) -> str:
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def na(store_key: str) -> str:
    return "no Mercado Livre" if store_key == "mercadolivre" else "na Shopee"


def discount(p: dict) -> int:
    old = p.get("old_price") or 0
    return round((1 - p["price"] / old) * 100) if old > p["price"] else 0


def sold_text(n: int) -> str:
    if not n:
        return ""
    return f"{n // 1000} mil+ vendidos" if n >= 1000 else f"{n} vendidos"


def page(p: dict, cats: dict, related: list[dict]) -> str:
    pid = safe_id(p)
    link = safe_link(p["url"])
    img = safe_image(p.get("image", ""))
    off = discount(p)
    store = STORE[p["store"]]
    cta = f"Ver no {store}" if p["store"] == "mercadolivre" else f"Ver na {store}"
    desc = f"{p['title']} por R$ {brl(p['price'])} {na(p['store'])}" + (f", {off}% OFF" if off >= 5 else "") + ". Um dos mais vendidos da semana."
    facts = []
    if p.get("rating"):
        facts.append(f"★ {str(p['rating']).replace('.', ',')}")
    if p.get("sold"):
        facts.append(sold_text(p["sold"]))
    rel = "".join(
        f'<a class="rel" href="/p/{safe_id(r)}.html"><span class="rel-t">{esc(r["title"])}</span>'
        f'<span class="rel-p">R$ {brl(r["price"])}</span></a>' for r in related)
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{CSP}">
<meta name="referrer" content="strict-origin-when-cross-origin">
<title>{esc(p['title'])} · Garimpo da Semana</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{BASE}/p/{pid}.html">
<meta property="og:type" content="product">
<meta property="og:title" content="{esc(p['title'])}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{BASE}/p/{pid}.html">
{f'<meta property="og:image" content="{esc(jpg(img))}">' if img else '<meta property="og:image" content="' + BASE + '/assets/img/og-image.jpg">'}
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="/favicon.ico" sizes="48x48">
<link rel="icon" href="/assets/img/icon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/assets/img/apple-touch-icon.png">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Figtree:wght@400;600;700&family=Rubik:wght@600;700&display=swap">
<link rel="stylesheet" href="/assets/style.css">
</head>
<body>
<header class="header"><div class="wrap wrap-simple">
  <a class="logo" href="/"><img class="logo-mark" src="/assets/img/icon.svg" alt="" width="40" height="40"><span class="logo-text">garimpo<small>DA SEMANA</small></span></a>
  <a class="cta-tg" href="/#canal">Canal de ofertas</a>
</div></header>
<main class="wrap">
  <p class="crumbs"><a href="/">Mais vendidos</a> › {esc(cats.get(p.get('category'), 'Ofertas'))}</p>
  <article class="pd section">
    <div class="pd-img">{f'<img src="{esc(img)}" alt="{esc(p["title"])}" referrerpolicy="no-referrer">' if img else ''}
      {f'<div class="badge-off">{off}%<small>OFF</small></div>' if off >= 5 else ''}</div>
    <div class="pd-body">
      <span class="store {p['store']}">{store}</span>
      <h1>{esc(p['title'])}</h1>
      <p class="meta">{' · '.join(esc(f) for f in facts)}</p>
      {f'<p class="price-old">R$ {brl(p["old_price"])}</p>' if off >= 5 else ''}
      <p class="price"><span class="price-now"><span class="cur">R$</span>{brl(p['price'])}</span>{f' <span class="price-off">{off}% OFF</span>' if off >= 5 else ''}</p>
      {f'<a class="btn-buy {p["store"]} pd-cta" href="{esc(link)}" target="_blank" rel="sponsored nofollow noopener noreferrer">{cta}</a>' if link else ''}
      <p class="pd-note">Preço consultado em {CHECKED}. O valor final, o frete e o estoque são definidos pela loja. Link de afiliado: podemos receber comissão, sem custo extra para você.</p>
    </div>
  </article>
  {f'<section class="section"><h2 class="rel-h">Outros mais vendidos</h2><div class="rel-grid">{rel}</div></section>' if rel else ''}
</main>
<footer class="footer"><div class="wrap"><p class="legal">Shopee e Mercado Livre são marcas de seus respectivos donos. Este site é independente. <a href="/politica-privacidade.html">Política de privacidade</a></p></div></footer>
</body>
</html>
"""


def bf_page(products: list[dict]) -> str:
    deals = sorted([p for p in products if discount(p) >= 20], key=lambda x: discount(x), reverse=True)[:24]
    cards = []
    for p in deals:
        img = safe_image(p.get("image", ""))
        off = discount(p)
        cards.append(f"""<article class="card">
  <a class="card-img" href="/p/{safe_id(p)}.html">{f'<img src="{esc(img)}" alt="{esc(p["title"])}" loading="lazy" referrerpolicy="no-referrer">' if img else ''}<div class="badge-off">{off}%<small>OFF</small></div></a>
  <div class="card-body">
    <span class="store {p['store']}">{STORE[p['store']]}</span>
    <h3 class="title"><a href="/p/{safe_id(p)}.html">{esc(p['title'])}</a></h3>
    <span class="price-old">R$ {brl(p['old_price'])}</span>
    <div class="price"><span class="price-now"><span class="cur">R$</span>{brl(p['price'])}</span><span class="price-off">{off}% OFF</span></div>
    <a class="btn-buy {p['store']}" href="{esc(safe_link(p['url']))}" target="_blank" rel="sponsored nofollow noopener noreferrer">{'Ver no Mercado Livre' if p['store'] == 'mercadolivre' else 'Ver na Shopee'}</a>
  </div>
</article>""")
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{CSP.replace("default-src 'self';", "default-src 'self'; script-src 'self';")}">
<title>Black Friday 2026: os maiores descontos · Garimpo da Semana</title>
<meta name="description" content="Black Friday 2026 na Shopee e no Mercado Livre: os produtos mais vendidos com os maiores descontos, atualizados toda semana.">
<link rel="canonical" href="{BASE}/black-friday.html">
<meta property="og:title" content="Black Friday 2026: os maiores descontos dos mais vendidos">
<meta property="og:image" content="{BASE}/assets/img/og-image.jpg">
<link rel="icon" href="/favicon.ico" sizes="48x48">
<link rel="icon" href="/assets/img/icon.svg" type="image/svg+xml">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Figtree:wght@400;600;700;800&family=Rubik:wght@600;700&display=swap">
<link rel="stylesheet" href="/assets/style.css">
</head>
<body>
<header class="header"><div class="wrap wrap-simple">
  <a class="logo" href="/"><img class="logo-mark" src="/assets/img/icon.svg" alt="" width="40" height="40"><span class="logo-text">garimpo<small>DA SEMANA</small></span></a>
  <a class="cta-tg" href="/#canal">Canal de ofertas</a>
</div></header>
<main class="wrap">
  <section class="bf">
    <div>
      <div class="bf-kicker">Black Friday 2026 · 27 de novembro</div>
      <h1 class="bf-h1">Os maiores descontos entre os mais vendidos</h1>
      <p>Produtos com nota alta e milhares de vendas que já estão com 20% OFF ou mais. A lista muda toda semana até a Black Friday.</p>
    </div>
    <div class="countdown" id="countdown">
      <div class="cd-box"><div class="cd-num" data-k="d">00</div><div class="cd-lbl">dias</div></div>
      <div class="cd-box"><div class="cd-num" data-k="h">00</div><div class="cd-lbl">horas</div></div>
      <div class="cd-box"><div class="cd-num" data-k="m">00</div><div class="cd-lbl">min</div></div>
      <div class="cd-box"><div class="cd-num" data-k="s">00</div><div class="cd-lbl">seg</div></div>
    </div>
  </section>
  <section class="section">
    <div class="section-head"><h2>{len(deals)} ofertas com 20% OFF ou mais</h2><span class="sub">Preços consultados em {CHECKED}. Confira o valor final na loja.</span></div>
    <div class="grid">{''.join(cards)}</div>
  </section>
  <section class="tg-band"><div><h2>Receba os descontos da Black Friday no celular</h2><p>Avisamos no canal do Telegram assim que os preços caírem.</p></div><a class="cta-tg" href="/#canal">Entrar no canal</a></section>
</main>
<footer class="footer"><div class="wrap"><p class="legal">Links de afiliado: podemos receber comissão, sem custo extra para você. Shopee e Mercado Livre são marcas de seus respectivos donos. <a href="/politica-privacidade.html">Política de privacidade</a></p></div></footer>
<script src="/assets/bf.js" defer></script>
</body>
</html>
"""


def main() -> int:
    data = json.loads((SITE / "data" / "products.json").read_text(encoding="utf-8"))
    if data.get("meta", {}).get("demo"):
        print("Demo catalog: skipping product pages.")
        return 0
    global CHECKED
    upd = data.get("meta", {}).get("updated_at", "")
    CHECKED = f"{upd[8:10]}/{upd[5:7]}/{upd[0:4]}" if len(upd) >= 10 else "data recente"
    products = [p for p in data["products"] if safe_link(p.get("url", ""))]
    cats = {c["id"]: c["label"] for c in data.get("categories", [])}

    out = SITE / "p"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir()
    for p in products:
        related = [r for r in products if r["category"] == p["category"] and r["id"] != p["id"]][:6]
        (out / f"{safe_id(p)}.html").write_text(page(p, cats, related), encoding="utf-8")

    # Stable timestamp (catalog date) so re-running the build does not change the file.
    upd = data.get("meta", {}).get("updated_at")
    now = format_datetime(datetime.fromisoformat(upd) if upd else datetime.now(timezone.utc))
    items = []
    for p in sorted(products, key=lambda x: (discount(x), x.get("sold", 0)), reverse=True):
        if len(items) >= FEED_SIZE:
            break
        img = jpg(safe_image(p.get("image", "")))
        if not img:
            continue
        off = discount(p)
        desc = f"{p['title']} por R$ {brl(p['price'])} {na(p['store'])}" + (f" ({off}% OFF)" if off >= 5 else "") + \
               f". {sold_text(p.get('sold', 0))}. Veja mais achados em garimpodasemana.com"
        items.append(f"""  <item>
    <title>{esc(p['title'])}</title>
    <link>{BASE}/p/{safe_id(p)}.html</link>
    <guid isPermaLink="true">{BASE}/p/{safe_id(p)}.html</guid>
    <description>{esc(desc)}</description>
    <pubDate>{now}</pubDate>
    <enclosure url="{esc(img)}" type="image/jpeg" length="0"/>
    <media:content url="{esc(img)}" medium="image"/>
  </item>""")
    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">
<channel>
  <title>Garimpo da Semana</title>
  <link>{BASE}/</link>
  <description>Os mais vendidos da Shopee e do Mercado Livre, atualizados toda semana.</description>
  <language>pt-BR</language>
  <lastBuildDate>{now}</lastBuildDate>
{chr(10).join(items)}
</channel>
</rss>
"""
    (SITE / "feed.xml").write_text(feed, encoding="utf-8")
    (SITE / "black-friday.html").write_text(bf_page(products), encoding="utf-8")

    urls = [f"{BASE}/", f"{BASE}/black-friday.html", f"{BASE}/politica-privacidade.html"] + [f"{BASE}/p/{safe_id(p)}.html" for p in products]
    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + \
              "\n".join(f" <url><loc>{u}</loc></url>" for u in urls) + "\n</urlset>\n"
    (SITE / "sitemap.xml").write_text(sitemap, encoding="utf-8")
    print(f"{len(products)} product pages, {len(items)} feed items")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
