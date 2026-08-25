<div align="left">

[中文](README.zh-CN.md)

</div>

# Benchmark Radar

<!-- The record-count badge is data-driven: it is regenerated from the corpus on
every collection, so it states what the project actually holds rather than a
hand-edited number (issue #197). -->

<p align="center">
  <a href="https://koutian.is-a.dev/benchmark-radar/"><img alt="Benchmark records collected" src="https://img.shields.io/endpoint?url=https%3A%2F%2Fkoutian.is-a.dev%2Fbenchmark-radar%2Fdata%2Frecords-badge.json&amp;style=for-the-badge"></a>
  <a href="https://koutian.is-a.dev/benchmark-radar/data/radar.json"><img alt="Download dataset" src="https://img.shields.io/badge/Dataset-download%20JSON-2f81f7?style=for-the-badge&amp;logo=json&amp;logoColor=white"></a>
  <a href="https://x.com/ktwu01"><img alt="X" src="https://img.shields.io/badge/X-000000?style=for-the-badge&amp;logo=x&amp;logoColor=white"></a>
  <a href="https://www.linkedin.com/in/ktwu01"><img alt="LinkedIn" src="https://img.shields.io/badge/LinkedIn-0A66C2?style=for-the-badge&amp;logo=linkedin&amp;logoColor=white"></a>
  <a href="https://scholar.google.com/citations?user=s9w1k-cAAAAJ&amp;hl=en"><img alt="Google Scholar" src="https://img.shields.io/badge/Google%20Scholar-4285F4?style=for-the-badge&amp;logo=googlescholar&amp;logoColor=white"></a>
</p>

I kept running into new benchmarks while doing benchmark research, so I built a
crawler that continuously collects benchmark-related signals from across the
web. It pulls evidence from arXiv, GitHub, Hugging Face, OpenAlex, OpenReview,
first-party lab feeds, Brave Search, Semantic Scholar, Hacker News, and more
every day, and keeps updating.

**Click the image to watch how reported AIME 2025 scores saturated over time.**

<a href="https://koutian.is-a.dev/benchmark-radar/?view=leaderboard&lfrontier=llm-stats-aime-2025">
  <img src="assets/aime-2025-leaderboard.png" alt="AIME 2025 leaderboard frontier chart, plotting every reported score against each model's release date" width="720" />
</a>

## Use it

- **[Open the dashboard](https://koutian.is-a.dev/benchmark-radar/)** — today's insights, trends, popular benchmarks, model-card adoption, and more
- **[Subscribe via RSS](https://koutian.is-a.dev/benchmark-radar/feed.xml)** — get new benchmark signals every day
- **[Download the complete dataset](https://koutian.is-a.dev/benchmark-radar/data/radar.json)** — free, public, machine-readable JSON; no crawler or contact required
- **[Contribute](CONTRIBUTING.md)** — add benchmarks, model cards, sources, or fixes

If Benchmark Radar saves you research time, **[star the repository](https://github.com/ktwu01/benchmark-radar)**. It helps other eval builders find it.

## More

- **Scoring rubric:** [`src/benchmark_radar/rubric.py`](src/benchmark_radar/rubric.py)
- **Model-card adoption data:** [`data/model_cards.yml`](data/model_cards.yml)
- **Public corpus schema:** [`docs/cumulative-corpus.schema.json`](docs/cumulative-corpus.schema.json)
- **Citation metadata:** [`CITATION.cff`](CITATION.cff)
- **Configuration:** [`config.yml`](config.yml)
- **Run locally:** `python -m pip install -e '.[dev]' && benchmark-radar`
- **Support / bugs:** [open an issue](https://github.com/ktwu01/benchmark-radar/issues)
- **Contact:** [@ktwu01](https://github.com/ktwu01)
- **License:** MIT

## Join the WeChat group

Scan the QR code to join the WeChat group for daily benchmark updates and eval discussions:

<img src="assets/wechat-group-qr.jpg" alt="WeChat group QR code" width="280" />

## Acknowledgements

The frontier-model score layer (including the AIME 2025 chart above) is built on
benchmark data collected by [LLM Stats](https://llm-stats.com). Thank you for
keeping that data open.

## Citation

If Benchmark Radar supports your research or evaluation work, please cite it:

```bibtex
@misc{wu2026benchmarkradar,
  title        = {Benchmark Radar: A Daily, Evidence-First Radar and Machine-Readable Corpus for AI Benchmarks},
  author       = {Wu, Koutian},
  year         = {2026},
  howpublished = {\url{https://github.com/ktwu01/benchmark-radar}},
  note         = {Daily benchmark radar and open dataset}
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
