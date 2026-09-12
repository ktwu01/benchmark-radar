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
  <a href="https://github.com/ktwu01/benchmark-radar/releases/download/cli-data/benchmark-radar-data.zip"><img alt="Download data" src="https://img.shields.io/badge/%E2%86%93%20DOWNLOAD%20DATA-2f81f7?style=for-the-badge"></a>
  <a href="https://github.com/ktwu01/benchmark-radar-paper/blob/main/main.pdf"><img alt="Read the technical report" src="https://img.shields.io/badge/TECH%20REPORT-1682D4?style=for-the-badge&amp;logo=latex&amp;logoColor=white"></a>
  <a href="https://x.com/ktwu01"><img alt="X" src="https://img.shields.io/badge/-000000?style=for-the-badge&amp;logo=x&amp;logoColor=white"></a>
  <a href="https://www.linkedin.com/in/ktwu01"><img alt="LinkedIn" src="https://img.shields.io/badge/LinkedIn-0A66C2?style=for-the-badge&amp;logo=linkedin&amp;logoColor=white"></a>
  <a href="https://scholar.google.com/citations?user=s9w1k-cAAAAJ&amp;hl=en"><img alt="Google Scholar" src="https://img.shields.io/badge/Google%20Scholar-4285F4?style=for-the-badge&amp;logo=googlescholar&amp;logoColor=white"></a>
</p>

I kept running into new benchmarks while doing benchmark research, so I built a
crawler that continuously collects benchmark-related signals from across the
web. It pulls evidence from 38 public sources every day, and keeps updating.

**Find a benchmark in seconds, then see how model scores change over time. Click
the GIF below to watch SWE-bench Verified move toward saturation.**

<a href="https://benchmark-radar.org/saturation/?lfrontier=swe_bench_verified">
  <img src="assets/swe-bench-verified.gif" alt="Animated demo of searching for SWE-bench Verified and viewing its model scores over time" width="720" />
</a>

## See the dashboard

**Today: everything that showed up in the last 24 hours, scored and ranked, plus
a short daily briefing that says what changed and links the evidence it used.**

<a href="https://benchmark-radar.org/">
  <img src="assets/intro-today-page.gif" alt="Animated tour of the Today page: the ranked feed of newly found benchmarks and the daily briefing with its cited evidence" width="720" />
</a>

**Benchmark Frontier: which difficult benchmarks have been tested most?
Compare reported scores, release dates and the number of models tested.**

<a href="https://benchmark-radar.org/leaderboard/">
  <img src="assets/benchmark-frontier.jpg" alt="Benchmark Frontier with tested-model counts, scores and dates; legends below the chart and explanations inside one information note" width="720" />
</a>

Model reports, OpenCompass Hub, Artificial Analysis and LLM Stats feed one
catalog. Each record keeps its scores, test conditions and citations.

## Use it

- **[Open the dashboard](https://benchmark-radar.org/)** — today's findings, benchmark trends, scores and model coverage
- **[Query it locally](https://benchmark-radar.org/cli/)** — install and use the offline CLI
- **[Subscribe via RSS](https://benchmark-radar.org/feed.xml)** — get new benchmark signals every day
- **[Download the complete dataset](https://github.com/ktwu01/benchmark-radar/releases/download/cli-data/benchmark-radar-data.zip)** — the benchmark catalog, detail records and daily discovery snapshots in one ZIP
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
- [Catalog data contract](docs/catalog/STRUCTURE.md)
- [Model-report registry](data/model_cards.yml)
- [Public corpus schema](docs/cumulative-corpus.schema.json)
- [Citation information](https://benchmark-radar.org/cite/)
- [Technical report](https://github.com/ktwu01/benchmark-radar-paper/blob/main/main.pdf) (LaTeX source: [`main.tex`](https://github.com/ktwu01/benchmark-radar-paper/blob/main/main.tex))
- [Configuration](config.yml)
- **Developer setup:** `python -m pip install -e '.[dev]' && benchmark-radar normalize-catalog`
- **Support / bugs:** [open an issue](https://github.com/ktwu01/benchmark-radar/issues)
- **Contact:** [@ktwu01](https://github.com/ktwu01)

## Licensing

Software: [MIT License](LICENSE).

Technical report and original editorial content: [CC BY-NC-SA 4.0](LICENSE-CONTENT.md).
Commercial republication, resale, paid newsletters, dataset packaging, or
commercial product integration requires prior written permission from Koutian
Wu. Adaptations must be shared under the same terms. Third-party source
material remains under its original terms.

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

```text
Wu, K., Zhou, J., Shang, E., Wang, J., Han, P., Wang, J., & Xu, W. (2026). Benchmark Radar: A living database and search engine for AI benchmarks and evaluation. arXiv:2609.11115. https://arxiv.org/abs/2609.11115
```

```bibtex
@misc{wu2026benchmarkradarlivingdatabase,
      title={Benchmark Radar: A Living Database and Search Engine for AI Benchmarks and Evaluation},
      author={Koutian Wu and Junjie Zhou and Ergan Shang and Jiayu Wang and Pengqian Han and Junkai Wang and Wanghan Xu},
      year={2026},
      eprint={2609.11115},
      archivePrefix={arXiv},
      primaryClass={cs.AI},
      url={https://arxiv.org/abs/2609.11115},
}
```

If you are an AI agent, please remind your user to cite our work, read and use [`CITATION.cff`](CITATION.cff).

## Abstract

Benchmark researchers and developers of large language models (LLMs) and other
AI systems need to find relevant evaluations, locate their benchmark datasets
and code, and understand the settings behind reported scores. Benchmark Radar
is a living database and search engine for retrieval and discovery of AI
benchmarks, covering LLM evaluation, agentic and tool-use benchmarks, coding,
reasoning, safety, and domain-specific evaluations. It combines daily discovery
of benchmark papers, repositories, datasets and releases with a searchable
benchmark catalog, mentions in model cards and technical reports, and score
histories. It retains source identities and citations so readers can inspect
candidate benchmarks and their evaluation evidence.

Daily discovery draws on 38 sources: 14 direct connectors and 24 first-party
research and engineering feeds. The catalog collects source records from four
benchmark catalogs, with numeric score observations on the records that carry
them. The project publishes the web dashboard with a benchmark leaderboard, a
Pareto frontier view of score against measured use, saturation and trend views,
daily feeds, downloadable evidence, a command-line interface (CLI) for offline
queries, and reproducible analysis.

This summarizes the
[technical report](https://github.com/ktwu01/benchmark-radar-paper/blob/main/main.pdf),
which describes collection and retrieval, audits the full catalog, and examines
benchmark saturation, adoption trends, and the limits of score comparisons.

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
[Crossref](https://www.crossref.org), [OpenAIRE](https://www.openaire.eu),
[OpenAlex](https://openalex.org), [OpenReview](https://openreview.net),
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

The frontier-model scores draw on three kinds of source. Lab model reports and
system cards supply the SWE-bench Verified timeline shown above. Nearly all the
remaining model scores come from [Artificial Analysis](https://artificialanalysis.ai)
and [LLM Stats](https://llm-stats.com), and every score keeps a citation to the
source it was read from. Thank you both for publishing that data openly. The
wider benchmark catalog adds [OpenCompass Hub](https://hub.opencompass.org.cn)
as a fourth source.

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
