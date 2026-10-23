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

## 50. Reports, Phase A step 2: question lists (23 Oct 2026)

A question list is a report you can run again. It sits under **Lists** in the toolbar; questions are added with **Add to list** under any answer.

- **What an item stores:**
  - the question as asked;
  - the reading it was saved with: measure, topic, filter, shape (single, by month, by week, trend) and aggregate;
  - the period it was asked for;
  - a period token.

  Comparisons, two-measure answers, declines and lists of top items keep no reading. They run as written.
- **Period tokens:** last full month, month to date, last 7 days of data, since January, since the pop-up launch, Budget Day, full period, or "as asked (pinned)". A saved item gets the token that matches how it was asked: "last month" becomes last full month; an explicit range stays pinned.
- **Run for <month>** moves every item to that month except the pinned ones.
- **Comparisons:** a single figure in a report gets the period before it, by the dashboard's rule (a whole month against the previous month, anything else against the window just before), with the change in points or per cent. The Ask bar leaves ratios without a change; a report doesn't.
- **Re-reading:** each run asks the saved question again out of sight. If the Ask bar now reads it differently, the item says so ("now reads … as …; this report keeps the reading it was saved with").
- **The report** is drawn as paper in either theme:
  - each item has its light-theme chart image, figure and sentence, a table (left out when the chart has more than 14 points), definition, caveats and re-ask link;
  - one footer covers the whole report, with the caveats that apply to any item;
  - **Copy report** gives HTML (images included) and Markdown; **Markdown** downloads a `.md` file; **Print or save as PDF** prints it.
- **Where lists live:**
  - in the browser (`askci-qlists`);
  - in a link, `#qlist=` followed by the base64url JSON of the list. A link is untrusted: names and questions lose control characters and angle brackets, readings must name a known measure, and tokens, periods and shapes must come from fixed sets. At most 30 items.
  - a link opens as "<name> (shared)" and never overwrites the viewer's own lists.
- **Built-in lists** come from the case tags in `tests/ask_cases.json`: `"lists": ["monthly"]` is "Monthly management questions". They are read-only; "Make an editable copy" copies one.
- **How it runs:** the answers are produced by the Ask bar itself. The answer area is swapped for a hidden one, the reading is rendered, its copy payload and light chart are captured, and the visible answer, its chart and the follow-up memory are restored. A report can't drift from the Ask bar's own answer.
- **Tests:** every run opens a list link carrying markup and an unknown measure (it must be cleaned) and runs it for September 2026 (it must show "86.5%" and "August 2026: 91.9% (−5.4 pts)").

## 51. Reports, Phase A step 3: the fact sheet (23 Oct 2026)

- **What it is:** fifteen figures for the last full month, one line each:
  - turns, conversations and turns per day;
  - the cited, not-found and clarification rates;
  - conversations that reached a cited answer;
  - click-throughs per 100 cited answers;
  - response time p50;
  - the pop-up share and the out-of-hours share;
  - dislikes per 1,000 cited answers;
  - spend and generation cost per turn;
  - the top topics.

  Each figure is followed by the month before and the change, with its caveats under it. The definitions are gathered at the end, and the footer gives the data, config and outcome-rule versions and the page and data commits.
- **Where it comes from:** the questions tagged `"lists": ["facts"]` in `tests/ask_cases.json`, answered by the page itself through the question-list engine (§50). The sheet and the Ask bar can't disagree, and every figure's wording is pinned by a case.
- **`tools/make_facts.py`** serves the repo, opens the page in headless Chrome and writes `reports/facts-YYYY-MM.md`. For the default month it also writes `reports/facts-latest.md`; `--month YYYY-MM` writes any month, and `--stdout` prints. It stamps the page and data commits the way the deploy does, and fails on any page error.
- **The deploy runs it** after the commit stamp, so the published site carries the sheet for the data it serves. The Lists panel links `reports/facts-latest.md`. `reports/` is git-ignored: any month can be rebuilt from the repo's data.
- **"Fact sheet" is also a built-in list** in the Lists panel, so it can be run as a full report with charts for any month. "Run for" a month now also moves a question that says "last month" and is kept as written (top topics).
- **Fixed on the way:** "dislikes per 1,000 cited answers" read as the cited answer rate. The comma in 1,000 had become a space, so the longer "cited answer" match won. The measure now matches the whole phrase, and a case pins it.

## 52. Reports, Phase A step 4: the CSV export (23 Oct 2026)

**Export CSV** (the ⋯ menu and ⌘K) now writes the selected range with one row per day, week or month, following the View. Phase A is complete.

- **Columns:**
  - the period and its From, To and Days, so a part week or month is visible;
  - turns and conversations;
  - every outcome count (scored, cited, not found, clarification, error, out of scope, uncited, partial) and the cited, not-found, clarification and partial rates;
  - dislikes on cited answers and dislikes per 1,000 cited;
  - mature conversations, reached a cited answer (count and %), and not-found and clarification answers with how many later got a cited answer (count and %);
  - click-throughs by surface and in total, and per 100 cited answers;
  - response time p50;
  - billed, generation, fixed and variable cost, generation and allocated cost per turn, and the billing status.
- **Rules:**
  - counts are summed per row and every rate is computed from those sums;
  - a rate below the small-sample rule is left blank, never printed;
  - the click-through rate is blank before both surfaces are measured;
  - cost per turn uses settled billing days with turns only.
- **Notes after the table**, a blank row and then "Notes":
  - the rows and the sum-then-divide rule;
  - the small-sample thresholds;
  - the outcome rules version and the unvalidated flag;
  - the mature-conversation and later-cited definitions;
  - click-throughs as minimums, with the tracking dates;
  - a line when the last row runs past the usage data;
  - response time and cost-per-turn rules;
  - the footer, as on every copy.
- **Format:** the file starts with a UTF-8 BOM and uses CRLF line ends, so Excel opens "£" and "’" correctly. It is named `askci-<view>-<from>-to-<to>.csv`.
- **The figures match the fact sheet:** September 2026 reads 86.5% cited, 6.0% not found, 7.4% clarification, 88.0% reached a cited answer, 5.5 click-throughs per 100 cited answers, 11.8s and £1,009.80. The test run checks that row and the notes on every run.

## 53. Plan of record: diagnosing 14 September from the data on hand (23 Oct 2026)

Replaces the Phase B order in §48. No team input, no new data. Structural facts from a one-off backend log extract are kept in a local, git-ignored note; the conclusion that matters here is that the second, smaller model does preprocessing only. **Routing between the two models is ruled out as a suspect.** Three suspects remain:
- the outcome rules misreading the new wording;
- the model;
- the prompt.

Prompts can change without a deploy.

The order:

0. **Hand-labelled sample.** The tools and the drawn sample are ready (§48 amendments); the analyst is the labeller, on the machine where the raw feed lives. It is the only step that gives ground truth. It runs whenever the hour can be spared; nothing below waits for it.
1. **Rule IDs and the wording fingerprint.** `redact_feed.py` records which outcome rule fired on each answer (an ID, no text) and a few wording counts (length, lists, hedges, apologies, signposting, questions back). `make_usage.py` writes daily counts per rule and per outcome. The dashboard shows the rule mix by day with a drift flag.
   - It tells whether the post-14 Sep not-found answers are one new phrase pattern or spread across the old ones.
   - A wording shift on a date with no model change in the cost meters is the trace of a prompt change. The data can show **that** a prompt changed, not **what** changed.
2. **Same question before and after.** Fixed starter prompts, plus questions typed identically on both sides (matched locally, counts only).
   - Reported as counts with intervals. About 700 per side detects a 4-point drop, not a 2-point one.
   - First check that the chip texts themselves didn't change around 14 Sep: they load from a database.
   - This confirms a system change; it cannot separate model from rules.
3. **What people do next** after each kind of answer: rephrase, new topic, ended, gap. If post-14 Sep "not found" answers are followed the way cited answers used to be, the label is suspect. This is evidence, not a substitute for step 0.
4. **Change report, calibrated on the March model change** (a known answer) before it is run on 14 Sep. It uses matched windows, the weekday mix, the topic mix with Unknown left out, intervals, guardrail measures and the rule-drift check.
5. **Era scorecard.** One row per model or prompt era, labelled as such: outcomes, response time, length, pages per answer, cost per turn, dislikes, click-throughs, conversation length.
6. **Follow-ups.** Not-found rates for follow-ups against first turns, before and after, and topic drift between turns.
7. **Content lists:**
   - partial share by page;
   - pages lost or gained at 14 Sep;
   - old or off-list addresses;
   - cited and never clicked;
   - index lag from LastMod to first citation, with Budget 2027 as the test case.
8. **Chip scorecards** and how much traffic a starter-prompt cache would cover.
9. **Incident candidates:** error spikes against cost meters.
10. **Safety counts** in `redact_feed.py`, counts only: identifiers typed in, injection patterns, off-topic themes.
11. **Log parser** for any future one-off backend extract, counts only. It matters only if an extract appears.

Correctness against the page and groundedness stay parked: they need people beyond the analyst.

## 54. Diagnosis step 1: rule IDs, the wording fingerprint, and what they show (23 Oct 2026)

**Built:**
- **`redact_feed.py`** records, per turn, the ID of the phrase that decided the outcome:
  - not-found and clarification IDs, such as `nf.couldnt_find` and `cl.more_detail`;
  - `cited.partial.<phrase>` for a cited answer that also contains a not-found phrase;
  - `oos.flagged`, `err.empty` and `uncited`.

  It also records six wording counts read from the answer before it is dropped: list lines, hedges, apologies, signposting verbs, question marks and links (`STYLE_VERSION`).
  - The patterns are the same alternatives, joined in the same order, so the outcomes are unchanged: all 145,098 raw rows classify identically, and the rules version stays 2026.10.08-1.
- **`make_usage.py`** writes `outcome-rules-daily.csv` (Date, Rule, Turns) and `answer-style-daily.csv` (sums per day and outcome). The eleven existing files rebuilt byte-identical.
- **The audit** checks that every turn carries one rule, that each rule family matches its `usage.csv` outcome every day, and that the style counts add up.
- **Usage › Answer wording**, a new sub-tab:
  - deciding phrases per 1,000 turns, by week;
  - a drift chart: total variation distance of the not-found, clarification and partial phrase mix against the 4 weeks before. It flags at 20% and judges only weeks with 100+ phrases;
  - flagged weeks, each checked against confirmed model changes. Blue means a model change within a week, or the weeks settling after one; amber means none, so a candidate prompt or configuration change;
  - the fingerprint per outcome against the comparison window;
  - every phrase per 1,000 turns against the comparison window.

**What it shows:**
- **No amber week since the volume became readable in March.** Every wording shift lines up with a confirmed model change: 9 Mar, 1 Jul and 14 Sep. Within this data there is no sign of a prompt change without a model change.
- **Each model change brought its own way of saying "not found":**
  - GPT 5 (to 29 Jun) said "couldn't find";
  - chat-latest (1 Jul to 13 Sep) said "could not find", mostly *inside cited answers*;
  - 5.4 (from 14 Sep) says "couldn't find" again, both alone and inside cited answers.
- **The 14 Sep baseline was itself unusual.** By model era:

  | Era | Cited | Not found | Clarification | Partial (of cited) | Cited, not partial |
  |---|---|---|---|---|---|
  | GPT 5 (10 Mar–29 Jun) | 87.2% | 7.7% | 3.9% | 2.7% | 84.8% |
  | chat-latest (1 Jul–13 Sep) | 92.0% | 3.2% | 4.7% | 14.1% | 79.0% |
  | 5.4 (14 Sep–22 Oct) | 82.2% | 8.2% | 9.4% | 26.2% | 60.6% |

  chat-latest turned many would-be not-found replies into cited answers that say they "could not find" something. 5.4's not-found rate is back near GPT 5's. What is new with 5.4 is twice the clarification (with two phrases barely seen before, "what you mean" and "more detail") and nearly twice the partial share. "Cited, not partial" has fallen era by era.
- **Wording, 14 Aug–13 Sep against 14 Sep–13 Oct:**
  - clarification answers went from 76 to 43 words, with fewer lists;
  - cited answers carry fewer hedges (2.2 to 1.5 per answer) and more inline links (5.0 to 7.3);
  - not-found answers signpost more (2.0 to 2.8 contact or visit verbs).

**What it cannot say.** Whether a "partial" or "not found" label is right. A cited answer that says "I couldn't find the exact figure, but…" may be a good answer or a real gap. The hand-labelled sample (step 0) settles that. The headline comparison for 14 Sep should no longer be the 92.3% of the chat-latest era alone: GPT 5's 87.2% belongs beside it.

## 55. Diagnosis step 2: the same question before and after 14 September (23 Oct 2026)

**Built:** `tools/same_question.py` runs locally on the raw feed and prints only counts and rates. It covers:
- starter prompts (chip texts are configuration);
- first-turn typed questions repeated in both windows, matched on the normalised text;
- 95% Wilson intervals for each rate and Newcombe intervals for each difference;
- a question-by-question view, so a few common questions can't carry the result;
- first, a check that the fixed input is fixed: each chip by week, and any first-turn text asked 30+ times in a week that isn't a configured chip.

**The fixed input wasn't fixed.** The chip set changed three times, all inferred from the feed:
- **15–16 Jul:** Back to School, HAP limits and passport renewal added.
- **11 Sep:** low pay, maternity benefit and auto-enrolment removed. That was three days before the model change; their last use was 10 Sep.
- **14 Oct:** "How do I apply for the Household Benefits Package" replaced Back to School.

All three are now candidate `chips` events in `events.json`. The new chip is added to `redact_feed.STARTER_PROMPTS`, and the data was rebuilt:
- `usage.csv` starter and organic first turns, `category-outcomes-daily.csv` organic first turns and `starter-prompts-monthly.csv` changed;
- every other file is byte-identical;
- the audit passes.

**Result, 14 Aug–13 Sep against 14 Sep–13 Oct.** Only three chips span both windows (Back to School, passport, HAP), with 575 and 777 scored first turns:

| Rate | Before | After | Change (95%) |
|---|---|---|---|
| cited (any) | 99.8% | 99.6% | −0.2 pts (−1.0 to +0.6) |
| cited, not partial | 99.1% | 87.1% | **−12.0 pts (−14.6 to −9.5)** |
| partial | 0.7% | 12.5% | +11.8 pts |
| not found | 0.0% | 0.4% | +0.4 pts |

- On fixed questions the new model still cites a page every time. What changed is that it adds a "couldn't find" phrase to some answers.
- That is almost all one chip: HAP limits went from 97% to 67% not partial. Back to School and passport are unchanged.
- HAP limits is a table of rates. That points at the rates-in-tables question (critique #3), and makes "partial" on rate questions the first thing to read in the hand-labelled sample.
- **The not-found rise doesn't appear on chip questions.** These are well-covered topics, so it lives in typed questions.
- **Typed repeats are too rare to say anything.** Only 21 distinct questions were asked twice or more in both windows (54 and 89 turns), and every interval is about ±14 points.

**What it proves:** a system change on fixed questions, not a change in the question mix. As expected, it can't separate the model from the outcome rules. For HAP it narrows the question to one testable thing: whether the "couldn't find" in a HAP answer marks a real gap in the rates or a cautious phrase on a complete answer.

## 56. Diagnosis step 3: what people do next after each kind of answer (23 Oct 2026)

**Built:** `tools/next_step.py` runs locally on the raw feed. For every answer in a finished conversation (no turn in the last 24 hours of the data), by model era and answer class (cited not partial · partial · not found · clarification), it counts what came next: the conversation ended; the next question was typed, a chip or a new topic; it came within a minute; it was a rephrase (a typed question sharing at least half its words with this one, matched on the raw text, count only); the next answer was cited; this answer was disliked. Each share carries a 95% Wilson interval, and a last block gives the distance between each 5.4 class and every earlier class (half the summed absolute difference across the seven shares; 0 is identical). It writes `answer-next-daily.csv` (Date, Class, counts), which the audit checks (known classes, Ended within Answers, every next count within Answers − Ended, answers per day within usage.Questions) and **Usage › Answer wording** shows as a card, "What people do next": the range against the comparison window, with a one-line verdict for not-found and partial answers on which earlier profile they resemble.

**The test.** If, after 14 Sep, "not found" answers were followed the way cited answers used to be, the label would be suspect: people would be moving on satisfied from answers the rules call failures. If they are followed as not-found answers always were, the rise is real.

**Result, by model era (finished conversations, shares of answers):**

| After a … answer | Era | Answers | Ended | Rephrased | Typed next | Chip next | Within 1 min | Next cited |
|---|---|---|---|---|---|---|---|---|
| cited, not partial | GPT 5 | 23,624 | 41.7% | 1.2% | 26.1% | 29.2% | 32.9% | 52.4% |
| | chat-latest | 34,121 | 51.5% | 1.3% | 21.4% | 24.4% | 29.1% | 45.5% |
| | 5.4 | 19,411 | 53.5% | 1.7% | 21.0% | 21.6% | 28.2% | 40.6% |
| not found | GPT 5 | 2,294 | 72.8% | 3.0% | 21.0% | 3.1% | 17.7% | 16.3% |
| | chat-latest | 1,376 | 75.9% | 3.1% | 19.9% | 1.5% | 16.2% | 18.3% |
| | 5.4 | 2,628 | 80.3% | 2.5% | 15.4% | 0.3% | 12.1% | 12.9% |
| partial | chat-latest | 5,593 | 60.8% | 2.0% | 20.0% | 16.3% | 24.8% | 35.2% |
| | 5.4 | 6,881 | 58.9% | 1.9% | 20.8% | 17.7% | 24.6% | 34.6% |
| clarification | chat-latest | 2,029 | 25.1% | 4.4% | 67.0% | 0.7% | 58.7% | 60.8% |
| | 5.4 | 3,049 | 22.7% | 5.3% | 63.5% | 1.5% | 67.1% | 47.6% |

Intervals are about ±1 point on the cited rows and ±2 on the others.

- **The not-found rise is real.** 5.4's not-found answers are followed like not-found answers always were: distance 0.11 to chat-latest's and 0.13 to GPT 5's, against 0.56 to chat-latest's cited answers. Four in five conversations end on them, almost nobody clicks a chip after one, and the few who ask again are cited less often than before. They are, if anything, a slightly harder dead end than the old ones.
- **"Partial" behaves like a cited answer, not a not-found one.** In every era, partial answers sit between the two profiles but nearer cited (5.4: 0.16 to cited, 0.30 to not found; 0.03 from chat-latest's partial). People end on them a little more often than on a clean cited answer and click chips a little less. That fits a mostly complete answer with a cautious phrase better than a real gap, and keeps the HAP question from step 2 open for the hand-labelled sample rather than closing it either way.
- **Clarification answers changed most in how they are followed.** After 5.4 asks a clarifying question, people reply within a minute far more often (67% against 59%) but the next answer is cited less often (48% against 61%), and 12% go to a new topic (against 7%). The shorter clarifications (43 words, §54) draw a quick reply that less often gets an answer.
- **Rephrasing is rare after every class** (1–5%), so it is not a useful signal on its own. The rule (half the words of three or more letters in common) is coarse; it is kept because it needs no text to leave the machine.
- **Dislikes are too rare to use** (0.0–0.4% of answers in every cell).

**What it settles and what it doesn't.** Step 1 showed the wording changed with the model; step 2 showed the same questions get more partial answers; this step shows the not-found label is behaving as a real failure and the partial label as a near-cited answer. None of it reads an answer, so none of it says whether a given label is right: that remains the hand-labelled sample (step 0). Next in §53 is step 4, the change report calibrated on the March model change.

## 57. Diagnosis step 4: the change report, calibrated on 9 March, then read on 14 September (23 Oct 2026)

**Built:** `tools/change_report.py DATE` writes `reports/change-DATE.md` from the published files alone (no feed, no Chrome), so it runs anywhere the repo does. The deploy workflow runs it for every confirmed model event, beside the fact sheet. Equal windows of 28 days each side; the change day and the event's settling days are left out; whole weeks, so both windows hold the same weekday mix by construction (the counts are printed). It lists every other event on record inside the windows as a rival explanation, then gives:
1. **Outcomes** on scored turns with 95% Wilson intervals and Newcombe intervals on each difference: cited, not found, clarification, partial (of cited), cited and not partial, uncited, the cited rate for web and pop-up turns separately, dislikes per 1,000 and click-throughs per 100 cited answers, words and pages per cited answer.
2. **Guardrails**: traffic and the question mix, which a model-only change should leave alone (turns and conversations a day, pop-up and starter shares, typed and chip follow-ups, non-Latin script, greetings, out of scope).
3. **System** measures a model change may move but an outage or capacity change moves too: response time p50 and p90, the over-30-second share, errors, generation cost a turn on settled billing days.
4. **Topic mix**: the cited rate among topic-attributed turns, the after rate re-weighted to the before window's topic mix with "unknown" left out, the share of the change the mix accounts for, and a per-topic table with its own intervals.
5. **Deciding phrases**: total variation distance of the wording-rule mix between the windows, the phrases that moved most, and the share of the after window's not-found and partial answers on phrases the before window used for under 1% of them.
6. **Wording** per answer by outcome, and **conversations** by start day: reached a cited answer, chip use, what followed a not-found answer or a clarification.
7. **A reading**, mechanical and non-causal: what moved, which guardrails moved, the mix share, the drift. "Moved" = the interval excludes zero and the change is at least 1 point (rates) or 10% (means).

**Calibration.** Three runs before 14 September was read:
- **9 March, the known model change (gpt-4o to GPT 5).** Found cleanly: cited 94.6% → 89.5% (−5.1, −6.2 to −4.0), clarification 0.4% → 3.6%, words per cited answer +20%, pages −16%; 6 of 12 topics with 50+ turns moved, every large one; the mix accounts for none of it; 30% of the phrase mix moved, led by a clarification phrase that barely existed before. The guardrails earned their place: pop-up turns went from 0% to 20% of turns, which is the pre-launch Modal rows from 24 March (a candidate event, listed by the report). The web-only cited rate still fell 4.3 points, so the finding survives that rival. System measures moved as a model change should: response time p50 7.9 s → 15.5 s, generation cost a turn −34%, errors 0.13% → 1.65%.
- **1 July, the second known change (GPT 5 to chat-latest).** Found: cited +6.0, not found −5.1, partial +11.0 points; 63% of the phrase mix moved; cost a turn up sixfold. Traffic fell 21% across the windows (summer), which the guardrails flagged.
- **10 August, a date with no event.** Quiet: no outcome moved, 1% of the phrase mix moved, one guardrail (conversations a day +10%) and one conversation measure (single-turn share +2.0) crossed the line. That is the false-positive rate of the instrument on 15,000-turn windows: small and in the places that drift anyway.

So in this report a model change looks like: outcomes moving across most topics, no mix share, a phrase-mix shift well above 20% with new phrases, traffic guardrails steady or explained by a listed event, and response time or cost moving.

**14 September, read with the calibrated report** (17 Aug–13 Sep against 15 Sep–12 Oct; rivals inside the windows: the 11 Sep chip removal, the 29 Sep error spike, Budget Day):
- **Outcomes:** cited 92.3% → 81.3% (−11.0, −11.7 to −10.4); not found 2.9% → 8.5%; clarification 4.7% → 10.0%; partial 14.2% → 26.7% of cited; cited and not partial 79.2% → 59.6%. Web turns −10.3 and pop-up turns −11.2 alike, so the surface mix is not it. Words, pages and click-throughs per cited answer within 10%; dislikes per 1,000 cited fell 2.6 → 1.0.
- **Topics:** 14 of 16 moved; the mix accounts for none of the change; "unknown" rose from 3.0% to 8.8% of scored turns, which is the failures themselves.
- **Guardrails:** turns a day +34% and conversations +37% (the autumn rise, with Budget Day inside the window); chip follow-ups −4.4 points (three chips were removed on 11 Sep); pop-up share −2.3; out of scope 0.94% → 2.41%. Out of scope is AskCI's own flag with no phrase, so its doubling on the model change day is a finding in itself, not noise.
- **System:** response time steady (p50 11.7 s → 10.9 s, errors 1.32% → 1.30%); the over-30-second share 0.1% → 1.6%; generation cost a turn −55%.
- **Phrases:** 66% of the mix moved, and 99.5% of the after window's not-found answers use phrases the before window hardly used ("couldn't find" in place of "could not find"), as §54 found.
- **Conversations:** reached a cited answer 93.0% → 83.9%; after a not-found answer, ended there 75.6% → 80.2% and a later cited turn 20.2% → 15.0%; after a clarification, a later cited turn 68.8% → 60.5%.

**Verdict.** 14 September matches the calibrated signature of a model change on every count, at about twice the size of March's, and the two guardrails that moved each have a listed event to account for them. The report cannot separate the model from a prompt change made on the same day, and like everything before step 0 it cannot say whether a label is right. What it adds to steps 1–3 is that the fall is not traffic, not the surface, not the topic mix and not a chip, and that it is of a kind the instrument has seen before.

**Traffic for the record:** the autumn rise means the after window has 5,500 more scored turns than the before window; intervals are correspondingly narrow, and the 1-point floor on "moved" is what keeps tiny effects (uncited +0.09) out of the reading.

Next in §53 is step 5, the era scorecard, which the report's per-window sums can feed directly.

## 58. Diagnosis step 5: the era scorecard (23 Oct 2026)

**Built:** an **Era scorecard** card at the top of Usage › Before / after. One row per model or prompt era, the eras cut at the confirmed model (or prompt) events in `events.json`: a new `era` field on each such event names the era it starts, and `era_before` on the first names the era before it. The change day and an event's settling days belong to neither era. `prompt` is now an allowed event kind, for the day an amber week on Answer wording is confirmed as a prompt change; there is none yet, so every era here is a model era. Each row is that era's own sums over the whole data (not the selected range): turns, the outcome rates, words and pages per cited answer, response time, generation cost a turn on settled join days, dislikes per 1,000 and click-throughs per 100 cited answers, turns per conversation, and the share of finished conversations that reached a cited answer. The launch and chip events inside an era are listed under the table rather than adjusted for. Every figure was recounted from the CSVs independently and agrees. Note on names: billing calls the March-to-June model GPT 5 Chat (with GPT 5 Mini and a little GPT 5); §54–§56 called that era "GPT 5".

| Era | Span | Turns | Cited | Not found | Clarif. | Partial of cited | Cited, not partial | Words | Pages | p50 | Gen. p/turn | Dislikes /1,000 | Clicks /100 | Turns /conv. | Reached cited |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| gpt-4o | 1 Jan–8 Mar, 67 d | 11,416 | 95.3% | 3.8% | 0.4% | 3.9% | 91.6% | 162 | 1.90 | 8.0 s | 1.04p | 1.0 | — | 1.93 | 91.1% |
| GPT 5 Chat | 11 Mar–30 Jun, 112 d | 45,525 | 87.1% | 7.7% | 4.0% | 3.0% | 84.5% | 188 | 1.52 | 13.3 s | 0.55p | 1.4 | 4.0 | 2.20 | 85.8% |
| chat-latest | 2 Jul–13 Sep, 74 d | 44,091 | 92.1% | 3.1% | 4.7% | 14.1% | 79.1% | 180 | 1.82 | 12.1 s | 3.01p | 1.8 | 5.1 | 1.91 | 92.7% |
| 5.4 | 15 Sep–23 Oct, 39 d | 33,819 | 82.0% | 8.4% | 9.5% | 26.6% | 60.2% | 190 | 1.73 | 11.4 s | 1.39p | 1.3 | 4.8 | 1.84 | 84.3% |

**What it shows:**
- **Every model change moved the outcome mix, and not in one direction.** GPT 5 Chat cut the cited rate by 8 points and doubled not-found; chat-latest won most of that back but brought "partial" in at 14%; 5.4 is the weakest row on every outcome. The only monotone line is **cited and not partial: 91.6% → 84.5% → 79.1% → 60.2%**, era by era.
- **5.4 is the fastest model since gpt-4o and less than half the cost of chat-latest** (11.4 s and 1.39p against 12.1 s and 3.01p). Whatever happened on 14 September, it was not bought with time or money.
- **People's own signals barely move.** Dislikes sit between 1.0 and 1.8 per 1,000 cited answers in every era, and click-throughs per 100 cited answers are 5.1 under chat-latest and 4.8 under 5.4: the answers that are still cited are clicked as before. The cost of 5.4 shows in the conversations instead: the fewest turns per conversation (1.84) and the lowest share reaching a cited answer (84.3%) of any era with the pop-up live.
- **Pages per cited answer** fell under GPT 5 Chat (1.90 → 1.52) and have been near 1.7–1.8 since; words rose from 162 to about 190 and stayed there.

**Caveats, in the card's footer and here:** the gpt-4o era is the web box alone before the pop-up, at a sixth of today's traffic, and has no click-through coverage; the GPT 5 Chat era holds the pre-launch rows, the launch and the 20 May step, so its traffic measures mix two populations; the 5.4 era is 39 days with Budget Day inside it; its labels are unvalidated until step 0. The scorecard describes eras; the calibrated change report (§57) is the instrument for the boundaries between them.

Next in §53 is step 6, follow-ups: not-found rates for follow-ups against first turns, before and after, and topic drift between turns.

## 59. Diagnosis step 6: follow-ups against first questions, and topic drift between turns (23 Oct 2026)

**Why it matters.** Follow-up questions pass through the question-rewriting step, which the backend extract showed is the smaller model's only job (§53). First questions do not. If follow-ups moved more than new questions on 14 September, the rewriting step is implicated; if they moved alike, the change is downstream of it.

**Built:**
- `make_usage.py` now counts, per conversation start day in `conversations-daily.csv`, the follow-up turns where this turn and the one before both carry a topic, and how many changed topic, by the question type of the later turn (`TypedTopicBoth`, `TypedTopicSwitched`, `ChipTopicBoth`, `ChipTopicSwitched`, `NewTopicBoth`, `NewTopicSwitched`). A topic comes from the cited page, so drift is measured only between two cited answers. Every other file rebuilt byte-identical; the audit checks the new columns.
- The change report has a section **Follow-ups against new questions**: cited and not-found rates by question type on each side with intervals, the difference in differences for typed follow-ups against new topics, and the topic-switch shares. The verdict rests on typed follow-ups: chips are a fixed set of well-covered questions at a 99% ceiling, and the set itself changed on 11 September.
- **Usage › Conversations › Follow-up mechanisms** shows the share of typed and chip follow-ups that changed topic for the selected range.
- `next_step.py` now takes its eras from `events.json`, as the era scorecard does, instead of three literal dates. Its conclusions are unchanged (5.4 not-found answers: distance 0.11 to chat-latest's, 0.15 to GPT 5 Chat's; 0.56 to cited).

**Result, 17 Aug–13 Sep against 15 Sep–12 Oct:**

| Question type | Before n | Cited | Not found | After n | Cited | Not found | Cited change |
|---|---|---|---|---|---|---|---|
| New topic | 9,658 | 90.1% | 3.6% | 13,478 | 78.4% | 9.9% | −11.7 (−12.6 to −10.8) |
| Typed follow-up | 4,004 | 91.5% | 3.3% | 5,623 | 77.8% | 9.6% | −13.6 (−15.0 to −12.3) |
| Chip follow-up | 3,713 | 99.0% | 0.7% | 3,811 | 96.7% | 2.0% | −2.3 (−3.0 to −1.7) |

- **Follow-ups and first questions fell together.** Typed follow-ups fell 1.9 points more than new topics (−3.6 to −0.2), and their not-found rise is identical (+6.3 on both). The rewriting step accounts for at most 14% of the follow-up fall; the rest is shared with questions that never pass through it. **The change is downstream of the rewriting step: in retrieval, the answering model or the prompt.**
- **Topic drift fell, not rose.** Of typed follow-ups where both answers cite a page, 27.1% changed topic before and 19.7% after (−7.3, −9.4 to −5.2); chips 17.4% → 13.5%. A rewriting step that had started misreading follow-ups would send more of them to another topic, not fewer. The fall is also partly selection: fewer answers are cited, so the pairs that remain are the easier ones. The null date in August moved this measure +2.5 points, so only the September fall is beyond noise.
- **Calibration:** on 9 March follow-ups and new topics moved alike (+1.5, −1.2 to +4.1); on 1 July typed follow-ups gained 3.7 points less than new topics, so that change did fall unevenly across the two paths; on the August null date nothing moved.

**What it settles.** Of the three suspects left in §53, this step takes the rewriting step out for 14 September as a main cause: a change confined to follow-ups would show here and does not. It cannot tell the answering model from the prompt. The remaining steps are content and chips (7, 8), incidents (9), safety counts (10) and the log parser (11); none of them bears on 14 September directly, and step 0 remains the one that gives ground truth.

## 60. Incorporating the system prompts: storage, fingerprint, coverage check and one rules version (23 Oct 2026)

**Principle.** A snapshot of the system prompts (exported 28 August 2026, 13 prompts) is the specification the outcome rules were guessing at. It is treated like the raw feed: held in the git-ignored review folder, read by tools on the analyst's machine, never published. The repository gets a set-level fingerprint, rule IDs and counts. The snapshot predates 14 September by two weeks and there is no change history, so everything below is tagged "checked against the 28 August snapshot, unverified since", and nothing in the plan waits on a newer export.

**Built:**
- **Storage and canary.** One dated folder per export, one file per prompt, each starting with a canary line. The pre-commit hook refuses any staged file carrying the canary; the audit, which the deploy runs, checks every tracked file for it.
- **`tools/prompt_fingerprint.py`** writes `prompts.json`: snapshot date, prompt count, one SHA-256 over the set, `verified_current`, and a history of snapshots. No names, no text. The data-quality strip shows "prompts · snapshot 28 Aug 2026 · unverified since", amber until a current export is confirmed. The era scorecard's footer says the eras are model eras with the prompts assumed constant.
- **`tools/check_rules_vs_prompts.py`** (local; output stays beside the prompts) extracts every fixed wording the response prompts prescribe, checks which outcome rule matches it, and counts its occurrences in the raw feed by outcome and model era. 74 prescribed wordings; after the rules change below, **no gaps** (a wording that occurs in the feed with no rule) and **none landing in another family**.
- **Outcome rules 2026.10.23-2**, one bundled change, outcomes defined by what the answer says as before:
  - `nf.template`: the fixed no-results sentence, listed first so it wins over the shorter phrase inside it. 476 exact uses, all before 14 Sep; the eight-word stem 3,180 times, 2,798 of them under GPT 5 Chat, 13 under chat-latest and **none under 5.4**.
  - Out of scope gains `oos.not_covered` (225 uses, all under 5.4, previously caught only by the flag), `oos.public_services` (528), and the two refusal wordings `oos.cannot_assist` (21) and `oos.internal_guidelines` (1). Refusals sit in the Out of scope family rather than a new class: fewer than 25 rows, and a new class would add columns to every file.
  - `gr.what_would_you_like`: a prescribed greeting form that 22 flagged turns had been counted as Out of scope.
  - **Effect on published figures: 21 turns move from Out of scope to Greeting across 295 days; every other outcome count, including cited, not found, clarification and partial, is identical.** Five files changed (`usage.csv`, `category-outcomes-daily.csv`, `conversations-daily.csv`, `outcome-rules-daily.csv`, `answer-style-daily.csv`); the other eight rebuilt byte-identical; the audit passes; the Ask bar cases are unchanged.
- **Wording fingerprint 2026.10.23-2** adds eight counts for forms the answer format prescribes or forbids: a sign-off line linking the site, a continuity opener on follow-ups, invitation phrases, a bare "Yes." or "No.", heading or bold markup, nested list lines, the "(external)" link marker and the "remain in effect" freshness form. Six of them join the "How the answers are written" table on Usage › Answer wording.

**What the prompts explain (local reading, recorded here as conclusions only):**
- **"Partial" is prescribed behaviour.** The answer format tells the model, when the specific detail is not in the retrieved content, to say it could not find it and point to the closest page. A cited answer with a "couldn't find" phrase is compliance, not malfunction. The labelling question for HAP becomes whether the missing detail was on the cited page.
- **The 14 Sep phrase swap is model style, not a prompt edit.** The prompt says "could not find"; chat-latest echoed it, 5.4 contracts it. Consistent with §54's "no amber week".
- **The relevance-check instruction behind the not-found rise was in the prompt on 28 August.** 5.4 applies an existing instruction more readily; it was not given a new one, as far as this snapshot can tell.
- **5.4's not-found answers come from the answering model, not from empty retrieval.** The empty-retrieval path uses a fixed sentence and offers follow-up chips; 5.4 never uses the sentence and a chip is clicked after only 0.3% of its not-found answers (3.1% under GPT 5 Chat, §56).
- **Standalone clarifications come from the pre-search classifier, which is the smaller model.** Their doubling under 5.4 is that model's behaviour, separate from the not-found and partial rise.
- **Each model reads the same format rules differently, and 5.4 is the most literal on most of them.** Share of cited answers carrying each form, by era (gpt-4o · GPT 5 Chat · chat-latest · 5.4): nested lists 0.3 · 2.4 · 0.8 · **0.0%**; a bare "Yes." or "No." 6.2 · 1.9 · 1.1 · **0.1%**; apologies 0.3 · 0.2 · 0.0 · 0.1%; hedging words 70 · 75 · 82 · **69%**; links per answer 3.2 · 3.4 · 5.0 · **7.5**. The exception is bold or heading markup, which the format forbids: 25 · 70 · **0.2** · 19%, so chat-latest obeyed that rule and 5.4 does not. Invitation phrases are absent in every era and the sign-off link is present in 99.9%+ of cited answers in every era. A model that applies the linking and absolutes rules more literally is the measurable form of the "prompt as read by a more literal model" suspect, and the same literalness would apply to the decline instruction; the bold figure says it is not literal on everything.

**Caveats.** The snapshot is a reference point, not a specification of the live system; a prompt edit on or after 14 September would be invisible here. Dating prompt edits from the feed is limited to verbatim template sentences and would be recorded as candidate `prompt` events only. The request to the AskCI team, for when contact resumes: the current prompt set, and where `brief_mode` is used.

**Order from here:** step 0 (the labelling hour, with a rubric that scores "partial" by whether the detail was available), then §53 steps 7 and 8 on the settled rules, then 9 to 11.

## 61. Step 0 ready: the labelling sheet redrawn under rules 2026.10.23-2, with a rubric and a HAP stratum (23 Oct 2026)

- The sheet is redrawn by `make_label_sample.py` under the new rules (the four sampled classes are untouched by the rules change, so the draw is the same kind of sample): 20 cited, 10 partial, 10 not found and 10 clarification per period, 14 Aug–13 Sep and 14 Sep–13 Oct, shuffled and blind, plus a second sheet of 20 for a second labeller.
- **A fifth stratum: 20 answers to the HAP limits chip from after 14 September** (13 the rules call cited, 6 partial, 1 error). The same question asked hundreds of times, so these labels say directly what changed on a fixed input (§55). They are scored on their own, never weighted into the period mix.
- **A new column, `detail_on_page`**, filled only for answers that say something is missing or couldn't be found: the labeller opens the cited page and says whether the missing detail is in fact there. "Yes" is a miss by the model; "no" is a real gap in the content. The README explains, without quoting anything, that saying so is the designed behaviour, so the judgement is about whether the detail was available, and that a table of rates on the page counts as available.
- `score_labels.py` reports, per period, the share of "missing" answers where the detail was on the page, and a block for the starter stratum: what readers called the answers, whether they answered, and the detail-on-page share. The README's list of allowed values is also fixed (it had printed on one line).
- The sheet is in `exports/labelling-2026-10-23/` on the analyst's machine, 120 rows. About an hour for the main sheet; the second sheet is optional. Nothing else waits on it, but every conclusion since §54 is an inference until it is done.

## 62. Step 7: content lists, the pages behind the rates (24 Oct 2026)

**Built:**
- `citations-monthly.csv` gains `Answers` (answers citing the page, once each), `Partial` (of those, answers that also say something is missing) and `Dislikes`. The existing columns are byte-identical.
- **`pages-cited.csv`**, new, one row per cited page over all the data: first and last citation day, citations, answers, partial, dislikes, the page's `LastMod` from `site-pages.csv`, the first day it was cited on or after that LastMod and how many answers cited it since. That last pair is the index lag. The audit checks it against the monthly file; every other file rebuilt identical.
- **Usage › Pages** gains five cards under the existing two, for the months overlapping the selected range: answers that say something is missing by page; pages lost and gained at the latest model change (the full month before against the latest month after); addresses off the site's list and the oldest pages cited; pages cited often and never clicked; and the index lag with a count of pages changed 7+ days ago and not cited since.

**What the lists show, September and October 2026:**
- **"Something is missing" is concentrated on a few kinds of page.** 23% of all page-answers say something is missing. Of 138 pages cited in 100+ answers, five are at 40% or more: Budget 2024 (60%), the AskCI "about" page (52%), Budget 2023 (52%), the Christmas Bonus (44%) and local-authority housing grants (40%). Budget 2027 itself is at 34% on 742 answers. Past budget pages are asked for a current figure they do not hold; the "about" page is asked things about AskCI it does not say; the Christmas Bonus page is a rate question in October. **The rise since 14 September is broad, not local:** of 118 pages with 100+ answers on both sides, 68 rose by ten points or more and none fell by ten. That is the model, not the pages, which agrees with §57.
- **Almost no pages were lost or gained at the change.** 1,339 pages were cited in August and 1,325 in October. Five were cited ten or more times in August and never in October (Leaving Cert appeals, fishing licences and other seasonal pages); nine the other way, led by the two Budget 2027 pages with 930 citations between them. The change is in how pages are used, not which pages.
- **Off-list addresses are negligible:** 20 citations to 4 addresses out of 61,260, 16 of them to the site root. Moved or retired pages are not a live problem.
- **Old content is cited more than its share.** 22% of citations to dated pages go to pages last changed before 2026. The oldest pages cited 50+ times are Budget 2022 (October 2021), Unfair Dismissal (April 2022), freedom of movement in the EU, health and safety at work, entitlement to public health services and redundancy payments (all 2022). A rates page from 2022 is a content question; a procedure page may be fine.
- **Cited often, never clicked:** 14 of the 138 pages cited 100+ times recorded no GA4 click-through in September and October, led by the State Pension (Contributory) page with 741 citations, deferring the State Pension, the "about" page, maternity leave and tenants' rights. The data cannot separate "the answer was complete" from "the link went unseen"; the missing-detail share beside each page is the hint. The "about" page at 52% missing and never clicked is the clearest case of an answer that does not satisfy and offers nowhere to go.
- **Index lag is short.** Of 170 cited pages with a LastMod since 6 October, 119 have been cited since their change: 74 on the same day, 22 within three days, 17 within a week, 6 later. Of the 141 information pages the site changed since 6 October, 139 have been cited at some point. The Budget 2027 page was first cited on 29 September, a week before Budget Day, and the social-welfare rates page on 7 October, the day after its LastMod. The index is not the bottleneck; the pages "not cited since their change" are mostly changed in the last days of the data or rarely asked about.

**What it changes.** Of the content fixes others can act on, three stand out: the past-year Budget pages (route current-rate questions to the current page, or say on the old page that it is historical), the AskCI "about" page (it is asked questions it does not answer, in 195 answers over two months, and nobody clicks through), and the 2022-dated rates pages. Nothing here bears on the 14 September cause: the partial rise is across pages, and the index is keeping up.

Next: §53 step 8, chip scorecards and the share of traffic a starter-prompt cache would cover.

## 63. Step 8: chip scorecards, clarification loops, and what a cache would cover (24 Oct 2026)

**Built:**
- `starter-prompts-monthly.csv` gains, per chip and month: Partial, NotFound, Clarification, Disliked, Words, TimedTurns, ResponseMsSum, Mature and EndedThere. Existing columns identical. `conversations-daily.csv` gains `ClarThenClar`: clarification answers followed by another clarification.
- **`tools/cache_coverage.py`** (raw feed, local) writes `repeat-questions-monthly.csv`, counts only: first turns, turns, chip first turns, distinct normalised first-turn texts, texts asked twice or more, the first turns covered by the top 10, 25, 50, 100 and 250 texts, and the same for clicks on the model's suggested follow-ups. The texts themselves are printed for the analyst and never written.
- **Usage › Conversations**: the Starter prompts card is now a **scorecard** (count, share, cited, cited-not-partial, not found, clarification, then typed, then chip, ended there, dislikes, words, mean response time); a card **What a cache of fixed questions would cover**; and **Clarification loops**. The audit checks all three files.

**Chip scorecard, July–August against September–October:**

| Chip | n before → after | Cited, not partial | Not found | Ended there | Response mean |
|---|---|---|---|---|---|
| HAP limits | 174 → 516 | 93.7% → **68.2%** | 0.0 → 0.6% | 56.9 → 66.6% | 11.4 → 13.4 s |
| Renew my passport | 112 → 561 | 91.1% → 88.4% | 0 → 0 | 66.1 → 74.2% | 12.2 → 14.4 s |
| Back to School allowance | 151 → 254 | 87.4% → 86.6% | 0 → 0 | 62.3 → 78.0% | 10.9 → 11.4 s |
| Household Benefits Package (from 14 Oct) | — → 242 | 96.3% | 0 | 56.5% | 8.9 s |

- **HAP is the one chip that changed**, as §55 found: a quarter of its answers now carry a "couldn't find" phrase. Nothing else about it moved: still cited 93%, no not-found, no dislikes, the same length. The 20 HAP answers in the labelling sheet will say whether the phrase marks a missing rate.
- **People end on chip answers more often than before** on every chip that spans the change (passport +8, Back to School +16, HAP +10 points). That could be a better answer or a less inviting one; dislikes are zero either way, and the chip-next share fell on all three (the chip set changed on 11 Sep).
- **Chips get empty answers six times as often as other first turns.** Of 1,680 chip first turns in September and October, 143 (8.5%) were neither cited, not found nor clarification; the feed check shows they are empty responses (`err.empty`). First turns overall run at 1.4%, later turns at 1.2%. The passport chip is worst at 11%, Back to School 13%, the new Household Benefits chip 3%. A chip is a click, not a typed question, so this points at the chip request path (a click before the session is ready, or a chip request the backend handles differently). **This is the first finding of the diagnosis that is an incident rather than a model question, and goes to step 9 and to the team.**
- The three retired chips (auto-enrolment, low pay, maternity benefit) still appear 30–40 times a month after 11 September: people typing the old chip text, or a cached page.

**Clarification loops, 15 Sep–12 Oct:** of 2,298 clarification answers, 540 (23.5%) were the last turn, and of the 1,758 that got a reply, 492 (28.0%) were followed by another clarification. Before 14 September the loop rate was 23%: more clarifications, and more of them repeated.

**What a cache would cover, September–October:** chips are 7.2% of first turns (3.9% of all turns). The top 250 first-turn texts, chips included, cover 11.9% of first turns and 6.4% of turns; 21,058 distinct texts among 23,336 first turns is the long tail. A cache keyed on exact text would not change the cost or response-time picture. The model's own suggested follow-ups concentrate more (the top 25 texts take 5.9% of 7,509 clicks), and two of the most clicked are "yes" and "yes please", which the answer format forbids as follow-up questions: the model is offering yes/no follow-ups and people are clicking them.

Next: §53 step 9, incident candidates from error spikes against the cost meters, with the chip empty-answer rate as the first case.

## 64. Step 9: incident candidates, and the chip path as a standing defect (24 Oct 2026)

**Built:**
- **`tools/incidents.py`** (published files only; the deploy runs it, output at `reports/incidents.md`). A candidate day has an empty-answer share of at least 3%, at least three times its trailing 28-day median, and 20+ errors. For each it reports the hours the errors fell in and how concentrated they were, turns and response time p50 and p90 against their trailing medians, each cost-meter group's spend that day against its own trailing median (Search units and ranker queries; container vCPU and memory, active and idle; model input and output tokens; bandwidth), and whether the day is already in `events.json`. New candidates are printed as event lines.
- `usage.csv` gains `StarterPromptErrors` and `OrganicFirstErrors`: empty answers on chip and typed first turns, per day. The audit checks them.
- **Usage › Volume** gains an **Incident candidates** card with the same detection on the selected range (Search and Container read as service totals; the per-meter reading is in the report). **Usage › Conversations** shows, under the chip scorecard, chip clicks that got an empty answer against typed first questions.

**What the candidates say.** The detector finds the four spike days already on record as candidates and nothing else, and reads each one differently:

| Day | Empty answers | Hours | Response time | Meters that moved | Reading |
|---|---|---|---|---|---|
| Tue 27 Jan | 130 of 168 (77%) | 8 of 19 hours, whole hours at 100% | p90 1.5× | ranker 0.2×, container active 0.4×, model tokens 0.2× | **Outage.** Nothing billed by use; the service was down for most of the day. |
| Wed 13–Thu 14 May | 54 of 496, 68 of 548 (11–12%) | spread through 16 and 12 hours | p90 1.9× then 1.2× | Search 2.0×, ranker 2.3–2.6×, container active 2.0–2.5× | **Capacity under launch load.** Turns 2.6–2.8× the median; every use-billed meter doubled. |
| Fri 29 May | 79 of 710 (11%) | 15:00 at 100%, 16:00 at 89%: 57% of the day's errors | p90 1.8× | model tokens 1.5–1.6×; search and container within range | **A burst on the model side.** An hour and a half of total failure with the model meters up and the rest of the stack normal. |
| Tue 29 Sep | 47 of 905 (5%) | spread through 11 hours | p90 2.4× | container active 2.3×; search and model within range | **Container pressure.** The smallest spike, with the p90 more than doubled and only the container meters moving. |

Each stays a candidate: the readings say where to look, not what happened. They go in the events' detail fields when the team confirms them.

**The chip path is a standing defect, not an incident.** Chip clicks get an empty answer in every month since January, at 4–14% (8.7% in October, 82 of 940), against 0.2–1% of typed first turns in the same months (0.66% in October). It holds on every chip (passport 11%, Back to School 14%, HAP 6%, the new Household Benefits chip 3%), on both surfaces (pop-up 10%, web 6%), at every hour of the day, and the failures are not clustered on particular days. The same text typed by hand is answered. So it is the chip's request path that fails: a click sent before the session is ready, a chip request the backend handles on a different route, or a race between the chip and the first-turn setup. It predates every model change and the launch. **This is the single most actionable finding of the whole diagnosis for the team: roughly one chip click in twelve returns nothing, and has done all year.**

**What it changes for 14 September.** Nothing. The error rate did not move at the change (§57), and the chip defect is constant across it. The incident list is the operations record; the diagnosis stays with the answering model and the prompt.

Next: §53 step 10, safety counts in `redact_feed.py` (identifiers typed in, injection patterns, off-topic themes), counts only.

## 65. Step 10: safety counts (24 Oct 2026)

**Built:** `redact_feed.py` sets flags on each question before the text is dropped (`SAFETY_VERSION` 2026.10.24-1): an identifier typed in (PPS number, phone, email, IBAN, 16-digit card), an injection phrasing (ignore your instructions, system prompt, pretend you are, developer mode, reveal your rules and the like), and one of six themes (creative writing, code, sport, entertainment, weather, crisis language). The identifier itself is never kept; the redacted feed carries 1 or blank. `make_usage.py` writes `safety-daily.csv` (Date, Flag, Turns, and the flagged turns' outcomes); the audit checks it; **Usage › Volume** shows a **Safety counts** card with each flag per 1,000 turns and what AskCI answered. Every other file rebuilt byte-identical.

**What it shows, all 136,752 turns:**

| Flag | Turns | Per 1,000 | Cited answer | Declined | Clarification |
|---|---|---|---|---|---|
| Any identifier typed in | 16 | 0.12 | 25% | 6% | 19% |
| Injection phrasing | 24 | 0.18 | 21% | 75% | 0% |
| Crisis language | 80 | 0.59 | 76% | 8% | 0% |
| Off topic: entertainment | 21 | 0.15 | 81% | 5% | 10% |
| Off topic: code | 11 | 0.08 | 18% | 73% | 9% |
| Off topic: creative | 9 | 0.07 | 33% | 67% | 0% |

- **Identifiers are rare and the counts are small enough to be exact:** 4 PPS numbers, 9 phone numbers, 3 email addresses, no IBAN and no card number in ten months. The data-protection point is not the volume but the fact: the raw feed holds them as typed, and the backend's own placeholder redaction (the rewriting step) does not reach the feed. The redacted feed never has.
- **Injection attempts are rare and mostly declined.** 24 in ten months; 18 were declined as out of scope, 5 got a cited answer (an answer to the embedded question, which is the designed behaviour for a hybrid query) and 1 a not-found. Nothing here suggests the guardrails are being worked.
- **Crisis language is the row to read.** 80 turns, 0.6 per 1,000, and 76% got an ordinary cited answer. That may be right (the question was about a service and the words were incidental, or the cited page is the right support page) or not (a plain information page is not what the moment needed). The counts cannot tell; the pattern also catches medical uses of "overdose". Whether AskCI signposts a crisis line on these turns is a question for the system owners, and these counts put a number on how often it arises: about two turns a week.
- **Off-topic traffic is negligible.** 45 turns across five themes in ten months; the entertainment theme is the weakest pattern ("film" and "movie" match classification questions), which is why 81% of it is cited. The scope rules' tiny closed list of out-of-scope kinds is sized correctly for this traffic.

**Limits.** These are patterns, not judgements, and the counts are small; the per-1,000 rates are stable only on the whole-data view. The flags describe questions, not answers, except through the outcome columns.

Next: §53 step 11, the log parser for any future backend extract, which matters only if an extract appears. After it the plan of record is complete apart from step 0, the labelling hour.

## 66. Plan of record, step 12: what people ask, from the question text (24 Oct 2026)

Agreed after one round of proposal and critique. The same design as the safety flags (§65): rules run in the redaction step on the analyst's machine; class names, counts and the site's own page addresses leave it; nothing a citizen typed does.

**What gets classified, per turn:**
- **Intent, one class by rule on the normalised question**, in precedence order: personal case status (my claim, my application, why haven't I), contact or office, documents needed, how to apply, rate or amount, eligibility, timing (when, how long, deadline, backdated), definition (what is), other. Chips are included and reported separately, since their intent is fixed.
- **Form flags beside the intent**, so every question has an intent and a form: a year mentioned; a euro amount mentioned; a yes/no form; and **personal situation** (long, first person, several conditions), which is a flag and not a class because it would otherwise swallow the intent. The 14 September question is whether the rise landed on rate questions phrased personally, which needs both.
- **Topic from the question itself.** A versioned lexicon built from the site's page titles plus an alias list (dole, HAP, GP card …) and a stop list of generic titles (Housing, Rights …), with a minimum match length. The longest scheme name found gives a matched page and its category; a flag marks two or more schemes named. Stored as the page address and category.
- **Expected outcome per intent**, recorded once in the lexicon file: status → redirect expected (AskCI cannot see a claim; a not-found there is correct); contact, documents, apply, rate, eligibility, timing, definition → cited expected. "Unexpected outcomes" is the quality measure; the raw mix sits beside it so the table is not misread.

**What gets published:**
- `question-intent-daily.csv`: Date, Intent, Chip (yes/no), Turns, outcomes, and the form-flag counts.
- `asked-pages-monthly.csv`: Month, matched page, Asked, and what the answer did: cited that page, cited another page in the same category, cited a different category, not found, clarification, other. The agreement column is the nearest thing to a retrieval hit rate the feed can give: pages people name that retrieval does not return are a chunking list, not a content list. Small-sample rule on every page × outcome cell (under 5 suppressed).
- `category-outcomes-daily.csv` gains the question-derived topic as a fallback where the answer carried none, with a source column, so the two are never mixed silently.
- The lexicon (`question-lexicon.json`) and a rules version; audit checks; the test fixture.

**Where it shows and what it tests:**
- A **What people ask** sub-tab under Usage: intent mix over time; unexpected outcomes by intent for the range against its comparison window, with the raw mix; the share of failed answers that now have a topic; the asked-about pages list with the agreement columns, sorted by not-found.
- The change report gets **Outcomes by what was asked**: intervals and difference-in-differences by intent and by the personal-situation flag, calibrated on 9 March before 14 September is read. Rate questions point at the figure-needs-a-link rule meeting tables; personal situations at the relevance check; everywhere at the model's threshold.
- **Validation before any claim.** The labelling sheet gains two columns: the intent the reader sees, and the scheme asked about as a page from the lexicon. The scorer reports agreement per class, since 80% overall can hide a 40% class. Below 80% in a class, that class is relabelled or merged before it appears in the brief.

**Acceptance:** at least four in five typed questions land in a named intent; the question-derived topic cuts "unknown" among not-found turns by at least half; per-class reader agreement 80%+; every other file rebuilds byte-identical.

**Order:** the lexicon builder with aliases and stop list, iterated against the most frequent unmatched tokens locally (budget the iteration, not just the build); intent rules and topic match in the redaction step with a synthetic test set; the files, the category fallback, audit and fixture; the sub-tab; the change-report section; the two labelling columns; the brief section with the 14 September reading. Step 11 follows and matters only if an extract appears.
