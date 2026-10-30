"""Where share images live (issue #671).

Images in this repository would grow every clone, so none are committed here.
Each catalog benchmark's card is rendered by the Pages build into
``site/cards/`` and served from the site's own domain, and the same files are
archived in ktwu01/benchmark-radar-cards. Daily share images live only there,
served by its GitHub Pages site.
Imports nothing from the package but ``feed``, so the daily share code and the
static benchmark pages can both name a card without importing each other.
"""

from __future__ import annotations

from .feed import SITE_URL

CARDS_REPOSITORY = "ktwu01/benchmark-radar-cards"
# The branch GitHub Pages serves on CARDS_DOMAIN: the benchmark-card archive,
# and each day's share images under daily/<date>/. Pages is a CDN on a domain
# of ours; raw file URLs are neither, and are rate-limited.
CARDS_BRANCH = "cards"
CARDS_DOMAIN = "cards.benchmark-radar.org"
CARDS_SITE_URL = f"https://{CARDS_DOMAIN}"
# Where the site serves each benchmark's card. On the page's own host because X
# showed no preview for a benchmark page whose og:image sat on
# cards.benchmark-radar.org, while the same image on that host's own page, and
# this host's og-card.png on this host's pages, both showed (#891).
# site/assets/share-card.js builds the same path in the browser.
SITE_CARDS_DIR = "cards"


def benchmark_card_name(slug: str) -> str:
    """File name of a catalog benchmark's card."""
    return f"{slug}.png"


def benchmark_card_url(slug: str) -> str:
    """Public URL of a catalog benchmark's card on the site."""
    return f"{SITE_URL}/{SITE_CARDS_DIR}/{benchmark_card_name(slug)}"
