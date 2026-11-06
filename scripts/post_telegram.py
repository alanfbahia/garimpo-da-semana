"""Posts deals from site/data/products.json to the Telegram channel.

Each run posts POSTS_PER_RUN products that were not posted in the last REPOST_AFTER_DAYS days,
preferring the biggest discounts and best sellers. History is kept in data/posted.json.

Required environment variables (repository secrets):
  TELEGRAM_BOT_TOKEN   token from @BotFather (the bot must be an admin of the channel)
  TELEGRAM_CHAT_ID     channel username (@garimpodasemana) or numeric id
Optional:
  POSTS_PER_RUN (default 2), DRY_RUN=1 to print instead of sending
"""
from __future__ import annotations

import html
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "site" / "data" / "products.json"
HISTORY = ROOT / "data" / "posted.json"
REPOST_AFTER_DAYS = 10
STORE = {"shopee": "Shopee", "mercadolivre": "Mercado Livre"}
CAT_EMOJI = {"casa": "🏠", "pet": "🐾", "beleza": "💄", "tecnologia": "🎧", "auto": "🏍️", "moda": "👕", "esporte": "💪"}


def brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def discount(p: dict) -> int:
    old = p.get("old_price") or 0
    return round((1 - p["price"] / old) * 100) if old > p["price"] else 0


def caption(p: dict) -> str:
    e = html.escape
    lines = [f"{CAT_EMOJI.get(p.get('category'), '🔥')} <b>{e(p['title'])}</b>", ""]
    off = discount(p)
    if off >= 5:
        lines.append(f"De <s>{brl(p['old_price'])}</s> por <b>{brl(p['price'])}</b>  ({off}% OFF)")
    else:
        lines.append(f"Por <b>{brl(p['price'])}</b>")
    facts = []
    if p.get("rating"):
        facts.append(f"⭐ {str(p['rating']).replace('.', ',')}")
    if p.get("sold", 0) >= 1000:
        facts.append(f"{p['sold'] // 1000} mil+ vendidos")
    elif p.get("sold"):
        facts.append(f"{p['sold']} vendidos")
    if p.get("free_shipping"):
        facts.append("frete grátis")
    if facts:
        lines.append(" · ".join(facts))
    lines += ["", f"🛒 Comprar na {e(STORE[p['store']])}:" if p["store"] == "shopee" else f"🛒 Comprar no {e(STORE[p['store']])}:",
              e(p["url"]), "", "<i>Preço sujeito a alteração pela loja. Link de afiliado.</i>"]
    return "\n".join(lines)


def api(token: str, method: str, params: dict) -> dict:
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/{method}", data=data, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def main() -> int:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat = os.environ.get("TELEGRAM_CHAT_ID", "")
    dry = os.environ.get("DRY_RUN") == "1"
    per_run = int(os.environ.get("POSTS_PER_RUN", "2"))
    if not dry and not (token and chat):
        print("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set: nothing to do.")
        return 0

    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    if catalog.get("meta", {}).get("demo") and not dry:
        print("Catalog is still demo data: not posting.")
        return 0

    history = json.loads(HISTORY.read_text(encoding="utf-8")) if HISTORY.exists() else {}
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=REPOST_AFTER_DAYS)

    def fresh(p):
        last = history.get(p["id"])
        return not last or datetime.fromisoformat(last) < cutoff

    pool = [p for p in catalog.get("products", []) if fresh(p) and p.get("url", "").startswith("https://")]
    pool.sort(key=lambda p: (discount(p), p.get("sold", 0)), reverse=True)

    # Alternate stores so the channel does not show the same shop twice in a row.
    picked, last_store = [], None
    for p in pool:
        if len(picked) == per_run:
            break
        if p["store"] != last_store or all(q["store"] == last_store for q in pool[pool.index(p):]):
            picked.append(p)
            last_store = p["store"]

    for p in picked:
        text = caption(p)
        if dry:
            print(text, "\n" + "-" * 40)
        else:
            img = p.get("image", "")
            try:
                if img.startswith("https://"):
                    api(token, "sendPhoto", {"chat_id": chat, "photo": img, "caption": text, "parse_mode": "HTML"})
                else:
                    raise ValueError("no image")
            except Exception:
                api(token, "sendMessage", {"chat_id": chat, "text": text, "parse_mode": "HTML", "disable_web_page_preview": "false"})
            print(f"posted {p['id']}")
        history[p["id"]] = now.isoformat(timespec="seconds")

    if not dry:
        # Keep history small: drop entries older than 60 days.
        old = now - timedelta(days=60)
        history = {k: v for k, v in history.items() if datetime.fromisoformat(v) >= old}
        HISTORY.parent.mkdir(parents=True, exist_ok=True)
        HISTORY.write_text(json.dumps(history, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
