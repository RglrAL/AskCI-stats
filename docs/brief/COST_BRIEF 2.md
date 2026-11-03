# AskCI cost data brief (v3)

Prepared 1 Oct 2026. Revised 1 Oct 2026 after two review rounds. Context for an agent integrating the Azure cost export into the AskCI Analytics Dashboard spec (producing spec v4 from v3). Sections 1 to 4 are data facts from the export and are unchanged from v1 except where marked. Sections 5 to 7 are the agreed integration.

Summary of the decision: cost has two roles. It is a separately scoped financial view with its own tab, filter contract and validity rules, and it is a source of established infrastructure and model events that enrich the QA-feed timeline. The two pipelines meet only at calendar-day grain and are never merged into one analytical table. A failure in the cost pipeline never affects the QA-feed tabs.

## 1. What the file is

`costs.csv` in the working directory. An Azure Cost Management daily export for the production resource group `rg-askci-prod`, which hosts the AskCI chatbot and its admin dashboard.

| Property | Value |
|---|---|
| Rows | 12,714 |
| Grain | One row per UsageDate, ResourceId and Meter |
| Date range | 1 Jan 2026 to 17 Aug 2026, 229 days, no missing days |
| Date format | DD/MM/YYYY |
| Currency | GBP in `Cost`, with a `CostUSD` column (implied rate 0.746) |
| Columns | UsageDate, ResourceId, ResourceType, ResourceLocation, ResourceGroupName, ServiceName, Meter, CostUSD, Cost, Currency |
| Pricing model | Consumption meters throughout; no PTU (provisioned throughput) meters |
| Zero-cost rows | 441 (Key Vault operations and similar); no negative rows |

Not present: any quantity or unit-of-measure column. Token counts cannot be derived. Model name and token type (input, cached input, output) are only readable from the `Meter` text.

Added in v2: the export is stale relative to the QA feed. Cost ends 17 Aug 2026; the QA feed runs to 28 Sep 2026. Until a refreshed export arrives, the Cost tab is historical, not operational, and the join window for ratios is 1 Jan to 17 Aug. August in this file means 1 to 17 August and must be labelled "Aug 1–17" wherever it appears.

## 2. Totals and composition

Total 1 Jan to 17 Aug, whole resource group (scope: all): £4,537.71 ($6,079.76).

| ServiceName | GBP | Share | Main resource |
|---|---|---|---|
| Azure Cognitive Search | 2,080.93 | 46% | srch-askci-prod (S1 units £1,963 + semantic ranker £118) |
| Foundry Models (Azure OpenAI) | 1,167.03 | 26% | oai-askci-prod |
| Azure Container Apps | 917.00 | 20% | backend £472, background £144, frontend £134, admin backend £101, admin frontend £67 |
| Virtual Network | 242.72 | 5% | six private endpoints at about £40 each |
| Bandwidth | 62.68 | 1% | storage account egress |
| Defender, Registry, Storage, Monitor, Cosmos, Key Vault | 67.35 | 1% | |

Fixed versus variable, by meter: fixed £3,049.52 (67%), variable £1,488.20 (33%). Fixed meters are Search S1 Unit, container idle memory and idle vCPU, private endpoints, Defender nodes, registry unit, alert rules. Container idle charges alone are £784 of the £917 Container Apps total.

Daily total: median £15.34, range £2.25 to £44.85.

## 3. Generation (Foundry Models) detail

Meters by model family and first/last billed day:

| Model family (from meter text) | First day | Last day | GBP |
|---|---|---|---|
| gpt-4o 1120 (input, cached input, output) | 1 Jan | 9 Mar | 42.7 |
| gpt-4o-mini 0718 | 1 Jan | 9 Mar | 1.9 |
| GPT 5 Chat (input, cached input, output) | 1 Jan | 30 Jun | 279.8 |
| GPT 5 Mini | 9 Mar | 17 Aug | 66.1 |
| GPT 5 | 10 Mar | 17 Aug | 4.9 |
| chat-latest 05052026 (input, cached input, output) | 1 Jul | 17 Aug | 771.5 |
| text-embedding-3-small | 1 Jan | 17 Aug | 0.07 |

Two meter transitions are visible: 9 to 10 March (gpt-4o family last billed, GPT-5 Mini and GPT-5 first billed) and 1 July (GPT-5 Chat last billed, chat-latest 05052026 first billed). First and last days that coincide with the edges of the file (1 Jan, 17 Aug) say nothing about additions or retirements. Embedding cost is negligible.

Added in v2, approximate daily run-rates derived from the totals above (recompute from the file): GPT 5 Chat about £1.55/day Jan to Jun; gpt-4o 1120 about £0.63/day Jan to 9 Mar; GPT 5 Mini about £0.41/day from 9 Mar; chat-latest about £16/day from 1 Jul; GPT 5 and gpt-4o-mini about £0.03/day each. So the highest-spend meter (GPT 5 Chat) was unchanged in March; the March transition is in the second-tier meters. What each deployment does in the AskCI architecture is not established by the billing data and is an OGCIO question (section 6). Billing confirms meter transitions, never a deployment's product role. Do not describe any deployment's role in the spec.

Monthly generation unit cost per turn, joined to the QA feed by day (pence): Jan 1.06, Feb 1.02, Mar 0.73, Apr 0.66, May 0.56, Jun 0.49, Jul 2.94, Aug 1–17 2.80. The July transition raised generation unit cost about sixfold. This measure moves with model prices, prompt and output length, model mix and workload, so it is a unit cost, not an efficiency measure.

Total cost per conversation (pence): Jan 14.0, Feb 16.9, Mar 16.5, Apr 16.2, May 9.2, Jun 6.4, Jul 11.8, Aug 1–17 11.2. The fall in May and June is volume spreading fixed cost, not efficiency.

Cached-input meters exist for the three main families. Without quantities, the cached share of input cost understates the cached share of input tokens, because cached input is priced below ordinary input. Call it cached-input billed-cost share and never a cache hit rate.

## 4. Other observations

- Search S1 daily cost stepped from about £6 to about £11 in May 2026. The step is established in the billing data; the explanation (replicas or partitions for the Modal launch) is a hypothesis until OGCIO confirms.
- Day-level correlation between generation cost and feed turns is 0.58 at zero lag, 0.49 and 0.51 at plus or minus one day. Consistent with billing day matching feed day, but not proof.
- Weekday share of generation cost tracks weekday share of turns closely.
- The Foundry Models resource bills in Sweden Central with global deployments. Every other resource is in North Europe. The public AskCI page states the service is hosted in North Europe. The billing file alone does not establish where inference was processed; see section 6.
- Legacy dashboard cross-check: its token-estimated $41.90 for 29 Mar to 26 Apr compares with $43.54 billed for the same window. This is evidence that token and model information existed in the previous implementation, not proof that per-turn values are retrievable as a feed today.
- Added in v2, coincidences with the QA feed timeline (facts, not causes): the March meter transition falls in the same month as the clarification step from 0.4% to 2.5% of turns and the start of the latency incident (p50 14.2 s in March, 20.9 s in April). The July transition shows no clarification step in the QA feed (6.32% in June, 6.69% in July). The September clarification step (4.7% to 6.8%) cannot be checked against billing because the export ends 17 August.

## 5. How the spec uses it

### 5.1 Pipeline

Update the Data pipelines and freshness table in the spec:

| Field | Value |
|---|---|
| Source | Azure Cost Management export for `rg-askci-prod`; today a one-off CSV, target a scheduled daily export to storage. The scheduled export is a pipeline dependency and must exist before the tab goes live |
| Cadence | Daily, with 24 to 48 h settlement lag and possible restatements (both to confirm) |
| Grain | Day by resource by meter. No quantities |
| Currency | GBP as billed. `CostUSD` is stored for reconciliation and never displayed |
| Filters honoured | Date range and granularity only |
| Freshness line | "Azure cost through 17 Aug 2026 (settled through 14 Aug)" until refreshed; hidden entirely when the pipeline is not configured |
| Billing status | Every billing day carries `billing_status` = provisional or settled. A day is provisional until it is more than `SETTLEMENT_DAYS` (initially 3, to confirm) before the latest billing day. Provisional days draw on billed-cost charts with shading and are excluded from allocated ratios, comparisons and What changed by default. Status is set by age, not by whether the value changed |
| Restatements | Re-ingest replaces the day's rows. A change to a day already marked settled is counted in ingest health as "restated settled days"; a non-zero count means the settlement window is wrong |
| Schema | Must accept negative `Cost` rows (credits, corrections, restatements) as data. "No negative rows" is a fact about the frozen fixture, not a validation rule |
| Join window | Ratios are computed only on calendar days that are complete in the QA feed and settled in billing. The window is shown on the Cost tab: "Ratios cover 1 Jan to 14 Aug 2026" once settlement is applied to the frozen file; the fixture in 5.6 states the window it was computed on |
| Partial periods | A calendar month or preset that is not fully covered by settled join days is labelled with its actual span ("Aug 1–17"). Comparisons are made only between equivalent complete windows, never full July against part of August |
| Failure | A failed cost load leaves the previous load in place, turns the cost freshness line red and writes to ingest health. It never affects the QA-feed tabs |

### 5.2 Events registry

The billing pipeline is a source of candidate events; a person makes them authoritative.

Status semantics. Add `status` to the events registry with three values. `confirmed` means the event is established as having happened, whether or not its cause is known; causes that are hypotheses go in the detail field, per the existing title rule. `candidate` is reserved for events detected automatically and awaiting a human look. `rejected` keeps the record of what was looked at and dismissed. Add an `evidence` field (free text, for example "Azure billing export, meter first billed 1 Jul"). Charts draw confirmed events only; candidates appear in an admin queue in the registry UI. Every existing v3 seed row is `confirmed`, since each records something observed in the data.

What billing confirms. A meter or model-family billing transition. It never confirms a deployment's product role, so no event title says which model answered users.

Automated detection. Billing ingest emits candidates for model-family additions and retirements, subject to these rules, all configuration:

- Cumulative cost threshold `MODEL_EVENT_MIN_COST` (initially £10) before any candidate is emitted for a family. Keeps stray test calls out of the queue. GPT-5 at £4.90 and gpt-4o-mini at £1.90 fall below it.
- No "added" candidate when a family's first billed day is the first day of available history.
- No "retired" candidate when a family's last billed day is the latest billing day or falls inside the settlement window.
- Gap tolerance `MODEL_EVENT_GAP_DAYS` (initially 7): a family absent for fewer days than this and then billed again is not retired and re-added; a "retired" candidate is emitted only after the gap exceeds the tolerance beyond the settlement window.
- Meters that match no entry in the model-family lookup are not eligible for events; they are reported as unparsed (5.5).

Capacity steps in fixed meters (the Search change in May) are manual seed rows, not automated.

Seed rows to add or change in spec v4:

| Start | End | Kind | Status | Evidence | Applies to | Title and detail |
|---|---|---|---|---|---|---|
| 9 Mar 2026 | 10 Mar 2026 | model | confirmed | Azure billing export | outcomes, latency, cost | gpt-4o 1120 and gpt-4o-mini last billed 9 Mar; GPT-5 Mini first billed 9 Mar, GPT-5 first billed 10 Mar. Detail: coincides with the clarification step and the start of the latency incident; relationship unconfirmed; deployment roles unknown. Replaces the v3 "observed change, prompt change suspected" row for March |
| May 2026 | | observed change | confirmed | Azure billing export | latency, cost | Search S1 daily cost steps from about £6 to about £11. Detail: capacity increase for the Modal launch suspected, unconfirmed |
| 1 Jul 2026 | | model | confirmed | Azure billing export | outcomes, latency, cost | GPT 5 Chat last billed 30 Jun; chat-latest 05052026 first billed 1 Jul. Detail: generation unit cost 0.49p per turn in June to 2.94p in July; before/after analysis per 5.7 |

The v3 September "observed change" row stays as it is; billing data for September does not exist yet.

### 5.3 Cost tab

Shown only when the pipeline is configured. Banner: "Azure billing data, GBP as billed. Date range and granularity apply; source, category, outcome and starter-prompt filters do not. Meter classification and resource scope are configuration. Per-turn and per-conversation figures are allocated daily ratios over settled days, not request-level costs. Ratios cover [join window]. Provisional days shaded." The tab has its own freshness line, its own What changed and its own validity rules (5.4).

Tile order, replacing the v3 Cost table:

| Tile | Type | Content |
|---|---|---|
| Generation unit cost | Line, by period | Allocated generation cost per turn over settled join days. Confirmed model events annotated. Provisional days shaded and excluded from the line. Partial periods labelled with their span |
| Fixed, variable and unclassified cost | Stacked bar, by period | From the versioned meter classification. Unclassified is its own band and never folded into variable. Shows why total unit cost falls with volume |
| Cost by service | Stacked bar, by period | Search, Foundry Models, Container Apps, Virtual Network, Bandwidth, Other |
| Generation cost by model and meter type | Stacked bar | Pounds billed per model family, split input / cached input / output, parsed from meter text through the lookup table. Unparsed generation meters shown as their own band. Replaces the v3 "Tokens by meter and deployment" tile, which cannot be built: the export has no quantities |
| Cached-input billed-cost share | Small number, per family and overall | Tooltip states that cost share understates token share because cached input is priced lower |
| Allocated unit economics | Table | Total, variable and generation cost per turn and per conversation over the settled join window, labelled allocated, with the window and the day count shown |
| Cost by resource | Table with drill-down | Service to resource to meter, within the tab. Scope toggle: service (default), admin, shared, all |
| Resource inventory | Static table | Resource, service, region, cost, share, scope. Low on the page. Carries a governance badge on the Foundry resource until the deployment-type question is answered |
| What changed (cost) | Up to three computed statements | Date and granularity only. Candidates: generation unit cost, total billed cost, variable cost. Materiality: 10% or 0.2p per turn for ratios, 10% for totals, all configuration. Compares equivalent complete settled windows only. Never merged into the Overview's What changed |

Chart clicks on this tab open the daily meter and deployment detail for the clicked day. They do not open the Explorer.

Do not add a USD toggle, a USD KPI or any converted figure.

### 5.4 Metric definitions and validity rules

| Metric | Numerator | Denominator | Notes |
|---|---|---|---|
| Billed cost | Sum of `Cost` over the period, settled and provisional, provisional shaded | | GBP. Scope per the toggle, default service |
| Fixed cost share | Cost on fixed-class meters | Billed cost | Classification is versioned configuration; unclassified cost is reported separately and is in neither numerator nor share |
| Allocated total cost per turn | Billed cost summed over settled join-window days in the period | Turns received on those days | Summed then divided; never a mean of daily ratios |
| Allocated variable cost per turn | Cost on variable-class meters, same window | Turns received on those days | |
| Generation unit cost (allocated generation cost per turn) | Foundry Models generation meters, same window | Turns received on those days | The headline cost metric. A unit cost, not an efficiency measure |
| The same three per conversation | As above | Conversations started on those days | |
| Cached-input billed-cost share | Cost on cached-input meters | Cost on all input meters | Per model family and overall; understates token share |

Remove the two v3 metrics "Allocated cost per turn" and "Allocated cost per conversation", superseded by the three-way split.

Validity rules for the Cost tab, replacing any reference to the Overview's small-sample rule. Billed pounds are not a sample, so the numerator guard does not apply. Three rules do:

- An allocated ratio for a period is shown only if the period has at least `MIN_SETTLED_JOIN_DAYS` (initially 7) settled join days; otherwise a dash with the day count in the tooltip.
- An allocated ratio is shown only if its denominator (turns received or conversations started over those days) is at least `MIN_RATE_DENOMINATOR` (50, shared with the QA tabs); an outage day with a handful of turns is noise.
- A What changed statement is emitted only when both windows pass the two rules above and the delta passes the materiality threshold.

### 5.5 Configuration (versioned, shown in ingest health)

- Meter classification: every meter is `fixed`, `variable` or `unclassified`. Initially fixed = Search S1 Unit, container idle memory, container idle vCPU, private endpoints, Defender nodes, registry unit, alert rules; variable = the remaining meters in the frozen file, listed explicitly. A meter not in either list is unclassified, raises an ingest-health warning and is shown as its own band until someone classifies it. Never "fixed list, everything else variable".
- Model-family lookup: maps `Meter` text to a family (gpt-4o 1120, gpt-4o-mini 0718, GPT 5 Chat, GPT 5 Mini, GPT 5, chat-latest 05052026, text-embedding-3-small) and a meter type (input, cached input, output, embedding). A generation meter matching no entry is unparsed, raises a warning and is shown as its own band.
- `cost_scope` per resource: service, admin, shared. Proposed initial mapping for CIB to confirm: service = srch-askci-prod, oai-askci-prod, backend, background and frontend container apps; admin = askci-admin backend and frontend container apps (£168 to date); shared = virtual network and private endpoints, Key Vault, registry, Defender, Monitor, storage and bandwidth, Cosmos. A resource not in the mapping is unassigned, raises a warning and is shown separately. Default view is service; admin, shared and unassigned are always visible as separate figures, never silently folded in.
- `SETTLEMENT_DAYS`: 3. `MODEL_EVENT_MIN_COST`: £10. `MODEL_EVENT_GAP_DAYS`: 7. `MIN_SETTLED_JOIN_DAYS`: 7. Cost materiality thresholds.

Ingest-health panel additions for the cost pipeline: latest billing day; latest settled day; provisional days in the current load; restated settled days; unclassified meters; unparsed generation meters; unassigned resources; candidate events awaiting review; meter classification, lookup and scope versions.

### 5.6 Fixture (extend Data quality and acceptance tests)

Scope statement, so nobody reads the default view as a failed test: every fixture total below is `scope: all`, the whole resource group. The default Cost tab view is `scope: service`, which will show a smaller number by design. Per-scope totals are added to the fixture once CIB confirms the mapping; until then the fixture asserts that service + admin + shared + unassigned equals the all-scope total.

Hard assertions on the frozen `costs.csv`:

| Assertion | Expected |
|---|---|
| Rows | 12,714 |
| Billing days, first, last, missing | 229; 1 Jan 2026; 17 Aug 2026; 0 |
| Total `Cost` / `CostUSD`, scope all | £4,537.71 / $6,079.76 |
| Zero-cost rows; negative rows | 441; 0 |
| Service totals | Search £2,080.93; Foundry Models £1,167.03; Container Apps £917.00; Virtual Network £242.72; Bandwidth £62.68; other £67.35 |
| Fixed; variable; unclassified; fixed + variable + unclassified = total | £3,049.52; £1,488.20; £0.00; within rounding |
| Unparsed generation meters; unassigned resources | 0; 0 |
| Scopes sum to total | service + admin + shared + unassigned = £4,537.71 within rounding |
| Model family first and last billed day | As the table in section 3 |
| Monthly generation unit cost, Jan to Aug 1–17 (pence), computed on all 229 join days as in v1 | 1.06; 1.02; 0.73; 0.66; 0.56; 0.49; 2.94; 2.80 |
| Settled join window at `SETTLEMENT_DAYS` = 3 | 1 Jan to 14 Aug 2026, 226 days; the series above recomputed on this window is frozen on first run and replaces the v1 series for UI acceptance |
| Candidate events emitted at £10 threshold with edge rules | Exactly four: gpt-4o 1120 retired 9 Mar; GPT 5 Mini added 9 Mar; GPT 5 Chat retired 30 Jun; chat-latest added 1 Jul. No "added" for 1 Jan families, no "retired" for 17 Aug families, nothing for GPT 5 or gpt-4o-mini |
| Partial-period labelling | August renders as "Aug 1–17" on every tile |

Diagnostic, reproduced on the frozen fixture but not asserted on live data: generation cost to turns correlation 0.58 at zero lag, 0.49 and 0.51 at plus or minus one day.

### 5.7 Analysis task (not a tile)

Before/after 1 July 2026, descriptive only: median and p90 latency, partial-answer rate, cited-answer rate, clarification rate, median response length, likes and dislikes per 1,000 cited answers. Compare the complete month of June against the complete month of July; treat August as 1–17 and report it separately. Record the result in the events registry detail for the July row. Do not frame it as what the extra cost bought unless the deployment change can be isolated from other changes in the same window.

## 6. Open questions the data raises (priority order)

1. **Refresh and schedule the export.** Re-export through the current date and set up the scheduled daily export. Without this the Cost tab is a historical report and the September clarification step cannot be checked against billing.
2. **Per-turn tokens and model in the QA feed.** Ask OGCIO whether the AskCI platform already logs input, cached-input and output tokens and the model or deployment per turn (the legacy tile's 4% reconciliation suggests something is recorded). If so, expose them in the QA feed; if not, add them prospectively. This enables a second cost concept, estimated request cost per turn that follows source, category and outcome filters, reconciled monthly against billed cost. It is the stronger ask; UsageQuantity in the billing export only gives daily aggregates.
3. **What each deployment does.** Ask OGCIO which deployment answers the user, and what GPT-5 Mini, GPT-5 and the earlier gpt-4o deployments were used for. Needed before any March coincidence can be interpreted.
4. **Foundry resource deployment type and region.** Confirm the deployment type (the export indicates global deployments, a type with documented cross-region inference routing), where inference is processed, whether an EU data-zone deployment was considered, and whether the public "hosted in North Europe" statement and the DPIA cover it. Escalate to OGCIO and the DPO; the dashboard records the fact and draws no conclusion.
5. **Settlement window and restatements.** Confirm how many days back a daily export can change and how restatements arrive. Sets `SETTLEMENT_DAYS`; "restated settled days" in ingest health will show if the value is wrong.
6. **Billing-day timezone** against the feed's timestamp timezone (itself unconfirmed). The 0.58 zero-lag correlation is consistent with same-day alignment. At daily grain a one-hour offset is immaterial; document, do not block.
7. **Resource scope policy.** CIB to confirm the proposed service / admin / shared mapping, and whether "AskCI cost" reported to management is service only. Per-scope fixture values are frozen on confirmation.
8. **Meter naming stability.** Ask whether Azure meter names for the Foundry resource change with model versions, so the lookup table can be kept current and unparsed meters stay at zero.
9. **UsageQuantity and UnitOfMeasure.** Still worth requesting in the export as a fallback to item 2; it would allow token volume and cost per million tokens on the Cost tab.

## 7. Reproduction notes

pandas in a venv; read with `dtype=str`, parse UsageDate with `%d/%m/%Y`, cast Cost and CostUSD to float, allow negatives. Mark days within `SETTLEMENT_DAYS` of the latest billing day as provisional. Join to the QA feed on calendar day and restrict every ratio to days that are complete in the QA feed and settled in billing. Sum cost and sum turns over the window before dividing. Meter classification, model-family lookup and cost_scope are configuration files beside the script, never inferred; anything unmatched is reported, not guessed. Label any partial month with its span.

## Changes from earlier versions of this brief

v2 (first review round): staleness and join window stated; run-rates added; deployment roles out of scope; coincidences with the QA timeline recorded as facts; section 5 rewritten around the two-role framing, candidate/confirmed events, removal of the tokens tile, three-way allocated metrics, GBP only, cost-only What changed, configuration and fixture; section 6 prioritised with the tokens question redirected to the QA feed.

v3 (second review round):
- Provisional versus settled billing days, with provisional days excluded from ratios and comparisons; restated settled days as a health signal.
- Edge-of-file and gap-tolerance rules for automated event detection; candidate events now exactly four on the fixture.
- Status semantics fixed: confirmed means established, candidate means auto-detected awaiting review; evidence field added; the May Search row corrected to observed change, confirmed.
- Meter classification is fixed / variable / unclassified; model-family lookup reports unparsed meters; resource scope reports unassigned resources.
- Fixture scope stated as all; per-scope totals deferred to confirmation; scopes must sum to total.
- "Generation unit cost" replaces "efficiency metric"; "cached-input billed-cost share" with the understatement caveat.
- Partial calendar periods labelled with their span; comparisons only between equivalent complete settled windows.
- Cost tab given its own validity rules in place of the Overview's small-sample rule, keeping only the denominator guard.
