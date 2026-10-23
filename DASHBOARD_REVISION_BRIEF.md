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

## 23. Ask bar: by month or week, and trends (9 Oct 2026)

- **Grouped answers.** "by month", "monthly", "by week", "weekly" on any metric, with any category or filter: each bucket is computed exactly as the single answer would be (sum then divide inside the bucket), partial months carry their span, buckets that fail validity or the small-sample rule show a dash. Rendered as chart, table and CSV; a month opens the month panel, a week sets the range. Superlatives ("busiest month") keep their old meaning. Events, hours, top-service and run-rate questions have no grouped form and say so.
- **Trend answers.** "is X rising", "trend of X", "increasing", "getting worse" and similar compare the first half of the period with the second, judged by the dashboard's materiality thresholds (rates 1 point, counts 10%, latency 10% or 2 s, pence per turn 10% or 0.2p) and reported as rising, falling or no material change with both values, the delta and the threshold. A trend with no period defaults to the last 90 days; "since July" is a range from 1 July to the latest day. Descriptive wording only; the daily series is drawn with the half-way point marked.
- Follow-up chips offer "by month" and "is it rising" on any answer.

Checked: "not-found rate by month" (Jan 3.4% … Jun 8.2%, Jul 3.5% …), "p90 by week last 3 months", "cited rate for modal by month this year", "is the not-found rate rising" (3.1% → 7.0% over the last 90 days, rising), "trend of p90 since July" (16.5 s → 17.0 s, no material change), "is clarification rate increasing in housing this year" (2.2% → 5.2%, rising).

## 24. Ask bar: "read as" chips and "what changed in <period>" (9 Oct 2026)

- **Read as.** Every single, grouped and trend answer ends with a row of chips showing how the question was parsed: metric, period, category, filter, shape (single, by month, by week, trend) and aggregation. Each chip is a select listing the alternatives, including every service and model family, every month in the data and the sixteen categories. Changing one re-runs the answer from the adjusted intent without re-parsing, writes the resulting question into the input, and becomes the context for follow-ups. A wrong guess by the keyword matcher is a one-click fix, and the chips double as a map of what the bar can answer.
- **What changed in a period.** "What changed in September", "what moved last month", "what changed" (last 28 days) return the dashboard's own What changed statements for the service set and the cost set separately, with their class chips, the comparison window and rule, and the confirmed events in range. "Why did spend change" keeps its cost attribution answer.
- A grouped answer with no computable bucket now says why (for instance, p90 is not available by category) instead of "no data".

## 25. Click-throughs and conversation outcomes (23 Oct 2026), config `2026.10.23-1`

- **Data refresh.** All aggregates regenerated from the four feed exports, 1 Jan to 22 Oct 2026 (136,752 turns, 69,096 conversations; 23 Oct dropped as partial). This replaces a three-column `usage.csv` uploaded on 16 and 23 Oct that had lost the outcome, source, type, latency and feedback columns and carried 23 turns for 9 Mar (feed: 206). `make_usage.py` fixes: starter-prompt first turns were never counted in `usage.csv` (the redacted feed holds the chip text, not "yes"); categories with equal counts are ordered by slug so regenerations are byte-stable. `tools/audit_data.py` recounts the feed independently and checks every file; run it after each refresh.
- **Click-throughs, data.** `tools/make_clicks.py` turns unsampled GA4 Exploration exports (`ga4/Ask-ci-click-throughs*.csv`: Date × Page location, Views, Total users, Sessions by device) into `ga4/clicks-daily.csv` (Date, Source, Views, Sessions, Mobile, Desktop, Tablet, OtherDevice) and `ga4/clicks-pages-daily.csv` (Date, URL, Source, Views). It refuses exports that don't add up (devices to totals, rows to the Grand total, overlaps, gaps). URLs are normalised with `norm_url`, so they join to `citations-monthly.csv`. A sampled export (every value a multiple of about 3.6) was deleted; export a month or two at a time and check the shield reads 100% of data.
- **Click-throughs, definitions.** A click-through is a GA4 page view of a citizensinformation.ie page whose address carries `utm_medium=chatbot&utm_campaign=citation`, reloads included. Source from `utm_source`: `askci-embed` is the pop-up (feed Modal), `askci-app` the standalone site (Web); `askci` was an early tag (1 view, 9 Jan). Rates have matched denominators: pop-up clicks ÷ Modal cited answers, standalone ÷ Web cited answers, combined ÷ all cited answers, labelled "per 100 cited answers". Measured from `CONFIG.click_tracking_from`: standalone site 10 Mar (clicks go from about 0 to 2–6 per 100 that week), pop-up 11 May (its 980 pre-launch questions produced no tagged clicks); combined from 11 May. Before those dates a surface is "not measured", never zero. Per-page rates are per 100 times *cited* (a different unit, labelled as such); topic rates are per 100 cited answers attributed to the topic. GA4 counts only visitors who accept analytics cookies, so every figure is a minimum and says so, including on the Overview tile. Click-throughs are kept out of What changed for that reason.
- **Click-throughs, figures.** 4,883 click-throughs in the exports (4,869 to 22 Oct; 4,510 from 11 May to 22 Oct), about 4.7 per 100 cited answers combined since 11 May; 79% from the pop-up; 67% on mobile; 814 distinct pages.
- **Click-throughs, screen.** New Usage › Click-throughs sub-tab: minimums banner; KPI row (click-throughs, per 100 cited answers, CI pages reached, on mobile) with changes against the comparison window; rate by week (or month) per surface with direct labels, hollow partial weeks and event lines; click-throughs by week stacked by surface; surface and device 100% bars; rate by topic; cited-vs-clicked page table with four sorts and a badge on pages cited 100+ times with no recorded click. Overview gains a click-through tile (combined rate, minimum caveat on the tile, opens the sub-tab). The day panel gains a click-throughs section.
- **Open checks.** (1) GA4 property reporting time zone must be Europe/Dublin to match the feed's days. (2) State Pension (Contributory) is cited 2,283 times since May with no recorded click while its "-pre-2025" page gets 63: confirm in a browser whether the cited address redirects, then settle the badge wording.
- **Conversation outcomes, data.** `conversations-daily.csv` gains, over mature conversations by start day: `ReachedCited`; per not-found, clarification and error answer (`NF`, `Clar`, `Err`) `Turns`, `LaterCited`, `Ended`, `NextTyped`, `NextChip`, `NextNew`, `NextOther`; `WithTopic`, `MultiTopic`, `TopicReturn`; `Gap0to1` … `GapOver60` (minutes between consecutive questions). The diagnostic formerly printed as "not-found turns recovering a category" counted category *attribution*, not answers, and is relabelled.
- **Conversation outcomes, definitions and figures (1 Jan – 22 Oct, 68,509 mature).** 88.3% reached a cited answer. Counted per answer, not per conversation, and a later cited answer may be to a different question, so nothing here is called recovered or resolved: after a not-found answer the conversation later got a cited answer 19%, continued without one 6%, ended there 75%; after a clarification 63% / 12% / 25%; after an error 6% / 2% / 92%. 14.6% of conversations with a cited topic covered more than one topic and 21.1% of those came back to an earlier one; 92% of follow-up questions came within 5 minutes.
- **Conversation outcomes, screen.** The Conversations sub-tab opens with: Conversations that reached a cited answer (hero, change, weekly sparkline, history); After a not-found, clarification or error answer (100% bars with a table view) beside What came next (next-question split, each row summing to 100%); Topics in a conversation; Pace between questions. Overview gains a Reached a cited answer tile; What changed gains it as a quality candidate.
- **Ask bar.** New metrics: click-throughs, click-throughs per 100 cited answers, reached a cited answer, not found then a later cited answer; "top clicked pages". All work by month, week and trend.
- **Shared fixes.** Event-line labels now stagger onto up to three rows instead of overprinting, on every chart. Chart table views take a first-column label other than "Date".

## 26. Audit fixes (23 Oct 2026)

A full audit (data checks, two independent code reviews, a render sweep of every sub-tab in Day, Week and Month views across seven ranges, and on-screen numbers checked against independent calculations) found the following, now fixed.

- **Feed figures and cost figures on separate bases.** Outcome rates, latency, feedback and volumes per day were computed only over settled join days, so the Overview showed 88.3% cited answers against 88.2% on the Usage tab and in the Ask bar, and the 7-day range showed no outcome figures. `perTurnStats` now computes feed figures over every day with usage data (`udays`, `uspan`, `uvalid`; the small-sample rule applies to each rate) and cost-per-turn figures over settled join days as before. What changed compares each set on its own basis, so both windows are complete and equal in length (service: usage days, at least five each side; cost: settled join days), and its demand attribution compares per-day rates.
- **Starter-prompt shares** divided whole-month prompt counts by the range's conversations (a 7-day range showed 19.5% against a true 5.7%); they now divide by conversations started in the same months.
- **Cost per turn by week or month** now uses settled join days only; the top tiles' week-over-week chips compare the last 7 qualifying days with the 7 before, sum then divide, with no provisional or cost-only days; the month panel's cost per turn is per settled join day and its averages count usage days only; the Usage monthly summary no longer counts the cost-only 23 Oct as a zero-turn day and labels a clipped first month with its days; the meter panel totals the meter over the selected range, not all time.
- **Ranges and dates.** The 7D / 1M / 3M buttons covered 8 / 31 / 92 days; now 7 / 30 / 91. Date arithmetic is UTC throughout. Usage period labels end on the last usage day, not a later cost-only day. URL values for view, range and theme are validated.
- **Reach.** Both shares are upper bounds (GA4 undercounts sessions and searches, AskCI is counted in full): shown as "at most" with a banner; changes in percentage points; a clipped first month is dropped like a partial last month; the adoption wording no longer calls standalone-site conversations site visits.
- **Unvalidated outcomes.** `CONFIG.outcome_rules_unvalidated_from` (14 Sep 2026) adds a note wherever outcome figures cover those days, and an amber item in the data-quality strip, until a hand-labelled sample shows whether the answers or the text rules changed. Not-found also rose in May and June and fell after the 1 Jul model change, so each model change has moved these measures.
- **Events.** Event lines now draw in Week and Month views (`bucketLabel`). `events.json` adds Budget Day (confirmed, kind `other`, which draws on charts but gets no before/after row) and, as candidates awaiting confirmation, the 14 Sep outcome shift and error spikes on 27 Jan, 13–14 May, 29 May and 29 Sep.
- **Ask bar.** ISO dates no longer read as the whole year; month names match whole words ("decreasing" was December); service aliases match whole words ("across" was Container Registry); "5.4" keeps its decimal point; "new topics" is a filter, not the topic list; highest / lowest week or month of a rate is computed per bucket, not by adding daily rates; explicit ranges ("15 March to 30 April", "March to May") work; the click-through rate falls back to the standalone site before 11 May, as the Click-throughs tab does; questions asking for a share or rate are not sent to the glossary.
- **Smaller.** Chart tables keep the plotted order and sort blanks safely; the hour heatmap's busiest hour is by turns in every mode and its not-found mode is labelled a share of turns; Uncited answer no longer shares Cited answer's green; month-panel labels say what they include; the Reach footnote's hard-coded figures are gone.

Known and left as they are: fixed share is computed three ways (report: settled join days; KPI row: settled days in range; Cost insight: all settled days); the non-Latin share tile is over all turns while its history is over turns with letters; the cited-vs-clicked page table divides clicks from part of a month by citations from whole months (labelled); the toolbar overflows at phone width.

## 27. Ask bar: hours of the day (23 Oct 2026)

- **Hour ranges.** "Questions between 8pm and 9am", "between 20:00 and 09:00 in October", "after 8pm on 6 October", "conversations before 7am", "not-found rate between midnight and 6am", "response time after 10pm", and any of these by month or week. Answers come from `usage-hours.csv` (Irish time, hour precision; ranges may wrap midnight) and give the share of the period's questions. Metrics with no hourly form (cost, citations, outcomes other than not-found and error) say so instead of answering for the whole day; previously the hour clause was silently ignored and the full-day total returned.
- **Comparisons.** "vs the prior Nd" now clips a period that runs past the data (e.g. "October" on 22 Oct) to the last day with data before taking the prior window, so a part month is no longer compared with a whole one; an hour-range answer compares the same hours of the prior window.

## 28. Ask bar covers the Department of the Taoiseach figures; the site's page list (23 Oct 2026)

Every figure sent for the Department of the Taoiseach post can now be asked in several phrasings, and each answer was checked against an independent recount.

- **Named moments.** "Budget Day" and "Budget week" (from the confirmed Budget Day event), "the pop-up launch", "since the launch".
- **Day ranges.** "5 to 11 October", "October 5 to 11", alongside "15 March to 30 April" and "March to May".
- **A single day is compared with the same weekday** over the previous four weeks ("2.4× the average of the previous four Tuesdays (924)"), including when narrowed by topic or hours (money and tax on Budget Day: 10.2×; after 8pm: 3.2×). Answers narrowed by topic, filter or hours compare the same narrowing in the prior window.
- **Growth.** "How much has usage grown since April", "growth since the pop-up launch": questions per day in the base month (for the launch, the whole month before it) against the latest complete month.
- **Counts.** "How many links" (citations, with the share to citizensinformation.ie), "how many different pages were cited" (1,892 addresses; 1,440 of the site's 1,493 English information pages), "how many pages did people click through to" (814). Any "how many" question returns a count, never a list.
- **Topics.** "What do people ask about most", "top topics": with each topic's share of questions with an identifiable topic.
- **Clicks.** "How many times did people click a link", "which page do people read most".
- **Site page list.** `tools/make_site_pages.py` turns a saved sitemap into `site-pages.csv` (URL, Language, Kind by address depth, LastMod, ListedOn); 3,749 pages on 23 Oct, 1,493 English information pages. The Ask bar uses it for page coverage, and the Click-throughs page table marks cited addresses that are not on the list (old or moved addresses, or links slightly wrong). State Pension (Contributory) is on the list yet had 2,896 citations and no recorded click; worth checking the link in AskCI itself.

## 29. Ask bar audit, step 1: never answer a different question without saying so (23 Oct 2026)

An audit put 128 realistic questions (management, quality, content, clicks, cost, comms, loose phrasing, combined questions, follow-ups, questions to decline) to the Ask bar, each from a clean state. Before: 53 right, 14 partly right, 8 unparsed, and **53 confidently answering a different question** without saying so (e.g. "questions this quarter" → the all-time total; "questions on weekends" → the total; "is the answer quality getting worse" → a trend in spend; "what did people ask about the budget" → Budget Day's cost). After: none of the 128 answers a different question; three are partly right (answered share vs cited rate, topic list by rate when "most not-found answers" may mean a count, a pop-up-vs-standalone rate that gives the pop-up only).

- **No silent defaults.** A question naming no measure gets "Which measure?" with one-click choices, never total spend. A comparison naming no measure gets the same.
- **Follow-ups only when the question reads as one** ("and August?", "what about housing?", "by week", three words or fewer) and always announced ("Following on from …"); they carry topic, source, hours and days forward. Non-scalar answers end the chain. Before, any question without its own dates silently took the previous question's.
- **Notices** above an answer state every correction or limit: "Read 'conversatons' as 'conversations'", "Counting weekends only", "AskCI has no login, so people can't be counted: showing conversations", "This list covers every source", "This answers one measure; ask … for the other", "The data is daily, so this shows the latest full day".
- **Declined plainly, with something answerable offered:** question text (privacy), who uses AskCI, languages (only the alphabet is recorded), holidays and seasons (no calendar), causes outside cost, usage predictions and forecasts beyond the current month, year on year (data starts 1 Jan 2026), comparisons with the phone service, device outside click-throughs, hours combined with a topic or source, unsupported source filters, ranking topics by change, page click-through-rate rankings (pointing to Usage › Click-throughs).
- **Now understood:** quarters (Q3, this/last quarter), fortnight, first/last week of a month, weekends, weekdays and named weekdays (filter), morning / afternoon / evening / night / lunchtime and "between 9 and 5", "last 24 hours", busiest day of the week, time of day, questions per conversation, ended after one question, cost per conversation, what a question costs, models' cost, fail to find, out of scope share, quality (cited answer rate), share of questions about a topic, pages cited for a topic, topic journeys and "what do people ask about after X", a named page's citations and click-throughs by month, click-throughs by surface and by device, the click-through rate by surface, Reach shares ("site visitors", "site search", at most), "how is AskCI doing" (latest month's summary), "what will October cost" (the forecast), abbreviations (NF, qs, wk, convos, CTR, pop-up, standalone) and near-miss spellings.
- **Fixed on the way:** comparisons coloured a rising not-found or error rate as good; rate comparisons now show percentage points; "how did September compare to August" parses; "monthly run rate" no longer groups by month; the glossary no longer catches cost or site-search questions.

Next steps from the audit: (2) commit the 128-question battery as an automated regression test; (3) one declarative definition per measure; (4) a scored slot grammar with "did you mean"; (5) an optional model step that only translates questions into the same structured request, decided later.

## 30. Ask bar regression test (23 Oct 2026)

`tools/test_ask.py` runs 179 questions (the audit's 128, the 48 verified figures including every number sent for the Department of the Taoiseach post, and context-bleed sequences) through the real page in headless Chrome, in about seven seconds, and checks each answer: text it must contain and, for the questions that used to answer something else, text it must not. The page is the current `index.html`; the data is frozen at the commit in `tests/ask_fixture_ref`, read with `git show`, so no data is duplicated and refreshes never move the expected answers. The pre-commit hook runs it on the staged page whenever `index.html` or a test file is committed. Deliberately breaking quarter parsing and the follow-up rule made it fail on the cases that cover them, as it should. Also fixed: "what do people ask about after social welfare" now lists journeys from that topic (the topic was not recognised after "after").

## 31. Ask bar audit, step 3: one definition per measure (23 Oct 2026)

`ASK_METRICS` in the Ask bar is the single definition of each of its 55 measures: label, unit (count, gbp, pence, pct, per100, perk, ms, ratio, hour, weekday, list), polarity (lower or higher is better, or neutral), whether it comes from billing data, whether it can be grouped by week or month or compared with the prior window, whether it can be split by source, whether it is in the "read as" menu, its synonyms (each with a priority) and its definition.

- **Derived from it:** the 23 hand-typed lists that decided rates, money formatting, colour polarity, prior comparisons, grouping, source filters and the read-as menu. Several had drifted (cost per conversation, pages and weekday listed as percentages; trend and compare colouring disagreeing on which measures are better lower).
- **Parsing:** 45 synonym rules now sit on their measure's entry; 15 rules that build their answer from the question (label variants, services, model families) are hooks in `PARSE_HOOKS`; both run in one priority order. The conversion was checked by comparing the full text of all 179 test answers before and after: identical.
- **Definitions:** "define X", "explain X", "what does X mean", "what is meant by X", "how is X calculated / counted" answer from the registry, in the dashboard's own words.
- **Self-check:** malformed entries (duplicate id, unknown unit or polarity, a bad synonym) are listed in `window.__askRegistryProblems`, and `tools/test_ask.py` fails on any.
- **Adding a measure** now takes a registry entry and, unless it is a simple daily sum or share already handled, a calculation branch. Moving the calculations themselves onto the registry (numerator, denominator, source file) is the remaining part of this step; the scored grammar is step 4.

## 32. Ask bar audit, step 4: best fit, combined questions, typos (23 Oct 2026)

- **Best fit.** Every synonym rule and hook that matches a question is collected with where and how much of it matched. The longest match wins and priority breaks ties, rather than the first rule in the list. "Which language model costs the most" is now about models (chat-latest), not total cost. "How long do answers take" is response time (12.0s), and "how long are conversations" is conversation length (22.1% over five minutes). A filter phrase ("for the suggested follow ups") is taken out before the measure is scored, so it can't be read as the measure. Other readings that matched apart from the winner and aren't generic are offered as "Also read as" chips.
- **Combined questions answered in full.** "Questions and conversations in September", "not-found rate and error rate last month" and "not-found rate for housing vs employment" show both values in one card, the second under the first with its own counts and note. When the answer is a table or a trend ("cost and questions by month") it still says "This answers one measure; ask … for the other", because two tables in one card don't read well.
- **Typos.** Near-miss spellings are corrected against a vocabulary built from the registry's measure names, the topic phrases, service names, months and weekdays, plus a short hand list. Before, it was a fixed list of 40 words; "latncy", "clarifcation", "helth", "tuesdy" and "cosmso" were missed. Swapped letters count as one edit. Plain question words ("spent", "latest", "total") are never corrected. Every correction is still announced ("Read 'helth' as 'health'"), and none of the suite's other questions picked one up.
- **Silent answers closed:**
  - "cost of foo" says that foo isn't in the cost data and that the answer is total spend.
  - "spend on housing" says that costs aren't split by topic and shows questions in Housing.
  - "cost of the modal" says that costs aren't split by surface.
  - "citations for the justice category" is Justice's citations, not the topic ranking.
- **Tests:** 201 cases (16 new, grouped `combined`, `bestfit`, `typos`), all passing.

Still open: "which topics get the most citations" ranks topics by questions (the card says so) rather than by citations; a topic with no measure ("housing last month") asks which measure rather than offering that topic's choices. Moving the calculations onto the registry (rest of step 3) and the optional model step (step 5) are not started.

## 33. Ask bar audit, step 3 finished: calculations on the registry (23 Oct 2026)

28 of the Ask bar's measures now carry their calculation in their `ASK_METRICS` entry rather than in a branch of code. The entry gives the source (`row` = usage and cost, `ux` = the feed's columns in usage.csv, `conv` = conversations-daily.csv), the numerator and, for a rate, the denominator (a column, columns added together, or turns on days with feed columns), the scale (per 100 or per 1,000), and the wording of the denominator and note. `cat` gives the same rate by topic (category-outcomes-daily.csv) and `byf` by source or question type. One function computes them all: one day's value for charts and the busiest or quietest day, and the period's rate (summed then divided, with the small-sample rule). This covers the counts (spend, generation, fixed and variable cost, turns, conversations, citations, organic first turns) and 20 rates: cited, not found, clarification, error, partial, dislikes, feedback, suggested follow-ups, starter prompts, pop-up share, over 30 s, out of scope, reached a cited answer, later cited after not found, ended after the first turn, follow-up use, conversations over 5 minutes, and the answered, unanswered and flagged shares. Five hand-written branches and the hand-kept list of rates by topic and source are gone. The self-check now also fails an entry with an unknown source, a rate without a denominator, or a unit that doesn't match its calculation (a deliberately broken entry was caught).

Measures whose calculation is genuinely its own stay as branches: cost per turn and per conversation (settled billing days), latency (turn-weighted daily percentiles), click-throughs (matched denominators per surface, measured windows), hours, pages cited and clicked, Reach shares, the busiest weekday, script share, voice, run rate and the top service or model.

Checked by comparing the full text of 231 answers (the 201 test cases and 30 more by day, week, month, topic and source) before and after. 217 are identical. The 14 that changed:
- conversation measures, out-of-scope share and over-30 s now come with a chart, since they now have a daily series;
- the dislikes notes now end "sum then divide", like the other rates;
- the peak feedback day is shown to two decimals, like the feedback rate;
- in "modal share by week", the weeks before the pop-up now show 0.0%. That matches the single-week answer, which was already 0.0% (0 of 869); before, the weekly table showed a dash.

All 201 tests pass.

## 34. Ask bar visual audit, step 1: broken layouts fixed (23 Oct 2026)

Screenshots of 26 kinds of answer (dark and light themes, desktop, and phone width in a true 390 px frame) found five broken things, now fixed:

- **Squeezed cards.** Answers without a chart (busiest weekday, top model, combined questions) squeezed their text into a one-word column, with "Read as" over it. The card now wraps, and "Read as" always takes its own row.
- **Cost change.** "Why did cost go up" when it fell now says so first ("Cost didn't go up in September 2026: it fell 10%"). The waterfall measured from £0, where changes were hairlines; it is now a chart of the changes themselves, either side of zero, with service names on the axis.
- **Click-throughs by device** answered with the total. It now shows the split (mobile 67%, desktop 32%, tablet 2%), as ranked bars with counts.
- **Long tables.** Grouped answers with more than 12 rows (weekly) fold their table under "Show all N weeks as a table". Monthly tables stay open.
- **Phone width.** Axis labels on dense charts no longer collide, ranked labels have more room, and long service names are shortened on narrow charts.

The earlier finding that answers overflow a phone screen was wrong: headless Chrome has a 500 px minimum window, so the screenshots were cropped. In a real 390 px frame the page is exactly 390 px wide.

Next, step 2: the answer card itself (larger headline, a coloured change chip, a one-line "Read as"), and chart rules by answer type (weekly roll-up for long ranges, highlighted busiest bar, event flags, average line, page names in ranked lists).

## 35. Ask bar visual audit, step 2: the answer card and its charts (23 Oct 2026)

- **Headline.** The number is about twice the size (2.1–2.9 rem). The change against the prior window is a chip beside it, green or red by the measure's polarity from the registry (grey where up or down is neither good nor bad); on a phone it sits on its own line. Under it is one plain sentence, with the method ("1,249 of 20,790 scored turns · sum then divide") in smaller type. The question echo is in normal case and quoted, not capitals.
- **Read as.** Folded to one line ("Read as: not-found rate · September 2026 · total ▾") that opens the six controls on click.
- **Actions.** "Open September 2026 detail →" and the like are accent-coloured pill links.
- **Charts.**
  - Daily answers longer than about two months show weeks: counts are summed, and rates are recomputed per week (sum then divide).
  - A dashed reference line shows the period's rate for a rate, or the average per day, week, hour or month for a count, with its value.
  - Confirmed events are flagged on daily, weekly, monthly and trend charts. They are matched by date to the bar's span, with short labels.
  - The answer's own bar or point is highlighted: the busiest hour, the busiest weekday, the peak day, or the week holding the peak day.
  - "Busiest day of the week" now has a 7-bar chart.
- **Ranked lists.** Page names and their section ("Fuel Allowance · Social Welfare"), with the full address on hover, instead of truncated paths. Journeys from one topic no longer repeat it on every row.
- **Money.** Thousands separators everywhere (£1,010, £3,031), on the dashboard and on chart axes too.
- **Phone.** Fixed a cause of answers wider than the screen: stacked cards that also wrapped sized themselves to their widest content. Checked at 390 px in a real frame.
- **Tests.** The regression harness now leaves the echoed question out of the answer text, so "must not contain" checks test the answer, and `--record` no longer depends on the echo. Expectations updated for the deliberate changes (money separators, page names, journey labels); 204 pass.

Next, step 3: the special answers (the "How AskCI is doing" summary, growth, combined questions, "What changed", events).

## 36. Ask bar visual audit, step 3: the special answers (23 Oct 2026)

- **Summary** ("how is AskCI doing", "summary of September", "what happened on 27 January"):
  - Six tiles: turns, conversations, reached a cited answer, not-found rate, click-throughs per 100 cited, and spend. Each has a coloured change chip and a daily sparkline.
  - Then the top three What changed statements and the period's events, on a timeline.
  - The tiles compare against the same window as What changed (for a part month, the same elapsed days of the previous month), so one card never shows two different changes for the same measure.
- **Growth** ("how much has usage grown since April"): the multiple is the headline (4.2×), above the two months compared. The chart is the month-by-month path between them (per day), with events flagged, instead of two bars in unrelated colours.
- **Combined questions** ("questions and conversations in September"): two equal tiles, each with its value, sentence, change chip and sparkline. Single-measure comparisons draw the earlier period muted and the later one in the accent colour.
- **What changed:** each statement leads with its change as a chip, green or red by the measure's polarity (lower is better for failures, latency and cost; higher for cited answers and reached a cited answer), and grey for demand.
- **Events:** a timeline (coloured dot, date, title, two-line detail) under a questions chart with each event flagged where it happened.

## 37. Ask bar visual audit, step 4: final check and colour validation (23 Oct 2026)

All 26 answer types were screenshotted again in the dark theme on desktop, with the summary, trend, cost-change, weekly and combined answers also in the light theme and at 390 px. Colours were checked with the dataviz skill's `validate_palette.js`, run in headless Chrome, over all pairs on the dashboard's own surfaces.

- **Event colours** (used across the dashboard).
  - Before: launch amber and "other" orange were indistinguishable even with full colour vision (ΔE 7, floor 15), and the dark-theme colours were used unchanged on the light theme (contrast under 3:1).
  - Now: four hues from the reference palette, chosen by testing all 70 four-colour sets over every pair (events can sit side by side in any order): model change blue, launch magenta, observed change green, other yellow, and chips violet (no events yet). Each theme has its own shade. Full-colour-vision ΔE is at least 19 in both themes. Colour-blind ΔE is 13 in light and 6.9 in dark; the dark figure is acceptable only with a second cue, and every event line carries a text label.
  - Flag labels are now drawn in the text colour, with the event's colour on the dot, the tint and the line.
- **Good and bad.**
  - Before: the change chips used the dashboard's green and red, which fail for red–green colour blindness (ΔE 2.2).
  - Now: the Ask bar uses a validated pair per theme (#56d364 / #da3633 dark, #0f5323 / #e5534b light; colour-blind ΔE 17 and 14). Chip text stays in the text colour; the hue is on the arrow, tint and border.
  - The trend verdict ("rising") and the cost-change answer now use the same chips, the same colours and the same text colours.
- **Not changed:** the accent-versus-muted highlight of the answer's own bar fails the validator's "chroma floor" check. That check is for categorical palettes; the muted bars are meant to read as grey context.
- **Also:** the cost-change chart's axis is fitted to the changes, so the bars aren't squeezed on a phone. The screenshot harness now switches the dashboard's theme properly rather than setting the attribute alone.

205 regression cases pass. Two trend expectations gained the chip's arrow ("rising ▲ +39%").

## 38. Checks before every deploy (23 Oct 2026)

The publish workflow used to redact `costs.csv` and deploy whatever was pushed, so a wrong-shaped upload went live. In one incident a three-column `usage.csv` uploaded through the GitHub website replaced the full file. Now:

- **`tools/audit_data.py --files-only`** runs in the workflow before deployment. The feed recount needs the feed, which never leaves the analyst's machine, so it is skipped. Every other check runs: a new schema check that each of the 13 files the dashboard reads has the columns it reads, the cross-file identities, the click-through checks and the sanity checks. A schema failure stops the audit with the missing columns named. 83 checks pass in this mode, and 105 with the feed.
- **New join-rate check:** at least 99% of click-throughs must land on a page AskCI cited that month. It is 99.96% now (4,881 of 4,883).
- **The Ask bar regression test** (`tools/test_ask.py`, 205 questions) also runs in the workflow, since web uploads skip the local pre-commit hook. The checkout fetches full history because the test reads its frozen data from an earlier commit.
- **When either check fails, nothing is deployed** and the last good version stays live. The redacted `costs.csv` is still committed back, so an unredacted upload never stays in the repository.
- **The page itself refuses a damaged usage file.** One with some feed columns but not all is refused, with the missing columns named. The minimal form (date, questions, conversations) still loads, with an amber "usage columns: minimal" item in the data-quality strip.

Checked by replacing `usage.csv` with its first 3 columns (the audit fails on the schema; the page loads with the warning) and with its first 20 (the page refuses it).

## 39. Usage › Pages: site traffic against AskCI citations (23 Oct 2026)

A new sub-tab compares, page by page, how often a page is read on citizensinformation.ie (GA4 page views, `ga4/categories-and-views.csv`, already loaded but used only at topic level) with how often AskCI cites it (`citations-monthly.csv`). Both files are monthly, so it uses the months overlapping the range. Only English information pages on the site's page list count, so the home page, site search and topic index pages drop out. 99.8% of citations to CI pages join a page with site views (a new audit check requires 98%).

- **Tiles:**
  - information pages cited: 1,440 of 1,493;
  - citations per 1,000 site views across them (the typical rate): 17.4;
  - busy pages rarely cited: 11 of the 150 most-read, under a quarter of the typical rate;
  - cited pages rarely read: 87 cited 50+ times, over 4× the typical rate.
- **Scatter:** every information page with 200+ views and at least one citation, both axes logarithmic, the typical rate as a dashed line, and the two lists' top 12 in colour. Click a dot to open the page.
- **"Read on the site, rarely cited by AskCI":** the 150 most-read pages, fewest citations per 1,000 views first. Mostly quick-fact pages (when the clocks change, school terms, public holidays): busy on the site and rarely asked about. Others are worth a look for how findable their answer is.
- **"Cited by AskCI, rarely read on the site":** pages cited 50+ times with 200+ views, most citations per 1,000 views first. Returning-to-Ireland pages lead: AskCI brings people to content they rarely reach through the site. The list also shows pages that look out of date, such as "Budget 2023" (224 citations) and "Your rights if you bought in a shop before November 2022", which the content team should review.
- **Wording:** descriptive throughout; the note says a low or high ratio is a place to look, not a verdict. GA4 views are a minimum (cookie consent).

## 40. Answer length, outcome by script, peak hourly load (23 Oct 2026)

Three additions from the data review, all from data already on the analyst's machine; nothing new leaves it.

- **Answer length.** `make_usage.py` writes `AnswerWords`, `AnswerWordsTurns`, `CitedWords` and `CitedWordsTurns` to `usage.csv` (from the redacted feed's Response Words). Usage › Volume has an Answer length card: average words per cited answer and per answer, by the Day, Week or Month view, with events marked.
  - Cited answers grew from about 160 to about 195 words at the 9 March model change, and stayed near 180 to 190 since. After 14 September the all-answers line falls while cited answers lengthen.
  - The Ask bar answers "answer length", "how long are the answers" and "words per answer" (measure `answerlen`, on the registry).
- **Outcome by script.** A new file, `script-outcomes-daily.csv` (Date, Script, Turns, Scored, Cited, NotFound, Clarification), feeds a table under Query script.
  - Over 1 Jan to 22 Oct, questions in other alphabets reach cited answers at least as often as Latin-script ones: Cyrillic 92.1% (316 scored), Arabic 90.9% (186), Latin 88.2%. CJK (37) and Devanagari (3) are below the small-sample rule.
  - It describes the alphabet a question starts in, not its language.
- **Peak hourly load.** Computed in the page from `usage-hours.csv`: a tile in the Hour of day card (216 turns, Budget Day 15:00) and a "Busiest hour each day" chart. The Ask bar answers "peak hourly load" and "most questions in one hour" (`peakload`).
- **Not built: reported turns.** The raw exports hold 6 reported turns in all, between January and June, and none since. That is too few to be a signal; it is worth asking whether the report button still works.
- **Correction to the data review:** the outside-phone-hours share was already shown, as a tile in Usage › Volume's Hour of day card.
- **Tests:** the Ask test fixture moved to commit `90d07ed` (the same data plus the new columns and file); all 205 earlier cases pass on it, plus 5 new (answer length, its trend, peak load). "Are answers getting longer" reads as a trend.
- **Checks:** every existing file regenerated byte-identical; `usage.csv`'s existing 59 columns are identical on every row. The audit has a schema entry for the new file and checks that script turns per day equal usage questions, script cited equals usage cited, and word counts are within answers (89 checks files-only, 111 with the feed). The droplet copies the new file (rebuilt). The Ask test harness skips files missing at its fixture commit.

## 41. Independent review, step 1: periods, prior windows and comparison direction (23 Oct 2026)

An independent review of the Ask bar (`ask review/`, 29 findings, 42 proposed cases) found 31 of 215 new questions gave a wrong number, a reversed direction, or a silently different question. Step 1 fixes the shared plumbing behind the most serious ones.

- **Comparisons point the right way** (findings 1 and 2).
  - Before: "questions in September vs August" showed ▼ 16% when September was 20% higher, and a rise in the not-found rate was coloured as good.
  - Now: the later period is always compared with the earlier one, whichever order they are named in. The sides are shown earlier → later, and the card says it in words: "September 2026 is 20% above August 2026 (+3,563)". The chip follows the measure's polarity, with a neutral colour for volumes. Two-period summaries follow the same rule.
- **Periods end where the measure's data ends** (findings 4, 5 and 24). `lastDayFor(measure)` returns the billing data's last day for cost, the click exports' (capped at the question data's) for click-throughs, and the question data's for everything else. Relative periods ("last week", "last N days", "this month", "to date", the full period) are anchored on it.
  - "Last week" is 16–22 Oct (6,679), not 17–23 Oct with an empty day (5,820), and says how it was read.
  - "Today" says "23 Oct isn't in the question data yet (data to 22 Oct)", not 0.
  - Trends and rolling windows move by a day as a result (usage over 90 days +47%, not +39%).
  - Click-through totals end on 22 Oct (4,869), matching the Click-throughs tab and the figure sent to the Department; they were 4,883 including the partial 23 Oct.
- **One comparison window** (findings 9 and 11). The prior-period chip uses the dashboard's `comparisonWindow`: a whole month against the previous calendar month ("▲ up 20% vs August"), a month in progress against the same elapsed days of the previous month ("vs Sep 1–22"), anything else against the window just before. Before, it used its own "prior 30d", so one card said +22% and the summary said +20% for the same question.
- **Spend notes provisional billing days** ("includes 3 provisional billing days (after 20 Oct)").
- **Topic shares compare in points** (finding 3). The share is a flag on the request, so its prior window computes a share too; before, the prior fell back to a count.
- 9 existing expectations moved with the anchoring (listed in their notes). 10 review cases were added in our wording. 220 pass.

## 42. Independent review, step 2: every word accounted for (23 Oct 2026)

- **Residue check** (finding 12). Before a single-measure answer is drawn, every word of the question must be accounted for. The known vocabulary is built from the registry's measures and synonyms, the parse hooks, topics, services, model families, months, weekdays, event titles, and a list of function and ordinary words.
  - A leftover content word gets a card: "“pensions” isn't a topic or measure the Ask bar knows". It says how the rest of the question reads and offers that reading, matching pages by name, and the topic list.
  - Before, "questions about pensions", "questions in Fingal" and "not found rate in foo" returned the whole-dataset figure.
  - Page names are deliberately not in the vocabulary: questions aren't counted by page, so a page's words used as a subject get the card with the matching pages.
  - Checked against the 128-question audit battery: no false alarms after the vocabulary fixes.
- **Periods** (findings 7, 8, 12):
  - "since / from / after 14 September" is that day to the end of the data. "Cited answer rate since 14 September" gives 82.2% (27,104 of 32,964), not the single day's 92.0%.
  - "week of 5 October" or "w/c 5 Oct" is the Monday-to-Sunday week (8,323).
  - "week 40" is the ISO week.
  - "first half of the year" and "H1/H2" are January–June and July–December.
  - Day/month dates in Irish order ("6/10", "06/10/2026").
  - "the past month" is the last 30 days; "latest week" is the last week.
- **Measures:**
  - "Uncited answer rate" is a new registry measure (0.5% overall, 688 of 131,332), also by topic. "Cited" no longer matches inside "uncited" (finding 14).
  - "Thumbs down" and "thumbs up" read as dislikes and likes.
  - "Social welfare share of questions" and "what share of questions are social welfare" are topic shares (finding 13).
- **Declines** (findings 15–17, 19, 20):
  - correctness ("answered correctly", "accurate") isn't measured, with the nearest measures offered;
  - "most common question" gets the question-text card;
  - "about the budget": subjects beyond topics aren't counted, with Budget Day and the Budget 2027 page offered;
  - "has the model change affected quality": causes aren't established, with the periods either side offered;
  - "top topics in October vs September" gets the ranking-by-change card;
  - "questions in Arabic" gets the languages card.
- 21 review cases added in our wording; 241 pass.

## 43. Independent review, step 3: notes and labels on correct figures (23 Oct 2026)

- **Click-through rate by month** (finding 6) showed a dash for every month although each month computes. The grouped table took its number format from the first bucket, January, which is "not measured" and formats as a dash. It now takes the format from the first bucket with a value. Months on a different basis are named: "Mar'26, Apr'26: the standalone site only (the pop-up is measured from 11 May)".
- **Unvalidated outcome figures** (finding 22). Any outcome-based measure (cited, not found, clarification, partial, uncited, out of scope, reached a cited answer, later cited, dislikes) whose period reaches `CONFIG.outcome_rules_unvalidated_from` (14 Sep 2026) carries a notice: "Outcome figures from 14 Sep are unvalidated: the rules that classify answers haven't been re-checked against the model in use since then." August does not.
- **Partial periods:**
  - Weekly buckets clipped by the range or by the end of the data say so: "w/c 28 Sep (4 days)" (finding 23).
  - Monthly labels end on the measure's last day, "Oct 1–22", from step 1's anchoring (finding 24).
  - The dash note reads "too few to show (small-sample rule) or not measured".
- **Click-through rate** (finding 25) states the days it covers and when each surface is measured: "measured 11 May to 22 Oct (standalone site from 10 Mar, pop-up from 11 May)". The 4,510 used in the rate no longer looks like a different count from the 4,869 total.
- **Page answers** (findings 10, 21, 26):
  - The figure is the page's current address, as the rankings count it: Fuel Allowance 4,291, "and 4 to an older address of the same page". It was 4,295 with the two merged silently.
  - A page name holding a year ("Budget 2027") is no longer read as a period.
  - A period inside a month names the months used, since citations are monthly.
  - A page cited 100+ times with no recorded click-through says the link may redirect.
- 9 review cases added (some merged into existing cases), and 2 Fuel Allowance expectations moved to 4,291. 249 pass.

## 44. Independent review, step 4: coverage and accessibility (23 Oct 2026)

- **Follow-ups that change only the topic or the source.** "not found rate in housing" then "and employment?", or "questions in September" then "and the pop-up?", follow on with the new topic or source. Before, they could not be parsed; only periods carried over.
- **Phrasings:**
  - "how much does a question cost" gives the allocated cost per turn, and "what does a conversation cost" the cost per conversation.
  - "unique visitors", "distinct users" and the like get the no-login notice and conversations, as "how many users" already did. "Site visitors" is still the Reach measure.
  - "average" is no longer echoed into a rate or percentile label ("6.0% not-found rate", not "average not-found rate"); the method line already says how it is computed.
- **The "Read as" measure menu** is grouped: Usage, Quality, Conversations, Click-throughs, Response time, Cost, Cost by service, Cost by model. It was one flat list of 72 entries.
- **Accessibility:**
  - Answer charts are named for screen readers ("Chart of not-found rate by date, 30 values. The Table button lists them.").
  - The ▲ and ▼ arrows are hidden from assistive technology. Chips that carry a judgement start with a hidden "better:" or "worse:".
  - A short live summary is announced instead of the whole card: notices, the headline figure and its sentence.
  - Focus deliberately stays in the question box, so a follow-up can be typed straight away. The reviewer suggested moving focus to the answer; the live summary gives the same information without taking the cursor away.
- 6 review cases added; one expectation moved ("average response time" is labelled as the p50 it is). 255 pass.

**The review's 29 findings, after steps 1–4:**
- Fixed: findings 1–17, 19–29. Finding 3 (topic shares) is fixed at the cause, though it did not reproduce in Chrome.
- Finding 18, "not found rate for the pop-up vs the standalone site" answering the pop-up only, is still open: the two-tile answer exists for topics but not yet for sources.
- The reviewer's recommendations on the language-model step and on recording misses are adopted as the plan of record: no model step yet; misses to be counted as structured events, with question text only by opt-in.

## 45. Independent review: the last finding, and the review on record (23 Oct 2026)

- **Finding 18.** "not found rate for the pop-up vs the standalone site" answered for the pop-up only. Naming both sources now gives two tiles, as two topics already did: not-found Modal 6.3%, Web 5.3%; cited Web 91.3%, Modal 87.0%. "Modal vs web …" phrasing without a measure-for-source reading still gives the Modal share, as before.
- All 29 findings of the review are now addressed.
- **On record:**
  - The reviewer's 42 cases are in `tests/review-2026-10-23/` as delivered. Adapted versions are in `tests/ask_cases.json` (group `review`).
  - Their browser-free runner is `tools/test_ask_node.js` (see `tests/README.md`).
  - The review report itself (PDF) is kept local, not in this public repository (`ask review/` is git-ignored).
- 256 cases pass.

## 46. Ask bar: topics by citations, topic-specific choices, "What can I ask?" (23 Oct 2026)

- **Topics ranked by citations.** "which topics get the most citations" and "most cited topic" rank by citations from `categories-daily.csv` (Social Welfare 50,865, 36.9% of citations). Before, they ranked by questions, or by cited-answer rate. "top topics by cited answer rate" still ranks by the rate, and topics can also be ranked by uncited rate.
- **A topic with no measure** ("housing last month", or just "social welfare") gets "Which measure for Housing?" with that topic's choices: questions, not-found rate, cited answer rate, citations and share of questions, for the period asked.
- **"What can I ask?"** (a chip under the box, or "help", "what can I ask", "examples"). The card is built from the registry, so a new measure appears without editing it. It has:
  - every measure grouped as in the Read-as menu, each a chip that asks it for the latest full month, with the measure's definition on hover;
  - costs by service or model;
  - period phrasings;
  - narrowing by topic or source;
  - shapes: by week or month, trends, comparisons, combined questions, rankings, what changed, the summary;
  - definitions;
  - what is not in the data.
- **Every chip was asked through the page before release**, which found 8 that parsed wrongly. Each was a bug a person could hit too, and all are fixed:
  - "response time p90" and "p99" answered with the p50 ("response time" outranked "p90");
  - "generation cost" answered with cost per turn;
  - "organic first turns" was read as the new-topics filter;
  - "out-of-scope" with hyphens wasn't recognised;
  - "modal share of conversations" and "conversations over 5 minutes" answered with conversations;
  - "different pages cited" and "pages clicked through to" gave a ranking (the card now asks them as "how many …").
- **"Also read as" is tighter:** no alternative whose words overlap the chosen reading, and none when the question names the measure outright.
- 13 cases added; 269 pass.

## 47. Ask bar: suggestions while typing, with a preview of the reading (23 Oct 2026)

Built after a proposal and a critique of it; the critique's changes are in.

- **Preview line.** As you type, one line under the box says how the question will be read before it is asked:
  - "Reads as: not-found rate · Housing · the full period";
  - "Compares: …", "Ranks: topics · …";
  - "Answers with: The question text isn't available here" for a decline;
  - "“pensions” isn't a topic or measure the Ask bar knows" for an unknown word;
  - corrections in brackets: "(Read “helth” as “health”)".

  A word still being typed is left out, marked "…", rather than warned about. The preview uses the same parser, unknown-word check and declines as the answer. It never changes what a follow-up inherits.
- **Suggestions come only from tested questions:**
  - the help card's questions;
  - eight topic templates ("not found rate in {topic} last month", "{topic} questions by month" …), each naming the test case that backs its shape.

  `tools/test_ask.py` asks every suggestion through the page on every run: none may give a "not understood" card, and a template without its backing case fails the run. A deliberately broken template was caught both ways. The order is hand-ranked: there is no record of real questions yet.
- **Matching:** every finished word must appear in the suggestion, and the word being typed as the start of one of its words. A misspelling is retried as the Ask bar would correct it. Up to 6 suggestions, 4 on a phone.
- **Keyboard and screen readers.** It is a combobox: `role="combobox"`, `aria-expanded`, `aria-controls`, `aria-activedescendant` on the box, and a listbox of options.
  - ↑/↓ move, Enter asks the highlighted suggestion (or what is typed), Esc closes. Tab is left alone so keyboard users can move on.
  - The preview and the number of suggestions are announced.
  - The focus ring is on the whole bar, not inside it.
- **Recent.** An empty, focused box shows the last five questions asked in this browser, with Clear (offices share machines), and "What can I ask?". They are stored in this browser's local storage only, never in the page address or anywhere central.
- **Placeholder.** One fixed example ("e.g. “not found rate in housing last month”"). No rotating text, per WCAG 2.2.2.
- **Phone width.** The whole dashboard was measured in a true 390 px frame. A long value in the data-quality strip widened the page to 417 px; strip values now wrap on phones and the page is 390 px. The main tab row already scrolls within itself. The date-range toolbar fits.
- **Tests:** 11 typing cases (preview, unknown word, decline, correction, ranking, partial word, ↓ highlight, ↓ + Enter asks, Esc closes, Recent and help in an empty box). 280 pass.

## 48. Plan of record: reports, then diagnosing system changes (23 Oct 2026)

Agreed after two rounds of proposal and critique. The aim of the second half is to turn what the data shows *changed* into what to *do*: which rule, model, prompt, page or chip to adjust.

**What the 14 September change looks like** (14 Aug–13 Sep against 14 Sep–13 Oct, from the published files):
- Cited answer rate 92.3% → 81.7%; not found 2.9% → 8.3%; clarification 4.7% → 9.8%.
- Partial answers 14.1% → 26.4% of cited answers; out of scope 0.9% → 2.3% of questions.
- Uncited 0.07% → 0.15% (small).
- Pages cited per cited answer 1.84 → 1.72; words per cited answer 180 → 189.
- **Topic mix explains none of it.** Among topic-attributed questions the cited rate falls 95.2% → 89.3%; reweighted to the before period's topic mix, 89.1%.
  - Failed answers usually carry no topic, so the "unknown" topic grew 571 → 2,100 scored turns.
  - Any mix adjustment must leave "unknown" out, or it understates the change: done wrongly, it claimed a third of the fall was mix.
- **Dislikes are not evidence either way.** Per 1,000 cited answers they fell 2.4 → 1.1, but that describes the answers still cited. On other answers they went 1 → 6 in absolute numbers.
- **Generation spend since 14 Sep:** GPT-5.4 £378, GPT-5.4 mini £63. Without token quantities (the cost export has none), the turn split between them is unknown, so a routing change cannot be told from a model change.
- **Suspects, none yet ruled out:** the outcome rules misreading the new model's wording; the model itself; the system prompt as read by a more literal model; and routing between 5.4 and 5.4 mini.

**Phase A: reports** (agreed in §47's discussion):
1. **Copy with definition** on tiles and Ask answers: a sentence with its caveats, Markdown, TSV tables and a light-theme chart image with the title and period drawn on. Formatted and plain text go on the clipboard together. A re-ask link (the hash is untrusted input: escaped and tested).
   - Footer: data-to date, config and outcome-rules versions, the unvalidated flag, minimums, the page commit (stamped at deploy) and the data commit.
   - Alongside it, management-question cases with their caveat or decline wording pinned, tagged `"lists": ["monthly"]`: accurate? pressure off the phones? vs last year? twice the volume (Scenario planner)?
2. **Reports as question lists.**
   - Each item stores the question and its parsed reading. A re-run that reads it differently says so on the item.
   - Period tokens (last full month, month to date, last 7 days of data, since January, since the pop-up launch, Budget Day, a fixed range), with pinned items and comparisons re-run on the same token.
   - "Run for <month>"; print/PDF, Markdown and formatted copy.
   - Lists are kept in the page address and the browser, and built from case tags.
3. **Fact sheet** from cases tagged `facts`, each figure with its caveat beside it, written to `reports/facts-<date>.md` at each data refresh.
4. **CSV export** with the conversation, outcome and click-through columns, and the footer.

**Phase B: diagnosing changes**
0. **Hand-labelled sample: first, because it settles 14 September directly.**
   - 50 answers before and 50 after, stratified by outcome, labelled blind (no date, no model, no rule label).
   - `tools/make_label_sample.py` builds the sheet from the raw feeds on the analyst's machine (git-ignored; text never leaves it). `tools/score_labels.py` gives agreement per outcome class, before and after.
   - A small monthly re-check afterwards.
1. **Rule hits.** `redact_feed.py` records which outcome rule matched each answer (an id, no text), and `make_usage.py` writes daily counts per rule. The dashboard shows the rule mix by day and by model era, with a **drift flag** when the mix shifts (the "style fingerprint": hedging and refusal phrases per answer, answer length). This answers "is the new not-found one phrase pattern?".
2. **Model-era scorecard.** One row per era, taken from confirmed model events until version columns exist. Columns:
   - cited, partial, not found, clarification, uncited, error;
   - p50/p99 response time, answer length, pages per answer;
   - cost per turn, cached-input share, generation spend by family;
   - dislikes, click-throughs per 100 cited, turns per conversation, ended after the first question.
3. **Profile matching, not verdicts.** After each outcome, the distribution of what happens next: rephrased, new topic, ended, gap, clicked.
   - A relabelled answer should look like the class it really belongs to. If after-14-Sep "not found" answers are followed like before-14-Sep cited answers, the label is wrong.
   - No single behaviour is called satisfied or abandoned.
4. **Content lists:**
   - partial share by cited page (pages that exist but lack what is asked);
   - pages lost and gained at a change;
   - citations to old or off-list addresses (Budget 2023, moved pages);
   - old content cited, from `site-pages.csv` LastMod;
   - pages cited often and never clicked, split into redirect and complete-answer cases.
5. **Chips and starter prompts:** each one's own outcome, what followed, and the ended-there rate. Clarification loops.
6. **Incident candidates** from error spikes and cost meters together (a search or container meter jumping on an error day names the component).
7. **Change reports.** For a confirmed event or a version change: matched windows with the weekday mix controlled, the topic mix standardised (excluding "unknown"), confidence intervals, guardrail measures, and the rule-drift check.
   - First run on **prompt caching** (4% cached-input share), which cannot affect answer quality, to validate the machinery before it is needed for anything contested.

**Phase C: one request to the AskCI team**
- **Per-turn columns** (no personal data):
  - model actually used (5.4 or 5.4 mini, for routing);
  - prompt version;
  - retrieval config (index version, top-k, chunking);
  - chip set version;
  - UI build;
  - referring page for pop-up questions.
- **Token quantities** in the cost export.
- **A fixed question set** (about 100 staff-written questions, each with the page that should be cited and the expected outcome) run before every model, prompt or index change.
- **Two experiments with known cost:** route everything to 5.4 for a week, and prompt caching.

**Phase D: needs governance sign-off** (offline text processing; only aggregates leave the machine):
- **Repair mining:** a not-found answer followed by a rephrase that gets cited gives synonym pairs and second-attempt pages. Only pairs seen 10+ times, with names, numbers and capitalised words stripped.
- **Not-found themes against the page list:** a theme with no page is a content gap, for the CI content team; a theme whose page exists is a retrieval failure, for the AskCI team.

**Amendments to §48 after review** (23 Oct 2026):
- **Labelling design** (Phase B step 0, now built):
  - The sample is stratified by the rule-assigned class *within each period*: 20 cited, 10 partial, 10 not found and 10 clarification before, and the same after. Fifty random answers after 14 Sep would hold about four not-found answers.
  - Results are weighted back to each period's real mix. Labelling is blind (no date, model or rule class), with a "can't tell" option.
  - A second labeller gets 20 of the items, for agreement.
  - `tools/make_label_sample.py` reuses `redact_feed.classify`, so the sample is drawn by exactly the rules being measured. It writes `label_sheet.csv`, `label_sheet_second.csv`, `key.csv` and `README.txt` under `exports/` (now git-ignored as a whole), and never prints text.
  - `tools/score_labels.py` prints a confusion matrix, each rule class's agreement with a 95% range, an estimated catch rate (within the sampled classes), weighted overall agreement, the figure that settles 14 Sep ("rule 'not found' answers a reader says did answer"), and inter-labeller agreement with Cohen's kappa. Its last line is the `CONFIG.outcome_rules_measured` entry.
  - The first sample is drawn: 100 answers from 14 Aug–13 Sep and 14 Sep–13 Oct (29 Sep is missing from the raw exports on hand). The scorer was checked on synthetic labels.
- **Data-quality strip:** once `CONFIG.outcome_rules_measured` is set it reads "agreement X% on N hand-labelled answers, <date>", with the before, after and not-found figures in its tooltip, instead of "unvalidated".
- **Categories tab:** a note above the outcome-by-topic table explains that failed answers usually have no topic and sit in Unknown, so topic failure rates are lower bounds and period comparisons by topic leave Unknown out.
- **Phase C order:** the version columns must land before the two experiments, or a week on GPT-5.4 can't be told from any other week. Caching first. Add **per-turn token counts** to the request: they give exact cost per turn by model, which the cost export can only approximate.
- **Recorded so it isn't re-run:** dislikes on answers that weren't cited went 1 → 6 across 14 Sep; too few to mean anything.

**Parked (23 Oct 2026): anything that needs other people's time.** No team scoring or input is available for now. On hold:
- the hand-labelling (Phase B step 0) and the second labeller; the tools and the drawn sample stay ready;
- the request to the AskCI team (Phase C): version columns, token counts per turn, the caching and model experiments.

The strip keeps saying "unvalidated" (`CONFIG.outcome_rules_measured` stays null). Work continues on what one analyst can do from the data on hand: Phase A, and the parts of Phase B that need neither labels nor new columns. Those findings about the 14 Sep change say "the outcome rules are unvalidated" next to them.

## 49. Reports, Phase A step 1: copy with definition (23 Oct 2026)

A figure pasted into an email or a report now takes its definition, caveats and provenance along with it.

- **Ask answers** get a copy bar under the card, built from the answer as drawn, so every kind of card copies the same way:
  - **Copy answer** puts two formats on the clipboard together: formatted HTML (for Word, Outlook and Docs) and Markdown as plain text. It holds:
    - the question;
    - the figure and its sentence, including the change against the comparison period;
    - the table (chart values, grouped or top-N rows);
    - the measure's registry definition;
    - every notice above the answer, as a caveat;
    - for click-throughs, the minimums caveat when the answer doesn't already say it;
    - a re-ask link;
    - the footer.
  - A declined question copies its explanation and the questions it suggests instead.
  - **Copy chart image:** the chart is redrawn in the light theme whatever the page theme, with the question, its sentence and the footer, as a PNG. If the browser blocks image copying, the PNG is downloaded instead.
  - **Copy table** copies tab-separated text for a spreadsheet; **Copy link** copies the re-ask link.
- **Tiles:** the history window that opens from a tile has **Copy with definition**, with these parts:
  - the tile's figure for the selected range, its sub-line and its change;
  - the catalogue definition;
  - the unvalidated caveat on outcome tiles and the minimums caveat on click-through tiles;
  - a link to the same dashboard view;
  - the footer.

  It also has **Copy chart image**.
- **Re-ask link:** `#ask=<question>`. The hash is untrusted. It only ever becomes the text of the question box: control characters are removed and it is cut to 200 characters. The test suite opens a link whose question is markup on every run.
- **Footer:**
  - "Source: AskCI dashboard";
  - the usage-data and billing end dates, with years;
  - the config version;
  - the outcome rules version, marked "unvalidated from 14 Sep 2026" when the figure depends on the outcome rules and they haven't been measured;
  - the click-through minimums note where relevant;
  - the page commit and the data commit. These come from a new deploy step that stamps `<meta name="askci-build">` after the tests, using the last commit to `index.html` and the last commit to the data files. A local copy says "local".
- **Management questions** are now cases tagged `"lists": ["monthly"]`, with the decline wording pinned:
  - "Are AskCI's answers accurate?" says correctness isn't measured.
  - "Has AskCI taken pressure off the phones?" is a new decline: there is no phone or centre data.
  - "How does this compare with last year?" says there isn't enough history.
  - "What if volume doubled?" is a new card that points to the Scenario planner, which is a model rather than data.

  Three copy cases pin the definition, the caveats and the footer.
