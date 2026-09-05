<div align="left">

[中文](README.zh-CN.md)

</div>

# Benchmark Radar

<!-- The record-count badge is data-driven: it is regenerated from the corpus on
every collection, so it states what the project actually holds rather than a
hand-edited number (issue #197). The source count in the intro below is
manually maintained: update it when `config.yml` adds or removes a collection
connector, a first-party feed, or the Hacker News attention source. -->

<p align="center">
  <a href="https://benchmark-radar.org/"><img alt="Benchmarks collected" src="https://img.shields.io/endpoint?url=https%3A%2F%2Fbenchmark-radar.org%2Fdata%2Frecords-badge.json&amp;style=for-the-badge"></a>
  <a href="https://benchmark-radar.org/data/radar.json"><img alt="Download data" src="https://img.shields.io/badge/%E2%86%93%20DOWNLOAD%20DATA-2f81f7?style=for-the-badge"></a>
  <a href="https://zenodo.org/records/22167102"><img alt="Read the technical report" src="https://img.shields.io/badge/TECH%20REPORT-1682D4?style=for-the-badge&amp;logo=zenodo&amp;logoColor=white"></a>
  <a href="https://x.com/ktwu01"><img alt="X" src="https://img.shields.io/badge/-000000?style=for-the-badge&amp;logo=x&amp;logoColor=white"></a>
  <a href="https://www.linkedin.com/in/ktwu01"><img alt="LinkedIn" src="https://img.shields.io/badge/LinkedIn-0A66C2?style=for-the-badge&amp;logo=linkedin&amp;logoColor=white"></a>
  <a href="https://scholar.google.com/citations?user=s9w1k-cAAAAJ&amp;hl=en"><img alt="Google Scholar" src="https://img.shields.io/badge/Google%20Scholar-4285F4?style=for-the-badge&amp;logo=googlescholar&amp;logoColor=white"></a>
</p>

I kept running into new benchmarks while doing benchmark research, so I built a
crawler that continuously collects benchmark-related signals from across the
web. It pulls evidence from 37 public sources every day, and keeps updating.

**Find a benchmark in seconds, then see how model scores change over time. Click
the GIF below to watch SWE-bench Verified move toward saturation.**

<a href="https://benchmark-radar.org/leaderboard/?lfrontier=swe_bench_verified">
  <img src="assets/swe-bench-verified.gif" alt="Animated demo of searching for SWE-bench Verified and viewing its model scores over time" width="720" />
</a>

## See the dashboard

**Today: everything that showed up in the last 24 hours, scored and ranked, plus
a short daily briefing that says what changed and links the evidence it used.**

<a href="https://benchmark-radar.org/">
  <img src="assets/intro-today-page.gif" alt="Animated tour of the Today page: the ranked feed of newly found benchmarks and the daily briefing with its cited evidence" width="720" />
</a>

**Leaderboard: which benchmarks labs actually report in their model cards, and
how scores on each one climb until there is almost no headroom left.**

<a href="https://benchmark-radar.org/leaderboard/">
  <img src="assets/intro-leaderboard-page.gif" alt="Animated tour of the Leaderboard page: benchmarks ranked by model-card adoption, a scores-over-time chart, and remaining-headroom cards" width="720" />
</a>

## Use it

- **[Open the dashboard](https://benchmark-radar.org/)** — today's insights, trends, popular benchmarks, model-card adoption, and more
- **[Query it locally](https://benchmark-radar.org/cli/)** — install and use the offline CLI
- **[Subscribe via RSS](https://benchmark-radar.org/feed.xml)** — get new benchmark signals every day
- **[Download the complete dataset](https://benchmark-radar.org/data/radar.json)** — free, public, machine-readable JSON; no crawler or contact required
- **[Contribute](CONTRIBUTING.md)** — add benchmarks, model cards, sources, or fixes

If Benchmark Radar saves you research time, **[star the repository](https://github.com/ktwu01/benchmark-radar)**. It helps other eval builders find it.

## Query it locally (CLI version)

```bash
npx skills add ktwu01/benchmark-radar
```

Then ask your coding agent about benchmarks. It installs the command-line tool
and downloads the data to your computer the first time you ask. What it does is
written in the
[setup and usage guide](https://github.com/ktwu01/benchmark-radar/blob/main/skills/benchmark-radar/SKILL.md).

## More

- [Design principles](design.md)
- [Scoring rubric](https://benchmark-radar.org/rubric/)
- [Model-card adoption data](data/model_cards.yml)
- [Public corpus schema](docs/cumulative-corpus.schema.json)
- [Citation information](https://benchmark-radar.org/cite/)
- [Technical report](https://doi.org/10.5281/zenodo.22167102)
- [Configuration](config.yml)
- **Developer setup:** `python -m pip install -e '.[dev]' && benchmark-radar normalize-external`
- **Support / bugs:** [open an issue](https://github.com/ktwu01/benchmark-radar/issues)
- **Contact:** [@ktwu01](https://github.com/ktwu01)

## Licensing

Software: [MIT License](LICENSE).

Technical report and original editorial content: [CC BY-NC 4.0](LICENSE-CONTENT.md).
Commercial republication, resale, paid newsletters, dataset packaging, or
commercial product integration requires prior written permission from Koutian
Wu. Third-party source material remains under its original terms.

## Join the WeChat group

Scan the QR code to join the WeChat group for daily benchmark updates and eval discussions:

<img src="assets/wechat-group-qr.jpg" alt="WeChat group QR code" width="280" />

## Contributors

Thanks to everyone who helps make Benchmark Radar more useful.

<a href="https://github.com/ktwu01/benchmark-radar/graphs/contributors">
  <img src="assets/contributors.svg" alt="Benchmark Radar contributors" />
</a>

## Citation

If Benchmark Radar supports your research or evaluation work, please cite the
technical report:

```bibtex
@misc{wu_2026_22167102,
  author       = {Wu, Koutian and Zhou, Junjie},
  title        = {Benchmark Radar v0.9.0: Technical Report},
  month        = aug,
  year         = {2026},
  publisher    = {Zenodo},
  version      = {0.9.0},
  doi          = {10.5281/zenodo.22167102},
  url          = {https://doi.org/10.5281/zenodo.22167102}
}
```

See [`CITATION.cff`](CITATION.cff) for machine-readable citation metadata.

## Star History

<a href="https://www.star-history.com/#ktwu01/benchmark-radar&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/ktwu01/benchmark-radar/star-history/assets/star-history-dark.svg" />
    <img alt="Benchmark Radar star history chart" src="https://raw.githubusercontent.com/ktwu01/benchmark-radar/star-history/assets/star-history.svg" />
  </picture>
</a>

## Acknowledgements

The daily evidence feed is built on public data from [arXiv](https://arxiv.org),
[GitHub Search](https://github.com/search), [GitHub organizations](https://github.com),
[GitHub Releases](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases),
[Hugging Face datasets and Spaces](https://huggingface.co), [Hugging Face Papers](https://huggingface.co/papers),
[Crossref](https://www.crossref.org), [OpenAlex](https://openalex.org), [OpenReview](https://openreview.net),
[Kaggle datasets](https://www.kaggle.com/datasets), [Zenodo](https://zenodo.org),
[Semantic Scholar](https://www.semanticscholar.org), [Brave Search](https://search.brave.com),
and [Hacker News](https://news.ycombinator.com), plus first-party lab feeds from
[OpenAI](https://openai.com/news), [Google AI](https://blog.google/technology/ai/),
[Google DeepMind](https://deepmind.google/blog/), [Google Research](https://research.google/blog/),
[Meta Research](https://research.facebook.com), [Microsoft Research](https://www.microsoft.com/en-us/research/),
[AWS Machine Learning](https://aws.amazon.com/blogs/machine-learning/),
[Apple Machine Learning Research](https://machinelearning.apple.com),
[NVIDIA AI Blog](https://blogs.nvidia.com), [NVIDIA Developer](https://developer.nvidia.com/blog/),
[Hugging Face Blog](https://huggingface.co/blog), [Ai2](https://allenai.org),
[Mistral AI](https://mistral.ai/news), [Together AI](https://www.together.ai/blog),
[Sakana AI](https://sakana.ai), [Qwen](https://qwenlm.github.io/blog/),
[Ollama](https://ollama.com/blog), [Stability AI](https://stability.ai),
[Nomic AI](https://www.nomic.ai), [Replicate](https://replicate.com/blog),
[IBM Research](https://research.ibm.com), [Databricks](https://www.databricks.com),
[LangChain](https://www.langchain.com/blog), and [Meituan Engineering](https://tech.meituan.com).

The frontier-model score layer, including the SWE-bench Verified timeline above,
is built on benchmark data collected by [LLM Stats](https://llm-stats.com).
Thank you for keeping that data open.

A special thank you to [Xiaopai Liu](https://github.com/liuxiaopai-ai)
([@bourneliu66](https://x.com/bourneliu66)) for the shout-out on X, and to his
daily builder brief, [BuilderPulse](https://github.com/BuilderPulse/BuilderPulse).

<details>
<summary>Internal documentation</summary>

- [SEO and indexing guide](docs/seo-indexing-guide.md)
- [Benchmark logo gallery](https://benchmark-radar.org/logos.html)

<details>
<summary>contribute score</summary>

[See the public contribution-score ledger and rules.](docs/contributor-points.md)

</details>

</details>
