"""Renders short vertical videos (1080x1920) from the current catalog for YouTube Shorts / TikTok / Reels.

Each video: hook card -> 5 product cards (photo, rank, price, discount, sales) -> call to action.
Outputs media/videos/<date>/<slug>.mp4 plus <slug>.json with title, description and hashtags.
Files are kept under ~3.3 MB so they can be uploaded from a browser extension.

Needs: Pillow, ffmpeg. Product images are downloaded from the store CDNs.
"""
from __future__ import annotations

import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "site" / "data" / "products.json"
FONTS = ROOT / "tools" / "fonts"
ICON = ROOT / "site" / "assets" / "img" / "icon-512.png"
OUT_ROOT = ROOT / "media" / "videos"
W, H = 1080, 1920
ORANGE, ORANGE_D, GOLD, INK, RED, GREEN = (242, 107, 29), (201, 82, 14), (255, 197, 51), (31, 35, 48), (224, 52, 43), (19, 138, 79)
STORE = {"shopee": "Shopee", "mercadolivre": "Mercado Livre"}
SITE = "garimpodasemana.com"


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), size)


F_HOOK = lambda s: font("InterDisplay-ExtraBold.otf", s)
F_BOLD = lambda s: font("Inter-Bold.otf", s)
F_SEMI = lambda s: font("Inter-SemiBold.otf", s)


def brl(v: float) -> str:
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def discount(p: dict) -> int:
    old = p.get("old_price") or 0
    return round((1 - p["price"] / old) * 100) if old > p["price"] else 0


def sold_txt(n: int) -> str:
    return f"+{n // 1000} mil vendidos" if n >= 1000 else (f"+{n} vendidos" if n else "")


def wrap(draw, text, fnt, width, max_lines):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=fnt) <= width:
            cur = t
        else:
            lines.append(cur)
            cur = w
            if len(lines) == max_lines:
                break
    if len(lines) < max_lines and cur:
        lines.append(cur)
    if len(lines) == max_lines and " ".join(lines) != text:
        while draw.textlength(lines[-1] + "…", font=fnt) > width:
            lines[-1] = lines[-1].rsplit(" ", 1)[0]
        lines[-1] += "…"
    return lines


def fetch_image(url: str) -> Image.Image | None:
    if not url:
        return None
    candidates = [url]
    if url.endswith(".webp"):
        candidates.insert(0, url[:-5] + (".jpg" if "mlstatic" in url else ""))
    for u in candidates:
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0 (garimpo-video-builder)"})
            with urllib.request.urlopen(req, timeout=20) as r:
                return Image.open(io.BytesIO(r.read())).convert("RGB")
        except Exception:
            continue
    return None


def background() -> Image.Image:
    bg = Image.new("RGB", (W, H), ORANGE)
    d = ImageDraw.Draw(bg)
    for y in range(H):  # vertical gradient orange -> deep orange
        t = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip((255, 138, 43), (226, 69, 12))))
    return bg


def logo_row(img: Image.Image, y: int):
    icon = Image.open(ICON).convert("RGBA").resize((110, 110))
    img.paste(icon, (80, y), icon)
    d = ImageDraw.Draw(img)
    d.text((215, y + 6), "garimpo", font=F_HOOK(64), fill="white")
    d.text((219, y + 76), "DA SEMANA", font=F_SEMI(26), fill="white")


def hook_card(hook: str, sub: str) -> Image.Image:
    img = background()
    logo_row(img, 120)
    d = ImageDraw.Draw(img)
    y = 560
    for line in wrap(d, hook, F_HOOK(118), W - 160, 5):
        d.text((80, y), line, font=F_HOOK(118), fill="white")
        y += 132
    y += 40
    d.rounded_rectangle([80, y, 80 + d.textlength(sub, font=F_BOLD(46)) + 60, y + 86], radius=43, fill=GOLD)
    d.text((110, y + 16), sub, font=F_BOLD(46), fill=(106, 58, 0))
    return img


def product_card(p: dict, rank: int, photo: Image.Image | None) -> Image.Image:
    img = background()
    d = ImageDraw.Draw(img)
    # header
    d.text((80, 110), f"#{rank}", font=F_HOOK(120), fill=GOLD)
    d.text((80 + d.textlength(f"#{rank}", font=F_HOOK(120)) + 30, 150), STORE[p["store"]].upper(), font=F_BOLD(44), fill="white")
    # photo card
    card = [70, 300, W - 70, 300 + 860]
    d.rounded_rectangle(card, radius=48, fill="white")
    if photo:
        ph = photo.copy()
        scale = min((W - 220) / ph.width, 780 / ph.height)  # fit the card, enlarging small photos
        ph = ph.resize((max(1, int(ph.width * scale)), max(1, int(ph.height * scale))), Image.LANCZOS)
        img.paste(ph, ((W - ph.width) // 2, 300 + (860 - ph.height) // 2))
    off = discount(p)
    if off >= 5:
        label = f"-{off}%"
        tw = d.textlength(label, font=F_HOOK(80))
        d.rounded_rectangle([W - 110 - tw - 60, 330, W - 110, 450], radius=28, fill=RED)
        d.text((W - 110 - tw - 30, 344), label, font=F_HOOK(80), fill="white")
    # text block
    y = 1210
    for line in wrap(d, p["title"], F_BOLD(56), W - 160, 2):
        d.text((80, y), line, font=F_BOLD(56), fill="white")
        y += 68
    y += 20
    if off >= 5:
        old = f"R$ {brl(p['old_price'])}"
        d.text((80, y), old, font=F_SEMI(46), fill=(255, 225, 205))
        tw = d.textlength(old, font=F_SEMI(46))
        d.line([(80, y + 28), (80 + tw, y + 28)], fill=(255, 225, 205), width=4)
        y += 62
    price = f"R$ {brl(p['price'])}"
    d.rounded_rectangle([70, y, 70 + d.textlength(price, font=F_HOOK(120)) + 60, y + 150], radius=34, fill="white")
    d.text((100, y + 8), price, font=F_HOOK(120), fill=INK)
    y += 180
    facts = " · ".join(x for x in [f"★ {str(p['rating']).replace('.', ',')}" if p.get("rating") else "", sold_txt(p.get("sold", 0))] if x)
    if facts:
        d.text((80, y), facts, font=F_SEMI(46), fill="white")
    return img


def cta_card() -> Image.Image:
    img = background()
    logo_row(img, 120)
    d = ImageDraw.Draw(img)
    y = 620
    for line in ["Links de todos", "os produtos", "no perfil"]:
        d.text((80, y), line, font=F_HOOK(124), fill="white")
        y += 140
    y += 50
    d.rounded_rectangle([70, y, W - 70, y + 140], radius=40, fill="white")
    d.text((110, y + 34), SITE, font=F_HOOK(72), fill=ORANGE_D)
    y += 200
    d.text((80, y), "Ofertas todo dia no canal do Telegram", font=F_SEMI(44), fill="white")
    d.text((80, y + 70), "Preços podem mudar. Links de afiliado.", font=F_SEMI(34), fill=(255, 225, 205))
    return img


def render(frames: list[tuple[Image.Image, float]], out: Path):
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        parts = []
        for i, (im, dur) in enumerate(frames):
            png = tmp / f"f{i}.png"
            im.save(png)
            part = tmp / f"p{i}.mp4"
            n = int(dur * 30)
            # gentle zoom-in for motion (Ken Burns)
            vf = (f"scale=1188:2112,zoompan=z='min(zoom+0.0009,1.06)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                  f":d={n}:s={W}x{H}:fps=30,format=yuv420p")
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", str(png), "-vf", vf, "-frames:v", str(n),
                            "-c:v", "libx264", "-preset", "veryfast", "-crf", "30", str(part)], check=True)
            parts.append(part)
        lst = tmp / "list.txt"
        lst.write_text("".join(f"file '{p}'\n" for p in parts))
        total = sum(d for _, d in frames)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                        "-f", "lavfi", "-t", str(total), "-i", "anullsrc=r=44100:cl=stereo",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "30", "-maxrate", "1300k", "-bufsize", "2600k",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "64k", "-shortest", "-movflags", "+faststart", str(out)],
                       check=True)


def themes(products: list[dict]) -> list[dict]:
    by_sold = sorted(products, key=lambda p: p.get("sold", 0), reverse=True)
    by_off = sorted(products, key=lambda p: (discount(p), p.get("sold", 0)), reverse=True)
    pick = lambda xs: [p for p in xs if p.get("image")][:5]
    t = [
        {"slug": "achados-ate-50", "hook": "5 achados até R$ 50 que estão vendendo muito", "sub": "Shopee e Mercado Livre",
         "items": pick([p for p in by_sold if p["price"] <= 50]), "tags": "#achados #achadinhos #shopee #mercadolivre #ofertas"},
        {"slug": "maiores-descontos", "hook": "Os 5 maiores descontos da semana", "sub": "Entre os mais vendidos",
         "items": pick(by_off), "tags": "#promoção #desconto #ofertas #blackfriday #achados"},
        {"slug": "moda-mais-vendidos", "hook": "As roupas mais vendidas da semana", "sub": "Com até 60% OFF",
         "items": pick([p for p in by_off if p["category"] == "moda"]), "tags": "#moda #look #achadosdemoda #mercadolivre #shopee"},
        {"slug": "casa-achados", "hook": "Achados para casa que todo mundo está comprando", "sub": "Preço de verdade",
         "items": pick([p for p in by_sold if p["category"] == "casa"]), "tags": "#casa #organização #achadosdacasa #shopee #utilidades"},
        {"slug": "academia-fitness", "hook": "Os mais vendidos para treinar", "sub": "Suplementos, tênis e roupas",
         "items": pick([p for p in by_sold if p["category"] == "esporte"]), "tags": "#academia #fitness #treino #creatina #achados"},
    ]
    return [x for x in t if len(x["items"]) >= 3]


def main() -> int:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    if data.get("meta", {}).get("demo"):
        print("Demo catalog: no videos.")
        return 0
    date = datetime.now(timezone(timedelta(hours=-3))).strftime("%Y-%m-%d")
    out_dir = OUT_ROOT / date
    if OUT_ROOT.exists():  # keep only the current batch in the repo
        shutil.rmtree(OUT_ROOT)
    out_dir.mkdir(parents=True)
    cache: dict[str, Image.Image | None] = {}
    for th in themes(data["products"]):
        frames = [(hook_card(th["hook"], th["sub"]), 2.6)]
        for i, p in enumerate(th["items"], 1):
            if p["id"] not in cache:
                cache[p["id"]] = fetch_image(p.get("image", ""))
            frames.append((product_card(p, i, cache[p["id"]]), 3.0))
        frames.append((cta_card(), 3.0))
        mp4 = out_dir / f"{th['slug']}.mp4"
        render(frames, mp4)
        lines = [f"#{i} {p['title']} – R$ {brl(p['price'])} ({STORE[p['store']]})" for i, p in enumerate(th["items"], 1)]
        meta = {
            "title": (th["hook"] + " #shorts")[:100],
            "description": th["hook"] + "\n\n" + "\n".join(lines) +
                           f"\n\n🔗 Links de todos os produtos: {SITE}\nPreços consultados em {date}; podem mudar. Links de afiliado.\n\n" + th["tags"],
            "tags": th["tags"],
            "products": [p["id"] for p in th["items"]],
        }
        (out_dir / f"{th['slug']}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{mp4.name}: {mp4.stat().st_size / 1e6:.2f} MB, {len(th['items'])} products")
    return 0


if __name__ == "__main__":
    sys.exit(main())
