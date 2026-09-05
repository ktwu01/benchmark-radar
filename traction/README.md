# Traction record

Benchmark Radar has **77 recorded posting actions across 27 destinations**.
The clearest repeatable channels so far are X, the Benchmark Radar discussion
group, the GitHub blog, and WeChat Moments. This directory turns scattered
GitHub checklists into one place to see what shipped, what was said, and what to
try next.

Snapshot: **September 3, 2026**. GitHub Issues remain the source of truth; these
files are a review-friendly index of their bodies, checked items, and comments.

## What is here

- [Checklist history](checklist-history.md): every completed posting checkbox,
  normalized by destination.
- [Issue index](issues.md): all 45 issues carrying the `traction` label, including
  Chinese-titled work filed as 用户、推广、软广、知乎、小红书, or SEO work.
- [Comment notes](comment-notes.md): the 27 comments left by `@ktwu01` across 16
  traction issues, grouped by the decision or idea they record.

## Counting rules

- The 55 checks in 21 dated daily-social issues count as posting actions.
- The launch plan in [#88](https://github.com/ktwu01/benchmark-radar/issues/88)
  adds 20 completed destination checks. Its eight product/setup checks are not
  counted as posts.
- [#202](https://github.com/ktwu01/benchmark-radar/issues/202) adds two completed
  community posts.
- Spelling variants such as `小红书1` and `小红书` are merged. The historical
  `COLM group` labels are treated as one destination.
- SEO, CTA, analytics, and social-preview checkboxes stay in the issue index but
  are not mixed into the posting total.

## Next decision

The history measures activity, not results: most old checks have no URL,
timestamp, referral count, or star/fork delta. For the next post, record those
four fields beside the checkbox. After several posts, keep channels that bring
readers, citations, issues, or contributors—not merely the channels with the
largest activity count.

## How to update this record

1. Query open and closed GitHub Issues and inspect titles, bodies, and comments;
   do not rely on `Daily social checklist` in the title. Search Chinese terms
   such as 用户、推广、软广、知乎 and 小红书 as well as SEO, CTA, and traction.
2. Add the `traction` label only after reading the issue. Attention-data
   ingestion and unrelated product work are not promotion merely because they
   mention users or Hacker News.
3. Count completed destination checkboxes from both issue bodies and comments.
   Keep product/setup, SEO, and analytics tasks in the issue index, outside the
   posting total.
4. Normalize only obvious aliases and record the rule. Never infer that two
   similarly named communities are the same without evidence.
5. Update `config/social.yml` for future checklists. Past checked state belongs
   to the GitHub Issues and should not be rewritten.
6. Run `pytest -q tests/test_social.py`, then confirm every checked daily-social
   issue has the `traction` label before updating this snapshot date.
