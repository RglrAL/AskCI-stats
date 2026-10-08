# AskCI Cost Intelligence: standalone dashboard revision brief

Prepared 1 Oct 2026. Context for an agent revising `index.html`, the standalone single-file cost dashboard, so that its numbers agree with the cost data brief (v3). Scope is this file only. It is not the Cost tab of the AskCI Admin app; that is specified separately. The aim is a trustworthy standalone tool for the next few months, and a visual prototype the admin-app Cost tab can borrow from.

Governing rule: keep the design system and the interactions, rebuild the calculation layer. No number on screen may rest on an assumption that is not in the data or in named configuration.

## 1. What the file is

| Property | Value |
|---|---|
| File | `index.html`, about 400 KB, 7,031 lines, single page |
| Stack | Vanilla JS, Chart.js 4.4.1 and PapaParse 5.4.1 from cdnjs, lucide icons from unpkg (`@latest`, unpinned), DM Sans / DM Mono from Google Fonts |
| Inputs, uploaded | `costs.csv` (Azure Cost Management export) and `usage.csv` (daily `Date, Questions, Sessions`) via drag-and-drop |
| Inputs, fetched from relative paths | `ga4/session-and-users.csv`, `ga4/searches-and-sessions.csv`, `ga4/categories-and-views.csv`, `categories.csv` (year hard-coded to 2026) |
| Browser storage | Theme, custom event markers, monthly spend target, an Anthropic API key for the Ask bar |
| Panes | overview, timeline, breakdown, usage, reach, categories, llm, impact, projections, plus report mode, command palette, KPI history modal, day / month / service / meter drill-down panels |
| Hard-coded | Resource-group filter (`rg-askci-prod`, `me_cae-askci-prod`); `KNOWN_EVENTS` = Modal launch 2026-05-11, Label change 2026-05-20; fixed-service list; cache price ratio; ROI minutes default |

Reference data for acceptance: `costs.csv` as described in the cost brief (12,714 rows, 1 Jan to 17 Aug 2026, £4,537.71 total, GBP).

## 2. Defects to fix, in order

1. **De-duplication drops real rows.** `parseCosts` builds the duplicate key as `date|service|meter|rawCost` and ignores ResourceId. Rows for different resources on the same meter at the same daily cost (private endpoints, Defender nodes, container idle meters on identically sized apps) collapse to one. Fix: key on `date|resourceId|meter|rawCost`; the parser already extracts ResourceId for the resource-group filter. Report `dupesRemoved` in the data-quality strip (section 6) rather than silently. Test: total must equal £4,537.71 and Virtual Network £242.72.
2. **Fixed cost is defined three ways.** `FIXED_SVCS` classifies whole services (all of Cognitive Search fixed, all of Container Apps variable). `fixedEst` separately defines fixed cost as the mean of the cheapest 8% of days and drives the Overview insight and every Projections figure. The cost brief classifies by meter. Fix: one versioned meter classification (section 4), delete `fixedEst`, and make every reference to fixed cost read from the same aggregate.
3. **Estimated cache savings is invented.** `cacheSaved = cachedCost × 3` on the comment "uncached costs ~4× cached". The ratio is not in the data and differs by model. Remove the metric everywhere (KPI, Projections `cacheSavingsPQ`, the polish-layer hero). Rename `cacheRate` to cached-input billed-cost share, tooltip: "share of input-meter cost billed on cached-input meters; understates the cached share of tokens because cached input is priced lower; not a cache-hit rate".
4. **Two forecasts and an overstated run-rate.** The Ask bar projects the month as `avgDaily × remaining days` where `avgDaily` is a post-launch weekday-only mean; `monthForecast` uses separate weekday and weekend means over the last 28 days; the hero run-rate is `avgDaily × 30.5`. Fix: one function, the 28-day weekday/weekend method, used by the hero, the KPI row, the Ask bar and the report. Run-rate for a month = that method applied to a 30-day calendar, not weekday mean × 30.5.
5. **ROI and "cheaper per question" claims.** `updateROI` multiplies questions by a user-typed minutes value (default 15) and shows "Time saved/month". The impact pane shows "Cheaper/question (modal)" and "(fab)". Remove the ROI grid, the cheaper-per-question KPIs and the launch narrative. What remains of the impact pane is descriptive: turns per day, billed cost per day and allocated generation cost per turn before and after confirmed events, labelled as before/after, not impact.
6. **Projections treat fixed cost as constant.** The scale model extrapolates `fixedD + totalVarPQ × volume` to 10,000 questions a day and reports a crossover volume. The data shows the Search tier stepping from about £6 to about £11 a day in May, so fixed cost is a staircase and the crossover is an artefact. Demote the pane to "Scenario planner (model, not data)", move it last, state its assumptions in the pane header, and remove the crossover KPI. If kept at all, the fixed line must be the current fixed daily cost with a note that it steps up with capacity.
7. **Launch dates by heuristic.** `analyse` falls back to the two largest day-over-day jumps in questions when `KNOWN_EVENTS` dates are outside the data; the code comment notes this is fooled by Monday spikes. Remove the heuristic. Events come only from the events file (section 5).
8. **Anomaly detection has no stable baseline.** `detectAnomalies` flags days more than two standard deviations from the all-time mean of generation cost per question. With regime changes in March, May and July there is no single distribution. Replace with the deterministic "What changed" statements (section 4.4).
9. **Browser-side API key.** `askLLM` calls `api.anthropic.com` from the page with a key in localStorage and the `anthropic-dangerous-direct-browser-access` header. Remove `askLLM`, `normalizeLLM` and the key preference. The regex parser (`parsePeriod`, `parseMetric`, `parseCompare`, `parseTopN`, `parseDigest`, `parseForecast`) stays and answers everything the Ask bar needs.
10. **Date parsing is unchecked.** `parseDate` assumes `DD/MM/YYYY` for slash dates and does not reject a month above 12. Add validation; on a file where more than 1% of dates fail, refuse the load and say why, rather than silently dropping rows.
11. **Unpinned dependency.** Pin lucide to a specific version.

## 3. Feature decisions

| Feature | Decision | Notes |
|---|---|---|
| Cost by service timeline | Keep | GBP billed; stacked by service; provisional days shaded |
| Fixed vs variable | Keep the display, replace the engine | Meter classification with Fixed / Variable / Unclassified bands |
| Service → resource → meter drill-down | Keep | Add resource scope (service / admin / shared) as a toggle |
| Model-family breakdown | Keep | Parse meter text through a lookup table; unparsed shown as its own band |
| "Token Type Split" chart | Rename | "Generation billed cost by meter type": input, cached input, output, embeddings, in pounds |
| LLM cost per question | Keep, redefine, relabel | "Generation cost per turn", allocated over the settled join window; remove "leading indicator of cost efficiency" and the cache-hit tooltip |
| All-in cost per question | Keep, redefine | "Allocated total cost per turn" and "Allocated variable cost per turn" alongside it |
| Estimated cache savings | Remove | Unsupported by the export |
| Cache rate KPI | Rename | "Cached-input billed-cost share" |
| Cost anomalies | Replace | Deterministic What changed, section 4.4 |
| Launch impact and ROI | Remove | Replace with before/after descriptive table keyed to confirmed events |
| Projections | Demote | Scenario planner, last pane, assumptions stated, no crossover |
| Budget / spend target | Keep | Optional, user-set, labelled "self-set target"; drives the hero colour only |
| Report mode | Keep | Rebuild its narrative from the same functions as the Summary; keep print CSS |
| Ask bar | Keep regex parser, remove model call | Add "generation cost per turn" and "fixed share" as metrics; forecasts use the single forecast function |
| Events popover | Keep for personal annotations | Shared events come from a file; personal markers stay in localStorage and are drawn in a distinct style |
| Command palette, KPI history modal, chart-to-table toggle, day / month / service / meter panels, theme toggle | Keep | Unchanged |
| RAG pipeline stages (Store → Chunk → Embed → Retrieve → Generate) | Keep | Stage mapping becomes configuration; delete the canned insight sentence and show computed shares only |
| Usage pane, reach pane, categories pane | Keep as optional | Shown only when their files are present; see section 7 for the usage file |
| Hero headline | Keep | Numbers from the single forecast function; "led by" driver is the largest service over the selected range, not the last 30 days regardless of range |

## 4. Calculation layer

Replace `parseCosts`, `analyse`, `fixedEst`, `cacheSaved`, `detectAnomalies` and the three forecast routines with the following. Keep the output shapes the renderers expect where possible; where a field is removed, remove its renderer.

### 4.1 Configuration

One versioned `CONFIG` object at the top of the script (or `config.json` fetched alongside the CSVs; either, but one place), with a `version` string shown in the data-quality strip:

- `resource_groups`: the two prefixes now hard-coded.
- `meters.fixed[]` and `meters.variable[]`: exact meter names from the frozen file. Initially fixed = Search S1 Unit, container idle memory, container idle vCPU, private endpoints, Defender nodes, registry unit, alert rules; variable = every other meter in the frozen file, listed explicitly. A meter in neither list is `unclassified`.
- `model_families[]`: `{match: regex on meter text, family, type}` for gpt-4o 1120, gpt-4o-mini 0718, GPT 5 Chat, GPT 5 Mini, GPT 5, chat-latest 05052026, text-embedding-3-small, with type input / cached input / output / embedding. A Foundry meter matching nothing is `unparsed`.
- `scope`: resource name to service / admin / shared. Initially service = srch-askci-prod, oai-askci-prod, backend, background and frontend container apps; admin = askci-admin backend and frontend; shared = virtual network and private endpoints, Key Vault, registry, Defender, Monitor, storage and bandwidth, Cosmos. Unmapped resources are `unassigned`.
- `rag_stages`: the stage-to-service/meter mapping now hard-coded in `buildRagCostStages`.
- `settlement_days`: 3. `min_settled_join_days`: 7. `min_rate_denominator`: 50. `model_event_min_cost`: 10. `model_event_gap_days`: 7.
- `materiality`: ratios 10% or 0.2p per turn; totals 10%.
- `launch_date`: public Modal launch, used only to label the pre-launch cohort in the usage file if that file carries a source column; otherwise unused here.

### 4.2 Ingest

1. Parse with PapaParse as now. Validate dates (section 2, item 10). Accept negative costs.
2. De-duplicate on `date|resourceId|meter|rawCost`. Count removed rows.
3. Filter to configured resource groups. Count excluded rows.
4. Classify each row: meter class (fixed / variable / unclassified), model family and type (Foundry rows only; else none / unparsed), scope (service / admin / shared / unassigned).
5. Mark `billing_status`: provisional if the date is within `settlement_days` of the latest billing day, else settled. Status is set by age only.
6. Aggregate per day: total, by service, by meter class, by scope, by model family and type. Keep per-meter detail for the drill-down panels.

### 4.3 Join and metrics

- Join window: days that have a usage row with turns greater than 0 and a settled billing row. Everything per-turn is computed on this window only, and the window is displayed wherever a per-turn figure appears ("ratios cover 1 Jan to 14 Aug, 226 days").
- Partial periods are labelled with their span ("Aug 1–17"). Month buckets that are not fully covered carry the label on the axis and in tables.
- Metrics, all in pence per turn unless stated:
  - Generation cost per turn = sum of Foundry generation cost (all families and types except embedding) over the window ÷ turns on those days.
  - Allocated total cost per turn = sum of all cost in the selected scope over the window ÷ turns.
  - Allocated variable cost per turn = sum of variable-class cost ÷ turns.
  - The same three per conversation, using the conversations column.
  - Fixed share = fixed-class cost ÷ (fixed + variable), with unclassified reported separately and in neither.
  - Cached-input billed-cost share = cached-input type cost ÷ (input + cached-input type cost), per family and overall.
  - Billed cost, by period, settled and provisional shown separately.
- Sum then divide, always. Never average daily ratios.
- Validity: a per-turn figure for a period is a dash with the counts in the tooltip when the period has fewer than `min_settled_join_days` settled join days or fewer than `min_rate_denominator` turns.

### 4.4 What changed (replaces anomalies and the templated narrative deltas)

Compare the selected range with the immediately preceding range of equal length, both restricted to settled join days. Candidates: generation cost per turn, total billed cost, variable cost, fixed share. Emit up to three statements where the delta passes materiality and both windows pass validity, ranked by delta ÷ that metric's threshold. Each statement names the metric, both values, the delta and the window spans. If a confirmed event falls inside the selected range, append "event in range: [title]". No causal language ("because", "improved", "drove").

### 4.5 Forecast (one function)

Month forecast = month-to-date settled cost + (remaining weekdays × 28-day settled weekday mean) + (remaining weekend days × 28-day settled weekend mean). Used by the hero, the KPI, the Ask bar and the report. Label: "projected, 28-day pattern". Year figure only on request in the Ask bar, same method applied to remaining days.

## 5. Events

- Shared events come from `events.json` fetched alongside the CSVs, with fields: start, end (optional), kind, status (confirmed / candidate / rejected), evidence, applies_to, title, detail. Only confirmed events draw on charts. Personal markers from the popover stay in localStorage, drawn dashed, and are never written to the file.
- Seed `events.json`:

| Start | End | Kind | Status | Evidence | Title |
|---|---|---|---|---|---|
| 2026-03-09 | 2026-03-10 | model | confirmed | Azure billing export | gpt-4o 1120 and gpt-4o-mini last billed 9 Mar; GPT-5 Mini first billed 9 Mar; GPT-5 first billed 10 Mar |
| 2026-05 | | observed change | confirmed | Azure billing export | Search S1 daily cost steps from about £6 to about £11. Detail: capacity increase suspected, unconfirmed |
| 2026-05-11 | | launch | candidate | old dashboard KNOWN_EVENTS | Modal launch. Detail: the admin-app spec assumes 1 May; confirm with OGCIO |
| 2026-05-20 | | chips | candidate | old dashboard KNOWN_EVENTS | Label change. Detail: meaning to confirm |
| 2026-07-01 | | model | confirmed | Azure billing export | GPT 5 Chat last billed 30 Jun; chat-latest 05052026 first billed 1 Jul |

- Automated candidates: on load, emit candidate model events from meter first and last billed days, subject to `model_event_min_cost`, no "added" on the first day of the file, no "retired" on the latest billing day or inside the settlement window, and `model_event_gap_days` tolerance. Show them in the events popover under "Detected, unconfirmed"; they draw nowhere until a person sets them confirmed in `events.json`.

## 6. Layout changes

Collapse the current tab set into three groups plus two optional ones:

- **Cost** with sub-nav Summary | Services | Models.
  - Summary: hero, KPI row (generation cost per turn, allocated total per turn, billed cost, fixed share, cached-input cost share), cost by service timeline with fixed/variable/unclassified toggle, What changed.
  - Services: service → resource → meter drill-down, scope toggle, resource inventory with region, RAG stages graphic.
  - Models: generation billed cost by family and by meter type, model timeline with confirmed events.
- **Usage** (shown when `usage.csv` is loaded): the existing usage pane, before/after table keyed to confirmed events in place of the impact pane; reach and categories panes only when their GA4 files are present.
- **Scenario planner** (last, demoted, assumptions stated).
- **Report**: unchanged entry point; narrative rebuilt from What changed and the single forecast.

Add a data-quality strip under the header, visible on every pane: config version; billing days loaded; latest billing day and latest settled day; provisional days; rows de-duplicated; rows excluded by resource group; unclassified meters; unparsed Foundry meters; unassigned resources; join window; candidate events awaiting confirmation. Any non-zero in the three "un-" counts is amber.

## 7. The usage file

Keep the `Date, Questions, Sessions` contract so existing files still load, but document that the columns mean turns received and conversations started, and generate the file from the QA feed rather than from the old analytics. Reproduction, pandas in a venv:

```python
import pandas as pd
df = pd.concat([pd.read_csv(f, dtype=str, keep_default_na=False) for f in FILES], ignore_index=True)
df["ts"] = pd.to_datetime(df["Timestamp"], format="%b %d, %Y %H:%M")
df["date"] = df["ts"].dt.date
turns = df.groupby("date").size().rename("Questions")
first = df[df["Turn #"] == "1"].groupby("date")["Conversation ID"].nunique().rename("Sessions")
out = pd.concat([turns, first], axis=1).fillna(0).astype(int).reset_index().rename(columns={"date": "Date"})
out.to_csv("usage.csv", index=False)
```

Feed timestamps are Irish local time (Europe/Dublin; confirmed 8 Oct 2026), so daily aggregates are Irish days. Note that in the file's header comment. Do not add any other column from the feed; only daily aggregates cross into this tool.

## 8. Acceptance checks on the frozen `costs.csv`

| Check | Expected |
|---|---|
| Rows after de-duplication and resource-group filter | 12,714 (the frozen file has no true duplicates; `dupesRemoved` = 0) |
| Total, scope all | £4,537.71 |
| Service totals | Search £2,080.93; Foundry Models £1,167.03; Container Apps £917.00; Virtual Network £242.72; Bandwidth £62.68; other £67.35 |
| Fixed; variable; unclassified | £3,049.52; £1,488.20; £0.00 |
| Unparsed Foundry meters; unassigned resources | 0; 0 |
| Scopes sum to total | service + admin + shared + unassigned = £4,537.71 |
| Model family first and last billed days | gpt-4o 1120 1 Jan–9 Mar; gpt-4o-mini 1 Jan–9 Mar; GPT 5 Chat 1 Jan–30 Jun; GPT 5 Mini 9 Mar–17 Aug; GPT 5 10 Mar–17 Aug; chat-latest 1 Jul–17 Aug; text-embedding-3-small 1 Jan–17 Aug |
| Candidate events at £10 threshold with edge rules | Exactly four: gpt-4o 1120 retired 9 Mar; GPT 5 Mini added 9 Mar; GPT 5 Chat retired 30 Jun; chat-latest added 1 Jul |
| Settled join window at 3 days, with a usage file covering the same dates | 1 Jan to 14 Aug, 226 days |
| Monthly generation cost per turn on all 229 join days (pence) | 1.06; 1.02; 0.73; 0.66; 0.56; 0.49; 2.94; 2.80 (Aug 1–17) |
| August labelling | Every tile and axis shows "Aug 1–17" |
| Hero, KPI, Ask bar and report month forecast | Identical figures |
| Strings that must not appear anywhere | "cache rate", "cache hit", "cache savings", "efficiency", "ROI", "time saved", "cheaper", "crossover", "Token Type Split" |

## 9. Out of scope for this revision

- Anything that needs the QA feed at turn level: outcomes, categories, latency. That is the admin app.
- Server-side anything. The file stays static, loads CSVs and JSON from the browser, and keeps personal preferences in localStorage.
- Visual redesign. Tokens, themes, typography and components stay as they are.
- Porting to the admin app's framework. Find out that framework first; this file is a pattern source, not a code source, unless the stacks match.

## 10. Open questions

1. Public Modal launch date: 1 May (spec assumption) or 11 May (this file's constant). Confirm with OGCIO; it decides which of the two candidate events becomes confirmed.
2. What "Label change" on 20 May refers to.
3. The admin app's front-end stack, which decides how much of this file's component work can be reused rather than re-implemented.
4. Whether a monthly spend target exists on CIB's side, which decides whether the target feature is a self-set tripwire or a real budget line.

## 11. Implementation status (1 Oct 2026)

Done in `index.html` (config version `2026.10.01-1`), `events.json` and `tools/make_usage.py`:

- Section 2, all eleven defects: full-row de-duplication with the count reported; one meter-based classification in `CONFIG`; cache savings and the ×3 ratio removed; one forecast function (`forecastSpan` / `forecastMonth` / `runRate30`) used by the hero, KPI row, Ask bar and report; ROI grid, "cheaper per question" and launch narrative removed; Scenario planner demoted with assumptions stated and no break-even volume; launch heuristic removed; anomaly detection replaced by What changed; browser-side API key and model call removed; date validation with refusal above 1% bad dates; lucide pinned to 1.49.0.
- Section 4: `CONFIG`, ingest, join window, per-turn metrics (sum then divide, validity thresholds), What changed, forecast.
- Section 5: `events.json` seeded as specified; detected model events shown in the Events popover and drawn nowhere; personal markers dashed.
- Section 6: tabs regrouped into Cost (Summary | Services | Models), Usage (Volume | Before / after, plus Reach and Categories only when their files are present; the whole group only when `usage.csv` is loaded) and Scenario planner last. Summary carries the hero, KPI row, the cost timeline with a by-service / fixed-variable-unclassified toggle, What changed and the day table. Services carries the scope toggle (service / admin / shared), the resource inventory with region and the RAG stages. Data-quality strip on every pane.
- Section 7: `tools/make_usage.py` reproduces the usage file from QA feed exports (`--compare` checks against an existing file without writing).
- Section 7, extended 8 Oct 2026: `tools/redact_feed.py` drops the four free-text columns from a feed export (output stays gitignored). `tools/make_usage.py` reads raw or redacted feeds and, with `--out-dir`, writes four daily-aggregate files: `usage.csv` (Date, Questions, Sessions unchanged, plus Answered / Unanswered / Flagged, question types, source turns and sessions, Citations, latency p50 and p90, and Voice columns when the export has an input-mode column), `usage-hours.csv` (Date, Hour, Turns, Sessions; Irish time), `categories.csv` in the current contract with stable display names, and `categories-daily.csv`. `--compare DIR` reports day-by-day and month-by-month differences against the files in DIR and writes nothing. Answered means at least one citation; Flagged means Flagged = Yes; Unanswered is neither. Raw and redacted inputs give identical outputs. The dashboard reads only Date, Questions and Sessions from `usage.csv` today; the other columns wait on a full export that passes the comparison. A Mac droplet, `tools/AskCI Feed Export.app` (built from `tools/feed_droplet.applescript`, logic in `tools/feed_export.sh`), runs redact, compare and generate on dropped feed files, writes everything to an `askci-export-<stamp>` folder beside the dropped file, and copies the four aggregate files into the dashboard folder only on an explicit second confirmation. The app bundle and the review folders are gitignored; rebuild with the one-line command in `.gitignore`.
- Section 8: all acceptance checks pass on the frozen file, with two corrections to the table: the proposed dedup key `date|resourceId|meter|rawCost` removes 87 Azure Monitor email rows that differ only by region (value £0.0016), so the implementation de-duplicates on the full row; March generation cost per turn is 0.76p, not 0.73p; "other" is £67.36 by rounding.

Open:

- `usage.csv` has not been regenerated. The only feed export in the repo covers 6–7 June 2026 (exported 08:13 on 7 June), and for 6 June it yields 398 turns and 167 conversations against 465 and 193 in the current file. Either the current file comes from the old analytics or the feed export is filtered; this needs a full feed export and a decision before the file is replaced. The parser now accepts the file's "Sept" dates, which the old parser silently dropped.
- The open questions in section 10 are unchanged.

## 12. Data refresh (8 Oct 2026), config `2026.10.08-1`

`costs.csv` now runs 1 Jan to 8 Oct 2026 (15,693 rows, £6,370.59). The export also restated August by £38.30, all on days that were provisional in the frozen file, so the section 8 total of £4,537.71 no longer reproduces from this file; rows to 17 Aug now sum to £4,576.02. `usage.csv` runs to 7 Oct; the GA4 files to 8 Oct; `categories.csv` to September (the September rows arrived with a blank Month column, filled in by hand; the upload also created a case-colliding `Categories.csv`, removed because the dashboard fetches the lowercase name).

Config additions, all driven by meters first billed 14 Sep 2026:

- Model families `5.4` and `5.4 mini` (six meters, variable) and `gpt-4o-transcribe` (two meters, variable; speech-to-text billed as tokens, so it counts in generation cost per turn under the section 4.3 rule).
- `Foundry Tools` service (Neural Text To Speech, variable) and the `spch-askci-prod` resource (scope service; its private endpoint is shared). Added to the Generation stage of the RAG pipeline.
- `Task vCPU Duration` (Container Registry) and the two data-transfer-in meters (Bandwidth), variable.
- Output meter type now also matches `out` (transcribe text-out meter).
- Voice (same day, config unchanged in version): `CONFIG.voice` names the speech-to-text and text-to-speech meters; the transcribe meters carry meter type `voice`; voice cost is excluded from generation cost per turn, as embeddings are, so the per-turn series stays comparable across 14 Sep. The Models pane gains a Voice billed-cost card (speech-to-text, text-to-speech, share of Foundry cost, daily chart) and the RAG stages gain a Voice stage. Billed cost only: the export carries no minutes, characters or voice turn counts. The admin app records input mode per conversation (September: 208 voice conversations of 11,431, about 3% of conversations since the 14 Sep launch); a daily voice-conversation column in `usage.csv`, generated from the feed, would unlock voice share and cost per voice conversation. Deferred.
- `events.json`: confirmed model event 14 Sep (GPT 5, GPT 5 Mini and chat-latest last billed; 5.4 and 5.4 mini first billed; voice meters begin), evidence Azure billing export.

Checks on the refreshed file: unclassified meters, unparsed Foundry meters and unassigned resources all 0; scopes sum to the total; detected model events 0 once the 14 Sep event is recorded; join window 1 Jan to 5 Oct, 278 days.

## 13. Full QA feed export validated (8 Oct 2026)

Two export parts, 1 Jan to 28 Sep 2026, 113,410 turns in 56,365 conversations, no overlap and no duplicate (conversation, turn) keys. No input-mode column, so no voice columns. Run through `tools/feed_export.sh`; outputs in `exports/askci-export-full/` (gitignored).

Usage against the current `usage.csv`: turns +0.1%, conversations +0.0% over 271 shared days. The differences are:

- 63 days where the current file has one to three more conversations: it counted conversations active on the day, so one spanning midnight counted twice; the feed count is conversations started, the brief's definition.
- 9 March: current file 23 turns / 15 conversations, feed 206 / 113. The old source lost most of the model-change day. The feed is right.
- 28 Sep: the export's last day, 15 turns short of the current file. Partial.
- 6 June: 465 in both. The June sample export was filtered; the discrepancy in section 11 is closed.

Categories against the current `categories.csv`: April identical; May to August the feed is 3 to 5% higher in every category uniformly, so the current file was built from an earlier, incomplete pull; September lower because the feed ends on the 28th. January to March the current file is 35 to 40% higher: until March the feed's Categories column repeated a category once per citation and the old file counted the repeats (`--category-rule tokens` reproduces it to within 1%). From April the column is distinct per turn. The generator's default, distinct per turn, is consistent across the whole period and is the rule to use; the Categories pane's early months will drop accordingly. The feed also carries a `my-situation` category (12 hits in August) that the current file omits; the dashboard's `CAT_EXCLUDE` decides whether it shows.

A third part (28 Sep to 8 Oct, exported 8 Oct 16:30) completed the range with no overlap. The generator now drops the export day itself as partial (`--keep-partial` overrides) and counts a (conversation, turn) once across input files. All three parts together: 1 Jan to 7 Oct, 122,647 turns, 61,481 conversations, +0.1% turns and +0.0% conversations against the old file.

Copied into the dashboard folder on 8 Oct 2026: `usage.csv` (with the optional columns), `categories.csv` (distinct-per-turn rule; January to March lower than before for the reason above), and the new `usage-hours.csv` and `categories-daily.csv`. Checked in the browser: 280 usage days, no rejected dates, 9 March now 206 turns, join window 1 Jan to 5 Oct, generation cost per turn 1.645p, Categories pane shows January to October. The dashboard still reads only Date, Questions and Sessions from `usage.csv`; the other columns and the hours file are the material for the next piece of work.

## 14. Usage detail from the feed-generated columns (8 Oct 2026), config `2026.10.08-2`

`parseUsage` reads the optional columns written by `tools/make_usage.py` and records which groups are present (outcomes, types, sources, latency, voice); each group switches its own card on. `usage-hours.csv` is fetched from the relative path like the GA4 files. The data-quality strip lists the groups found.

Usage › Volume gains, below the existing cards and only when the columns exist:

- Answer outcomes: answered / unanswered / flagged shares over the selected range, generation cost per answered turn on the settled join window, stacked chart by the selected granularity.
- Question types: new topic / typed follow-up / suggested follow-up (the chips) shares, turns per conversation, stacked chart.
- Source: Modal and Web conversation shares, turns per conversation by source, stacked chart.
- Response time: turn-weighted mean of the daily p50 and p90 (labelled as such; a true range percentile needs per-turn data), daily line chart with confirmed events.
- Hour of day: weekday × hour heat map of turns over the selected range, busiest hour, and the share of turns outside phone-service hours. The hours are `CONFIG.phone_service` (Mon–Fri 09:00–20:00, marked "to confirm" until checked against the published schedule).

Elsewhere: `perTurnStats` returns answered share, generation cost per answered turn and turn-weighted p50, all subject to the existing validity thresholds; What changed gains "Answered share" and "Response time p50" as candidates (same 10% materiality); the Before / after table gains Answered share and Response p50 columns. All shares are sum-then-divide; no causal wording.

Checked in the browser on the full range: answered 85.3%, unanswered 7.7%, flagged 6.9%, generation cost per answered turn 1.92p, suggested follow-ups 20.3% of turns, Modal 71.8% of conversations, p50 12.1s and p90 18.2s, 34.7% of turns outside the configured phone hours, busiest hour 11:00. Before / after around 9 March shows p50 rising from 8.3s to 15.8s and answered share falling from 92.9% to 86.8% with the GPT 5 family; descriptive only.

Not done: the Ask bar does not know the new metrics; report mode does not include them; a voice volume column still depends on an input-mode column in the export.

## 15. Gaps closed (8 Oct 2026)

- Open question 1 resolved from the feed's Source column: 3 Modal turns on 7 May (a test), then 408 of 568 turns on 11 May. `events.json`: Modal launch is now confirmed on 2026-05-11, evidence "QA feed Source column"; the 1 May assumption in the admin-app spec is not supported.
- Open question 2 partly resolved: suggested follow-ups (chips) have been present since 1 Jan, so the 20 May "Label change" is not their introduction. The feed shows Modal turns stepping from about 440 to about 820 a day on 20 May with Web unchanged; recorded as a confirmed observed change on 2026-05-20. The "Label change" candidate stays a candidate with that note.
- Ask bar: answered, unanswered and flagged share, response time p50 (turn-weighted; "slowest day" picks the highest daily p50), suggested follow-up share, Modal share of conversations, and citations. Shares are sum-then-divide; a question about a column the file lacks says so.
- Day panel: Answered and Response p50 cards when the day carries them. Report narrative: a sentence with answered share, flagged share and median response time on the join window.
- Usage › Volume: citations per answered turn in the Answered tile; the hour-of-day heat map toggles between turns and conversations.
- Cost › Models: weekly follow-up share against cached-input billed-cost share, descriptive.
- The site-search-versus-chatbot comparison already exists on Usage › Reach (information-seeking share and adoption rate); nothing new was needed there.

Still unused: `categories-daily.csv` (no daily counterpart on the GA4 side). Still unavailable: voice volume.

## 16. Drill-down audit (8 Oct 2026)

Targets are the existing day, month, service and meter panels and the KPI history modal. After the audit every chart except the Scenario planner's two, the Ask bar's and the burn-down opens something:

- Summary share donut: Fixed opens the fixed-share history, Generation opens Models, the rest opens Services.
- Usage: answer outcomes, question types and source bars drill by the selected granularity (day, busiest day of the week, month); the latency line opens the day; weekday/weekend bars open the month; hour-of-day cells open the busiest day in that weekday-hour slot; Peak day opens its day.
- Models: the weekly follow-up/cached-share chart opens the busiest day of the week.
- Before / after: the daily turns line opens the day; each event row opens the event's day.
- History modal entries for answered, unanswered and flagged share, generation cost per answered turn, new-topic, typed and suggested follow-up share, Modal and Web share, response p50 and p90; the tiles in the new Usage cards open them.

Left without a click: Reach and Categories (monthly, compared with GA4, no panel of their own), the Scenario planner (a model), the Ask bar chart and the burn-down.

## 17. Adopted from the admin-app analytics spec (8 Oct 2026), config `2026.10.08-3`

Reviewed `brief/AskCI Analytics Dashboard Spec (4).md`. Three pieces adopted; the rest needs query text or belongs to the admin app.

1. **Outcome taxonomy.** `tools/redact_feed.py` classifies every turn before it drops the text and writes Outcome, Partial and Outcome Rules columns into the redacted feed; the generator sums them per day into Cited, NotFound, Clarification, Error, OutOfScope, Greeting, Uncited, Partial, Scored and OutcomeRules. Rules are the spec's, in its order, with two changes recorded in the script: curly apostrophes are mapped to straight ones before matching (the feed mostly uses U+2019, which is why the spec's printed not-found pattern under-counts), and "does not (currently) provide/have" is added to not-found. Rule-set version 2026.10.08-1. Against the spec's fixture on the 1 Jan to 28 Sep rows: cited 97,594, error 1,732 and greeting 1,267 exact; not found 6,058 vs 5,949; clarification 4,821 vs 4,833; out of scope 1,284 vs 1,287; uncited 654 vs 748; partial 9,441 vs 7,449 (the wider not-found pattern marks more cited answers partial). Usage › Volume now shows the seven shares, the quality rates over scored turns, the error rate over all turns, and a 100% stacked outcome mix; the word Flagged leaves the screen when the taxonomy is present. Ask bar, history modal, report narrative and the data-quality strip (rule version) follow.
2. **Small-sample rule.** `rateOK(n, d)`: a rate needs `min_rate_denominator` (50) in the denominator and `min_event_numerator` (5) in the numerator, except an exact 0 on at least `min_zero_denominator` (500) is shown. Applied to the outcome tiles, the history-modal daily series, the Ask bar shares and `perTurnStats` rates.
3. **Comparison periods and What changed.** `comparisonWindow`: a full calendar month compares with the previous month; month to date (a range from the 1st that ends within the settlement window of the latest data) with the same elapsed days of the previous month; otherwise the preceding window of equal length. What changed now draws from fifteen candidates in five priority classes (failures; latency; quality and cost per turn; demand and cost; product behaviour), at most two per class and six in all, with the spec's thresholds: rates 1 point, counts 10%, latency 10% or 2 s, pence per turn 10% or 0.2p. Per-day figures replace window totals so unequal windows compare fairly.

Checked on the full range: cited answer rate 88.8%, not-found 5.8%, clarification 4.9%, error 1.5%, cited but partial 10.9%. September against August: not-found +2.9 pts, cited −5.4 pts, partial +6.7 pts, conversations per day +25%.

Sent back to the spec: its printed not-found pattern does not reproduce its own fixture (apostrophes); the public Modal launch is 11 May in the feed, not 1 May; the timezone is confirmed Irish; the 980 pre-launch Modal turns on 22 days are real and recorded as a candidate event.

## 18. Overview tab, corrections from the cost brief, feedback and prompts (8 Oct 2026)

Layout revision (supersedes the tab order in section 6): a new **Overview** group opens first. One screen: a headline sentence from the same functions as the report; six tiles (cited answer rate, not-found rate, response time p50, conversations, month forecast, generation cost per turn) with deltas against the comparison window; What changed for the service set; conversations by source and outcome mix. The cost hero and KPI row are hidden while it is active. Cost › Summary keeps its own What changed restricted to the cost set (generation cost per turn, billed and variable cost per day, fixed share; at most three statements), per cost brief v3 §5.3; the report carries both sets under separate labels. The approximate euro figure and `gbp_eur` are removed (cost brief §5.3, no converted figures). The KPI row shows four primary tiles; fixed share, cached-input share, total turns and average daily spend sit behind "more". On Usage › Volume the outcomes card comes first; the calendar heat map, the day table on Summary and the resource inventory are collapsed by default.

Generator additions from `brief/AGENT_BRIEF.md`: Likes, Dislikes and DislikesOnCited per day; StarterPromptFirstTurns and OrganicFirstTurns from the six chips listed in the brief, matched on normalised first-turn queries at redaction (versioned with the outcome rules; effective dates unknown); ScriptLatin … ScriptNone from the Unicode script of the first letter, a script not a language. Dashboard: Feedback card (counts beside every rate; dislikes per 1,000 cited answers under the small-sample rule), starter-prompt tile, Query script card, Before/after column for dislikes per 1,000, What changed candidate, history-modal entries and Ask bar metrics. Full range: 439 likes, 157 dislikes (150 on cited answers), feedback rate 0.49%, 1.4 dislikes per 1,000 cited answers, starter prompts 6.1% of first turns, non-Latin scripts 0.51% of turns (Cyrillic 333, Arabic 215).

July analysis (cost brief §5.7), written into the 1 July event: June to July, complete months, cited answer rate 86.2% → 91.8%, not found 8.2% → 3.5%, clarification 4.3% → 4.5%, cited but partial 3.0% → 14.0%, p50 11.3s → 12.5s, p90 16.3s → 17.0s, dislikes per 1,000 cited answers 1.73 → 1.19. The new model answers more often with a citation but hedges far more; descriptive only.

Not committed: the `screenshots/` folder added alongside the briefs.

## 19. First slice from the prototype mock-ups (8 Oct 2026)

Reviewed the six prototype screenshots in `screenshots/` (not committed). Taken now:

- Rate deltas in percentage points, latency deltas as percent with seconds, counts and money as percent (`deltaChip` units). The Overview tiles use them.
- What changed statements carry a class chip: service failure, latency, quality, demand, product behaviour, or cost.
- Generator: cited, not-found and scored counts by source (Modal, Web) and by question type (new topic, typed follow-up, suggested follow-up); latency p99 and the four latency bands (under 10, 10–20, 20–30, over 30 s), positive values only.
- Usage › Volume: "Outcome by source and question type" table (small-sample rule per cell); Response time card gains p99, an "over 30 s" share, the band chart stacked to 100%, an errors-per-day bar, and a dashed p90 target line from `CONFIG.latency_target_p90_ms` (20 s, provisional; spec open question 13).

Full range: Modal cited 87.6% and not found 6.0%; Web 91.9% and 5.1%; new topic 86.0% and 7.0%; typed follow-up 88.2% and 6.0%; suggested follow-up 96.5% and 2.4%. Latency bands: under 10 s 28%, 10–20 s 64%, 20–30 s 5%, over 30 s 2%; p99 28.0 s.

Second slice, not started: conversation grouping in the generator for turns per conversation, length by first outcome, observed span and category journeys; category-by-outcome attribution; top cited pages; per-prompt starter table; heat-map metric toggle.

## 20. Second slice: conversation-level aggregates (8 Oct 2026)

The generator now groups turns by conversation (a second pass over minimal per-turn records, no text) and writes five more files beside the four daily ones. Conversations start on the day of their first turn and are mature 24 h after it; depth metrics use the mature cohort only. Attributed category is a turn's own primary cited category, else the most frequent among the other turns of its conversation, else unknown; failed turns rarely carry their own category, so category failure rates are lower bounds and an Unknown row is always shown.

| File | Grain | Used by |
|---|---|---|
| `conversations-daily.csv` | start day: started, mature, turns histogram 1–10+, span buckets, chip and typed use, per first outcome counts, singles and turn sums | Usage › Conversations |
| `category-outcomes-daily.csv` | day × attributed category: turns by outcome, scored, organic first turns, dislikes on cited | Usage › Categories: demand and quality table, outcome heat map |
| `citations-monthly.csv` | month × normalised URL with its category | Usage › Categories: top cited pages, distinct pages, external share |
| `journeys-monthly.csv` | month × from × to category steps, mature conversations | Usage › Categories: journeys |
| `starter-prompts-monthly.csv` | month × chip: count, cited, followed by typed or suggested turn 2 | Usage › Conversations: starter prompts table |

`usage-hours.csv` gains NotFound, Errors, Timed and LatencySumMs per slot, so the hour-of-day heat map toggles between turns, conversations, not-found rate, error rate and mean response time (rates under the small-sample rule). The redaction script writes the matched chip text in Starter Prompt rather than Yes. The partial-day rule now skips only the newest export's own day.

Diagnostics against the admin-app spec fixture (ours runs to 7 Oct, the fixture to 28 Sep): follow-ups within 1 h 98.88% (fixture 98.84%), within 24 h 99.96% (same); conversations with two or more category steps 8,013 (7,304), with a return journey 1,722 (1,565); not-found turns recovering a category 2,859 of 6,834 (2,479 of 5,949, the difference being our wider not-found pattern). Full range: 54.1% of mature conversations end after the first turn, mean 2.00 turns; chips used in 25.5% and typed follow-ups in 27.2%; conversations starting with a not-found answer average 1.43 turns and 79% end there; clarification starts average 2.60; category known for 93.4% of turns; 1,879 distinct citizensinformation.ie pages cited, external citations 0.20%; the top journey is Employment → Social welfare.

Still open from the mock-ups: Overview "organic demand by topic" bars (the data now exists in category-outcomes-daily); the What changed "category accounted for X% of additional turns" clause; latency by response length and citation count, which would need per-turn word and citation counts kept at redaction.

## 21. Remaining mock-up items (8 Oct 2026)

- Overview: "Organic demand by topic", horizontal bars of organic first turns by attributed category (top 8 plus Unknown), segmented by those turns' outcomes, with the organic count and attribution coverage stated; click opens the Categories tables. The generator writes Organic<Outcome> columns into `category-outcomes-daily.csv` for it.
- What changed: for an increase in turns per day or in the not-found rate, when one attributed category accounts for 30% or more of the additional turns (or additional not-found turns) the statement says so, e.g. May against April: "Turns per day: 466 vs 173, +170%. Social Welfare accounted for 39% of the additional turns." Unknown is never named.
- Latency by response length and by citation count: the redaction script keeps a response word count (a number, not text); the generator writes `latency-buckets-daily.csv` (Date, Kind, Bucket, Turns, LatencySumMs); Usage › Volume shows mean response time per bucket, labelled as a mean, buckets under 50 timed turns blank. Full range: 6.5 s for answers under 50 words rising to 18.2 s over 300; 9.4 s with no citation rising to about 15 s with four or more.

Every tile in the six prototype screenshots that can be built from daily or monthly aggregates now exists here. The remaining ones (not-found work queue, top organic queries, disliked conversations, Explorer) need query text and stay in the admin app.

## 22. Ask bar coverage (8 Oct 2026)

The rule-based parser now reaches every generated file, so everything the panes show can be asked for.

- **Category dimension.** "in housing", "for social welfare", "tax category" on turns, organic first turns, cited, not-found, clarification and error rates and dislikes per 1,000, from `category-outcomes-daily.csv`. "Which category has the highest not-found rate" ranks categories (five for "which", ten for "top"), with each row's turn count.
- **Source and question-type filters.** "for modal", "on the web", "for chips", "for typed follow-ups", "for new topics" on cited and not-found rates (scored denominators from the cross columns) and on turns and conversations. "Modal share" and "by source" keep their old meaning.
- **New metrics.** Ended after first turn, suggested follow-up use and conversations over 5 minutes (mature cohort); p90 and p99 (turn-weighted, with the provisional target on p90); turns over 30 s; busiest and quietest hour (hour series charted); out-of-hours share; voice billed cost; non-Latin, Cyrillic and Arabic script shares; organic first turns; confirmed events in a period.
- **Lists.** Most cited pages (links open the page), starter prompts, category journeys.
- A category can also come first ("health citations", "housing not-found rate", "health last month" meaning turns in Health), and citations by category answer from `categories-daily.csv`, counted one per turn per category.
- The example chips and the "couldn't parse" hint show the new forms. Every rate goes through the small-sample rule; every answer names its denominator.

Checked: twenty-five questions across the new forms answer correctly, including "cited rate for chips this year" (96.5%), "web conversations in September" (1,546), "p99 in April" (68.1 s), "busiest hour this month" (14:00) and "events in May" (two confirmed events).
