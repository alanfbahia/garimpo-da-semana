# Garimpo da Semana

Static affiliate catalog of best-selling Shopee and Mercado Livre products, refreshed automatically.

## Layout

| Path | Purpose |
|---|---|
| `site/` | Published website (static hosting). `site/data/products.json` is the live catalog. |
| `scripts/update_catalog.py` | Daily: pulls best sellers from the Shopee Affiliate Open API and merges Mercado Livre items. |
| `scripts/post_telegram.py` | 4x/day: posts two deals to the Telegram channel. |
| `data/mercadolivre.json` | Mercado Livre items with affiliate links (refreshed weekly from the affiliate hub). |
| `data/posted.json` | Telegram post history (written by the bot). |
| `.github/workflows/` | Schedules: `site.yml` (catalog + deploy), `telegram.yml` (posts). |

## Configuration

Repository **secrets** (Settings → Secrets and variables → Actions → Secrets):

- `SHOPEE_APP_ID`, `SHOPEE_APP_SECRET`: Shopee affiliate Open API credentials
- `TELEGRAM_BOT_TOKEN`: bot token from BotFather (bot must be a channel admin)

Repository **variables** (same page → Variables):

- `TELEGRAM_CHAT_ID`: channel username, e.g. `@garimpodasemana`
- `TELEGRAM_CHANNEL_URL`: public link, e.g. `https://t.me/garimpodasemana`

Credentials live only in repository secrets. Never commit them; `.gitignore` blocks `.env` files.

## Local test

```
SHOPEE_MOCK_FILE=mock.json python scripts/update_catalog.py
DRY_RUN=1 python scripts/post_telegram.py
python tools/make_preview.py .   # single-file preview in build/
```

## Security notes

- Product data is treated as untrusted: rendered with `textContent`, links and images checked against host allowlists, Telegram captions HTML-escaped.
- Content-Security-Policy restricts scripts to the site's own files.
- No user data is collected; see `site/politica-privacidade.html`.
