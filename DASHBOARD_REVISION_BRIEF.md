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

## 67. Step 12: what people ask, and where the 14 September change landed (24 Oct 2026)

**Built, as §66 planned:**
- **`tools/make_lexicon.py`** builds `question-lexicon.json` (committed, public: the site's own addresses) from the English information page slugs, 194 aliases (the dole, HAP, GP card, social welfare, solar panels …), a stop list of generic slugs and a 6-character minimum. Category-level aliases carry a category and no page. It carries the expected outcome per intent. Its `--unmatched` mode (local) lists the most frequent words in questions it misses; three passes took the match rate from 44% to 58% of all questions, and what remains is intent wording (part time, how long does), not scheme names.
- **`redact_feed.py`** (`INTENT_VERSION` 2026.10.24-1) sets, from the question before it is dropped: an intent by rule in precedence order (status, contact, documents, apply, rate, eligibility, timing, definition, other; greetings and one-word replies are other), form flags (a year, a euro amount, a yes/no form, a personal situation: 25+ words, first person, two or more conditions), and the longest lexicon phrase found: its page address, category and a count of schemes named. A synthetic test set of 35 questions passes.
- **`make_usage.py`** writes `question-intent-daily.csv` (intent × chip × day: outcomes, partial, the four flags, turns naming a scheme, and the outcomes of personal-situation questions), `asked-pages-monthly.csv` (the page a question named and what the answer did: cited that page, cited another page in the same category, cited a different category, not found, clarification, other; pages asked under 5 times a month left out) and `question-topics-daily.csv` (the category the question named, for turns whose answer carried none). It is a separate file rather than extra rows in `category-outcomes-daily.csv`, so the two sources never mix; the plan's intent is kept. Every other file rebuilt byte-identical; four audit checks.
- **Usage › What people ask**: outcomes by intent for the range against its comparison window with the "unexpected" column; the personal-situation, scheme-named and unknown-topic tiles; topics of failed answers from the question; the retrieval agreement tiles; and the two page lists with cells under 5 shown as "<5".
- **The change report** gains **Outcomes by what was asked**: every intent with intervals, the spread, the rate-question test, and a difference in differences for the personal-situation flag.
- **The labelling sheet** gains `what_asked` and `scheme_page`; the key carries the rule's intent, form and page; `score_labels.py` reports per-class agreement and the page match rate. The sheet is redrawn with the same 120 items.

**Acceptance:** 60% of typed questions land in a named intent (short of the four-in-five target: 40% are "other", mostly fragments and personal narratives without a question word; the first thing to look at in the labelled sample). The question-derived topic cuts "unknown" among not-found turns from 64% to 9% after 14 September and from 60% to 12% before (target: half). Reader agreement is not yet measured. Every other file identical.

**What the questions say, typed questions 15 Sep–12 Oct against 17 Aug–13 Sep:**

| Intent | Share | Cited before → after | Not found before → after |
|---|---|---|---|
| eligibility | 21% | 94.9% → 86.1% (−8.8) | 2.4% → 8.1% |
| definition (what is X, or a bare scheme name) | 16% | 76.5% → 59.1% (−17.4) | 2.9% → 4.9% |
| apply | 9% | 95.3% → 87.0% (−8.3) | 1.6% → 7.1% |
| rate or amount | 8% | 91.4% → 84.0% (−7.3) | 4.5% → 8.8% |
| timing | 4% | 86.6% → 77.9% (−8.6) | 6.7% → 12.1% |
| other | 40% | 87.7% → 75.2% (−12.4) | 3.0% → 9.7% |
| all typed | | 89.1% → 76.9% (−12.1) | 2.9% → 8.4% |

- **The fall is on every intent, in the same direction, between 7 and 17 points.** That is the model's threshold, not one instruction. On 9 March the same test gives the same shape at half the size (−1 to −6 points). "Cited, not partial" fell 12 to 24 points on every intent.
- **Rate questions moved no more than the rest** (−7.3 against −12.1). The figure-needs-a-link rule meeting rate tables is not where it landed; the HAP chip (§55, §63) is a page-level case, not the pattern.
- **Personal situations moved further than everything else.** Not found went from 1.8% to 12.8% on them, against 3.0% to 8.1% on other typed questions: a difference in differences of **+5.8 points (+3.6 to +8.1)**. On 9 March the same difference is +2.7 (−2.5 to +7.9), nothing. The relevance-check instruction, which tells the model to decline retrieved content that does not address the question closely enough, is the instruction a more literal model applies hardest to a specific personal case, because no page addresses a specific case. **This is the first result that names an instruction rather than "the model or the prompt".**
- **Definition questions fell most** (−17.4) and are the only intent whose not-found barely moved; their loss went to clarification (27.8% of them), which is the classifier's "ambiguous" class on bare scheme names and short fragments (§60).
- **Status questions** (about the person's own claim, 32 in the window) get a cited answer 87.5% of the time, where the design expects a redirect. Few, but the design says they should not be answered from a page.
- **Retrieval agreement:** where the question named a page, the answer cited that page 57–58% of the time in both August and October, another page in the same category 23–28%, and not-found rose from 2% to 7%. The pages people name and are not answered from (employment permits, capital acquisitions tax, planning permission, applying for local authority housing, the Christmas Bonus) are a chunking list: the content exists and was named.

**What it changes.** The suspects in §53 were the model or the prompt. Steps 1 to 11 narrowed to the answering model applying an existing instruction more readily (§60). This step says which: the relevance check, applied hardest to personal cases, with a general rise in the threshold on everything else. The prompt-side remedy is a question for the team (a softer relevance rule for personal situations, or an instruction to answer the general case and say so); the labelling hour tells whether the declined answers were right to decline. The classes themselves remain a rule until the reader agreement is in.

**Order from here:** the labelling hour (two more columns, ten minutes), then step 11 if an extract ever appears.

## 68. Step 11: a parser for any future backend extract (24 Oct 2026)

**Built, locally.** A parser for container log streams lives in the git-ignored review folder beside the two UAT extracts it was written against, because it has to name the pipeline's stages and the standing rule keeps that detail out of the public repository. It turns a log stream into one row per turn of numeric and categorical fields only (no text, no conversation or turn identifiers): each stage's latency and token counts, the search's fetched and returned counts and each result's reranker score, the distinct pages returned, the follow-up type, language and classifier outcome, and whether the turn was decomposed; and a summary of medians and counts, the cache refreshes seen and the container revision. The summary is the part that can be quoted.

**On the two extracts to hand** (32 turns, 27–28 August 2026, UAT): every turn's search returned results above the relevance threshold, so every not-found in that sample was the answering model's judgement, which is the fact §53 rests on; about two thirds of input tokens were served from the prompt cache; the answering stage takes about two thirds of the turn's time. Nothing in it bears on 14 September directly: the extract predates the change.

**What it is for.** If a production extract around a change date ever appears, the parser gives, within the hour, the per-turn retrieval scores and the stage that declined, which is the one thing the feed cannot. The request stands on the parked list for when contact with the team resumes: an extract of the turns from one week before and one week after 14 September.

With this, the plan of record in §53 is complete apart from step 0, the labelling hour, which now carries four columns (what kind, answered, detail on page, what asked and scheme page) and is the only step that gives ground truth.

## 69. Plan of record: the question data across the dashboard (24 Oct 2026)

Agreed after one round. The intent and the asked-about page are two dimensions every existing view can be cut by; they are spread across the views that exist rather than kept on their own tab. Order:
1. **Overview:** a tile for answers that were not what the question needed ("unexpected outcomes": not found on a rate question, a cited answer on a status question), beside the cited rate, never instead of it; a candidate in What changed.
2. **Ask bar:** the intent dimension in the registry, and "what do people ask about" answered: intent mix plus top asked-about pages, every answer ending with the one caveat line (derived by rule from the question; reader agreement measured on N items, or not yet measured).
3. **Pages:** the four-quadrant list: named, cited and clicked (working); named but cited elsewhere (retrieval); cited but never named (AskCI surfacing content); named and not found (content or index gap).
4. **Categories:** the question-derived topic beside the answer-derived one with its source marked, and agreement (asked about X, cited X; same category; different category), so failure rates by topic stop being lower bounds.
5. **Conversations:** intent sequences (a new monthly transitions file), and after-a-setback by intent.
6. **Chips, day panel, eras, change report:** each chip's intent and the intents no chip covers; intent mix in the day panel; intent mix and personal-situation share per era; mix adjustment on intent in the change report.
7. **Volume** splits into Volume and Quality before the intent table lands there.

Not built from the feed, because the feed cannot carry them: the retrieval-empty against generator-declined split by intent (needs the log extract) and click-through rate by intent (GA4 is by day, not by turn). The golden set is Phase D and is tagged by intent when it exists.

Two rules throughout: every intent figure carries its rules version and the labelling agreement, as outcome figures do; and the question-derived topic is labelled as such wherever it stands in for the answer-derived one. Nothing from the classes goes on a headline tile without the agreement score beside it.

## 70. The question data across the dashboard: built (24 Oct 2026)

§69 built, in its order, with the two rules kept throughout: every intent figure carries the rules version and the labelling agreement (through one shared caveat line, "by rule from the question (2026.10.24-1) · reader agreement not yet measured", which `CONFIG.intent_measured` replaces once the sample is scored), and the question-derived topic is marked wherever it stands in for the answer-derived one.

1. **Overview.** A tile, **Not what the question needed**: typed questions with a named intent whose outcome is not the one the design expects (a not-found, clarification or uncited answer where a cited answer is expected; a cited answer where the question was about the person's own claim). 15 Sep–12 Oct: 18.7% of 14,006 typed questions, +10.7 points on the window before. It is a What-changed candidate in the quality class and a strip item with the rules version and agreement. The cited rate stays where it was.
2. **Ask bar.** "What kinds of questions do people ask" lists the intent mix; "which pages do people ask about most" and "what questions do people ask about housing" list the pages people name, with cited-it and not-found shares; "not-found rate for rate questions last month", "cited answer rate for personal situations in September" and "how many eligibility questions in September" apply an intent filter to questions, cited, not-found, clarification and partial; "answers not what the question needed" is a metric. Every such answer ends with the caveat line. The regression test's frozen data moved to the current commit (two September expectations and the CSV export row re-checked); seven cases added, 307 pass.
3. **Pages.** The four kinds of page: named, cited and read (the service working); named but cited elsewhere (retrieval or chunking); named and not found (a content or index gap); cited but never named (AskCI surfacing content). Named = 30+ questions naming the page in the months in range, cited = 100+ citations, read = a GA4 click-through in range. One known artefact: "cited, never named" holds pages whose own name is not a lexicon phrase when a sibling's is (the passport renewal page beside the passport application page).
4. **Categories.** Two marked columns on the demand table, "+ from the question" and "Not found, incl.": the turns whose answer carried no topic but whose question named the category, and the not-found rate with them added. Category known rises from 89% to 97% of turns in the after window. The note changes from "failure rates are lower bounds" to "the question supplies a topic for most". A new table, **where the question named a page, what the answer cited**, by category: cited that page 57.5% overall, same category 24.6%, other category 7.9%, not found 5.8%; Social Welfare 63% same page, Travel and Recreation 15% (people name the passport section, the answer cites a specific passport page).
5. **Conversations.** `intent-journeys-monthly.csv` (consecutive turns' intents, END after the last) and `setback-intents-monthly.csv` (after a not-found or clarification, by the question's intent: left, asked the same kind again, moved to another kind). The designed path is thin: of "what is X" questions followed by another, 14% go to eligibility; of eligibility, 12% go to apply; of apply, 9% go to documents. After a not-found, four in five leave whatever they asked; "what is X" questions are retried most (14%). After a clarification, "what is X" and "other" questions are asked again in the same kind 38–40% of the time, which is the classifier's ambiguous class asking for detail the person then gives.
6. **Chips, day panel, eras, change report.** Each chip's intent is on the scorecard (three apply, two rate, one eligibility, one definition) with the kinds of typed question no chip covers (eligibility is the largest). The day panel shows the day's intent mix against the 28 days before. The era scorecard gains personal situations (3.6 · 5.8 · 5.6 · 4.8% of typed questions by era) and not what was needed (3.7 · 11.6 · 8.4 · **18.2%**). The change report re-weights the typed cited rate to the before window's intent mix: the mix of what was asked accounts for 6% of the 14 September change (12% of March's), so the intent-by-intent reading of §67 stands.
7. **Volume split into Volume and Quality.** Volume keeps turns, conversations, weekday pattern, the heatmap, question types, sources, script and hours. Quality holds the outcomes, feedback, outcome by source and type, response time, answer length, incident candidates and safety counts.

Not built, as §69 said: the retrieval-empty against generator-declined split by intent (needs the log extract) and click-through by intent (GA4 is by day). The golden set is tagged by intent when it exists.

**What the spread shows that the sub-tab did not:** the "not what was needed" line is the first quality figure weighted by what the person wanted, and it is the one that moved most at 14 September (8.4% → 18.2% by era); the agreement table says retrieval finds the page people name about six times in ten and is steady across the change; and the journeys say the service is mostly single questions, with the designed path walked by a minority. All of it is by rule until the labelling hour gives per-class agreement, and the caveat line says so wherever a figure appears.

## 71. What people ask, after review: fixes, the "Other" class, and the three cuts that tell the stages apart (24 Oct 2026)

**Fixes from the review of §67 and §70**, all live:
- **Model-written suggested follow-ups are never counted as typed.** The chip flag takes three values (typed, starter prompt, suggested follow-up). A suggested follow-up is written to the prompt's own pattern and carries an intent by construction; 3,904 of them in the after window had been inflating "how do I" and "documents". Typed means typed everywhere: the page, the Ask bar and the change report.
- **Expectation has its second dimension.** A clarification is unexpected only when the question named a scheme; on "what is the benefit?" it is the designed outcome. Own-claim questions expect a cited answer (AskCI explaining how to check a claim is the right answer), reversing §66; the 87.5% "unexpected" figure in §67 is withdrawn.
- **Hubs and ordinary-phrase titles.** The lexicon marks 110 hub pages; a citation of a page beneath a named hub counts as a hit. Sixteen titles that are also ordinary phrases (cost of living, insurance, dismissal, signing on, accommodation, retirement …) no longer match. The same-page hit rate moves little (54%): the hub cases were a small part of the misses.
- **Counts, not suppression.** The asked-page tables show counts of questions and dash a rate under the small-sample rule; page counts are not people. The full-range comparison no longer reads a window before the data; the tiles say what they count.
- **Acceptance stated on the page.** The reach-note names the four-in-five target and the share reached.

**"Other", looked at locally** (10,944 typed questions after 15 September, counts only): three in five carried a question word the rules did not read, chiefly "can I …", "how do I …" and "is it …"; one in four were first-person accounts with no question word. Not keyword lookups, which the short-fragment rule already reads as "what is". So the rules broaden (rules 2026.10.24-2): any "can I / could my / is there" opening is eligibility, any "how do I / how to" opening is "how do I", and a **statement** class takes first-person accounts with no question word. Named intent goes from 60% to 77% of typed questions (target 80%); "Other" is 23%. The classes remain by rule until the labelled sample is scored; the sheet already carries the column.

**The three cuts for 14 September** (typed questions, 17 Aug–13 Sep against 15 Sep–12 Oct), which the review asked for because they tell the three stages apart:

1. **Partial by intent: not rate questions.** The share of cited answers that also say something is missing rose on every kind, and least on rate questions: eligibility 18% → 38%, statements 18% → 40%, how-do-I 13% → 27%, rate 24% → 34%, what-is 13% → 17%, timing 31% → 32%. The "found the page, not the figure" hypothesis for the partial doubling does not hold; it is "found the page, not the condition", on questions that describe a person. That is the answering model's relevance judgement, not table chunking.
2. **Clarification on "what is" questions: the classifier, whether or not a scheme is named.** With a scheme named, clarification went 4.4% → 14.1%; with none named, 20.5% → 35.7%. The pre-search classifier (the smaller model) asks for more detail three times as often even when the question names a scheme it could search. That is a classifier threshold change, separate from the answering model.
3. **Not-found by whether the question named a page: a decline, not a retrieval miss.** Not-found rose alike whether a scheme was named (3.1% → 10.1%) or not (3.9% → 9.1%). Of typed questions naming a page that exists, the answer cited that page or one beneath it 53% of the time in both August and October, while not-found on those same questions went from 2.9% to 9.2%. Retrieval found the page as often as before; the answering model declined it more often.

**What the three say together.** The three stages moved separately at the change: the classifier asks for clarification more (cut 2), retrieval is unchanged (cut 3), and the answering model declines retrieved evidence more, hardest on questions that describe a person (cut 1 and the personal-situation difference of §67, which holds at +5.2 points with the follow-ups removed). The model-era readings of §57 to §67 stand; this is the first place the mini and the generator are told apart from the feed alone.

**One finding about March, for the record:** the statement class fell from 1,413 to 328 typed questions across the 9 March change, which is a change in what people typed, not in the model: the pre-launch web box prefixed its suggested questions with "I want to know …", and those arrived as statements. The intent-mix adjustment in the change report absorbs it.

## 72. Findings and recommendations, consolidated (24 Oct 2026)

The record of what the data says the AskCI team should do, gathered from §54–§71. Each item carries its evidence section, the figure on 24 October as `tools/make_findings.py` computed it, and a confidence line: **measured** (a count from the published files), **inferred** (a reading of several measures), or **waiting on the labelling** (an outcome or intent class not yet checked against a reader). The same tool runs at every deploy and publishes `reports/findings.md`, every measurable item recomputed beside the figure here with a status, so this section stays the dated record and the report stays current. The dashboard page shows figures and claims no causes; the causes are here.

**For the system owners**

1. **The chip request path returns an empty answer to about one click in twelve, and has all year.** September: 8.2% of 740 chip clicks, against 0.99% of typed first questions; every month since January between 4% and 14%, on every chip, both surfaces, every hour. The same text typed by hand is answered. (§63, §64; measured.)
2. **The answering model applies the relevance-check instruction more readily since 14 September, hardest on questions that describe a person.** Not found on personal situations 14.1% against 9.2% on other typed questions in the last 28 days; the difference in differences across the change is +5.2 points (+3.0 to +7.5) and nothing like it appears at the March change. Retrieval cited the page people named as often as before (54.8%), so the decline is the model's, not a miss. The instruction was in the prompt before the change. Prompt-side options for the team: a softer relevance rule for personal cases, or an instruction to answer the general case and say so. (§57, §60, §67, §71; inferred; the labelling says whether the declines were right.)
3. **The pre-search classifier asks "what is …" questions to clarify three times as often, whether or not a scheme is named** (14.8% named, 33.9% not, in the last 28 days; 4.4% and 20.5% before the change). A separate change in the smaller model's threshold. (§71; inferred.)
4. **Questions about a person's own claim get a cited answer** explaining how to check it, which is the right outcome; no change needed, recorded because §66 first read it the other way. (§71; measured, small numbers.)
5. **The model offers "yes" and "yes please" as follow-up chips** against its own format rule; two of the most clicked. (§63; measured.)
6. **Two requests for when contact resumes:** the prompt set as it is now, with where brief mode is used, to close the "unverified since 28 August" caveat; and a log extract one week either side of 14 September, which the local parser turns into counts within the hour. (§60, §68.)

**For the content team**

7. **The past-year Budget pages are asked for current figures:** Budget 2024 at 60% and Budget 2023 at 52% of answers saying something is missing. Route current-rate questions to the current page or mark the old ones historical. (§62; measured.)
8. **The AskCI "about" page is asked things it does not say,** 52% of 195 answers in two months, and nobody clicks through. (§62; measured.)
9. **Citations to pages last changed before 2026 are 28% of citations to dated pages,** Budget 2022 and 2022-dated employment and health pages among them. A rates page from 2022 is a content question; a procedure page may be fine. (§62; measured.)
10. **Pages people name and are not answered from** (September, named 30+ times): divorce decrees 16% not found, jobseeker's benefit 15%, income tax 15%, driving licence 14%, applying for local authority housing 11%. The content exists and was named: a chunking list for whoever owns the index. (§67, §71; measured.)

**For whoever owns the chips**

11. The chips cover the large kinds of question (how do I, what is, can I, how much); what is left uncovered is small (timing 3%, contact 1%). The three retired chips are still typed in by hand 30–40 times a month. (§63, §70; measured.)

**A question, not a recommendation**

12. **About two turns a week carry crisis language, and 76% get an ordinary information page.** The pattern also catches medical uses of "overdose". Whether AskCI should signpost a crisis line is for the service to decide; the count is now on the record. (§65; measured, small numbers.)

**For the dashboard itself**

13. **The labelling hour.** 120 answers, four columns; until it is scored, every outcome figure since 14 September and every intent figure is an inference, and the page says so wherever one appears. (§61, §66.)
14. **The acceptance points still short:** 77% of typed questions in a named intent against 80%; reader agreement not measured. (§71.)
15. **Answers not what the question needed** is 11.9% of typed questions with a named intent in the last 28 days, the quality figure weighted by what the person wanted. It belongs beside the cited rate, not instead of it, until item 13 is done. (§69, §71; waiting on the labelling.)

**What is settled and what is not.** Settled, from counts: the chip defect, the content pages, the chips, the crisis count. Inferred, and consistent across six independent steps: 14 September was a model change in the answering model's threshold, hardest on personal cases, with a separate change in the classifier; retrieval, the rewriting step, the question mix and the pages are not it. Not settled: whether any individual label is right, which is the labelling, and whether the prompt changed on or after 14 September, which is the prompt export.

## 73. Plan of record: the content-gap register (24 Oct 2026)

Agreed after one round. Three of the signals already exist on the dashboard; what is missing is the step that turns them into a list with an owner, and the line between a gap in the content and a gap in finding it.

- **Four kinds of gap, from counts only:** the page exists but lacks the detail (a cited answer that says something is missing; by page and by the question's intent: figures, dates, conditions); the page exists but retrieval does not return it (not found on a question that named the page: a chunking or index item, never a content one); the page is stale (citations to pages last changed long ago); and the page may not exist (not found on a question naming no scheme the site has: the count is published by category, the subjects only after a local read, names and counts).
- **Two owners from the start:** named-page misses go to the AskCI team; partials on found pages and stale pages go to the content team. One list for each, never mixed.
- **A register, not a tab.** Two files: `content-gaps.csv`, evidence rows rebuilt each month by a tool (page or topic, intent, gap type, asks, not found, partial, period, rules and lexicon versions); and a small status file people edit, keyed by page and gap type (owner, status from a fixed list: raised, with owner, changed, measured, closed, won't fix; date raised, expected effect written at raise time, date closed). The dashboard joins them and counts the statuses; the information team works from the files. The evidence file's owner is the analyst; the status file carries a named person on the content side from day one, and the analyst's name until one is given.
- **Priority** by asks times unexpected-outcome rate, not rate alone: 870 asks at 11% outranks 35 at 23%.
- **Thresholds in config, read by the register, the Pages tab and the Ask bar alike:** 30 asks a month for the retrieval list, 100 answers for the content list.
- **Closure.** A content event (kind `content`) carries the page, a one-line description of what changed and the intent the edit was aimed at. The change report then compares that page's outcomes on that cut (partials by intent on that page) before and after, not the page's overall rate, which moves for other reasons. A page edit is local, dated and reversible, so this is the first place an intervention and its effect sit on one chart.
- **Data to add:** the question's intent per cited page and month (so a page's partials read as figures, dates or conditions), and a weekly asks file for pages asked 30+ times in a month (the content calendar: dates demand rose before a page caught up; and sharper closure later). Monthly closure first.
- **Not in the register until they exist:** the themes of the unanswered residue (the labelling discipline: read locally, publish names and counts) and GA4 site-search terms (a new export, text, the same local treatment).

**Order:** the two aggregates; the register tool and the status file; the content event kind; the card; the first two lists in the brief; then the calendar.

## 74. The content-gap register: built, with its first lists (24 Oct 2026)

**Built, as §73 planned:**
- Two aggregates in `make_usage.py`: `citations-intent-monthly.csv` (the question's intent per cited page and month, typed questions, rows under 5 answers left out) and `asked-pages-weekly.csv` (pages named 30+ times in a month, by ISO week: asked, cited it or a page beneath a named hub, not found, partial). Audit checks on both; every other file identical.
- **`register-config.json`**: the thresholds (30 asks a month for the retrieval list, 100 answers for the content list, two full months), the stale date (last changed before 2025), the retrieval rule (not found 10%+, or the page and its siblings reached in under 60% of the questions naming it), the fixed status list, and the owners. One file, read by the register tool and the Pages tab.
- **`tools/make_register.py`** rebuilds **`content-gaps.csv`**: one row per gap with kind, page or category, intent, evidence, asks, rate, priority (asks × the rate that raised it), team, period, and the rules and lexicon versions. It creates **`content-gaps-status.csv`** once, with the owner from config, and never overwrites it. The deploy rebuilds the evidence rows; the status file is the information team's.
- **A `content` event kind** in `events.json`, carrying the page, a one-line description of the change and the intent the edit was aimed at; the audit requires the page. The first such event is when closure is measured, on that page's partials by intent before and after.
- **A Content-gap register card on Usage › Pages**: the rows by owner, joined to their status, with the status counts, thresholds and versions in the title.

**The first lists, August–September 2026, 18 rows:**
- **For the AskCI team (retrieval), 3 pages.** The alias-target pages drop out once a cited sibling counts as reached (jobseeker's allowance, the state pension, the passport application page: siblings cited for half their questions). What is left: self-employment (named 122 times, the page or a sibling cited for a third), and two smaller pages. The retrieval list is short because retrieval is working: §71's hit rate of 53–55% plus a sibling 25% holds page by page.
- **For the content team (detail), 2 pages.** The AskCI "about" page (48% of 132 answers said something was missing, most on eligibility questions) and the "about Citizens Information" page (32% of 103). People ask these two pages about entitlements; the pages are about the service. A one-line signpost on each would answer the question the data shows.
- **For the content team (stale), 6 pages** cited 100+ times and last changed before 2025: housing supports for older people (December 2024), entitlement to public health services (October 2022), migrant workers (May 2024), the medical card means test under 70s (October 2024), health services for older people (September 2023), the medical card means test over 70s (September 2024). Two of the six are means-test pages, which is a rates question.
- **For the analyst (unknown), 7 rows.** 838 typed not-found answers in the two months named no scheme the lexicon knows, 49% of all typed not-found; and 444 named a social-welfare scheme but the answer cited no page, 102 moving-country, 75 employment, 60 housing. The subjects need the themes step: a local read, names and counts published.

**What the register changes.** The signals existed on three tabs; now each gap has a kind, an owner and a number, and the two owners see separate lists. Every row is "raised, no owner" today, which is the state the status file exists to change: the first monthly review is where a content-side name goes on it. The October rows, with the Budget pages, arrive when October closes.

## 75. Plan of record: derivation from question and answer text, the topic layer, and a logged exception (24 Oct 2026)

**Exception, logged.** On 24 October the housing pass below was produced by the analyst's Claude Code session reading
citizens' question text: about 900 question lines from the raw feeds (a not-found residue of 273 and six theme samples)
were printed into tool output and so read by a cloud model, to name the themes. §73 said the themes step needed
governance sign-off before it ran; it ran without it. Nothing a citizen wrote entered a tracked file, the brief, the
dashboard or any message to the user; what was published is theme names and counts. Decision: the design stays "the
analyst and the analyst's tools on this machine"; a model session is not the machine. This run is the one exception.
From here the rule is mechanical: **`tools/hooks/guard_feed_text.py`**, installed by `.claude/settings.json` as a
PreToolUse hook, denies any Read, Grep or Bash call in a session that would print feed text (anything under `exports/`,
the backend logs, any feed or redacted feed, any labelling sheet), and allows only the pipeline tools in `tools/` to
open those files, since they print counts. `tools/hooks/test_guard.py` holds its 20 cases. Topic buckets are built from
generic keywords the analyst chooses, with tooling that shows match counts per keyword and never the matching text. The
labelling sheet stays the analyst's to fill; the session scores it and never reads it. If the AskCI side later treats
the model provider as a processor under agreement, that is a governance ask recorded here; until it is answered the
exception route is the design.

**Why the plan exists.** The housing pass (first evidence, below) showed that a third of housing questions name no page
the lexicon knows, so they have no category and nothing says what they are about; and that the answer text, which the
redaction reduces to style counts, carries figures, scheme names, clarification asks and fixed wording that are all
safe as counts and all unused. The response text is less sensitive than the question but not clean: a good answer
restates the person's situation, a clarification repeats the question, and the model echoes what was typed. It stays
under the same rule: text read on this machine by tools, counts out.

**Question derivation, four layers**
1. **Topic layer in the lexicon.** Keyword buckets per category under a `topics` key, each a generic label and a list
   of generic words (rent, eviction, deposit), never a phrase lifted from a distinctive question. A check before commit
   (in `make_lexicon.py`) requires every keyword to match at least 20 questions in the local feeds, so nothing rare
   and identifying can enter a public file. `redact_feed.py` adds **Query Topic**; a question that names no page but
   matches a topic takes its category from the topic, and **Category Source** records page / topic / none. The "none"
   count is the published residue. This is the themes step of §73 by a safer route: generic labels, counts out.
2. **Situation entities.** What a clarification asks for: county or local authority, age band, household (children,
   partner, alone), work status, payment already on. Published as presence flags plus the county name, nothing finer.
   Allowed crossings, fixed now: county × category × month; each other flag × category × month; never flag × flag,
   never flag × county. Clarification-asked-for × situation-given is allowed because both sides are classes.
3. **Year asked about.** The year flag becomes the year value, so "asking about a past year" is countable per page.
4. **Shape.** Length band; more than one question in a turn; a pasted letter or URL. Pasted letters are the highest-PII
   turns in the feed and the generator may echo them: counted, fed to the safety row, and excluded from every phrase
   extraction on the response side.

**Response derivation, four layers, templates first**
1. **Fixed wording.** The bot's own formulas for not found, greeting, out of scope and safety: configuration, like the
   chips, so the phrase set is publishable and a change in it is the prompt-change signal the 14 September reading is
   waiting on. An afternoon; built first.
2. **Figures quoted.** Euro amounts, percentages, years, checked against every cited page's current text (public, fetched
   locally), forms normalised (€232 / 232, weekly / annual). Three results, matched / unmatched / unverifiable (the
   page's LastMod is after the answer date), by page and month. Dated local snapshots of page text at each LastMod
   start now, so later checks are against the page as it was. The word "accuracy" appears nowhere until the labelling
   sheet's figure-match column has calibrated it.
3. **Schemes and organisations in the answer.** The lexicon runs on the answer; "named but not cited" is where uncited
   claims show. A small organisations list (Intreo, RTB, Threshold, MABS, Revenue, HSE, a Citizens Information centre,
   a phone line) gives signposting by body.
4. **What the clarification asked for.** The same classes as question layer 2, so "asked for something already given"
   is one line. Later, with no new data: personalisation markers in answers ("in your case") against the situation
   entities in the question, the mirror measure.

**One version.** A single `derivation_version` bundles the lexicon's topics key, the response rules and the template
list, with a changelog line per bump, as the outcome rules work. The existing rules, style, safety and intent versions
stay as they are; the new work does not add four more.

**Published files, all counts.** Topics by month and category with outcomes and partials; situation flags under the
crossings above; figures by page and month in three columns; signposts by organisation; clarification asks by class;
template counts by day. Rows naming a county or topic need five or more.

**Where it lands.** A category picker on What people ask: volume and share, intent mix, pages named, topics with their
not-found and partial rates, the residue, and that category's register rows; the same view for every category. Ask bar
entities for topics and for "what can't be answered in <category>". The register gains the kinds this pass needed:
**missing-page** (no page exists for the subject), **signpost** (the site will never carry it; the right answer is an
organisation), and later **figure** (a page whose answers quote figures it does not carry); rows of the first two carry
no URL, the topic name and its count as evidence. Two housing cuts exist today (the published category files use the
page cited or named; the pass below adds vocabulary) and two numbers for one thing is not acceptable: the category
view and the register use the broad cut, the definition states its three tests, and once Category Source exists the
published category files and the Ask bar carry the same cut.

**Signposting as a prompt recommendation.** For a third of the housing not-found questions the right answer is
Threshold, the RTB, MABS or a centre, not a page. A theme-aware signpost in the no-results path is a small prompt
change, and the organisations list measures whether it happened; for those topics the expected outcome moves from
"cited" to "signposted", which stops them inflating the unexpected-outcome tile. Added to §72.

**Order.** Housing topic layer first, end to end, so the chain is visible: lexicon → redaction → aggregate → audit →
tests → category view. Then templates, then the organisations list, then figures with snapshots. Then social welfare,
employment, money and tax, moving country and health, which with housing cover most questions. Register kinds and the
housing rows go in now, flagged not reader-checked; the buckets and clusters go on the labelling sheet before they are
named on a tab.

**First evidence: housing, January–22 October 2026** (typed questions; chips and suggested follow-ups excluded; a
question is housing if the answer cited a housing page, or the question named one, or housing vocabulary matched).
- 13,319 questions, 12.9% of all typed, steady at 12–14% every month. Cited 88.3% (partial 16.4%), not found 7.3%,
  clarification 3.2%. The not-found rate tracks the all-questions rate month by month (13.0% vs 9.2% in May and
  13.2% vs 9.8% in June are the only months it runs clearly higher); partials run above the all-questions rate and the
  gap widened from July (19.7% vs 15.4%), before the September model change, which points at an answer-format or
  content cause rather than the generator: a line for the 14 September reading.
- Intent: eligibility 26.7%, other 24.3%, statement 15.1%, definition 12.5%, apply 12.2%, rate 5.9%. The most-named page
  is applying for local authority housing (675), then HAP (505), planning permission (157), rent supplement (156),
  home renovation grants (151).
- Themes (keyword buckets, not reader-checked), asked / not found: landlord and tenant rights 1,572 / 8.5%; grants
  1,435 / 4.9%; social and council housing 1,018 / 12.7%; HAP, rent supplement, RAS 939 / 6.5%; buying a home 707 /
  6.5%; inheriting, selling or transferring a home 605 / 9.8%; planning 415 / 9.9%; neighbours and boundaries 386 /
  18.9%; rent-a-room 377 / 7.4%; homelessness 369 / 4.1%; separation and the family home 235 / 10.6%; mould, repairs and
  standards in rented homes 82 / 28.0%.
- Not found: 978. A third named a page the site has (applying for local authority housing 92 of 675, 13.6%; HAP 38 of
  505; the social housing hub 16 of 87, 18.4%; tenants' rights 8 of 43). Two thirds named nothing the lexicon knows.
  Eight clusters, by register kind: **missing page**: local authority tenancy life (differential rent, adding a
  household member, succession, buying the house, transfers, what the means test counts, refusing an offer, repairs,
  under-occupancy); approved housing bodies and cost rental; apartment living (owners' management companies, fees,
  levies, block repairs); neighbour disputes as a housing-side subject. **Missing detail**: grants for specific works
  (wet rooms, roofs, flooring, furnishing, over the income limit); private tenancy edge cases (rent-a-room increases,
  a lease that has ended, inspections and cameras, belongings left behind, agent fees, evicting a family member).
  **Signpost**: market facts the site will never carry (average rents and prices, BER costs, management-fee norms);
  co-ownership and partners' rights, which is legal advice. **Noise**, about 270: household benefits misread as
  housing, workplace property, belongings, prompt-injection attempts.

**Built the same day (first leg: housing, end to end).**
- **Guard.** `tools/hooks/guard_feed_text.py` + `.claude/settings.json` (PreToolUse on Bash, Read, Grep, Glob); `tools/hooks/test_guard.py`, 28 cases. The pipeline tools stay runnable; everything that would print feed text is refused. `tools/collect_aggregates.py DIR` copies a review folder's aggregate CSVs into the repo root without touching a feed.
- **Topic layer.** `make_lexicon.py` carries `TOPICS` (housing, 22 topics as written), `TOPIC_MIN_MATCHES = 20` and `--topic-counts FEEDS`, which prints matches per keyword and refuses to write the lexicon while any keyword is under 20. The first run removed 205 of the keywords written from the housing pass and two whole topics (older people and the family home; building defects); three topics are left thin (inheriting or transferring a home 5 questions, mortgage arrears 7, apartment management companies 7). That is the rule working as intended: a specific phrase is also an identifying one, and what the layer loses in specificity it keeps in safety. 20 topics, lexicon 2026.10.24-4, `derivation_version` 2026.10.24-1 in the lexicon and in `redact_feed.py` (checked equal at run time). New redacted columns: Derivation Version, Query Topic, Category Source (page / topic / blank).
- **Aggregates** (`make_usage.py`): `question-topics-monthly.csv` (month, category, topic; rows under 5 left out), `question-categories-monthly.csv` (month, category, source: cited / page / topic, plus the `(none)` residue row), `question-intent-category-monthly.csv` (month, category, intent; rows under 5 left out). Every other file identical. Audit: schema and sums for the three, topic ↔ category agreement with the lexicon, the two-per-turn bound, the register's kinds (161 checks with the feed recount, 140 files-only, all pass).
- **Register.** `register-config.json` gains kinds `missing-page` and `signpost` (and `detail` named explicitly); `register-themes.json` seeds the housing topic rows (4 missing-page, 2 detail, 2 signpost, each flagged not reader-checked) and `make_register.py` copies them in until the topic layer computes them. 26 rows now.
- **Dashboard.** Usage › What people ask gains "One category, from the question": a category picker; the category's typed questions and share, not-found, partial and clarification; the definition with the three tests and their counts; topics with not-found, partial and clarification rates; the intent mix; the months; and the register rows for that category. Ask bar: "topics in housing", "what can't be answered in housing", "unanswered topics in employment" (entity `topic`, by questions or by not-found answers). A sub-view opens from a link as `#tab=<sub id>` (`#tab=asked`).
- **Housing on the broad cut, January–22 October:** 10,544 typed questions, 10.0% of 105,110; cited a housing page 2,888, named a housing page 3,561, topic only 4,095. Not found 6.4%, partial 18.4% of cited, clarification 3.1%. Site-wide residue, no page cited, none named, no topic: 13,187 typed questions (12.5%), 3,840 of them not found. Largest topics: housing in general 3,123; landlord and tenant 1,400 (8.1% not found); social and council housing 978 (13.3%); grants and energy upgrades 863 (3.2%); HAP, Rent Supplement and RAS 722; buying a home 606; planning 375 (10.7%); neighbours 307 (17.9%). The broad-cut figure is lower than the pass's 13,319 because the pruned vocabulary is narrower; the pass's number is superseded.
- **Next legs, in order:** the fixed-wording templates on the response side; the organisations list; figures with page snapshots; then social welfare, employment, money and tax, moving country and health topic tables; the labelling sheet gains topic and figure-match columns.

**Second leg: the bot's fixed wording (24 Oct 2026).** `tools/answer_templates.py --discover FEEDS` prints every
sentence that appears verbatim in 200+ answers and 50+ conversations after normalising case, digits and links; the two
thresholds are the privacy rule (a sentence that common across that many conversations is the bot's own, never one
person's), and nothing under them is printed. Across 134,697 answers it found 49 such sentences. Eighteen are prompt
formulas rather than content, and they are now `TEMPLATES` in `redact_feed.py` (families: sign-off, read more,
signpost, clarification, no results, out of scope, greeting), written to **`answer-templates.json`** by
`--write-templates`, recorded per answer in an Answer Templates column, and counted per day with outcomes in
**`answer-templates-daily.csv`** ("(none)" = answers carrying no template). Derivation version 2026.10.24-2 in the
redaction, the lexicon and the templates file; the audit checks the three agree and that every id in the daily file is
in the list. Usage › Answer wording opens with a **Fixed wording** card: each sentence's answers, share, first and last
date and status, and the dates the wording changed, each marked "with the model change of …" or "no model event: a
prompt change".

**What the sentences date.** By month share (the rule below), the fixed sentences give three wording changes: **10 March** ("Thank you
for your query", 10,587 answers, ends; "Thank you for using …", "Thanks for visiting …", "Thanks for checking …" and
the "for example, are you asking about" clarification form start; the "most up-to-date information" read-more line
falls away here too, its last 28 days before its final sighting on 9 April holding one answer), **30 June** (the
"accurate and up-to-date guidance" signpost and the fixed no-results sentence end; the read-more line changes) and
**14 September** (two new out-of-scope sentences start, the read-more line ends, "Thanks for checking …" returns).
All three fall on a confirmed model-change date (9 March, 1 July, 14 September): every deployment so far changed the
prompt as well as the model, and the data shows no prompt-only edit. That is what the 14 September reading (§67, §71)
must now weigh: the out-of-scope wording and the no-results handling changed the same day the model did. Three
candidate `prompt` events carry these dates in `events.json` for the AskCI team to confirm.
On the card each sentence is a share of the month's answers (a share, so traffic growth does not move the dates), and a
month-on-month step of two points or more that is also a quarter of the level, or a threefold change from 1%+, is a change, read against the model events:
in a month with one, settling in the 45 days after one, or neither. First and last sightings were tried and rejected:
a rare sentence's first or last day is noise, and a thin tail after a real drop dates it wrong (the "most up-to-date"
line was last seen 9 April with one answer in the 28 days before, which is not an April change).
`answer-templates-daily.csv`: 18 ids plus "(none)"; 90,007 of 136,752 answers carry no
template, which is the room the response layers that follow (organisations, figures) have to work in.

**Third leg: where the answers send people (24 Oct 2026).** `ORGS` in `redact_feed.py`: 39 organisations an answer
can signpost to, matched by name in the answer text, in six families (Citizens Information's own centre, phone line
and MABS; government departments; state agencies; local authorities; courts; charities, helplines and professionals
such as a solicitor or a GP). `tools/answer_templates.py --org-counts FEEDS` prints how often each is named, by
outcome, and refuses any named in under 20 answers (two were dropped). The redaction writes an Answer Orgs column;
`make_usage.py` counts answers per month, organisation and the turn's category into
**`answer-signposts-monthly.csv`**, with three pseudo-rows per month and category, "(any)" (named one or more),
"(external)" (named one outside the service's own channels) and "(none)", so shares need no double counting; category
rows under 5 are left out and "(all)" rows always kept. Derivation 2026.10.24-3 across the redaction, the lexicon and
`answer-templates.json`, which now carries the organisations list too. The audit checks the ids, the sums, that
category rows never exceed the "(all)" row, and that (any) + (none) equals the month's turns. Usage › Answer wording
gains **Where the answers send people**: the share of answers naming an organisation, the share of not-found answers
that signpost anywhere, the share naming an outside body, the same for partial answers, each organisation's answers
and its presence in not-found and partial answers, and a month table of where the not-found answers point. The
category picker shows the same for one category. `make_findings.py` item 12 carries the measure: not-found answers
naming an outside body in the last full month, baseline set on this first run.
**First figures, January–22 October.** 77,422 of 136,752 answers (57%) name an organisation; the Department of Social
Protection (19,556), a Citizens Information centre (19,416), the phone service (13,629), a local authority (8,678),
Intreo (8,609), Revenue (6,346), the HSE (6,224) and "your GP" (5,997) lead. Of the 7,909 not-found answers, 97% name
somewhere, and that somewhere is almost always the service's own centre (7,331) and phone line (7,275): an outside
body appears in 1,232 (15.6%), with a local authority (339) the only one above a hundred; the RTB appears in 12
not-found answers, Threshold in 41, MABS in 6. Partial answers point outside more often (6,470 of 10,045, 64%), which
is the cited page's own signposting coming through. September's figure, 21.2% of 1,249 not-found answers naming an
outside body, is the baseline in `make_findings.py` item 12; the recommendation is measured against it.
By month the picture moves: the share of all answers naming an outside body ran at 51–55% from January to June and
has fallen since, 49% in July, 43% in September, 37% in October; among not-found answers the outside-body share
jumped from about 9% to 24% in July, when the fixed no-results sentence and the guidance line were retired, and has
drifted back to 19% in October. Both are wording effects (§75 second leg) rather than content effects, and both are
now measured monthly, so the recommendation has a before.

**Fourth leg: figures quoted in answers (24 Oct 2026).** `tools/fetch_pages.py` keeps a dated local snapshot of every
cited page's text under `exports/site-text/<hash>__<LastMod>.txt` (1,893 pages on the first run; a page is fetched
again only when its sitemap LastMod moves, and the old file stays, so later checks read the page as it was). In
`redact_feed.py`, every euro amount, percentage and year in an answer is a figure; forms are normalised (€232 / 232 /
€232.00 / 232 euro); each figure is **matched** when its number appears on a usable snapshot of a page the answer
cites (one whose LastMod is on or before the answer's date), **unverifiable** when a cited page changed after the answer
or has no snapshot or nothing was cited, and **unmatched** when every cited page was checkable and none carries it.
Four Answer Figures columns; `make_usage.py` writes **`answer-figures-monthly.csv`** by month and cited page (an
answer's result counts for every page it cites; "(all)" and "(uncited)" rows; page rows under 5 answers left out).
Derivation 2026.10.24-4. The audit checks that matched + unmatched + unverifiable = figures and the bounds. Usage ›
Pages gains **Figures quoted in answers**: the share of answers with a figure, matched, unmatched (of checkable) and
unverifiable, the pages whose answers quote figures the page does not carry (100+ figures, 50+ checkable), and the
months. Unmatched is an upper bound: it fires on a figure from a second source, a rounding and a weekly rate the page
gives annually as well as on an error, and the word "accuracy" is not used for it until the labelling sheet's
figure-match column has calibrated it. Because snapshots start today, the back history is checkable only against pages
that have not changed since the answer; the Budget pages, changed in October, make most of their 2026 answers
unverifiable by construction, which is the honest result.
A by-product of the first snapshot run: 186 of the 1,893 pages the answers have ever cited now return 404 (removed or
moved since). The answers that cited them are almost all from January and February (122 and 123 citations), falling
to single figures from April and two in September, so the index was cleaned after the March deployment and this is
not a live problem; the figures from those early months are unverifiable against the pages that have gone, which the
three-way result records rather than hides.
**First figures, January–22 October.** 47,343 answers (35% of all) quote a figure, 142,801 figures in all, three per
such answer. 48.1% matched a usable snapshot of a cited page; 49.7% were unverifiable, which is the snapshot's youth
and not the answers' fault (78% unverifiable in January, 29% in October, falling as the pages' last changes move
behind the answers); of the figures that could be checked, **4.3% matched no cited page**, 2.7% in October, the
upper bound on quoted-figure error. The pages where the unmatched share is highest, with 100+ figures and 50+
checkable, are the employment-permit pages (work permits 27–40% of checkable figures unmatched across the months,
green-card permits 26–50%, the permits overview 30–34%), then invalidity pension (26%) and residence rights of
non-EEA nationals (22%). Salary thresholds and rates, in other words: the answers quote numbers the cited page does
not carry, which is either a second source, an older figure or a wrong one, and is the first list for the labelling
sheet's figure-match column. `make_findings.py` item 13 carries the unmatched share of checkable figures for the last
full month, baseline September 4.1%. 1,707 pages are snapshotted; 186 cited pages now return 404 (above); 25 of the
first run's connection failures were refetched. Snapshots are refreshed by `python3 tools/fetch_pages.py` before each
data refresh, and the derivation is 2026.10.24-4.
Over the whole period the card's page list reads: tax residence and domicile (36.6% of 116 checkable figures
unmatched), the employment-permits overview (34.4%), retiring to Ireland as a returning emigrant (31.0%), green-card
permits (30.9%), work permits (29.3% of 1,316), coming to work in Ireland (27.0%), then invalidity pension (20.1% of
1,216). Tax rules, permit salary thresholds and payment rates: the three places a figure from memory or from a second
page is most likely to differ from the cited one.

**Fifth leg: topic tables for the other five large categories (24 Oct 2026).** Forty-seven more topics in the lexicon,
written as generic keywords and pruned by the 20-match check (490 keywords removed, no topic lost): social welfare 12
(jobseekers; state pension; illness and disability payments; carers; families and children; extra benefits;
supplementary welfare; means tests and income limits; PRSI and contributions; appeals, overpayments and decisions;
working while claiming; general), employment 9, money and tax 8, moving country 9, health 9. Lexicon 2026.10.24-5,
derivation 2026.10.24-5; 67 topics in six categories. The redaction and every aggregate were rebuilt; the audit's
keyword-length rule now allows two-character acronyms (gp, 1g). The residue, typed questions no test places in a
category, fell from 13,187 to 10,614 (10.1% of typed). Topic-sourced questions by category: social welfare 5,249,
employment 3,703, housing 3,623, money and tax 2,633, health 2,355, moving country 1,628.

**What the new tables say, January–22 October, typed questions.** Social welfare's not-found rates are low across the
board (2.8–5.8% for every named topic; 9.5% only on appeals, overpayments and decisions, 389 questions), which is the
largest category being the best served. Employment: leave and holidays is the biggest topic (2,827) at 4.2% not
found; contracts and conditions 8.4%, rights and the WRC 9.3%, and the general bucket 10.8%: the further from a named
entitlement, the less the site answers. Money and tax: the two topics the site covers least are the two people ask
about in the moment, cost-of-living supports (13.8% not found, 30.5% partial) and the Budget (11.2% and 26.3%).
Moving country: citizenship is large and well served (2,181, 3.9%); residence permissions and stamps (10.3%) and visas
(10.6%) are not. Health: GP, hospital and waiting lists 11.1% not found, pregnancy and children 10.1%, the medical card
3.1%. These are the rows the register will compute once the topic layer feeds it; the seeded housing rows stand until
then.

**The register now computes its topic rows (24 Oct 2026).** `make_register.py` reads `question-topics-monthly.csv`
for the register period: a lexicon topic (never a category's general bucket) with `topic_min_turns` (100) typed
questions enters as **missing-page** when its not-found share is `topic_not_found` (10%) or more, or as **detail** when
the partial share of its cited answers is at least `topic_partial` (25%) and one and a half times the period's typical
partial share, so a site-wide rise in partials does not fill the register. A computed row replaces a seeded row of the
same category and topic; the other seeded housing rows and the two signpost rows (which no count can infer) stand. For
August–September the computation adds one row, residence permissions and stamps (266 typed questions, 16% not found),
and the relative partial rule, tried first as a flat 25%, removed eleven rows that were September's general rise
rather than a topic's problem. The October rows, with the Budget and cost-of-living topics (11–14% not found, 26–31%
partial over the year), arrive when October closes. Topic rows carry "not yet reader-checked" until the labelling
sheet's topic column says otherwise. Ten of the sixteen categories have no topic table yet (travel and recreation,
family and relationships, education, justice, consumer, death, returning to Ireland, government, environment, about);
their questions enter by page and citation only, and the next four by size are an afternoon each.

**Sixth leg: layer 2, the person in the question and the clarification against it (24 Oct 2026).** `redact_feed.py`
reads from each typed question, as classes only: a county named (26 counties), an age given in the first person
(banded 16–24, 25–44, 45–65, 66+), household flags (children, partner, alone), a work status (working, unemployed,
self-employed, student, retired), a payment already received (a first-person receiving phrase plus a social-welfare
page named), the year asked about, and the question's shape (a pasted letter: 80+ words with letter markers; more than
one question; a link). From each clarification answer it reads the classes asked for (where they live, age, payment or
income, status, household, work, dates, which scheme) and counts how many of those the question had already given.
From each cited answer, a personalisation marker ("in your case", "since you …"). Pasted letters are a safety flag
(Letter row in `safety-daily.csv` and on the safety card) and their answers are left out of the template, organisation
and figure extraction. Three files: **`question-situation-monthly.csv`** (month, category and "(all)", flag; flags
never crossed with each other; category rows under 5 left out), **`clarification-asks-monthly.csv`** (month, class,
given 0/1) and **`answer-personalisation-monthly.csv`** (month, detail given 0/1, personalised 0/1). Derivation
2026.10.24-6; audit 153 checks. Usage › What people ask gains two cards, **What people say about themselves** and
**What the clarification asked for**.

**First figures, January–22 October, typed questions.** 20,553 questions (19.6%) give a personal detail. With a detail
the outcomes are: not found 6.2% against 7.1% without, clarification 3.2% against 7.2%, partial 16.6% against 14.9%:
a detail halves the chance of being asked a question back and slightly raises the chance of a hedged answer. Details
given: a partner or spouse 3,344, children 3,226, living alone 1,354; working 4,918, unemployed 1,290, self-employed
874, retired 529, a student 290; a payment already on 4,899; an age 2,224, most often 66+ (914) and 16–24 (649); a
county 1,500, Dublin 678, Cork 207, Galway 126. The year asked about: 2026 in 1,026 questions, 2027 in 619 (10.3% not
found, the Budget questions), 2025 in 403. Pasted letters: 46 all year (17% not found); more than one question in one
turn: 1,031.

**The clarification measure.** 6,728 clarifications to typed questions, and 6,715 of them ask which scheme the person
means (the "for example, are you asking about:" form): the clarification step is scheme disambiguation, almost never a
request for circumstances. Asks for a circumstance are rare: payment or income 519, work 257, household 148, status 88,
where they live 85, age 71, a date 67. Of the 1,080 asks for a checkable circumstance, 142 (13%) asked for something the
question had already given, concentrated in household (73 of 148, 49%) and work (41 of 257, 16%); county and age are
almost never re-asked (1 each). Over all clarifications that is 2%. So the §71 question, "does it ask for what it was
told", has its answer: rarely, and when it does it is about household and work, which is a prompt-wording point rather
than a classifier fault. The mirror measure: 8.1% of cited answers used a personalisation marker when the question
gave a detail, 3.9% when it did not.

**Seventh leg: topic tables for the ten smaller categories (24 Oct 2026).** Forty-seven more topics: travel and
recreation 8, family and relationships 8, education 7, justice 8, consumer 4, death 3, government 2, and a general
bucket each for returning to Ireland and the environment; "about" gets four (about this service, contacting Citizens
Information, languages, accessibility and privacy, general). Written as generic keywords; 456 removed by hand before
the count check because they were question framing or words every category uses ("will", "rights", "fee",
"contract", "department of", "ireland", "help me", "what should i do"), and 1,094 more by the 20-match check. Every one
of the sixteen categories now has a topic table: 114 topics, lexicon 2026.10.24-6, derivation 2026.10.24-7. The
residue, typed questions no test places in a category, is 9,600 (9.1% of typed), down from 13,187 at the start of
the day. The register computes three topic rows for August–September: residence permissions and stamps (247, 15.8%
not found), **contacting Citizens Information (123, 18.7% not found)**, and crime, victims and the Gardaí (108,
10.2%).

**What the small tables say, January–22 October.** Travel is passports (1,556, 7.6% not found) and driving licences
(494, 5.5%); cars, tax and NCT run at 10.4% not found. Family is marriage, birth registration and separation in equal
measure (500 each); domestic violence questions are answered but a quarter of the answers are partial. Education is
third-level fees and grants (759, 5.8%) and schools (568, 10.7%). Justice is the weakest category the site has: going
to court 10.6% not found, criminal records and vetting 12.6%, the general bucket 14.6%, crime and the Gardaí 9.9%,
wills 10.2%. Death: the after-a-death payments topic (439) runs at 10.0% not found and 21% partial. And the "about"
category is the finding: people asking how to contact Citizens Information, where the nearest centre is or when it
is open are not found 14.4% of the time, and questions about languages and accessibility 13.7%; the service answers
questions about the State better than questions about itself.

## 76. Recommendations, consolidated after §75 (24 Oct 2026, evening)

§72 stands as the record at midday on 24 October. The seven legs of §75 added measures and moved some conclusions.
This is the current list, in the same three groups, with each item's figure, its measure on the page, and its
confidence: **measured** (a count from the published files), **inferred**, or **waiting on the labelling**. Items
carried from §72 keep their number in brackets.

**For the system owners**

1. **[1] The chip request path returns an empty answer to one click in twelve, all year.** Unchanged, still the
   first thing to report. Findings item 1. (§64; measured.)
2. **Every deployment so far changed the prompt as well as the model, and 14 September changed the out-of-scope and
   no-results wording the same day it changed the model.** The fixed sentences step in March, July and September and
   never otherwise. The September reading in §67 and §71 holds, with this added: part of what moved on 14 September is
   wording, and the labelling is what separates the two. Usage › Answer wording, Fixed wording; three candidate
   `prompt` events to confirm. (§75 second leg; measured.)
3. **The no-results answer sends people to Citizens Information's own channels and almost nowhere else.** 97% of
   not-found answers signpost; 15.6% name an outside body; the RTB appears in 12 not-found answers all year, MABS in 6.
   A theme-aware signpost (a tenancy question to the RTB and Threshold, a money question to MABS, a neighbour dispute
   to the justice pages and a centre) is a small prompt change. Findings item 12, baseline 21.2% (September).
   (§75 third leg; measured.)
4. **[2, 3] The answering model's threshold and the classifier's clarifications** are as §72 read them, with one
   correction from layer 2: the clarification step is scheme disambiguation (6,715 of 6,728 clarifications ask which
   scheme), it asks for a circumstance the question already gave in 2% of cases, concentrated in household and work,
   and giving a detail halves the chance of being asked back. So the classifier is not re-asking; the "what is …"
   clarification rise of §71 is a threshold on scheme ambiguity. (§71, §75 sixth leg; inferred.)
5. **[6] The two requests for when contact resumes** stand: the prompt set as now deployed, and a log extract one week
   either side of 14 September. The templates give the dates to ask about. (§60, §68, §75.)

**For the content team**

6. **[7, 9, 10] The register** now carries 29 rows for August–September across six kinds, with owners and a status
   file: 3 retrieval, 4 detail, 6 stale, 7 missing-page (4 from the housing read, 3 computed: residence permissions
   and stamps 15.8% not found, contacting Citizens Information 18.7%, crime and the Gardaí 10.2%), 2 signpost, 7
   unknown. Usage › Pages. The October rows add the Budget and cost-of-living topics. (§73, §74, §75; measured, topic
   rows not yet reader-checked.)
7. **People asking how to contact Citizens Information are not found 14.4% of the time** (347 questions, "about"
   topic table); languages and accessibility 13.7%. The cheapest row in the register: two lines on the about page.
   (§75 seventh leg; measured.)
8. **Figures quoted that the cited page does not carry: 4.3% of checkable figures, 2.7% in October**, an upper bound
   that fires on roundings and second sources as well as errors; highest on tax residence, the employment-permit
   pages, retiring to Ireland and invalidity pension. Findings item 13, baseline 4.1% (September). Not called
   accuracy until the sheet's figure-match column says what the bound contains. (§75 fourth leg; measured, waiting on
   the labelling.)
9. **[8] The AskCI "about" page** is still asked for entitlements; the register's detail row stands. (§62; measured.)
10. **Justice is the weakest category** (going to court 10.6% not found, criminal records and vetting 12.6%, the
    general bucket 14.6%), and money and tax covers least the two things people ask about in the moment (cost of
    living 13.8% not found, 30.5% partial; the Budget 11.2%, 26.3%). Usage › What people ask, the category picker.
    (§75 fifth and seventh legs; measured.)

**For whoever owns the chips**

11. **[5, 11]** Unchanged. (§63, §70; measured.)

**A question, not a recommendation**

12. **[12]** Crisis language: unchanged count; the organisations list now measures whether a crisis line is named
    (Samaritans, Pieta or 50808 appear in 84 answers all year). (§65, §75; measured, small numbers.)

**For the dashboard itself**

13. **[13] The labelling hour, with the sheet regenerated** to carry category, topic and figure-match columns and
    strata for the §75 layers; `score_labels.py` prints the category agreement, the topic overlap and the figures
    calibration beside the outcome and intent figures, as `CONFIG.derivation_measured`. Until it is scored: every
    topic row, the figures bound and the agreement caveat stay as they are. (§61, §66, §75.)
14. **[14, 15]** Unchanged: 77% of typed questions in a named intent against 80%; "not what the question needed"
    11.9%. (§71.)
15. **The residue**, typed questions no test places in a category, is 9,600 (9.1%), from 13,187 this morning; what is
    left is noise, greetings, and subjects the site does not have. It is the number to watch as the topic tables
    grow, not to drive to zero. (§75; measured.)
16. **The exception of 24 October** is logged in §75 and closed by the guard; the governance ask (the model provider
    as a processor under agreement, or not) is open and belongs to the AskCI side. (§75.)

**What is settled and what is not, revised.** Settled, from counts: the chip defect; the content rows in the
register; the chips; the crisis count; that every deployment changed the prompt; where the not-found answers send
people; that the clarification step disambiguates schemes and rarely re-asks. Inferred, consistent across the steps:
14 September was a model change in the answering model's threshold, hardest on personal cases, now known to have
come with a wording change on the same day. Not settled until the labelling: what the 14 September "not found"
answers actually are, whether the topic labels are right, and what the figures bound contains.

**The labelling sheet, regenerated (24 Oct 2026, evening).** A new labelling folder under `exports/`, dated 24
October: 122 answers, a second sheet of 24. `make_label_sample.py` keeps the outcome strata of §61 (per period: 12
cited, 8 partial, 8 not found, 6 clarification; 10 HAP starter turns) and adds the §75 strata from the after period,
typed turns only: 8 answers whose quoted figures all matched a cited page and 8 with one unmatched (populations 2,636
and 237), 8 questions giving a personal detail (3,934), the 4 pasted letters there were, and one question per category
placed by its topic alone (16 of 4,408). Three new columns for the labeller: **category** (one of the sixteen),
**topic** (the subject in the reader's own words) and **figure_match** (yes / no / partly / can't tell, checked on the
cited pages, with a rounding or an annualised rate counting as on the page). `key.csv` carries the rule's topic and
category, the figures result and the situation flags for every row, and stays shut until the labels are in.
`score_labels.py` adds three readings: category agreement (split by page-named and topic-placed rows), a loose
topic-word overlap, and the figures calibration (agreement, the bound's false alarms, the rule's misses), printed as
`CONFIG.derivation_measured` beside the outcome and intent entries. The folder of 23 October is superseded and can be
deleted. The analyst fills the sheet; the session scores it and never reads it.

**Audit response (24 Oct 2026, late).** Two agent audits ran against the repository from `brief/AUDIT_PROMPT.md`;
the second, from a clone, reproduced every figure it quoted and found three things that broke the system's own
rules. All fixed in one pass, with the audit at 157 checks:
- **`costs.csv` published the production estate**: 25 globally unique resource names, which only the subscription
  ID redaction had touched. `tools/redact_costs.py` now rewrites each name to a role label (service-openai,
  service-search, shared-storage, admin-backend, shared-endpoint-1 …), one label per original name so scopes and
  de-duplication hold; `--check` refuses a file with a name left; the audit checks every row. The names remain in
  git history, which is a decision for the repository owner, not the tool.
- **The five-row floor was skipped on "(all)" rows**: 193 situation rows (113 of them a county with a month and an
  outcome) and 29 organisation rows sat under five. The floor now applies to every row that names a class, the two
  totals excepted, and two audit checks enforce it.
- **The deploy checked the canary but not for text.** The audit now sweeps every tracked CSV, JSON and Markdown
  file for a text-column header, a free-text cell over 400 characters outside the known prose columns, identifier
  patterns (PPS, email, IBAN, mobile) and a production resource name, reporting file and rule only. Its first run
  found seven GA4 page paths in `ga4/categories-and-views.csv`, four carrying an email address in the path; those
  cells are masked. The deploy fails on any hit.
- **The partial rise is July's, not September's.** Until June, 60–92% of partials fired on "does not provide", a
  phrase ordinary sentences also use; from 1 July, when the fixed no-results sentence was retired, 88% fire on
  "could not find" inside a cited answer, and the count went from 558 in June to 2,236 in July. The series measures
  the model's phrasing of a gap as much as the gap. A card on Answer wording shows partials by deciding phrase and
  month; the page's configuration note and §67's reading are corrected accordingly; the labelling sheet's partial
  rows, by phrase, will say which are real gaps.
- Also from the audit: the Ask bar test exited green with no browser (it now fails unless `--allow-skip`, which the
  pre-commit hook passes and the deploy does not); the guard could be passed with a glob or a shell variable (denied
  now, six cases added, 34 in all); findings item 12 mislabelled "any organisation" as the service's own channels;
  the era footer said prompts were assumed constant; the page-detail threshold was hard-coded (now `page_partial`
  in `register-config.json`) and a person was named as owner in a public config (now a role); the page now shows
  the derivation version in its strip and carries a `derivation_measured` slot wired into the topic and figures
  caveats; the September system brief is archived under `brief/`; parsed log turns are ignored wherever they sit.
- Two corrections to this brief: the whole-period figures in the third and fourth legs above (77,422 answers
  naming an organisation; 47,343 answers and 142,801 figures; centre 7,331, phone 7,275) were written before
  derivation 2026.10.24-6 excluded the 46 pasted-letter answers; the files now read 77,389; 47,334 and 142,783;
  7,323 and 7,268. `reports/findings.md` is the live record. And "a detail halves the chance of being asked back"
  in the sixth leg is a comparison of two groups that also differ in length and in naming a scheme; read it as what
  moved, not as an effect.
- Accepted for later, in the audit's order: day-level intervals calibrated on the August null date; a sequential
  change-point test feeding candidate events; figures by kind with years out of the headline; a refresh runner with
  a manifest and one versions file; a data-protection note in the repo. Declined: splitting the page into
  concatenated source files (a build step by another name). The second audit's closing line stands: no new
  derivation layer until the sheet is scored.

**Day-level intervals in the change report (24 Oct 2026, late).** Every rate in `change_report.py` now carries two
intervals: the Newcombe interval on pooled turns, and a day-level one in which the days inside each window are
resampled with replacement (2,000 draws, fixed seed) and the window rate recomputed from the resampled days' pooled
counts, so the day, not the turn, is the unit. "Moved" now needs both intervals to exclude zero. Calibration: on
10 August, a date with no event, every outcome rate's day-level interval contains zero (cited +0.0, −0.7 to +0.7);
on 9 March it excludes it (cited −5.1, −6.4 to −4.0); on 14 September likewise (cited −11.0, −12.0 to −10.0; not
found +5.6, +5.0 to +6.2; partial of cited +12.5, +11.5 to +13.6). The two agree within a tenth of a point on the
outcome rates, because 28-day windows hold 15,000–23,000 scored turns; they part on quantities that move by the day,
where the day-level interval is three times as wide (the pop-up share of turns on 9 March: +20.3 points, turn
interval +19.1 to +21.4, day interval +13.3 to +26.9). The September verdicts stand on both. Reports regenerate at
deploy.

**The refresh runner and the manifest (24 Oct 2026, late).** `tools/refresh.py FEEDS` runs the refresh in order
and stops at the first failure: snapshots, the lexicon's 20-match check, each redaction, the templates file, the
aggregates, the two raw-feed tools, collection, the audit with the feed recount, the register, the findings, the
change reports, the incidents, the fact sheet, the Ask bar test, and finally **`VERSIONS.json`**: every version
string in force (rules, style, safety, intent, lexicon, derivation, page config), the recount's date and counts,
the test result, and a hash and row count of each aggregate file as committed. The deploy's files-only audit checks
the manifest's versions against the files and its hashes against the committed aggregates, so the published
aggregates are provably the ones the recount passed; the page's strip shows the recount date and count (the "audit
mode" labelling the first audit asked for). The tools' output goes to `refresh.log` in the review folder; the runner
prints each step's last line, counts only. `--from-audit` resumes after the aggregates; `--skip-fetch` and
`--skip-test` exist for repairs. First full run, 24 October: every step passed, the recount at 179 checks, the Ask
bar at 311, and the redaction and aggregates reproduced the committed files byte for byte (collect: 0 changed),
which is the reproducibility the audits could not test from outside.

## 77. UI pass 1: the polish layer removed, outcomes first, one caveat strip (24 Oct 2026, night)

Two UI/UX reviews of the page (kept in `brief/`, untracked) agreed on the same first five changes; this entry
records them as built, so the next pass (§76 items 6–12: Usage regrouped into six doors, outcome-over-time on
Quality, a 12px floor, small multiples, "show all", caching, accessibility) starts from a known state. The page
shrank by 256 lines; the Ask bar test still passes 311 of 311.

1. **Straight lines, no fills, square bars.** Every `tension` is 0 and every area fill is off, except the
   cumulative "settled to date" burn-down, where the filled area is the quantity. The global Chart.js overrides
   that rounded bars (`borderRadius 6`), curved lines (`tension .35`) and painted gradient fills under every line
   are gone. A line now reads as the data; a change of slope is a change in the figures, not an easing.
2. **The polish layer removed.** Glassmorphism, the gradient Ask button, the tab hover animation, the KPI
   `!important` restyles and the forecast hero (the £1,176 panel with its count-up) are deleted. Kept: the static
   background wash, the brand title, the focus ring and the editorial type scale. Month forecast is a tile again,
   placed last on Overview and labelled "detail on Cost".
3. **Overview re-ordered with outcomes first.** The tile order is cited answer rate, not found, not what the
   question needed, response time, conversations, reached a cited answer, click-through, then generation cost per
   turn and the month forecast. The cost KPI row above the group tabs now shows only when a Cost sub-view is active
   (`body.costs-active`), so a reader landing on Overview sees outcomes before money.
4. **One caveat strip.** The three standing caveats that were repeated on card after card (outcome rules
   unvalidated from 14 Sep; intent, topic and situation read by rule from the question; unmatched figures an upper
   bound) now appear once, in an amber strip under the data-quality strip, ending "One labelling sheet settles all
   three (brief §75)". `outcomeCaveat()` returns nothing; the per-card warnings are gone.
5. **Doughnuts to ranked bars.** The five share doughnuts (Cost summary's fixed / variable / generation, Services'
   by-service and Foundry-meter totals, Models' by-family and by-meter-type) are horizontal bars sorted by value,
   £ ticks, no legend, the same colours, the same click targets, with a shared `hbarOpts()` (350 ms animation,
   tooltip showing the value and its share). Hints read "click a bar".

**Before-and-after screenshots** are in `screenshots/before/` and `screenshots/after/` (untracked), fifteen views
in both themes. One capture caveat: headless Chrome leaves these five bar charts (and, before, the doughnuts) empty
because the chart animation never completes under a virtual-time budget; in a real browser they render, checked
live on the Models, Services and Cost summary views in both themes. The Ask bar test is unaffected.

**Not done in this pass, by design:** item 6 onward; the Overview's "What changed" list, the era footer and the
strip wording are unchanged; no definitions moved. The removed hero's forecast sentence ("£777 settled to 20 Oct
plus 11 days at the 28-day pattern") survives in the tile's sub-line and on Cost → Summary.

## 78. UI pass 2: Usage regrouped into six views, the old ids kept as doors (24 Oct 2026, night)

§76 item 6. Usage carried ten sub-views in one row, ordered by data file; both UI reviews asked for fewer views
grouped by the reader's question, with every `#tab=` id still working. Built:

- **Six sub-views, in this order:** Quality, Questions, Pages, Conversations, Answer wording, Volume. The Usage
  tab now opens on Quality (the owners' door) rather than Volume. Volume, Conversations and Answer wording are
  unchanged.
- **Three merged views.** Quality holds the former Quality and Before / after; Questions holds What people ask
  and Categories; Pages holds Pages, Click-throughs and Reach. Inside a merged view each former sub-view is a
  **part**: a section with a head (name, one-line note) and an anchor, in that order. A row at the top of the
  view, "In this view", lists the parts present and jumps to them. A part whose file is absent is hidden, with
  the same availability rule it had as a sub-view, and a view is offered when any of its parts is.
- **Nothing moved within a part.** Every card, chart and table renders as before, into the same functions; only
  the element each function writes to changed (`part-<id>` inside `pane-<view>`). No measure was removed or
  re-derived.
- **The old ids are aliases.** `#tab=impact`, `#tab=categories`, `#tab=clicks` and `#tab=reach` open the view
  they now live in and scroll to the part; saved preferences, the Overview tiles that open Click-throughs, the
  chart clicks that open Categories, the Ask bar's jump cards and the command palette all resolve through the
  same table (`SUB_ALIAS`). The palette lists the parts as "Usage · Pages · Click-throughs" and so on. Two Ask
  bar cards that named "the Click-throughs tab" now say "under Pages, in Click-throughs"; the three test cases
  that quoted them were updated, and the Ask bar test passes 311 of 311.

**Checked live** in both themes: the three merged views render with no console errors; the four aliases land on
their part; six pills fit one row at 1,330 px.

**Deferred, from the design review's fuller version of this item:** hour of day moving from Quality to Volume;
"Where the question named a page" appearing once instead of on both What people ask and Categories; the Reach
"Key insight" sentence as the Pages view's lead; the sub-nav collapsing to a select under 900 px. Each is a
content edit inside a part and can follow item 7 (outcome-over-time on Quality) without touching the navigation
again.

## 79. UI pass 3: outcomes over time at the top of Quality, with the comparison windows drawn (24 Oct 2026, night)

§76 item 7. The two rates the page exists to show, cited answer rate and not-found rate, were one click away
behind the tile's history modal; the Before / after chart showed one line with event lines and no sign of the
windows the statements compare. Built:

- **"Outcomes over time"** opens the Quality view: two daily line charts side by side, cited answer rate and
  not-found rate over scored turns, straight lines, no fill, days under the rate floor (50 scored turns) left
  as gaps, the confirmed events as lines, a click on a day opening the day panel. The chart-or-table toggle and
  the copy bar come with the card as on every chart.
- **One event chosen, its windows shaded.** A row of pills lists the confirmed events in range that take a
  before / after (the same rule as the Before / after table: not a one-off day such as Budget Day); the latest
  is chosen by default. Its 28-day windows are shaded on both charts, before grey and after blue, labelled
  along the bottom when there is room, and in each window the pooled rate is drawn as a line with its
  **day-level 95% interval as a band**. The windows follow `tools/change_report.py`: calendar days either side
  of the event, the event day excluded (and the days to its end date when it has one), cut to the selected
  range; a day counts when it meets the rate floor.
- **The interval is the day-level bootstrap, in the browser.** `dayBootstrap()` resamples the days of each
  window with replacement 2,000 times (a seeded generator, so the figure is stable between loads), recomputes
  each window's pooled rate and the difference, and takes the 2.5th and 97.5th percentiles. On 14 September the
  page gives cited −11.0 pts (−12.0 to −10.0) and not found +5.6 pts (+5.1 to +6.2), the same figures the
  change report printed from the feed recount (§75), which is the check that the browser's windows and day
  lists match the tool's. The caption under the charts states both windows, their day counts, the two rates,
  the difference and the interval, and says descriptive only; the generated report remains the record and
  carries the turn-level interval as well.
- **Before / after's daily-turns chart** now shades the 28-day windows of every event in its table, with the
  same colours and no levels, so the table's rows can be seen on the series.
- **Mechanics.** A `windowShade` chart plugin (bands and levels by label index, drawn under the datasets) that
  any chart can take, beside the existing event-line plugin; `eventWindows()` is the one place the window
  dates are computed. No measure changed; the history modal stays for the other tiles.

Ask bar test 311 of 311. Checked live in both themes at All and 3M.

**Still open from the review's reading of this item:** the Overview's "Outcome mix" stacked bar (the same
two lines were suggested there too); the era scorecard's wide table (item 10); the sub-nav select under
900 px.

## 80. UI pass 4: a 12px floor, long definitions out of card titles, the data stamp first (27 Oct 2026)

§76 item 8. The design review found card notes, footers and table cells at 9.6 to 10.9 px, definitions of up
to 200 characters squeezed into the right-hand half of card titles, and the copied text carrying its data
stamp on its last line, the one a paste into chat loses. Built:

- **A 12px floor for anything a reader reads.** The smallest type token is now 12px (was 11), and every
  hard-coded size that computed below 12px is raised to it: 150 literals, because the page's root font is
  14px and `.6rem` to `.85rem` all fell under the floor. Chart.js axis ticks, legends, tooltips and axis
  titles are 12px (were 8 to 11). A scan of every visible text element in the ten views, live, finds none
  under 12px. **One exception, stated:** the badges drawn inside charts (event names, window labels,
  reference-line labels) are 11px (were 9 and 10), because three stacked rows of 12px badges would cover about
  a fifth of a 210px chart; their text is repeated in the event list and the captions. Clipboard HTML keeps
  literal sizes, since Word and email cannot resolve the page's CSS variables.
- **Definitions once, under the title.** A card-title note longer than 90 characters is a definition, not a
  tag; it now moves out of the title into a full-width line beneath it in the prose face at 12px. Short notes
  ("click a bar", the period) stay in the title. One observer does this for every card the page renders,
  panes, modals and day panels alike, so the 70 templates were not edited; about half the notes move. The
  Answer outcomes note no longer repeats the outcome-rules version, which the strip carries.
- **Copy with definition puts the stamp first.** The copied title line now ends with the usage-data date and
  the page and data commits; the full footer stays at the end. One Ask bar test case that quoted the old first
  line was updated to check the stamp is there.

Ask bar test 311 of 311. Checked live in both themes.

**Not done here:** the 681 inline `style` attributes the review suggested lifting into classes (mechanical,
no visible change, better done with item 12's accessibility pass); a title-hover form of the definition
(the lifted line is visible without hovering, which suits the readers who must trust it).

## 81. UI pass 5: small multiples for the fixed wording and the categories (27 Oct 2026)

§76 item 9. The §75 findings about the prompt's fixed sentences lived in a month table and a list; the
categories had bar charts of totals and no shape over time. Both reviews asked for aligned small multiples on
one date axis. Built:

- **One helper, `smallMultiples()`**, drawing a grid of tiles in inline SVG (no chart instances): every tile
  on the same weeks so a step lines up down the grid, a null week drawn as a gap and never as zero, confirmed
  model changes as dashed lines, an optional reference line, and either one shared scale (to compare levels)
  or each tile on its own scale with its maximum printed. Each tile carries a title, the last week's value,
  its range total and an accessible label; a tile can open a view.
- **Fixed wording (Answer wording):** 18 tiles, one per prescribed sentence, its weekly share of answers,
  each on its own scale (they run from under 1% to 95%). The month table and the "months the wording changed"
  list stay, the table now under a "Month by month, as a table" disclosure. The grid shows at a glance what
  §75 established by reading: sentences start and stop together on 9 March, 1 July and 14 September, on the
  model-change lines.
- **Categories (Questions › Categories):** 15 tiles, one per category the answers were attributed to,
  largest first, the weekly not-found rate on one shared scale, with the rate across those categories together
  as a grey line in each. The note states the limit: a not-found answer usually cites no page, so most
  not-found turns carry no category here and every rate on the card is below the site's; the tiles compare
  categories with each other. A tile opens that category in "One category, from the question".
- Weeks under 50 answers (or 50 scored turns) are gaps, the page's rate floor.

Ask bar test 311 of 311. Checked live in both themes.

## 82. UI pass 6: "show all" on ranked lists, and the era scorecard in eight columns (27 Oct 2026)

§76 item 10. Ranked tables were cut at a fixed count (6, 8, 10, 12, 15, 20 or 25 rows) with no sign of what
was cut, and the era scorecard ran to 17 columns behind a horizontal scroll. Built:

- **No silent cuts in ranked lists.** A ranked list now renders its whole list up to 200 rows (`ROW_CAP`);
  its table body carries how many rows to show at first and how many exist, and one enhancer (on the observer
  that lifts long notes) hides the rest behind "Show all N", toggling to "Show the first N". A list longer than
  200 says so on the button ("the first 200 of 2,061; the rest are in the data file"). Applied to fifteen
  tables: top cited pages, category journeys, click-through pages, topics of failed answers, the two
  named-page lists, pages lost and gained at a model change, addresses off the site's list, the oldest pages,
  the four page quadrants and figures by page. Every row shown was already in a published file with its floor
  applied there; nothing new is disclosed. The quadrant cards' page counts were the cut count (8) and are now
  the true count. Month-by-month tables are not collapsed (hiding rows there would hide the latest months),
  nor is the county list inside the situations table, which shares one table with other sections.
- **Era scorecard, eight columns and a line.** Each era row keeps turns, cited, not found, clarification,
  partial of cited, cited-not-partial, response p50 and generation pence a turn, plus a sparkline of the weekly
  cited-not-partial rate inside the era, all eras on one scale (printed in the header), so a drift within an
  era and the level between eras show together. The other eight figures (words and pages per cited answer,
  dislikes, clicks, turns per conversation, reached cited, personal situations, not what was needed) open under
  the row with "More figures". The table fits at 760 px instead of 1,040. A typo in its footer is fixed.

Ask bar test 311 of 311. Checked live.

## 83. UI pass 7: the data files cached between deploys (27 Oct 2026)

§76 item 11. Every load fetched every data file with `?v=` and the current time, so neither the browser nor
GitHub Pages could serve anything from cache: 46 files, about 16 MB on disk, on each visit and each refresh.
Built:

- **One cache key: the deployed commit.** The deploy's stamping step now writes a third value into the
  `askci-build` meta, `build=` the short commit being deployed, beside the page and data commits it already
  wrote. Every data fetch (the CSVs, the lexicon, the register config, the templates, `VERSIONS.json`, the
  prompts and the events) goes through `dataURL()`, which keys it on that commit. A deploy changes the key, so
  a reader never gets a stale file after a release; between deploys the URLs are stable, so the browser's
  cache and GitHub Pages' own headers (a ten-minute max-age and an ETag on every file, checked) serve repeat
  visits from cache or with a "not modified" reply. The data commit alone would not do: it covers the CSVs and
  `events.json` but not the JSON files or anything regenerated at deploy.
- **A local copy is unchanged.** Without a deploy stamp the key stays the time of the load, so working on the
  page locally always reads the files as they are on disk. The fact-sheet tool and the Ask bar test serve the
  unstamped page and behave as before.
- Checked by serving a copy with a simulated stamp: all 46 data requests carried the commit key and the page
  loaded its data; only the logo has no key, as before.

**Not done, and why.** The review's second half of this item, loading files only when their pane opens, is
not worth its cost here: panes already render lazily on first visit, and the Ask bar answers from every file,
so all of them are needed at start for it. With the cache in place the start-up cost is paid once per deploy,
not once per visit.

Ask bar test 311 of 311.

## 84. UI pass 8: accessibility (27 Oct 2026)

§76 item 12, the last of the UI review's twelve. Both reviews asked for chart-table parity, keyboard focus that
behaves around overlays, contrast measured on the rendered colours, and no sideways scroll on a phone.
Built and measured:

- **Every chart has a text alternative.** Each canvas is an image named after its card ("Conversations by source
  per period. The values are in the table that follows."), and its data table is built when the chart is drawn
  and kept in the page, visually hidden, instead of being created only when the table toggle is pressed. A screen
  reader reaches the same numbers straight after the chart; the toggle now reports which view is pressed.
- **Focus in overlays.** One focus manager wraps the detail modal, the day, service and meter panels, the command
  palette, report mode and the events popover: opening one moves focus into it, Tab and Shift-Tab stay inside it,
  and closing it by Escape, its button or the overlay gives focus back to the control that opened it. Report mode
  had no keyboard exit and now closes on Escape. The day panel is marked modal; the detail modal takes its name
  from its title. Checked by script in the browser for each overlay: focus in, Tab wraps, Escape closes, focus
  returns.
- **Contrast, measured.** Every text colour against every surface (background and the three card levels) in both
  themes, from the computed styles. Six fell under 4.5:1 on at least one surface: in dark, the two secondary greys
  (4.14 and 3.73 on the lightest surface); in light, the accent blue, green, amber and purple (4.18 to 4.45).
  Each was moved the smallest step that clears 4.5:1 everywhere (2 to 12% toward white or black; the hues are
  unchanged to the eye) and the light chart palette used for copied images follows. After: the lowest text
  contrast in either theme is 4.56. Chart series colours were already 4.2:1 or better against every card surface,
  above the 3:1 graphics need.
- **No sideways scroll on a phone.** Every view loaded at 390 px wide and the page's scroll width compared with
  the window: the Usage sub-nav (six pills) pushed five views 7 to 8 px wide. It now wraps to two lines under
  900 px, which also settles the "sub-nav on narrow screens" item deferred in §78. After: zero overflow on all
  eleven views. Wide tables and the calendar keep scrolling inside their own boxes, as before.

Ask bar test 311 of 311.

**Not done:** a session with an actual screen reader (VoiceOver, NVDA). The checks above are by script and
measurement; how a screen reader announces the hidden tables and the canvases' names should be heard once
before this item is called closed. Colour as the only channel: a search for multi-series charts with the legend
hidden finds two, the topic-mix dumbbell and the topic-mix gap; the first names its two colours in its title
("AskCI citations (green) vs site browsing (purple)") and the second encodes by position (left and right of
parity), so no chart is left where colour carries meaning with no words beside it.

## 85. The Before / after table on the change report's windows (27 Oct 2026)

Noted in §79 and decided by the analyst: the Before / after table counted the event day as the first day of
"after" (14 Sep to 11 Oct for the 14 September change), while the change report and the Quality view's outcome
chart leave it out (15 Sep to 12 Oct). The table now uses the same rule through the same function
(`eventWindows()`): the 28 days before the event, and the 28 days after it starting the day after the event, or
the day after its end date when it has one. The event day belongs to neither window, so a part-day of the old
model or wording no longer counts as "after". The card's note says so.

What moved, after window only (before windows are unchanged):

| Event | After window, was → now | Turns a day | Generation p / turn | Answered | Response p50 |
|---|---|---|---|---|---|
| 9 Mar model change (ends 10 Mar) | 9 Mar–5 Apr → 11 Mar–7 Apr | 169 → 171 | 0.66 → 0.65 | 86.8 → 86.5% | 15.8 → 16.4 s |
| May Search cost step (month only) | 1–28 May → 1–28 Jun | 460 → 725 | 0.57 → 0.51 | 83.2 → 83.1% | 13.2 → 11.3 s |
| 11 May Modal launch | 11 May–7 Jun → 12 May–8 Jun | 675 → 690 | 0.55 → 0.55 | 82.3 → 82.2% | 12.1 → 12.0 s |
| 20 May Modal step | 20 May–16 Jun → 21 May–17 Jun | 771 → 769 | 0.55 → 0.55 | 83.0 → 82.9% | 11.3 → 11.3 s |
| 1 Jul model change | 1–28 Jul → 2–29 Jul | 577 → 577 | 2.92 → 2.95 | 88.5 → 88.8% | 12.5 → 12.5 s |
| 14 Sep model change | 14 Sep–11 Oct → 15 Sep–12 Oct | 851 → 860 | 1.43 → 1.37 | 77.8 → 77.4% | 11.4 → 11.3 s |

Most rows move by a few hundredths. The one large move is the Search cost step, which is dated to a month: the
whole of May is now the event, and "after" is June, where before it was May itself, the month in which the step
happened on a day nobody has recorded. That is the honest reading for a month-dated event; giving it a day in
`events.json` would let it use 28 days either side of that day instead. Ask bar test 311 of 311.


## 86. Daily series at full width (27 Oct 2026)

Measured every side-by-side pair in each view at 1508 px: the cramped ones were the daily series. At half width a
chart of the full range gives each of 296 days about 2 px, and the event labels overlap. Three changes:

- **Overview**: Conversations by source and Outcome mix now sit one above the other at full width.
- **Quality, Outcomes over time**: Cited answer rate and Not-found rate, likewise; a model change now falls at the
  same x in both.
- **Cost Summary**: the Fixed / variable / generation chart (170 px) and What changed no longer share a row. What
  changed set the row's height (about 1,440 px), which left about 1,250 px of the chart's card empty. Both are now
  full width, the chart taking only its own height.

Stacked pairs share a fixed y-axis width (`alignY()`, 56 px), so their plot areas start and end at the same x
(checked: identical chart areas in the day, week and month views). Everything else stays paired: ranked
horizontal bars of 4 to 15 items, short categorical bars, the 12-point scenario charts, the AskCI citations / site
views pair (side by side so they can be read across) and the table pairs, which are long rather than narrow. Rule
for new cards: a daily series gets the full width; a ranked or categorical chart can share a row. Phones were
already one column. Ask bar test 311 of 311.

## 87. The data status bar (27 Oct 2026)

The data-quality strip (19 items over four lines) and the amber caveat paragraph sat above the Ask bar on every view
and pushed it to 422 px down a 873 px window. They are now one bar of two lines (68 px; the Ask bar starts at 273 px):

- **Line 1**: the latest billing day, the settled-to day, provisional days, the config version and the number of
  amber items ("6 items need attention" today: the unclassified meter, outcome rules, derivation, what people ask,
  prompts, events awaiting confirmation), with **Data status ›**.
- **Line 2, the caveat in one sentence**, kept on screen: "Outcome figures from 14 Sep, what people ask, and the
  quoted-figures check are read by rule and not yet checked by a reader", built from the same three conditions as the
  full paragraph, with **Why ›**. It goes when the labelling sheet is scored, as the paragraph does. It is not hidden
  behind a click because it is the warning a reader who never clicks most needs.

Both open the Data status panel: the full caveat paragraph, then every strip item as a row, amber items first under
"Needs attention", each with the explanation that was a hover tooltip now in visible text (so touch and keyboard
readers get it too). The panel is a dialog under the focus manager (§84): focus moves in, Tab is kept inside,
Escape closes it and focus returns to the button that opened it (checked for both buttons). On a phone the
config version drops from line 1 and each button sits under its text; no sideways scroll. Printing shows the panel
in full instead of the bar, black on white whatever the theme (checked by applying the print rules on screen;
not test-printed on paper). Ask bar test 311 of 311.

## 88. Funnel plot of not-found by category, and the four kinds of page as a 2×2 (27 Oct 2026)

From a review of what could be shown better (the order agreed: funnel and 2×2 first, then partial by intent per page,
the transition grid, cited against clicked, lost and gained).

**Not-found rate against volume, by category** (Questions view, above "One category, from the question"). A funnel
plot: each category's typed questions across on a log scale, its not-found share up, the pooled rate as a line, and
95% and 99.8% limits that narrow as volume grows, so "outside the funnel" is the claim and a small category far from
the line is not evidence by its size. Category is the broad cut from the question (`question-categories-monthly.csv`:
the answer cited the category, the question named a page in it, or its topic gives it), not the answer-attributed
category, which drops most failed answers. Months overlapping the range; categories with 5+ questions; points labelled
directly; a click opens the category below; the table sits under "Show the table"; the outcome-rule note is in the
title when the months reach 14 Sep.

Overdispersion. With plain binomial limits 9 of 15 categories fell outside (the limits on 42,000 Social Welfare
questions are a fraction of a point wide), which says only that categories differ. The limits are widened by
sqrt(phi), phi the mean squared z-score winsorised at the 10th and 90th percentiles (Spiegelhalter 2005); phi is 21.7
on the full range, so the limits are 4.7× the binomial ones, and the card states both. Outside the widened funnel on
the full range: Justice above (8.1% of 3,318) and Returning to Ireland below (0.9% of 3,104). Housing, Health and
Employment are above the line and inside the funnel. Descriptive: above the funnel means failing more than size and
the usual spread between categories explain, not why.

**The four kinds of page as a 2×2** (Pages view, above the four tables). Pages are the headline in every box, because
"cited, never named" can only count pages; underneath, each box gives its own unit: questions naming the pages for the
three named kinds (28,513, 3,398 and 207 on the full range), citations for the never-named one (29,240). Each box is a
button that scrolls to its table. No axes: three of the four kinds are "named", so they are not two crossed
dimensions, and the boxes keep the tables' order.

Both charts have their table in the page and an aria-label naming where it is (`pointLabels` is a new direct-label
plugin that skips a label that would overlap; the table has every row). No sideways scroll at 390 px. Ask bar test 311
of 311.

## 89. The two unused files: partial by intent per page, and the weekly named-page hit rate (27 Oct 2026)

`citations-intent-monthly.csv` and `asked-pages-weekly.csv` were built by make_usage.py and read only by the register
tool and the Ask bar test. Both are now on the page, each in the form that suits it.

**Says something is missing, by what was asked** (Pages view, after "Answers that say something is missing, by
page"). Pages cited in 100+ answers in the months in range, by volume; columns are the page's share overall and then
one per intent of the question (those with at least one cell passing the small-sample rule). Each cell is the share of
the page's answers to that kind of question that said something was missing, shaded on one amber scale; a cell under
the rule is a dash with the counts on hover; a cell at 1.5× the page's own share or more is outlined (37 on the full
range). The intent mix alone would hide the useful reading, which is a page fine overall and failing one kind of
question: Housing Assistance Payment is 17% overall and 36% on rate questions, the housing pass's finding (the rates
table is not being read). Both rule notes are in the title: intent by rule from the question, not yet reader-checked,
and partial by rule, unvalidated from 14 Sep. A question that cites several pages counts once for each.

**Named-page hit rate, week by week** (Questions view, after "Where the question named a page"). Per page the weekly
file is too thin (the 30-a-month threshold is about 7 a week, so most cells would be dashes); summed over its pages it
is one weekly line: the share of typed questions naming a page whose answer cited it or a page beneath a named hub,
with not found beside it. Whole weeks inside the data only (5 Jan to 12 Oct on the full range); a week under the
small-sample rule is a gap; confirmed events as lines. It shows a change within days rather than months, which is what
the register's closure measurement needs. On the full range the not-found share of named-page questions steps from
about 3% to about 9% in the week of 14 Sep while the hit rate holds near its summer level. The per-page tables stay
monthly. Ask bar test 311 of 311.
