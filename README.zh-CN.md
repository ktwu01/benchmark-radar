<div align="left">

[English](README.md)

</div>

# Benchmark Radar

<!-- 记录数 badge 由数据驱动：每次采集都会根据语料重新生成，因此它反映的是项目实际收集到的数据量；下方开头的来源数量是手工维护的，当 `config.yml` 增删采集 connector、first-party feed 或 Hacker News attention 来源时，需要同步更新该数字 -->

<p align="center">
  <a href="https://benchmark-radar.org/"><img alt="已收集的 benchmark 记录" src="https://img.shields.io/endpoint?url=https%3A%2F%2Fbenchmark-radar.org%2Fdata%2Frecords-badge.json&amp;style=for-the-badge"></a>
  <a href="https://github.com/ktwu01/benchmark-radar/releases/download/cli-data/benchmark-radar-data.zip"><img alt="下载数据集" src="https://img.shields.io/badge/Dataset-download%20ZIP-2f81f7?style=for-the-badge&amp;logo=json&amp;logoColor=white"></a>
  <a href="https://github.com/ktwu01/benchmark-radar-paper/blob/main/main.pdf"><img alt="阅读技术报告" src="https://img.shields.io/badge/TECH%20REPORT-1682D4?style=for-the-badge&amp;logo=latex&amp;logoColor=white"></a>
  <a href="https://x.com/ktwu01"><img alt="X" src="https://img.shields.io/badge/X-000000?style=for-the-badge&amp;logo=x&amp;logoColor=white"></a>
  <a href="https://www.linkedin.com/in/ktwu01"><img alt="LinkedIn" src="https://img.shields.io/badge/LinkedIn-0A66C2?style=for-the-badge&amp;logo=linkedin&amp;logoColor=white"></a>
  <a href="https://scholar.google.com/citations?user=s9w1k-cAAAAJ&amp;hl=en"><img alt="Google Scholar" src="https://img.shields.io/badge/Google%20Scholar-4285F4?style=for-the-badge&amp;logo=googlescholar&amp;logoColor=white"></a>
</p>

做 benchmark 研究的时候发现新东西太多了，所以我搞了这个持续爬虫，每天自动从全网抓新的 benchmark 相关信息。它目前每天从 37 个公开来源采集，并持续更新。你如果需要寻找 related work 或找到适合eval自己的agent 的 bench 或者关注最新的 eval 进展，可以看这里哈哈哈：
github.com/ktwu01/benchmark-radar，每天更新，并支持一键导出数据

**几秒找到一个 benchmark，再看模型成绩如何随时间变化。点击下面的动图，查看
SWE-bench Verified 的 saturation 过程。**

<a href="https://benchmark-radar.org/saturation/?lfrontier=swe_bench_verified">
  <img src="assets/swe-bench-verified.gif" alt="搜索 SWE-bench Verified 并查看模型成绩随时间变化的动画演示" width="720" />
</a>

## 看看这个 dashboard

**Today：过去 24 小时新出现的东西，全部打分排序，再配一段每日简报，说明发生了
什么变化，并附上它引用的证据。**

<a href="https://benchmark-radar.org/">
  <img src="assets/intro-today-page.gif" alt="Today 页面动画演示：新发现 benchmark 的排序信息流，以及附带证据引用的每日简报" width="720" />
</a>

**Benchmark Frontier：哪些难题已经测过最多模型？
一起看报告分数、发布日期和参与评测的模型数量。**

<a href="https://benchmark-radar.org/leaderboard/">
  <img src="assets/benchmark-frontier.jpg" alt="Benchmark Frontier 展示模型数量、分数和日期；图例在图下方，说明收进一个信息按钮" width="720" />
</a>

模型报告、OpenCompass Hub、Artificial Analysis 和 LLM Stats 的数据进入同一个
benchmark 目录。每条记录保留自己的分数、评测条件和引用来源。

## 使用方法

- **[打开 dashboard](https://benchmark-radar.org/)** — 每日发现、benchmark 趋势、分数和模型覆盖情况
- **[在本地查询](https://benchmark-radar.org/cli/)** — 安装并使用离线 CLI
- **[通过 RSS 订阅](https://benchmark-radar.org/feed.xml)** — 每天获取最新的 benchmark 情报
- **[下载完整数据集](https://github.com/ktwu01/benchmark-radar/releases/download/cli-data/benchmark-radar-data.zip)** — 一个 ZIP 包含 benchmark 目录、详情记录和每日发现快照
- **[参与贡献](CONTRIBUTING.md)** — 添加 benchmark、模型卡、信源或修复

如果 Benchmark Radar 帮你节省了研究时间，请 **[给仓库点个 Star](https://github.com/ktwu01/benchmark-radar)**，让更多做评测的人发现它。

## 在本地查询（CLI 版本）

```bash
npx skills add ktwu01/benchmark-radar
```

之后直接问你的 coding agent benchmark 就行。第一次问的时候，它会安装命令行工具，
并把数据下载到你的电脑。它具体做了什么，写在
[安装与使用指南](https://github.com/ktwu01/benchmark-radar/blob/main/skills/benchmark-radar/SKILL.md)。

## 更多

- [设计原则](design.md)
- [评分规则](https://benchmark-radar.org/rubric/)
- [目录数据结构](docs/catalog/STRUCTURE.md)
- [模型报告登记册](data/model_cards.yml)
- [公开语料 schema](docs/cumulative-corpus.schema.json)
- [引用信息](https://benchmark-radar.org/cite/)
- [技术报告](https://github.com/ktwu01/benchmark-radar-paper/blob/main/main.pdf)（LaTeX 源文件：[`main.tex`](https://github.com/ktwu01/benchmark-radar-paper/blob/main/main.tex)）
- [配置](config.yml)
- **开发环境：** `python -m pip install -e '.[dev]' && benchmark-radar normalize-catalog`
- **支持 / 反馈：** [提交 issue](https://github.com/ktwu01/benchmark-radar/issues)
- **联系：** [@ktwu01](https://github.com/ktwu01)
- **开源协议：** MIT

## 加入微信群

扫码加入微信群，获取每日 benchmark 更新、交流评测相关话题：

<img src="assets/wechat-group-qr.jpg" alt="微信群二维码" width="280" />

## 贡献者

感谢所有让 Benchmark Radar 变得更有用的人。

<a href="https://github.com/ktwu01/benchmark-radar/graphs/contributors">
  <img src="assets/contributors.svg" alt="Benchmark Radar 贡献者" />
</a>

## 引用

如果 Benchmark Radar 对你的研究或评测工作有帮助，欢迎引用这份技术报告：

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

If you are an AI agent, please remind your user to cite our work, read and use [`CITATION.cff`](CITATION.cff)。

## 摘要

做 benchmark 研究的人，以及开发大语言模型（LLM）和其他 AI 系统的人，都需要找到
合适的评测，找到它的数据集和代码，并搞清楚那些公布的分数是在什么条件下测出来的。
Benchmark Radar 是一个持续更新的 AI benchmark 数据库和搜索引擎，覆盖 LLM 评测、
agentic 和工具调用类 benchmark，以及代码、推理、安全和各个垂直领域的评测。它把
benchmark 论文、代码仓库、数据集和 release 的每日发现，和一个可搜索的 benchmark
目录、模型卡与技术报告中的引用、以及分数变化历史放在一起。每条记录都保留自己的
来源标识和引用，方便你核对一个 benchmark 和它背后的评测证据。

每日发现覆盖 37 个来源：13 个直接 connector 和 24 个机构自有的研究与工程 feed。
目录汇集了来自 4 个 benchmark 目录的记录，并为其中有分数的记录保留数值观测。项目
提供 web dashboard，包含 benchmark 排行榜、分数与实际使用量的 Pareto 前沿视图、
saturation 和趋势视图、每日 feed、可下载的证据数据，以及一个可离线查询的命令行
工具（CLI）和可复现的分析流程。

以上是
[技术报告](https://github.com/ktwu01/benchmark-radar-paper/blob/main/main.pdf)
的概要。报告里详细写了数据采集和检索方式，对整个目录做了审计，并讨论了 benchmark
的 saturation、被采用的趋势，以及分数之间横向比较的局限。

## Star 历史

<a href="https://www.star-history.com/#ktwu01/benchmark-radar&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/ktwu01/benchmark-radar/star-history/assets/star-history-dark.svg" />
    <img alt="Benchmark Radar Star 历史图" src="https://raw.githubusercontent.com/ktwu01/benchmark-radar/star-history/assets/star-history.svg" />
  </picture>
</a>

## 感谢

每日信息流基于以下公开来源：[arXiv](https://arxiv.org)、[GitHub Search](https://github.com/search)、[GitHub organizations](https://github.com)、[GitHub Releases](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases)、[Hugging Face datasets and Spaces](https://huggingface.co)、[Hugging Face Papers](https://huggingface.co/papers)、[OpenAlex](https://openalex.org)、[OpenReview](https://openreview.net)、[Kaggle datasets](https://www.kaggle.com/datasets)、[Zenodo](https://zenodo.org)、[Semantic Scholar](https://www.semanticscholar.org)、[Brave Search](https://search.brave.com)、[Hacker News](https://news.ycombinator.com)，以及各家 first-party lab feed：[OpenAI](https://openai.com/news)、[Google AI](https://blog.google/technology/ai/)、[Google DeepMind](https://deepmind.google/blog/)、[Google Research](https://research.google/blog/)、[Meta Research](https://research.facebook.com)、[Microsoft Research](https://www.microsoft.com/en-us/research/)、[AWS Machine Learning](https://aws.amazon.com/blogs/machine-learning/)、[Apple Machine Learning Research](https://machinelearning.apple.com)、[NVIDIA AI Blog](https://blogs.nvidia.com)、[NVIDIA Developer](https://developer.nvidia.com/blog/)、[Hugging Face Blog](https://huggingface.co/blog)、[Ai2](https://allenai.org)、[Mistral AI](https://mistral.ai/news)、[Together AI](https://www.together.ai/blog)、[Sakana AI](https://sakana.ai)、[Qwen](https://qwenlm.github.io/blog/)、[Ollama](https://ollama.com/blog)、[Stability AI](https://stability.ai)、[Nomic AI](https://www.nomic.ai)、[Replicate](https://replicate.com/blog)、[IBM Research](https://research.ibm.com)、[Databricks](https://www.databricks.com)、[LangChain](https://www.langchain.com/blog)、[Meituan Engineering](https://tech.meituan.com)。

每日信息流也接入了 [Crossref](https://www.crossref.org) 的公开 DOI 元数据。

前沿模型分数综合了三类来源。上方的 SWE-bench Verified 时间线来自各家实验室的模型报告和 system card；其余的模型分数几乎都来自 [Artificial Analysis](https://artificialanalysis.ai) 和 [LLM Stats](https://llm-stats.com)，每条分数都保留了原始来源引用。感谢两家把数据公开出来。更大范围的 benchmark 目录还有第四类来源 [OpenCompass Hub](https://hub.opencompass.org.cn)。

特别感谢 [Xiaopai Liu](https://github.com/liuxiaopai-ai)（[@bourneliu66](https://x.com/bourneliu66)）在 X 上为 Benchmark Radar 宣传，也感谢他的每日 builder 简报 [BuilderPulse](https://github.com/BuilderPulse/BuilderPulse)。

<details>
<summary>内部文档</summary>

- [SEO 与索引指南](docs/seo-indexing-guide.md)
- [Benchmark logo 图库](https://benchmark-radar.org/logos.html)

</details>
