# SEO and indexing guide

Benchmark Radar now has one reliable public address:
`https://benchmark-radar.org/`. HTTPS, redirects, crawler files, and canonical
metadata passed the September 3 checks below, so search-engine setup can proceed
without sending conflicting domain signals.

## Live status

Last checked: **September 3, 2026**.

| Check | Live result | What to do |
| --- | --- | --- |
| DNS | Apex points to GitHub Pages; `www` points to `ktwu01.github.io` | Keep it |
| GitHub Pages domain | `benchmark-radar.org` is verified and publishing through GitHub Actions | Keep the publishing source on **GitHub Actions** |
| HTTPS | **Passing:** certificate approved and HTTPS enforced | Keep it |
| HTTP redirect | **Passing:** apex HTTP redirects to the HTTPS apex | Keep it |
| `www` redirect | **Passing:** HTTPS `www` redirects to the HTTPS apex | Keep it |
| `robots.txt` | **Current:** sitemap uses `benchmark-radar.org` | Keep it |
| `sitemap.xml` | **Current:** all 1,225 URLs use `benchmark-radar.org` | Keep it |
| Page metadata | **Current:** canonical and `og:url` use the HTTPS apex | Keep it |

Re-run the checks below after any DNS or Pages change. The table is a dated
snapshot, not a substitute for the live result.

## Fastest path to indexing

### 1. Keep workflow publishing and HTTPS healthy

In the GitHub repository, open **Settings → Pages** and confirm:

1. **Source** is set to **GitHub Actions**, not a branch and folder.
2. The custom domain is `benchmark-radar.org`.
3. **Enforce HTTPS** remains enabled.

This project deploys with a custom GitHub Actions workflow, so it does not need
a committed `CNAME` file. The domain configured in **Settings → Pages** is the
important setting.

On August 29, 2026, a root-level `CNAME` commit triggered a legacy deployment
from `main:/`. That source has no root `index.html` because the real artifact is
built from `site/`, so the successful legacy deployment replaced the dashboard
with a 404. Switching the publishing source back to GitHub Actions and rerunning
`.github/workflows/pages.yml` restored the site. Do not restore the root
`CNAME`; if a deployment succeeds but the public URL returns 404, check the
publishing source before changing DNS or the certificate.

Verify the result:

```bash
curl -I https://benchmark-radar.org/
curl -I http://benchmark-radar.org/
curl -I https://www.benchmark-radar.org/
```

Pass condition: the first URL has a valid certificate and returns `200`; HTTP
and `www` redirect to `https://benchmark-radar.org/`. Old project URLs should
also end at that HTTPS address, preferably in one redirect.

GitHub references:

- [Manage a custom domain](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/managing-a-custom-domain-for-your-github-pages-site)
- [Troubleshoot custom domains](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/troubleshooting-custom-domains-and-github-pages)
- [Secure a Pages site with HTTPS](https://docs.github.com/en/pages/getting-started-with-github-pages/securing-your-github-pages-site-with-https)

### 2. Deploy and check the canonical-domain files

The repository source is prepared to generate the new-domain metadata, feed,
robots file, and sitemap. After deploying, check the files search crawlers
actually receive:

```bash
curl -fsS https://benchmark-radar.org/robots.txt
curl -fsS https://benchmark-radar.org/sitemap.xml
curl -fsS https://benchmark-radar.org/ | grep -E 'canonical|og:url'
```

Every indexable URL should use `https://benchmark-radar.org`. There should be
no remaining `koutian.is-a.dev/benchmark-radar` or
`ktwu01.github.io/benchmark-radar` URLs in the live HTML, sitemap, feed,
generated pages, or internal links.

Use permanent redirects from both legacy hosts. Redirects are a stronger
canonical signal than a sitemap; combining redirects, `rel="canonical"`, and
consistent internal links makes the migration clearer to crawlers.

### 3. Add Google Search Console

1. Add a **Domain property** named `benchmark-radar.org` (no scheme or path).
2. Copy Google's TXT record into DNS and complete verification. A Domain
   property covers HTTP, HTTPS, the apex, and `www` together.
3. Submit `https://benchmark-radar.org/sitemap.xml` under **Sitemaps**.
4. In **URL Inspection**, test the live homepage and request indexing.
5. Inspect the canonical Google selected after crawling. It should be the HTTPS
   custom-domain URL.

Request indexing once after a meaningful fix. Google says crawling can take
days or weeks, is not guaranteed, and repeated requests do not make it faster.
The sitemap is also a hint, not a guarantee.

Google references:

- [Add a Search Console property](https://support.google.com/webmasters/answer/34592?hl=en)
- [Verify site ownership](https://support.google.com/webmasters/answer/9008080?hl=en)
- [Ask Google to recrawl a page](https://developers.google.com/search/docs/crawling-indexing/ask-google-to-recrawl)
- [Build and submit a sitemap](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap)

### 4. Add Bing Webmaster Tools

Import the verified Search Console property or add the site directly. Submit
the same sitemap, then use **URL Inspection** on the homepage. Bing also accepts
direct URL submissions.

[IndexNow](https://www.indexnow.org/) is optional. It is useful only if the
project wants search engines notified after each successful daily deployment;
it does not replace a sitemap or fix crawlability.

Bing references:

- [Submit URLs to Bing](https://www.bing.com/webmasters/help/URL-Submission-62f2860b)
- [Inspect a URL](https://www.bing.com/webmasters/help/URL-Inspection-55a30305)
- [Submit a sitemap](https://www.bing.com/webmasters/help/sitemaps-3b5cf6ed)

## Make each search result worth indexing

The homepage already supplies the right foundation: a descriptive title and
summary, a canonical URL, social preview metadata, and `WebSite` plus `Dataset`
JSON-LD. Validate the live HTML with Google's
[Rich Results Test](https://search.google.com/test/rich-results) after every
metadata change.

Each dashboard view and public utility is a real page at its own path:

```text
/leaderboard/
/trends/
/explore/
/cli/
/cite/
/rubric/
```

These are the dashboard, not summaries of it. Each one is written from
`site/index.html`, so it carries the same design and the same controls, and it
arrives with its own title, summary, canonical, breadcrumb, and a first screen
of real rows before any script runs. The script then takes over and the page
behaves like the rest of the dashboard.

The old `/?view=leaderboard` style of link still works and is rewritten to the
matching path in the browser, keeping any filters the reader arrived with. Those
query URLs are not listed in the sitemap, and neither are filter permutations:
a second URL for a page that already has one is a duplicate, not a second page.
The old `/#cli`, `/#cite`, and `/#rubric` links migrate the same way;
rubric versions use `/rubric/?version=<number>`.

Google references:

- [JavaScript SEO basics](https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics)
- [Canonical URL guidance](https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls)
- [Dataset structured data](https://developers.google.com/search/docs/appearance/structured-data/dataset)

## What to monitor

Check Search Console weekly for the first month after migration:

- **Page indexing:** the homepage is indexed under the HTTPS custom domain.
- **Sitemaps:** the sitemap is readable and its submitted URLs are discovered.
- **URL Inspection:** Google sees the intended canonical and no accidental
  `noindex` directive.
- **Performance:** impressions begin appearing for benchmark-related queries.
- **Core Web Vitals:** heavy dashboard data does not delay the first useful
  content.

Use Search Console as the source of truth. A `site:benchmark-radar.org` search
is a quick spot check, not a complete or authoritative index count.

## Launch checklist

- [x] Valid TLS certificate for the apex and `www`
- [x] **Enforce HTTPS** enabled in GitHub Pages
- [x] HTTP and legacy URLs permanently redirect to the HTTPS custom domain
- [x] Live `robots.txt`, sitemap, feed, canonicals, and internal links use only
      `https://benchmark-radar.org`
- [x] Google Search Console Domain property verified
- [x] Sitemap submitted successfully in Google and Bing
- [x] Homepage passes live URL inspection and structured-data validation
- [x] Dashboard view pages, utility pages, and one benchmark page return useful
      HTML with JavaScript disabled
- [ ] Indexing and performance reviewed after Google recrawls the site
