# Benchmark Radar

<!-- 记录数 badge 由数据驱动：每次采集都会根据语料重新生成，因此它反映的是项目实际收集到的数据量 -->

[![已收集 benchmark 记录](https://img.shields.io/endpoint?url=https%3A%2F%2Fkoutian.is-a.dev%2Fbenchmark-radar%2Fdata%2Frecords-badge.json)](https://koutian.is-a.dev/benchmark-radar/)

做 benchmark 研究的时候发现新东西太多了，所以我搞了这个持续爬虫，每天自动从全网抓新的 benchmark 相关信息。它目前每天从 **arXiv、GitHub、Hugging Face、OpenAlex、OpenReview、各家实验室官方 feed、Brave Search、Semantic Scholar、Hacker News** 等来源采集，并持续更新。你如果需要寻找 related work 或找到适合eval自己的agent 的 bench 或者关注最新的 eval 进展，可以看这里哈哈哈：
github.com/ktwu01/benchmark-radar，每天更新，并支持一键导出数据

**English version: [README.md](README.md).**

## 使用方法

- **[打开 dashboard](https://koutian.is-a.dev/benchmark-radar/)** — 每日洞察、趋势、热门 benchmark、模型卡采用排名等
- **[通过 RSS 订阅](https://koutian.is-a.dev/benchmark-radar/feed.xml)** — 每天获取最新的 benchmark 情报
- **[一键导出全部数据](https://koutian.is-a.dev/benchmark-radar/data/radar.json)** — 导出完整的机器可读语料
- **[参与贡献](CONTRIBUTING.md)** — 添加 benchmark、模型卡、信源或修复

如果觉得有用，可以给这个 repo 点个 **Star**。

## 更多

- **评分规则：** [`src/benchmark_radar/rubric.py`](src/benchmark_radar/rubric.py)
- **模型卡采用数据：** [`data/model_cards.yml`](data/model_cards.yml)
- **公开语料 schema：** [`docs/cumulative-corpus.schema.json`](docs/cumulative-corpus.schema.json)
- **配置：** [`config.yml`](config.yml)
- **本地运行：** `python -m pip install -e '.[dev]' && benchmark-radar`
- **支持 / 反馈：** [提交 issue](https://github.com/ktwu01/benchmark-radar/issues)
- **联系：** [@ktwu01](https://github.com/ktwu01)
- **开源协议：** MIT
