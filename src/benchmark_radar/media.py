"""Press, paper summaries, and community posts about Benchmark Radar (issue #906).

One list feeds three surfaces: the /media/ page, the citation card under the
citation formats, and app.js's mirror of that card. Keeping it here rather than
in ``site_about.py`` lets ``app_seeds.py`` read it without importing the page
writer.
"""

from __future__ import annotations

MEDIA_CONTACT = "ktwu@utexas.edu"

# Keep labels factual: a paper listing or social post is not an endorsement.
MEDIA_COVERAGE: tuple[tuple[str, str, str], ...] = (
    (
        "Daily AI Wire News",
        "https://dailyaiwire.news/article/benchmark-radar-ai-evaluation-database-search-engine",
        "Article",
    ),
    (
        "Moonlight",
        "https://www.themoonlight.io/en/review/"
        "benchmark-radar-a-living-database-and-search-engine-for-ai-benchmarks-and-evaluation",
        "Paper summary",
    ),
    ("Papers with Code", "https://paperswithcode.co/paper/2609.11115", "Paper listing"),
    ("alphaXiv", "https://www.alphaxiv.org/abs/2609.11115", "Paper discussion"),
    ("Hugging Face Papers", "https://huggingface.co/papers/2609.11115", "Paper discussion"),
    (
        "arXivDaily",
        "https://www.arxivdaily.com/universities/sjtu",
        "Shanghai Jiao Tong University paper feed (rolling)",
    ),
    ("Geepity", "https://geepity.com/2609.11115/", "Paper page"),
    ("Isfahan AI", "https://isfahan-ai.ir/news/1248", "News post"),
    (
        "Collected",
        "https://collected.ga/typesafe-ai-daily-benchmark-radar-a-living-database-"
        "and-search-engine-for-ai-benchmarks-and-eval/",
        "Typesafe AI Daily",
    ),
    (
        "Alexy Khrabrov on LinkedIn",
        "https://www.linkedin.com/posts/chiefscientist_typesafe-ai-daily-benchmark-radar-"
        "a-living-share-7504531089483309056-9uO7/",
        "Community post",
    ),
    (
        "Daily AI Wire News on LinkedIn",
        "https://www.linkedin.com/posts/benchmark-radar-launches-as-centralized-ai-"
        "share-7504478957413527552-jdN_/",
        "Article announcement",
    ),
    ("@SciFi on X", "https://x.com/SciFi/status/2098817718036127993", "Community post"),
    (
        "@HuggingPapers on X",
        "https://x.com/HuggingPapers/status/2099412410264060340",
        "Community post",
    ),
    (
        "@marcel_butucea on X",
        "https://x.com/marcel_butucea/status/2098914581204680765",
        "Community post",
    ),
    (
        "Moltbook",
        "https://www.moltbook.com/post/a65591a2-d28d-4f3d-b381-fe2836c4e4c3",
        "Community post",
    ),
)
