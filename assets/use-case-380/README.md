# Full-catalog category browser

`site/themes/index.html` is a small, committed static entry point. It reads the
same `/data/benchmark-index.json` as the homepage and imports the existing
`catalog-search.js` implementation used by `app.js`'s `searchBenchmarkIndex`.
There is no category-page generator, second tokenizer or copied ranking code.

## Reproduce

From a Python 3.12 development environment with Node 22 available:

```sh
python -m pip install -e '.[dev]'
benchmark-radar normalize-catalog
python -m http.server 8942 --bind 127.0.0.1 --directory site
```

Open `http://127.0.0.1:8942/themes/`. Normalization provides the shared catalog
and linked benchmark detail pages; it does not generate the category browser.
The daily workflow, snapshot writer, rebuild and classification code are unchanged
from main. No new workflow step, dependency or snapshot field is added.

## Coverage and controls

The fresh catalog has 3,228 records across five sources: 687 LLM Stats, 25
Artificial Analysis, 1,914 Claire Radar, 141 Model reports and 461 OpenCompass
Hub records. Every record is rendered once by default, including all four
uncategorized records and records missing dates or scores.

The menu has 12 common categories, All and Uncategorized. Its information note
states that 12 of 416 browsing categories are shown, 404 additional categories
remain searchable, and two data-quality labels are excluded from the menu.
Unsupported / 不支持 labels never remove their records from browsing or search.
Category counts overlap; record totals do not.

Search stays on this page, uses the existing shared search over the full corpus,
and then applies the category selection. Full and partial lexical matches are
labelled separately. Clearing both controls restores every record. Catalog load
or validation failure shows an error and no plausible subset; without JavaScript,
the page offers the full catalog download instead.

## Screenshots and checks

These captures use code `cdcc924e`, including main `5d86e015`:

- `themes-page.png`: desktop arrival, 1440 × 900.
- `themes-page-pinned.png`: Agents selected, 197 matching records, 1440 × 900.
- `themes-page-mobile.png`: mobile arrival, 390 × 844.

Device scale factor is 1. Browser checks reconciled the exact rendered ID set,
verified common and uncategorized membership, searched an omitted singleton
category (`faithfulness`), compared HLE and task-search results with the shared
module, exercised combined filters and reset, and tested 320, 390 and 1440 px
widths under both light and dark browser preferences. The shared site's existing
light palette is preserved. No script errors or document horizontal overflow
were found. HTTP errors and malformed catalogs were tested separately, including
the completed error-state text and absence of unhandled page errors.

The automated Node/Python checks exercise the same real catalog and shared
search module, rare-category access, and catalog-loading failure. The loading
regressions fail before the error-handler fix and pass afterwards.

## Transfer sizes

Measured from this build, with gzip mtime=0 (raw / gzipped bytes):

| File | Raw | Gzipped |
| --- | ---: | ---: |
| New static HTML | 11,446 | 3,786 |
| New category browser script | 6,088 | 2,231 |
| New category styles | 2,143 | 795 |
| Existing shared search module | 9,867 | 3,577 |
| Existing shared catalog | 9,567,593 | 1,383,426 |

New page resources total 6,812 gzipped bytes. A cold visit still needs the shared
catalog and existing styles/scripts; this is not a claim that the whole visit
costs 6.8 KB. Default HTTP caching is used. A controlled gzip/cache-header server
confirmed the catalog came from browser cache after visiting Saturation. The
plain local Python server sometimes retransferred it, so reuse depends on the
host's HTTP caching and is not a production transfer measurement.
