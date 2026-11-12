# Site design: capitolalpha.vercel.app

The project site presents the event study in `docs/results/event-study.md`.
It replaced the Spring 2025 "equity research note" page in November 2026,
after the audit retracted that page's headline.

## Brief

- Subject: CapitolAlpha, a pre-planned event study of congressional stock
  purchases (2020 to 2025) by Yinka Vaughan.
- Audience: research faculty, quant and analyst recruiters, curious readers
  who arrive from a resume or LinkedIn link.
- Job: state the answer in three seconds (no detectable alpha), then show
  enough of the method that a reader trusts it.
- Constraints: static files in `site/`, served by Vercel; no build step.
  CRSP stock-level data never ships; `site/data/figures.json` holds
  aggregates written by `pipeline.site_figures`.

## Concepts considered

| | Idea | Anchor | Signature | O/F/Fe/P/S |
| --- | --- | --- | --- | --- |
| A. Event time (material) | The page is one line in event time. It starts as the ground under the Capitol and becomes the average abnormal return of copied purchases, which never leaves zero | an event study measures returns in event time; this project's fix moved day 0 from the trade to the disclosure | scrolling advances event day; the line draws itself day by day inside its band | 4 / 5 / 4 / 2 / 4 |
| B. The filing (material) | The site is a periodic transaction report, filled in field by field | the STOCK Act form | a stamp lands on each part | 3 / 4 / 4 / 2 / 4 |
| C. Sealed plan (process) | The plan is sealed first and opened against the data | the plan was written before any return was computed | an envelope opens on the result | 3 / 3 / 3 / 3 / 3 |

Picked A: it is the study itself, the result is visible as a shape (a flat
line), and the disclosure delay becomes a place on the axis. Taken from B:
the filing unit, where a stamp marks event day 0.

## Concept card

```
Idea:        One line in event time. It begins as the ground under the Capitol and becomes the average abnormal return of copied purchases, which never leaves zero.
Metaphor:    an event-study plot: day 0, an estimation window, horizons, a band around zero
Signature:   3,942 dots, one per disclosed purchase. They fall onto the ground under the dome, leave for day 0 in filing order, then fan out into the real spread of returns while their average stays on zero; at day 62 the plot zooms in 18 times to the mean and its 95% band
Emotion:     calm and certain; a claim checked properly
Motion verb: plot: things draw left to right along the axis and settle on the line
Screenshot:  the dome sitting on a long zero line next to the question
Structure:   the site is the plot. Units are moments in event time (day -250, the trade, the filing, day 0, 20, 62, 125); the corner counter and the Index (event days) replace a navbar. After day 125 the plot unpins into the appendix: robustness, what changed, method, reading.
Escape hatch: the Index popover lists every unit by event day with real anchor links; every number is also in the HTML text.
```

## System

- Palette (dark, single committed theme; v2 after the light v1 read as timid):
  - ground `#0a0f1d` (deep navy, so thousands of dots read as points of light)
  - ground-2 `#111829` (popover surface)
  - ink `#edf1f7`
  - muted `#9aa5ba`
  - line `#242d42`
  - accent `#7b93ff` (the mean line, "No.", focus)
  - sheet `#eef2f8` with paper ink `#111418` for the filing drawing
- Type: Public Sans (the typeface the US government designed for its own
  sites), self-hosted variable 100 to 900. One family; weight and size carry
  hierarchy. Figures are tabular. Display 600, tracking -0.035em, leading 0.95.
- Grid: 12 columns, 24 px gutter, 1440 max. Units take columns 1 to 5, the
  stage 6 to 12. Phone: one column, the stage sticks to the top 42svh.
- Shape: 2 px radius on controls, 0 on figures.
- Motion: ease `power3.out` for entrances, `none` for scrubbed values,
  0.5 to 1.2 s; small things move first. Hovers: an accent rule draws left
  to right under primary links; Index entries slide their day label.
- Idle: the stage holds still at rest. A shimmer on the dots cost too much
  frame time on phones, and a null result reads better as a still mean line;
  the intro fall, the scroll-driven spread and the zoom carry the motion.
- Stage: one canvas, drawn only when the driver changes. Each dot's value and
  local spacing per day are precomputed from the 1st to 99th percentiles in
  `figures.json`, and dots are drawn in one batched path.

## Structure plan

```
desktop                                          phone
+--------------------------------------------+   +------------------+
| alpha CapitolAlpha            Index (pop)  |   | alpha CA   Index |
|--------------------------------------------|   |------------------|
| unit: question (h1)  | STAGE (pinned)      |   | STAGE (sticky)   |
| unit: day -250       |  dome on zero line  |   |  42svh plot      |
| unit: the trade      |  -> axis, band,     |   |------------------|
| unit: the filing     |     line to day d   |   | unit             |
| unit: day 0          |  now marker         |   | unit             |
| unit: day 20         |                     |   | ...              |
| unit: day 62         |                     |   |                  |
| unit: day 125        |                     |   |                  |
|--------------------------------------------|   |------------------|
| appendix: robustness (forest, own zero)    |   | appendix stacked |
| what changed | method & limits | reading   |   |                  |
| colophon                                   |   | colophon         |
| corner: "Event day +62"                    |   | counter in stage |
+--------------------------------------------+   +------------------+
```

Reduced motion and no-JS: no scrub and no tweens. Each unit sets the plot to
its state at once (zoomed for days 62 and 125), every unit is visible, and
the stamp shows its last frame.
Without JS the charts are absent, but every number is in the HTML text.

## Genericness check

- Skeleton: there is no navbar or hero band. The first unit is the question
  beside the dome on the zero line, and the page is the plot.
- Palette: cool form paper and federal cobalt in place of the old finance
  green, which signalled a gain the study does not find.
- Old ticker tape removed: it implied up arrows and live trading.

## Artwork (Glaxnimate)

Sources in `design/marks/`:

- `dome.svg`: the Capitol dome in line, drawn on at load (pattern A).
- `filing.svg`: a filing sheet and rubber stamp, keyed in Glaxnimate as a
  1.6 s SMIL timeline (`data-glax-ms="1600"`), scrubbed by the filing unit
  (pattern B).
- `mark.svg`: alpha on a zero line; the favicon and touch icon.
