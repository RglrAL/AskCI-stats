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

Dates are in the feed's own timezone, which is unconfirmed; note that in the file's header comment. Do not add any other column from the feed; only daily aggregates cross into this tool.

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

## 11. Implementation status (1 Oct 2026, first pass)

Done in `index.html` (config version `2026.10.01-1`) and `events.json`:

- Section 2, all eleven defects: full-row de-duplication with the count reported; one meter-based classification in `CONFIG`; cache savings and the ×3 ratio removed; one forecast function (`forecastSpan` / `forecastMonth` / `runRate30`) used by the hero, KPI row, Ask bar and report; ROI grid, "cheaper per question" and launch narrative removed; Scenario planner demoted with assumptions stated and no break-even volume; launch heuristic removed; anomaly detection replaced by What changed; browser-side API key and model call removed; date validation with refusal above 1% bad dates; lucide pinned to 1.49.0.
- Section 4: `CONFIG`, ingest, join window, per-turn metrics (sum then divide, validity thresholds), What changed, forecast.
- Section 5: `events.json` seeded as specified; detected model events shown in the Events popover and drawn nowhere; personal markers dashed.
- Section 6, partly: data-quality strip; Before / after table replaces Launch impact; resource inventory with scope and region added to Services. The tab regrouping (Cost: Summary | Services | Models) is deferred; the current Overview + Costs (Trend, Services, Models) + Usage + Scenario planner grouping carries the same content.
- Section 8: all acceptance checks pass on the frozen file, with two corrections to the table: the proposed dedup key `date|resourceId|meter|rawCost` removes 87 Azure Monitor email rows that differ only by region (value £0.0016), so the implementation de-duplicates on the full row; March generation cost per turn is 0.76p, not 0.73p; "other" is £67.36 by rounding.

Not done:

- Section 7: `usage.csv` is not regenerated from the QA feed (the local feed stops at 7 June; the file in the repo runs to 13 September). The parser now accepts the file's "Sept" dates, which the old parser silently dropped.
- Section 6 tab regrouping and the service / admin / shared scope toggle on charts (scope is computed and shown in the inventory only).
