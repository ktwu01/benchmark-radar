# Security Policy

## Supported Versions

Benchmark Radar is a continuously updated living database: there is one
supported version, the current `main` branch (and the daily snapshots and
data releases it produces). Older snapshots are archival records, not
supported releases — if a security issue affects historical data, it is
fixed in the current pipeline and noted in the fix.

| Version | Supported |
| ------- | --------- |
| `main` (current) | ✅ |
| Older snapshots / data releases | ❌ |

## Reporting a Vulnerability

Do not open a public issue for a suspected vulnerability. Report it
privately so it can be fixed before the details become public:

1. **Preferred:** use GitHub's private vulnerability reporting — on the
   repository page, go to **Security → Report a vulnerability**. The report
   goes to the maintainer without becoming public.
2. **If that is unavailable:** email the maintainer, Koutian Wu
   ([@ktwu01](https://github.com/ktwu01)), at
   [ktwugoat@gmail.com](mailto:ktwugoat@gmail.com) with the details.

Please include, where you can:

- what the vulnerability is and where it lives (file, workflow, endpoint,
  or dependency);
- steps to reproduce it, or a minimal proof of concept;
- what an attacker could do with it, and what data it could reach.

You will get an acknowledgement, and the fix will be credited in the
release notes unless you ask not to be named.

## Scope

In scope: the code and workflows in this repository, the CLI, the dashboard
site, and the data pipeline that publishes the daily snapshots and the
Hugging Face dataset.

Out of scope: the benchmark data itself (scores and citations are read out of
the cited documents, and a wrong score is a data correction — open a normal
issue for that), and vulnerabilities in third-party services the project
links to rather than runs.
