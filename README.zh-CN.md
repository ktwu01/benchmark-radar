<div align="left">

[English](README.md)

</div>

# Benchmark Radar

<!-- 记录数 badge 由数据驱动：每次采集都会根据语料重新生成，因此它反映的是项目实际收集到的数据量 -->

<p align="center">
  <a href="https://koutian.is-a.dev/benchmark-radar/"><img alt="已收集的 benchmark 记录" src="https://img.shields.io/endpoint?url=https%3A%2F%2Fkoutian.is-a.dev%2Fbenchmark-radar%2Fdata%2Frecords-badge.json&amp;style=for-the-badge"></a>
  <a href="https://koutian.is-a.dev/benchmark-radar/data/radar.json"><img alt="下载数据集" src="https://img.shields.io/badge/Dataset-download%20JSON-2f81f7?style=for-the-badge&amp;logo=json&amp;logoColor=white"></a>
  <a href="https://x.com/ktwu01"><img alt="X" src="https://img.shields.io/badge/X-000000?style=for-the-badge&amp;logo=x&amp;logoColor=white"></a>
  <a href="https://www.linkedin.com/in/ktwu01"><img alt="LinkedIn" src="https://img.shields.io/badge/LinkedIn-0A66C2?style=for-the-badge&amp;logo=linkedin&amp;logoColor=white"></a>
  <a href="https://scholar.google.com/citations?user=s9w1k-cAAAAJ&amp;hl=en"><img alt="Google Scholar" src="https://img.shields.io/badge/Google%20Scholar-4285F4?style=for-the-badge&amp;logo=googlescholar&amp;logoColor=white"></a>
</p>

做 benchmark 研究的时候发现新东西太多了，所以我搞了这个持续爬虫，每天自动从全网抓新的 benchmark 相关信息。它目前每天从 arXiv、GitHub、Hugging Face、OpenAlex、OpenReview、各家实验室官方 feed、Brave Search、Semantic Scholar、Hacker News 等来源采集，并持续更新。你如果需要寻找 related work 或找到适合eval自己的agent 的 bench 或者关注最新的 eval 进展，可以看这里哈哈哈：
github.com/ktwu01/benchmark-radar，每天更新，并支持一键导出数据

**点击图片即可查看 AIME 2025 报告分数随时间逐渐饱和的过程。**

<a href="https://koutian.is-a.dev/benchmark-radar/?view=leaderboard&lfrontier=llm-stats-aime-2025">
  <img src="assets/aime-2025-leaderboard.png" alt="AIME 2025 模型报告分数随发布日期变化的前沿图" width="720" />
</a>

## 使用方法

- **[打开 dashboard](https://koutian.is-a.dev/benchmark-radar/)** — 每日洞察、趋势、热门 benchmark、模型卡采用排名等
- **[通过 RSS 订阅](https://koutian.is-a.dev/benchmark-radar/feed.xml)** — 每天获取最新的 benchmark 情报
- **[下载完整数据集](https://koutian.is-a.dev/benchmark-radar/data/radar.json)** — 免费、公开、机器可读的 JSON，无需爬虫或联系作者
- **[参与贡献](CONTRIBUTING.md)** — 添加 benchmark、模型卡、信源或修复

如果 Benchmark Radar 帮你节省了研究时间，请 **[给仓库点个 Star](https://github.com/ktwu01/benchmark-radar)**，让更多做评测的人发现它。

## 更多

- **评分规则：** [`src/benchmark_radar/rubric.py`](src/benchmark_radar/rubric.py)
- **模型卡采用数据：** [`data/model_cards.yml`](data/model_cards.yml)
- **公开语料 schema：** [`docs/cumulative-corpus.schema.json`](docs/cumulative-corpus.schema.json)
- **引用信息：** [`CITATION.cff`](CITATION.cff)
- **配置：** [`config.yml`](config.yml)
- **本地运行：** `python -m pip install -e '.[dev]' && benchmark-radar`
- **支持 / 反馈：** [提交 issue](https://github.com/ktwu01/benchmark-radar/issues)
- **联系：** [@ktwu01](https://github.com/ktwu01)
- **开源协议：** MIT

## 加入微信群

扫码加入微信群，获取每日 benchmark 更新、交流评测相关话题：

<img src="assets/wechat-group-qr.jpg" alt="微信群二维码" width="280" />

## 感谢

前沿模型分数层（包括上方的 AIME 2025 图表）基于 [LLM Stats](https://llm-stats.com) 采集的基准数据构建，感谢他们把这些数据公开出来。

## 引用

如果 Benchmark Radar 对你的研究或评测工作有帮助，欢迎引用：

```bibtex
@misc{wu2026benchmarkradar,
  title        = {Benchmark Radar: A Daily, Evidence-First Radar and Machine-Readable Corpus for AI Benchmarks},
  author       = {Wu, Koutian},
  year         = {2026},
  howpublished = {\url{https://github.com/ktwu01/benchmark-radar}},
  note         = {Daily benchmark radar and open dataset}
}
```

机器可读的引用元数据见 [`CITATION.cff`](CITATION.cff)。

## Star 历史

<a href="https://www.star-history.com/#ktwu01/benchmark-radar&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/ktwu01/benchmark-radar/star-history/assets/star-history-dark.svg" />
    <img alt="Benchmark Radar Star 历史图" src="https://raw.githubusercontent.com/ktwu01/benchmark-radar/star-history/assets/star-history.svg" />
  </picture>
</a>
