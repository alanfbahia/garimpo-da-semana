"""Weekly catalog builder.

Pulls best-selling products from the Shopee Affiliate Open API (official GraphQL endpoint),
merges them with the Mercado Livre items kept in data/mercadolivre.json (affiliate links are
generated in the ML affiliate hub, which has no public API), and writes site/data/products.json.

Required environment variables (set as repository secrets, never committed):
  SHOPEE_APP_ID, SHOPEE_APP_SECRET
Optional:
  TELEGRAM_CHANNEL_URL   public channel link shown on the site (https://t.me/...)
  SHOPEE_MOCK_FILE       path to a JSON file with canned API responses (tests only)
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "site" / "data" / "products.json"
MANUAL_FILES = {"mercadolivre": ROOT / "data" / "mercadolivre.json", "shopee": ROOT / "data" / "shopee.json"}
ENDPOINT = "https://open-api.affiliate.shopee.com.br/graphql"
BRT = timezone(timedelta(hours=-3))

# Category -> search keywords. Each keyword is queried sorted by units sold.
CATEGORIES = {
    "casa": ("Casa", ["organizador cozinha", "mop", "cortina blackout", "jogo de lençol", "utilidades domésticas"]),
    "pet": ("Pet", ["areia gato", "cama pet", "comedouro", "brinquedo cachorro"]),
    "beleza": ("Beleza", ["sérum facial", "protetor solar", "skincare", "escova secadora"]),
    "tecnologia": ("Tecnologia", ["fone bluetooth", "caixa de som bluetooth", "câmera wifi", "carregador turbo"]),
    "auto": ("Auto e Moto", ["acessórios moto", "acessórios carro", "suporte celular moto"]),
    "moda": ("Moda", ["kit meias", "camiseta masculina", "calça feminina"]),
    "esporte": ("Esporte e Saúde", ["garrafa térmica", "academia", "suplemento"]),
}
PER_KEYWORD = 15
PER_CATEGORY = 10
MIN_RATING = 4.5
MIN_SALES = 300
SORT_ITEM_SOLD_DESC = 2

QUERY = """
query($keyword: String, $sortType: Int, $page: Int, $limit: Int) {
  productOfferV2(keyword: $keyword, sortType: $sortType, page: $page, limit: $limit) {
    nodes {
      itemId productName price priceMin priceMax priceDiscountRate sales ratingStar
      imageUrl offerLink productLink commissionRate shopName
    }
    pageInfo { page limit hasNextPage }
  }
}
"""


class ApiError(RuntimeError):
    pass


def _signed_post(app_id: str, secret: str, payload: dict) -> dict:
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    ts = str(int(time.time()))
    signature = hashlib.sha256((app_id + ts + body + secret).encode("utf-8")).hexdigest()
    req = urllib.request.Request(
        ENDPOINT,
        data=body.encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"SHA256 Credential={app_id}, Timestamp={ts}, Signature={signature}",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if data.get("errors"):
        raise ApiError(json.dumps(data["errors"], ensure_ascii=False)[:500])
    return data["data"]


def fetch_keyword(keyword: str, app_id: str, secret: str, mock: dict | None) -> list[dict]:
    if mock is not None:
        return mock.get(keyword, [])
    payload = {"query": QUERY, "variables": {"keyword": keyword, "sortType": SORT_ITEM_SOLD_DESC, "page": 1, "limit": PER_KEYWORD}}
    for attempt in range(3):
        try:
            return _signed_post(app_id, secret, payload)["productOfferV2"]["nodes"] or []
        except ApiError:
            raise
        except Exception as exc:  # network hiccup: retry with backoff
            if attempt == 2:
                print(f"  ! {keyword}: {exc}", file=sys.stderr)
                return []
            time.sleep(2 * (attempt + 1))
    return []


def _num(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_shopee(node: dict, category: str) -> dict | None:
    price = _num(node.get("priceMin") or node.get("price"))
    link = node.get("offerLink") or ""
    title = (node.get("productName") or "").strip()
    if price <= 0 or not link.startswith("https://") or not title:
        return None
    rating = round(_num(node.get("ratingStar")), 1)
    sales = int(_num(node.get("sales")))
    if rating < MIN_RATING or sales < MIN_SALES:
        return None
    rate = _num(node.get("priceDiscountRate"))
    old_price = round(price / (1 - rate / 100), 2) if 0 < rate < 90 else None
    return {
        "id": f"sp-{node.get('itemId')}",
        "title": title[:120],
        "category": category,
        "store": "shopee",
        "price": round(price, 2),
        "old_price": old_price,
        "rating": rating,
        "sold": sales,
        "free_shipping": False,
        "image": node.get("imageUrl") or "",
        "url": link,
        "tags": [],
    }


def load_manual(store: str) -> list[dict]:
    """Items whose affiliate links were generated in the store's affiliate portal."""
    path = MANUAL_FILES[store]
    if not path.exists():
        return []
    items = json.loads(path.read_text(encoding="utf-8")).get("items", [])
    out = []
    for i, it in enumerate(items):
        if not it.get("url", "").startswith("https://") or not it.get("title") or not it.get("price"):
            continue
        out.append({
            "id": it.get("id") or f"{store[:2]}-m{i}",
            "title": it["title"][:120],
            "category": it.get("category", "casa"),
            "store": store,
            "price": float(it["price"]),
            "old_price": float(it["old_price"]) if it.get("old_price") else None,
            "rating": float(it.get("rating") or 0),
            "sold": int(it.get("sold") or 0),
            "free_shipping": bool(it.get("free_shipping")),
            "image": it.get("image", ""),
            "url": it["url"],
            "tags": it.get("tags", []),
        })
    return out


def main() -> int:
    app_id = os.environ.get("SHOPEE_APP_ID", "")
    secret = os.environ.get("SHOPEE_APP_SECRET", "")
    mock_path = os.environ.get("SHOPEE_MOCK_FILE")
    mock = json.loads(Path(mock_path).read_text(encoding="utf-8")) if mock_path else None
    use_api = mock is not None or bool(app_id and secret)
    if not use_api:
        print("Shopee API keys not set: using data/shopee.json only.")

    products: list[dict] = []
    seen: set[str] = set()
    for cat_id, (_, keywords) in (CATEGORIES.items() if use_api else []):
        bucket = []
        for kw in keywords:
            for node in fetch_keyword(kw, app_id, secret, mock):
                p = normalize_shopee(node, cat_id)
                if p and p["id"] not in seen:
                    seen.add(p["id"])
                    bucket.append(p)
        bucket.sort(key=lambda p: p["sold"], reverse=True)
        products.extend(bucket[:PER_CATEGORY])
        print(f"{cat_id}: {min(len(bucket), PER_CATEGORY)} Shopee items")

    for store in ("shopee", "mercadolivre"):
        manual = [m for m in load_manual(store) if m["id"] not in seen]
        seen.update(m["id"] for m in manual)
        products.extend(manual)
        print(f"{store} (portal links): {len(manual)} items")

    if len(products) < 6:
        print("Too few products returned: keeping the current catalog.", file=sys.stderr)
        return 0

    previous = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    tg = os.environ.get("TELEGRAM_CHANNEL_URL") or previous.get("meta", {}).get("telegram_url", "")
    catalog = {
        "meta": {"updated_at": datetime.now(BRT).isoformat(timespec="seconds"), "demo": False, "telegram_url": tg},
        "categories": [{"id": k, "label": v[0]} for k, v in CATEGORIES.items()],
        "products": products,
    }
    OUT.write_text(json.dumps(catalog, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Wrote {len(products)} products to {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
