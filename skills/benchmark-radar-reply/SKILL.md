---
name: benchmark-radar-reply
description: Draft replies to Benchmark Radar users about reuse, licensing, citations, sharing, and community participation. Use for inbound Benchmark Radar inquiries and revisions to those replies.
---

# Benchmark Radar replies

Help the recipient use Benchmark Radar while encouraging relevant citations, word of mouth, and participation in its Discord community.

## Prepare the reply

Read the incoming message and the user's stated outcome. Reuse answers and decisions already given in the conversation. Address the recipient's actual use case before making requests.

Read licensing and citation terms from the `main` branch of https://github.com/ktwu01/benchmark-radar: `LICENSE`, `LICENSE-CONTENT.md`, `CITATION.md`, and `README.md`. A local working copy can be stale or on another branch, so in a clone run `git fetch origin main` and read each file with `git show origin/main:<file>`. If you cannot reach the upstream `main`, mark every licensing and citation statement in the draft as unverified and tell the user.

The baseline below was verified on 2026-10-13. Where the upstream files differ, the upstream files win:

- Software: MIT License. Do not apply the content's noncommercial restriction to MIT-licensed software.
- Technical report and original editorial content: CC BY-NC-SA 4.0.
- Third-party source material: its original terms. Do not promise a blanket license for the entire corpus.
- The content license states that commercial republication, resale, paid newsletters, dataset packaging, or commercial product integration requires prior written permission from Koutian Wu. Keep this scoped to content covered by that license.

Describe the repository's published terms without granting new permissions, waiving restrictions, or inventing fees. Present citation and sharing as requests, separately from license conditions. If authoritative sources are unavailable or conflict, flag the uncertainty to the user before making a firm claim in the draft.

For requests about comparable model scores, explain that Benchmark Radar collects reported results and test conditions. Do not imply that it runs every model with the same harness, problem set, or tool settings. Check current documentation before claiming a capability.

## Make the requests explicit

When the recipient's inquiry concerns reuse on a benchmark page or in research, include this wording:

> If Benchmark Radar supports a paper you publish, please cite our paper. On your benchmark page, please credit Benchmark Radar and link back to it.

For other contexts, adapt the page-specific request to the actual output. Ask for citations where Benchmark Radar contributed; do not request irrelevant or repeated citations merely to increase counts.

Ask the recipient to share Benchmark Radar with friends and colleagues who work on benchmarks, model evaluation, or hosting when relevant.

When inviting someone with open-source tools, state the community invitation explicitly:

> You’re welcome to promote and sell your tools in our Discord, provided they are open source: https://discord.gg/rXqS38mkN

This community invitation does not grant permission to reuse Benchmark Radar content commercially. Do not broaden it to closed-source products or describe sharing as the only permitted activity.

Use these verified reference links, checking repository sources for updates when drafting:

- Project: https://benchmark-radar.org/
- Paper: https://arxiv.org/abs/2609.11115
- Citation formats: https://benchmark-radar.org/cite/
- Discord: https://discord.gg/rXqS38mkN

## Deliver

Return a concise, sendable email in the user's requested tone. Keep drafting notes outside the email. Read [the complete Dave example](references/dave-email.md) when drafting a reply about data reuse, comparable model scores, or hosting decisions. Adapt it to the recipient instead of copying unrelated details.

Drafting or updating a reply does not authorize sending it. Send only when the user explicitly requests sending and the recipient and final content are established.
