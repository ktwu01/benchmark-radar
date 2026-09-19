# Research UI design system

This proposal covers Today, Explore, Leaderboard, Saturation, Trends, reading
pages, benchmark records, and resources. The root design.md and principle.md
remain authoritative, especially for coverage, search, and score semantics.

## Brand and palette

Preserve the original /icon.svg unchanged on every route. Use neutral surfaces
and blue interactions; charts retain colors that encode data. Avoid decorative
side stripes, serif headings, lifted cards, and oversized statistics.

| Token | Value | Purpose |
| --- | --- | --- |
| Canvas | #f6f7f9 | Page background |
| Surface | #ffffff | Panels, navigation, dialogs |
| Ink | #202733 | Titles, body, values |
| Secondary | #55606f | Dates, sources, supporting text |
| Border | #dee3e9 | One-pixel dividers |
| Accent | #2b5fa8 | Links, selection, focus |
| Selected | #edf3fc | Selected control background |
| Hover | #f0f2f6 | Neutral hover background |

Use 8px control and 10px panel radii. Spacing follows 4, 8, 12, 16, 24, 32,
and 48px steps. Body and supporting text must meet 4.5:1 contrast against their
actual backgrounds. Do not mute paragraphs through opacity.

## Typography

Use the system sans-serif stack with PingFang SC and Microsoft YaHei fallbacks.
Avoid remote font loading and layout shifts. Use tabular numerals for values;
reserve monospace for code and commands.

| Role | Size / line height | Weight |
| --- | --- | --- |
| Page title | 28 / 36px; mobile 24 / 32px | 600 |
| Section title | 20 / 28px | 600 |
| Record title | 16–18 / 24–28px | 600 |
| Body | 16 / 26px | 400 |
| Navigation and controls | 14 / 20px | 400–500 |
| Sources and dates | 13 / 20px | 400 |
| Summary value | 28 / 36px | 600 |

Wrap long titles; never squeeze adjacent controls. Avoid uppercase labels,
wide tracking, and small decorative text. Reading columns are at most 880px.

## Shared shell

The template design/header.html owns every header. Routes change only active
state. Desktop height is 72px, content width at most 1440px, horizontal padding
32px. Navigation controls are 44px tall with 12px horizontal padding and 4px gaps.
Language, contact, and GitHub controls stay in that order, each 44 by 44px.
Selection changes color and background, never geometry or font weight.

At 1100px and below, use a 64px brand-and-tools row and a 48px horizontally
scrolling navigation row. Keep all destinations accessible. Reserve scrollbar
space so changing routes does not shift the header. Content shares the shell's
width and horizontal alignment; narrower reading columns do not resize it.

## Fields and data

The desktop Explore sidebar is 224px wide. Present secondary directions once,
above the results. On mobile, primary fields scroll horizontally and directions
open through an explicit disclosure. Collapse the disclosure after selection.
Field cards occupy a single scrolling row on narrow screens.

Leaderboard and Saturation share field controls and URL state. Name search in
Saturation pauses browsing filters, preserving the full-catalog lookup contract.
Unknown scores, dates, units, and counts remain unknown. Field memberships may
overlap; counts describe source records, not deduplicated benchmark identities.

Panels have neutral 1px borders, no default shadow, and 24px padding; compact
cards use 16px. Panel gaps are 24px and card gaps 16px. Align headings and values
across adjacent cards. Keep expansion controls, rank, content, and score in
separate columns. Tables scroll inside their own containers.

Changing a chart background requires checking its labels, legend, axes,
selectors, and tooltips together. Put legends below the figure and secondary
method details in one accessible closed information note.

## Buttons

Actions, including footer, pagination, export, reset, and load-more controls,
share a 44px height, 14/20px text, 8px radius, and 16px horizontal padding.
Related actions have 12px gaps and at most one primary button.

| Role | Default | Hover / pressed |
| --- | --- | --- |
| Primary | #2b5fa8, white text | #244f8c / #1e4276, white text |
| Secondary | White, dark text, #b8c2cf border | Neutral gray backgrounds |
| Text | Transparent, secondary text | Blue text |
| Disabled | Pale gray, #687586 text | No hover change |

Use a 2px blue focus outline without moving layout. Footer Cite is primary;
Star and Share are secondary. Support panels use white instead of yellow.
Copy confirmation retains visible status text. Dialogs are at most 820px wide,
have 24px padding, and scroll independently. Touch targets are at least 44px.

## Implementation and review

CSS layers are legacy, tokens, base, components, pages, responsive.
Shared site-* classes isolate the shell from legacy selectors. Prefer tokens
over specificity overrides. Rebuild from source; generated output is never an
input. Approved production adoption should move transformations into canonical
templates rather than retaining a post-generation adapter.

Check every route's header, active state, original logo, utilities, and buttons.
Exercise English and Chinese, direct links, client navigation, Back and Forward,
field selection, empty results, and source details. Inspect 1440px, 1024px,
390px, and 320px widths for overflow, wrapping, focus, and contrast.

Compare catalog IDs with fresh generator output. DOM and stylesheet checks
support this review but do not establish visual alignment or replace browser QA.
