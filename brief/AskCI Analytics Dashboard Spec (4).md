# AskCI Analytics Dashboard Spec

Sep 30, 2026 · @Alan O'Connor

## Purpose and scope

The redesigned dashboard answers three questions for the Citizens Information Board pilot team: is AskCI being used, is it answering successfully, and where is it struggling. It replaces the Analytics Dashboard in AskCI Admin 1.1.0-Pilot, which reports activity counts and has several broken tiles.

Users are the AskCI product team, the citizensinformation.ie content team, and CIB management. The content team needs a work queue of unanswered questions. Management needs a period summary with comparisons. The product team needs drill-down to individual conversations.

The data source is the QA feed: one row per turn, 14 columns, currently exported as CSV (113,410 turns and 56,365 conversations from 1 Jan to 28 Sep 2026). This spec consolidates four design and review rounds into one build document. Where the feed cannot support a feature, the spec says so rather than approximating.

## Design principles

Six rules govern every tile. A tile that breaks one is out of scope.

1. **Outcomes before activity.** Service metrics (cited answers, not-found, errors, latency, dislikes) lead every page, including the Overview KPI row. Product metrics (conversations, turns, channel, follow-up use) give context.
2. **One period everywhere.** Every number on a page, including any written summary, is computed from the same selected date range and filters. The header states that period in words.
3. **Deterministic metrics.** Every KPI is a count, ratio or percentile over stored fields or rule-derived fields. No model call decides a number that appears on screen.
4. **Every QA-feed chart lands in the Explorer.** Clicking a bar, segment or table cell opens the conversation list with the same filters applied, using internal drill-down predicates where the visible filters are not enough. Cost charts drill to daily meter detail instead, because billing rows do not identify conversations.
5. **Say what you can measure.** Use "ended after first turn", not "abandoned". Use "observed conversation span", not "session duration". Label estimates as estimates.
6. **Definitions are inspectable.** Every KPI has a tooltip and an entry in the metric definitions drawer, using the definitions in this document.

## Data model

All derivation happens at ingest. The dashboard reads two tables, `turns` and `conversations`, and never classifies text in the browser.

### Source feed

| Column | Type | Notes |
| --- | --- | --- |
| Conversation ID | UUID | Session key |
| Turn # | int | 1-based, max observed 52 |
| User Query | text | May contain personal data |
| Assistant Response | markdown | Empty on errors |
| Timestamp | text `Mon DD, YYYY HH:MM` | Minute precision. Timezone unconfirmed, see Open questions |
| Question Type | enum | new\_topic, user\_followup, suggested\_followup, blank |
| Categories | text | Comma-separated slugs with duplicates, derived upstream from citation URLs. Empty on every turn without a citation. Called "cited category" in the UI |
| Response Time (ms) | int | 0 on errors |
| Feedback | enum | like, dislike, blank |
| Flagged | enum | Yes, blank. Retired in the UI, see Outcome taxonomy |
| Report Subject, Report Description | text | 6 rows in 9 months |
| Citations | text | Comma-separated URLs |
| Source | enum | Web, Modal, Others |

### Ingest pipeline

1. Parse CSV with a proper parser (quoted multi-line fields). Trim whitespace. Store Timestamp as a timezone-naive `source_ts`. Derive local date, hour and weekday from configuration: `assumed_source_timezone` (initially Europe/Dublin) and `timezone_status` (unconfirmed or confirmed). Ingest runs regardless; hour-based tiles carry a badge while unconfirmed, and a change replays from `source_ts`. Daily totals can shift slightly at midnight on confirmation; document it, do not block on it.
2. Normalise citation URLs: lowercase host, strip trailing slash, strip query and fragment, collapse `citizensinformation.ie` to `www.citizensinformation.ie`. Do not collapse language variants until the corpus inventory says which URLs are the same document. Split into `citation_urls[]`, `citation_count`, `citation_internal_count`, `citation_domains[]`. Set `citation_valid` per URL against the corpus inventory once it exists; until then mark URLs with fewer than three path segments or truncated slugs as suspect.
3. Clean categories: split on comma, trim, de-duplicate, drop `all-categories` and `my-situation`. Store `cited_categories[]` and `primary_cited_category`. These are empty on every non-cited turn by construction.
4. Set `is_error` when Assistant Response is empty and Response Time is 0.
5. Classify `outcome` per the Outcome taxonomy section, including the Flagged residual rule, and store `outcome_rule_version`.
6. Set `is_partial` on Cited answer turns whose response matches the not-found pattern.
7. Set `is_starter_prompt` when the normalised query (lowercase, trimmed, trailing punctuation removed) matches an entry in the starter-prompt configuration in force on that date and Turn # is 1.
8. Set `cohort` = `pre_launch_modal` on Modal turns dated before the configured public launch date (initially 1 May 2026). These turns stay in all totals, are excluded from Web-versus-Modal comparisons by default, and the exclusion is noted on those tiles.
9. Set `query_script` from the Unicode script of the first alphabetic character (Latin, Cyrillic, Arabic, CJK, Devanagari, other). Set `language_estimate` and `language_confidence` from an offline detector; null below the confidence threshold.
10. Compute `query_words`, `response_words`, `has_feedback`, `feedback`, `has_personal_data_hint` (regex for PPS number, email, phone, Eircode, "my name is", "date of birth").
11. Set `attributed_category` per turn: its own primary cited category; otherwise the most frequent primary cited category among the other turns of the same conversation; otherwise Unknown. This recovers a category for 2,479 of the 5,949 not-found turns in the feed to date. A later cited turn can give an earlier failed turn its category, so attribution can restate until the conversation is mature.
12. Roll up `conversations`: `turn_count`, `first_ts`, `last_ts`, `observed_span_min`, `source`, `cohort`, `first_outcome`, `outcomes[]`, `categories_touched[]`, `category_transitions[]` (the sequence of primary cited categories over category-bearing turns with consecutive duplicates collapsed, so Employment → Social welfare → Employment is kept and Housing → Housing is not), `suggested_followup_count`, `user_followup_count`, `new_topic_count`, `has_starter_prompt`, `has_dislike`, `has_like`, `has_error`, `has_partial`, and `is_mature` (first\_ts at least `conversation_maturity_hours`, initially 24, before feed freshness). Source is asserted single per conversation; a violation sets `source` to Mixed, raises a health warning, and excludes the conversation from source splits rather than picking one.
13. Validate after merging the day's rows with stored rows, never on the increment alone. Failures that stop the load: parse failures and duplicate (Conversation ID, Turn #). Everything else warns with a threshold and shows in the ingest-health panel: a conversation without turn 1; a Flagged turn with a citation (the rule order already classifies it safely as a Cited answer); blank Question Type above 3%; Flagged turns matching the not-found pattern; Unknown attributed category above 20% of turns; citation coverage above 100%; Mixed-source conversations. Upstream Flagged logic is undocumented and has already changed; it must never be able to stop the dashboard updating.

Re-ingest is idempotent on (Conversation ID, Turn #). Keep the raw row alongside derived fields so a rule change or a timezone confirmation can be replayed from source.

## Events and configuration registry

Every time-series chart draws the same annotation layer from one events table that admins maintain in the UI. Without it nobody can tell whether clarification rose because the prompt changed or because Modal users ask vaguer questions.

| Field | Notes |
| --- | --- |
| Start date | Effective date, local |
| End date | Optional; present for incidents and regimes |
| Kind | launch, rollout, prompt, model, retrieval, chips, content, incident, regime, observed change |
| Applies to | all, outcomes, latency, volume, cost; controls which charts draw the annotation |
| Title | Short label shown on hover; states what was observed, never an unconfirmed cause |
| Detail | Free text, including any hypothesis about the cause |
| Source | Who recorded it and on what evidence |

Seed rows, from the feed and the public page:

| Start | End | Kind | Applies to | Title |
| --- | --- | --- | --- | --- |
| Dec 2025 |  | launch | all | Standalone site public launch |
| 5 Jan 2026 | 30 Apr 2026 | rollout | volume, outcomes | Pre-launch Modal rows in the feed; limited rollout or internal use, to confirm |
| Jan 2026 | Apr 2026 | regime | all | Office-hours usage pattern: 6% weekend share against 15% from May |
| Mar 2026 |  | observed change | outcomes | Clarification rate steps from 0.4% to 2.5% of turns. Detail: prompt change suspected, unconfirmed |
| Mar 2026 | Apr 2026 | incident | latency | Latency incident, p50 20.9 s in April, 20% of turns over 30 s |
| May 2026 |  | launch | all | Modal on every citizensinformation.ie page |
| Sep 2026 |  | observed change | outcomes | Clarification rate steps from 4.7% to 6.8%. Detail: prompt change suspected, unconfirmed |

Configuration with effective dates lives beside it: starter-prompt list, outcome rule set, small-sample constants, materiality thresholds, assumed timezone. Each has a version shown in the ingest-health panel.

## Data pipelines and freshness

Two pipelines feed the dashboard with different semantics. The header shows a freshness line for each.

| Pipeline | Source | Cadence | Grain | Filters honoured | Freshness line |
| --- | --- | --- | --- | --- | --- |
| QA feed | Export from the AskCI platform, today a manual CSV, target a scheduled daily job | Daily by 06:00 | Turn | All | "QA feed through 28 Sep 2026 23:59" |
| Azure cost | Azure Cost Management export | Daily, with 24 to 48 h settlement lag and possible restatements | Day by meter and deployment | Date range and granularity only | "Azure cost through 26 Sep 2026" |

A failed QA ingest leaves the previous load in place and turns its freshness line red. A failed cost load does the same for the Cost tab only. Both write to the ingest-health panel. Freshness target for the pilot: QA feed no older than 36 hours on weekdays.

## Outcome taxonomy

Every turn gets exactly one outcome. The word "Flagged" does not appear in the UI, but the stored field is used at ingest: a Flagged turn that matches no earlier rule is Out of scope.

| Outcome | Definition | Turns, Jan–Sep 2026 | Share |
| --- | --- | --- | --- |
| Cited answer | At least one citation | 97,594 | 86.05% |
| Not found | Response says the information could not be found | 5,949 | 5.25% |
| Clarification | Response asks the user to clarify or give more detail | 4,833 | 4.26% |
| Error | Empty response and 0 ms response time | 1,732 | 1.53% |
| Out of scope | Refusal by pattern, or legacy Flagged with no earlier match | 1,287 | 1.13% |
| Greeting | Greeting, thanks or chit-chat reply | 1,267 | 1.12% |
| Uncited answer | No citation, substantive response matching no rule | 748 | 0.66% |

Rules are applied in the order drawn below. Matching is case-insensitive on the response text.

&#91;embedded content: outcome classification · 6 rules, 7 outcomes\]

A turn that matches no rule and has no citation is an uncited answer, the only outcome reached by default.

| Outcome | Rule |
| --- | --- |
| Error | `Assistant Response` empty AND `Response Time (ms)` = 0 |
| Cited answer | `citation_count` ≥ 1 |
| Not found | matches `couldn't find\|could not find\|wasn't able to find\|no specific information\|not find specific\|don't have (specific )?information` |
| Clarification | matches `could you (please )?(clarify\|tell me\|let me know)\|what you mean\|more detail\|which (scheme\|payment)` |
| Out of scope, by pattern | matches `specialise in providing information\|specialize in providing information\|can't help with that (particular )?topic\|not able to help with that topic\|outside (the )?scope` |
| Greeting | matches `^(hello\|hi)\b\|how can i help\|you're welcome\|glad to help\|glad to hear\|glad you\|glad i could` |
| Out of scope, Flagged residual | `Flagged` = Yes |
| Uncited answer | none of the above |

The pattern rule sits before Greeting so a refusal that opens with "Hi" or "I'd be glad to help, but" is not swallowed as a greeting; the Flagged residual sits after it so a Flagged greeting stays a greeting. No turn in the feed matches both patterns today, and that is a fixture assertion.

These rules were run against all 113,410 turns and the counts above are the frozen fixture values (see Data quality and acceptance tests). Keep the patterns in configuration, version them, and store `outcome_rule_version` on each turn so a pattern change can be replayed.

The rule order is deliberate and was tested. Checking citations before the semantic rules keeps partial and hedged answers as answers. Reversing the order reclassifies 19,500 cited answers: 7,449 of them say "I couldn't find X specifically, but the closest page is..." and 12,029 say "it depends on what you mean" and then answer. Neither is a failure, and reversing would report not-found at 11.8% and clarification at 14.9%.

Partial answers are still worth seeing. Set `is_partial` on a Cited answer whose text matches the not-found pattern. It is a flag, not an outcome: 7,449 turns, 7.6% of cited answers. It appears on the Quality tab as "Cited but partial".

The Out of scope rule leans on the legacy Flagged field because the refusal patterns alone catch 212 of the 1,287 refusals; the bot phrases refusals many ways and in many languages. Using Flagged makes the taxonomy depend on upstream logic that is not documented and whose rate quadrupled during the pilot, so its provenance is an open question. Three invariants guard it at ingest: a Flagged turn with a citation raises a high-severity warning and is classified as a Cited answer by the rule order, a Flagged turn matching the not-found pattern raises a warning (3 today), and the monthly share of Clarification plus Greeting plus Out of scope must reproduce the known rise from 2.71% in January to 9.81% in September on the reference data. About 74 of the 1,287 are non-English clarifications labelled as refusals; the labelled sample in Open questions tightens this.

## Metric definitions

Each metric is computed over the turns or conversations inside the selected period and filters. Three cohorts are used and always named. **Turns received** are rows whose own timestamp falls in the period. **Conversations started** are conversations whose first turn falls in the period; conversation-depth metrics use the **mature** subset, whose first turn is at least `conversation_maturity_hours` (24) before feed freshness, and include turns that land after the period ends. In the feed 98.8% of follow-up turns arrive within an hour of the previous turn and 99.96% within 24 hours, so the window costs one day of latency and removes the bias that would otherwise make the newest period look more single-turn. **Scored turns** are turns received excluding Greeting, Error and Out of scope, and are the denominator for quality rates so that chit-chat, outages and refusals do not dilute them.

Two words are used consistently. A **share** is one of a set of compositional percentages that sum to 100%, such as the seven outcome shares that drive every mix chart. A **rate** is any other KPI ratio with its stated denominator, which keeps conventional names like error rate and feedback rate.

| Metric | Numerator | Denominator | Notes |
| --- | --- | --- | --- |
| Conversations started | Conversations whose first turn is in period |  | The "Conversations" KPI |
| Turns received | Rows with timestamp in period |  | The "Turns" KPI |
| Outcome share | Turns with outcome X | Turns received | The seven shares sum to 100%; used for the outcome mix chart and the category heatmap |
| Turns per conversation | Sum of turn\_count over mature conversations started | Mature conversations started | Mean and median, cohort-based |
| Cited answer rate | Outcome Cited answer | Scored turns | The headline quality metric |
| Partial answer rate | Cited answer with is\_partial | Cited answer turns | Shown as "Cited but partial" |
| Not-found rate | Outcome Not found | Scored turns | The headline failure metric, owned by content and retrieval |
| Clarification rate | Outcome Clarification | Scored turns | Reported separately, not as a failure |
| Uncited answer rate | Outcome Uncited answer | Scored turns |  |
| Out-of-scope share | Outcome Out of scope | Turns received | Includes the Flagged residual rule |
| Error rate | Outcome Error | Turns received | Owned by engineering |
| Median response time | 50th percentile of Response Time | Turns received excluding Error | Also p90 and p99 |
| Latency bands | Turns in <10 s, 10–20 s, 20–30 s, >30 s | Turns received excluding Error | Shown as shares over time |
| Ended after first turn | Mature conversations with turn\_count = 1 | Mature conversations started | Never labelled abandonment |
| Observed conversation span | last\_ts minus first\_ts |  | Mature conversations started with turn\_count > 1, minute precision |
| Suggested follow-up use | Mature conversations started with ≥ 1 suggested\_followup turn | Mature conversations started |  |
| Suggested follow-up share | Turns of type suggested\_followup | Turns received with Turn # > 1 |  |
| Starter prompt share | First turns where is\_starter\_prompt | First turns in period |  |
| Organic first turns | First turns where not is\_starter\_prompt |  | Basis for topic demand; tiles using it carry an "Organic only" badge |
| Feedback rate | Turns with like or dislike | Turns received | Always displayed beside feedback counts |
| Dislikes per 1,000 answers | Dislikes on Cited answer turns | Cited answer turns / 1,000 | 146 of 151 dislikes to date are on cited answers |
| Citations per cited answer | Sum of citation\_count | Cited answer turns |  |
| Pages cited | Distinct normalised internal citation URLs |  |  |
| Corpus coverage | Pages cited that are in the corpus inventory | Pages in the corpus inventory | Requires the corpus list. A value above 100% is a data-quality failure, not a result |
| Citation link validity | Internal citations whose URL is in the corpus inventory | All internal citations | Until the inventory exists, show the count of suspect URLs instead: 18 landing-page or truncated URLs carry 365 citations to date |
| External citation share | Citations not on citizensinformation.ie | All citations |  |
| Cited category share | Turns whose cited\_categories\[\] include the category | Turns received with ≥ 1 cited category | Citation and journey tiles only. An "Unknown (no citation)" row always shows the excluded count |
| Category attribution coverage | Turns with attributed\_category other than Unknown | Turns received | Shown on every category view as "Category known for X% of selected turns" |
| Outcome share by attributed category | Turns with outcome X and attributed\_category = C | Turns with attributed\_category = C | Each row sums to 100%. Lower-bound estimate for failure outcomes, see Attribution limitations. Unknown row always shown |
| Cross-category conversations | Mature conversations with ≥ 2 steps in category\_transitions | Mature conversations started with ≥ 1 cited category | 1,565 of 7,304 such conversations to date contain a return journey |
| Language mix (estimated) | Turns with language\_estimate = X | Turns with a confident estimate | Labelled estimated in the UI |
| Allocated cost per turn | Billed cost for the day | Turns received that day | Cost tab only. An allocation, not a measurement |
| Allocated cost per conversation | Billed cost for the day | Conversations started that day | Cost tab only |

Comparison periods follow the selection. Rates are compared in percentage points, counts in percent.

| Selection | Comparison period |
| --- | --- |
| Last 7, 28 or 90 days | Immediately preceding period of equal length |
| Custom range | Immediately preceding period of equal length |
| Month to date | Same elapsed calendar days of the previous month |
| Full calendar month | Previous calendar month |
| Year on year (optional) | Same dates one year earlier |

Small-sample rule, applied everywhere a rate or share appears: a value whose denominator is below `MIN_RATE_DENOMINATOR` (50) or whose numerator is below `MIN_EVENT_NUMERATOR` (5) is shown as a dash with the counts in the tooltip, never as a percentage. The numerator guard matters for rare events: error rate runs at 1.5% and dislikes at 0.1% of turns, so 50 observations give a numerator of zero or one. One exception keeps informative zeros: when the numerator is exactly 0 and the denominator is at least `MIN_ZERO_DENOMINATOR` (500), show "0 of N (0%)", because a true zero on a large base is precise. Numerators of 1 to 4 stay suppressed with the count on hover. All three constants are configuration. Every tooltip shows n. The underlying records stay reachable in the Explorer; only the rate interpretation is suppressed.

## Attribution limitations

Categories come from citations, so the category system observes successful retrieval far better than failed retrieval. In the feed to date every Not found, Clarification, Out of scope, Greeting, Error and Uncited turn has an empty category. Conversation-level attribution recovers 2,479 of 5,949 not-found turns. The other 58% are single-turn conversations where the user did not continue, and they stay Unknown by construction, so per-category failure rates are biased toward conversations that recovered.

Three protections apply to every category view:

- An Unknown row or bar is always present and is never removed by sorting or top-N truncation.
- The attribution coverage figure is shown beside the view.
- Category-specific failure rates are labelled lower-bound estimates in the tooltip and the definitions drawer.

Retrieval-candidate logging removes the bias at source and is the first item in Open questions.

## Global controls and header

The header is identical on every tab and carries the filters that every tile obeys.

| Control | Options | Default |
| --- | --- | --- |
| Date range | Last 7, 28, 90 complete days in the QA feed; month to date; custom. A partially ingested current day is never included in a preset | Last 28 complete days |
| Comparison | Per the comparison table in Metric definitions; none | As the table |
| Source | All, Web, Modal. Pre-launch Modal is excluded from Web-versus-Modal comparison tiles by default and included in totals | All |
| Attributed category | All, each of the 16 categories, Unknown. The global filter acts on attributed category so recovered failed turns stay in view; cited categories appear only inside citation and journey tiles | All |
| Starter prompts | Include, exclude | Include everywhere. Tiles named Organic exclude them by definition and carry an "Organic only" badge |
| Granularity | Day, week, month | Day under 60 days, week under a year, else month |

Filter contract. Source, attributed category, starter prompt and cohort are turn-level properties, so their effect on each metric grain is fixed here: turn metrics count matching turns; first-turn metrics count matching first turns; conversation metrics include conversations started in the period that contain at least one matching turn, and report their full turn count. Two engineers given the same filter state must produce the same number.

Under the controls sits a one-line period summary in plain words, for example: "1–28 Sep 2026 · compared with 4–31 Aug 2026 · Web and Modal · all categories · starter prompts included". Beside it, one freshness line per pipeline: "QA feed through 28 Sep 2026 23:59 · Azure cost through 26 Sep 2026 · last 24 hours may restate". Hour-based tiles add "Times shown in Europe/Dublin, source timezone not yet confirmed" while the status is unconfirmed. Conversation-depth tiles show "n mature of N started" so the difference from the Conversations KPI is explained where it appears. These lines appear in every export and screenshot.

A "Metric definitions" link in the header opens a drawer listing every metric on the current tab with its numerator, denominator and exclusions, taken from the table above. Every KPI tile also carries an info icon that shows its own definition.

The URL encodes all structured filter state so a view can be bookmarked or pasted into a message, and so a chart click can open the Explorer with the same state. Free-text search terms are never placed in the URL.

## Tab by tab specification

Seven tabs: Overview, Quality, Content, Conversations, Operations, Cost, Explorer. Cost appears only when its pipeline is configured. Every chart on the QA-feed tabs opens the Explorer with its filters applied; Cost charts open the daily meter and deployment detail for the clicked day. Every time series draws its annotations from the events registry, filtered by the registry's applies-to field. Tiles are listed in reading order, top left to bottom right.

### Overview

One screen, no scrolling on a laptop. It answers "how much, how well, what changed" in ten seconds.

| Tile | Type | Content |
| --- | --- | --- |
| KPI row | 6 tiles with delta and sparkline | Cited answer rate, Not-found rate, Error rate, Median response time, Conversations started, Turns received. Service metrics first, per principle 1 |
| Volume over time | Stacked area, Web and Modal | Conversations started per period, with the events registry annotations. Pre-launch Modal shown as its own band |
| Outcome mix over time | 100% stacked area | Seven outcome shares per period, summing to 100%, cited answer at the base. Acceptance test: reproduces the Clarification plus Greeting plus Out of scope rise from 2.71% in January to 9.81% in September on the fixture |
| What changed | List of computed statements | Up to six deterministic statements. Candidates are every metric with a comparison delta that passes the small-sample rule and a materiality threshold: rates and shares 1 percentage point or more, counts 10% or more, latency p50 and p90 10% or 2 s or more, all tunable configuration. Selection by priority class, at most two per class: 1 not-found and error; 2 latency; 3 cited answer, partial, clarification, dislikes per 1,000; 4 demand (conversations, turns, channel mix); 5 product behaviour. Within a class, rank by the delta divided by that metric's own materiality threshold, so percentage points and per-thousand figures are commensurable. Each statement names the metric, both values and the delta. For count metrics, where one attributed category accounts for 30% or more of the additional turns, the statement says so in that form: "Housing accounted for 38% of the additional not-found turns." No rate decomposition in v1. No model. |
| Organic demand by topic | Horizontal bars with outcome colour | Top 8 attributed categories by organic first turns plus an Unknown bar, each segmented by outcome share. "Organic only" badge |

### Quality

| Tile | Type | Content |
| --- | --- | --- |
| Outcome breakdown | Table with bars | Outcome counts and shares for the period with comparison deltas, plus a "Cited but partial" row under Cited answer, and the quality rates over scored turns beneath |
| Category attribution coverage | Number | "Category known for X% of selected turns". Repeated on the Content tab |
| Outcome share by attributed category | Heatmap table | Rows = categories plus Unknown, columns = outcomes, cell = outcome share so each row sums to 100%. Cells under the small-sample rule show a dash. Footnote: categories derive from citations, failed turns are attributed through their conversation, failure shares are lower bounds. Sorted by volume |
| Outcome by source and question type | Small multiples | Cited answer and not-found rates for Web vs Modal and for new topic vs user follow-up vs suggested follow-up, same period only, pre-launch Modal excluded and noted |
| Zero-citation breakdown | Bar | What the non-cited turns are: not found, clarification, out of scope, greeting, uncited answer, error |
| Citation link validity | Number and list | Share of internal citations resolving to a corpus page, and the top suspect URLs. Until the corpus inventory exists, the count of landing-page or truncated URLs |
| Feedback | Two tiles | Likes and dislikes with the feedback rate beside them in the same font size. Dislikes per 1,000 answers by attributed category and by source, under the small-sample rule |
| Disliked conversations | List, analyst role | Most recent 20 disliked turns with masked query preview, outcome and category, opening in Explorer. Shows free text, so it is hidden from the viewer role |

### Content

Tiles labelled Organic exclude starter prompts by definition and carry an "Organic only" badge; the global starter-prompt filter does not change them. Category here means attributed category. Every category table carries an Unknown row and the coverage figure.

| Tile | Type | Content |
| --- | --- | --- |
| Demand and quality by category | Table | Attributed category, organic first turns, share, cited answer rate, partial rate, not-found rate, clarification rate, dislikes per 1,000. Sortable. Unknown row included. Small-sample rule applies per cell. The volume-times-quality view |
| Not-found work queue | Table with status, analyst role | Queries that produced Not found, grouped in three stages: 1 exact normalised text; 2 lexical near-duplicate groups from an offline similarity method (character n-gram or TF-IDF); 3 semantic themes from the nightly clustering job when approved. Stage 2 ships only if, on the reference CSVs, it brings the singleton share below 60% from today's 97.6% and both of two reviewers agree on at least 85% of a fixed sample of 200 grouped pairs that the pair shares an intent; the reviewers read raw queries, so they hold the analyst role and the review is logged like transcript access. Accurate groups at 70% singletons beat misleading ones at 55%. Group keys are stable: a new query joins a group only when it matches that group's fixed representative query (its earliest member), never any member, so groups cannot chain outward; groups are never rebuilt from history without a versioned re-key, and a re-key migrates every status to the new keys. First seen, last seen and count accumulate. Each group carries a status (open, addressed, won't fix) set by analysts and stored against the versioned group key. Category is never part of the grouping key. Columns: group, count, first seen, last seen, attributed category where known, status. Shows free text, so it is hidden from the viewer role and previews are masked |
| Top organic queries | Table, analyst role | Normalised first-turn queries by count, with outcome mix. "Organic only" badge. Free text, hidden from the viewer role, previews masked |
| Top cited pages | Table | Page, citations, change vs comparison period, category |
| Coverage | Two numbers and a list | Pages cited over corpus inventory (hidden until the inventory exists; above 100% is a data-quality failure), external citation share, external domains cited |
| Category journeys | Table | Consecutive pairs from category\_transitions, by count. "Employment → Social welfare". Return journeys are preserved |
| Language mix (estimated) | Bar | Estimated language share for the period with confidence threshold stated |

### Conversations

| Tile | Type | Content |
| --- | --- | --- |
| Turns per conversation | Histogram | 1 to 10+, with ended-after-first-turn share as the headline |
| Length by first outcome | Table | First-turn outcome, conversations, mean turns, ended-after-first-turn share |
| Follow-up mechanisms | Two bars | Suggested follow-up use and user follow-up share, side by side, never combined. Outcome of the suggested-follow-up turns themselves |
| Starter prompts | Table | Each configured prompt with count, share of first turns, the prompt's own outcome, and the share followed by a user-typed turn 2 |
| Observed span | Histogram | Minutes between first and last turn for multi-turn conversations, labelled minute precision |

### Operations

| Tile | Type | Content |
| --- | --- | --- |
| Latency | Line, three series | p50, p90, p99 per period with a dashed target line and the events registry annotations. Errors excluded and stated |
| Latency bands | 100% stacked area | Under 10 s, 10–20 s, 20–30 s, over 30 s |
| Errors | Bar | Error count and rate per period |
| Latency drivers | Two small charts | Median latency by response length bucket and by citation count |
| Activity heatmap | True heatmap, 7 rows by 24 columns | Metric toggle: conversations, median latency, not-found rate, error rate. Source filter applies. Rate cells under the small-sample rule show a dash. Carries the timezone badge while unconfirmed |
| Channel over time | Stacked area | Web, Modal and pre-launch Modal turns per period as three bands, with the rollout and launch events annotated |

### Cost

Shown only when the Azure Cost Management pipeline is configured. A banner at the top reads: "Filter scope: date range and granularity apply. Source, category, outcome and starter-prompt filters do not apply to Azure billing data." The tab has its own freshness line.

| Tile | Type | Content |
| --- | --- | --- |
| Billed cost by day | Bar | In the billing currency, with the settlement lag shaded |
| Tokens by meter and deployment | Stacked bar | Input and output quantities per deployment per day |
| Cost by resource | Table | Generation, embeddings, search, hosting, as the export breaks them down |
| Allocated cost per turn and per conversation | Line | Daily billed cost divided by that day's turns received and conversations started. Labelled allocated, not measured |
| Model and deployment changes | Annotations | Derived from meter names; also written to the events registry |

### Explorer

A filterable table of conversations, then a transcript view. Access rules are in the next section.

- Filters: everything in the header plus outcome, first outcome, question type, feedback, has error, turn count range, language estimate, has personal data hint, starter prompt, cohort, and free-text search over queries.
- Drill-down predicates carried from chart clicks, so that every click reproduces the clicked number: citation URL or domain, response-time range, weekday and hour, partial flag, category transition pair, outcome rule version, maturity. They are not sidebar controls but they are always visible, rendered as removable chips such as "From chart: citation = fuel-allowance", and they are part of URL state so a bookmarked chart-click view reproduces.
- Result summary above the list, at the grain of the clicked value: "143 matching turns · 117 conversations", and where citations are involved "204 citation occurrences · 143 turns · 117 conversations". The list itself is one row per conversation; the summary is what reconciles to the chart.
- List columns: first turn time, source, first query preview (masked), turns, first outcome, categories, feedback, latency of slowest turn.
- Transcript view: each turn with query, response rendered as markdown, outcome, citations as links, response time, question type, feedback. A copy-link button that carries the conversation ID.
- Export: CSV of the filtered list with masked previews only. Full transcript export requires the admin role and is logged.

## Explorer access and data protection

User queries contain personal data even though the service asks people not to enter it. Across the nine months of feed data, 1,542 queries state a specific euro amount, 1,680 run to 60 words or more and read as case narratives, 183 contain "my name is", 94 mention a date of birth, and 31 contain a PPS number, email, phone number or Eircode. The Explorer is therefore treated as a personal-data system, and so are the CSV exports themselves.

| Control | Requirement |
| --- | --- |
| Roles | Viewer: aggregate tiles only, no component that shows query text. Analyst: viewer plus the work queue, Top organic queries, Disliked conversations, Explorer list and transcripts, work-queue status. Admin: analyst plus exports, events registry and configuration |
| Audit log | Every transcript open, export, work-queue status change and grouping-review session is logged with user, time, conversation or group ID and filter state. A free-text search is logged as user, timestamp, search performed, result count and subsequent transcript opens, without the raw term. A restricted term store with its own retention, for incident investigation, is built only if the DPO approves it; it is opt-in after approval, not the default while the question is open |
| Masking in lists | Query previews in list views mask email addresses, phone numbers, PPS-number patterns and Eircodes. Full text appears only in the transcript view after a deliberate open |
| Search | Free-text search runs server side; results show masked previews; terms never enter the URL |
| Exports | List export carries masked previews only. Transcript export is admin-only and logged |
| Retention | Turn text is retained for the period the CIB publishes at the end of the pilot. Aggregates may be kept longer than raw text. The dashboard must keep working when text older than the retention period is deleted |
| Exports on laptops | The QA feed CSVs contain the same personal data. Store them under the same access rules as the Explorer and delete working copies when the pipeline is live |
| Privacy review | Any new processing purpose involving query text, or any new processor, sub-processor or data flow, requires privacy review before it is switched on. Reusing the existing Azure tenant may simplify that review but does not replace it |
| Work-queue writes | Analysts set group status only; no query text is written back; writes are logged |

Tiles that show only aggregates need no control beyond ordinary admin login and are visible to the viewer role. Any component that shows query text, however masked, inherits the Explorer's rules: the not-found work queue, Top organic queries, Disliked conversations and the Explorer itself are analyst-only, their previews are masked, and opens are logged. Viewers still see category demand, coverage, cited pages, journeys and language.

Masking is exposure reduction, not anonymisation. Regex misses names, medical circumstances, unusual identifiers and contextual personal data, so masked previews are still personal data. The Explorer list view is covered by the same roles and audit log as the transcript view.

## AI usage policy

No number on the dashboard is produced by a model. Every count, rate, percentile, comparison and classification is deterministic and reproducible from the stored fields and the versioned rule set. A model is permitted in one optional enhancement layer, switchable off without any tile disappearing.

1. **Theme discovery, nightly batch.** Cluster not-found queries and organic first-turn queries into themes using embeddings and clustering, then have a model name each cluster once. Output is a `theme` label per query that appears as an extra column in the not-found work queue and top queries tables. The theme column carries a "generated" marker. This job sends query text to a model, so it falls under the processor rule in the previous section and needs approval before it is switched on.

Nothing calls a model at page load. The "What changed" panel shows its computed statements directly; there is no narrative rewriting step. Outcome classification, language estimation, starter-prompt detection and personal-data hints all use rules or offline libraries. If a future rule set proves inadequate, the upgrade path is a supervised classifier trained on labelled turns, still run at ingest and still versioned, not a live model call.

## Retired features

Seven elements of the 1.1.0-Pilot dashboard are removed or replaced. Each has a stated reason so the decision is not reopened tile by tile.

| Feature | Decision | Reason |
| --- | --- | --- |
| Cost Trend | Replaced by a separately scoped Cost tab | The QA feed has no token counts. Azure Cost Management data is daily by meter and cannot honour Source, category or outcome filters, so it lives on its own tab behind a filter-scope banner rather than in the shared grid |
| Common Words Analysis | Removed | Frequent words duplicate the category view and drive no decision. Replaced by the not-found work queue and top organic queries |
| Question Complexity Analysis | Removed | Word-count buckets are a weak proxy for difficulty and query length is not important enough to keep |
| Trend Insights | Replaced by What changed | Free-text model output quoted figures from a different period than the tiles. The replacement is computed from the selected period |
| Flagged | Removed from the vocabulary, kept at ingest | The field marks three unrelated outcomes. Each is now shown by name; the field feeds the Out of scope rule |
| Source Distribution donut | Replaced by Channel over time | A period share is misleading when the Modal launched mid-period. The launch date is annotated on the time series |
| Hourly Activity Heatmap | Rebuilt as a real heatmap | The current tile is a bar chart by hour with no weekday axis |

## Data quality and acceptance tests

Every defect in the old dashboard was a wiring bug. The reference CSVs for January to September 2026 are a frozen golden fixture, and the build is accepted only when the pipeline reproduces these values exactly. A deliberate rule-set change re-baselines them against the new `outcome_rule_version`.

| Assertion | Expected on the fixture |
| --- | --- |
| Turns | 113,410 |
| Conversations | 56,365 |
| Duplicate (Conversation ID, Turn #) | 0 |
| Conversations with mixed Source | 0 |
| Source: Modal / Web / Others | 81,133 / 32,275 / 2 |
| Pre-launch Modal conversations (before 1 May 2026) | 462 conversations, 977 turns (3 conversations in January, 267 in March, 192 in April) |
| Feedback: like / dislike | 400 / 151 |
| Error turns | 1,732 |
| Zero-citation turns | 15,816 |
| Total citations | 165,838 |
| Blank Question Type | 1,822 |
| Flagged turns; with citation; matching not-found | 7,289; 0; 3 |
| Turns matching both the greeting and out-of-scope patterns | 0 |
| Outcomes | Cited 97,594; Not found 5,949; Clarification 4,833; Error 1,732; Out of scope 1,287; Greeting 1,267; Uncited 748 |
| is\_partial | 7,449 |
| Scored-turn rates | Cited 89.43%; Not found 5.45%; Clarification 4.43%; Uncited 0.69% |
| Monthly turns, Jan to Sep | 5,824; 4,479; 5,152; 5,188; 14,460; 22,248; 17,990; 18,155; 19,914 |
| Monthly conversations started, Jan to Sep | 3,089; 2,258; 2,553; 2,490; 6,545; 9,919; 9,322; 9,584; 10,605 |
| Clarification + Greeting + Out of scope share, Jan to Sep | 2.71%; 1.96%; 4.27%; 4.26%; 5.66%; 6.32%; 6.69%; 7.27%; 9.81% |
| Not-found turns recovering a category through their conversation | 2,479 of 5,949 |
| Follow-up turns within 1 h / 24 h of the previous turn | 98.84% / 99.96% |
| Conversations with ≥ 2 category steps; with a return journey | 7,304; 1,565 |

UI wiring tests, run against the fixture: every KPI tile shows a non-zero value where the fixture is non-zero; every legend uses the display label, never an enum value; every tile on a page reports the same period as the header; every chart click opens the Explorer with a filter state that reproduces the clicked number; every rate under the small-sample rule renders as a dash.

Ingest-health panel, opened from the header: data current through; rows loaded; parse failures; duplicate keys; blank Question Type share; Unknown attributed category share; Flagged invariant violations; Mixed-source conversations; suspect citation URLs; outcome rule version; starter-prompt configuration version; assumed timezone and status; last successful ingest for each pipeline. It answers the question "can I trust what I am looking at" and is part of the build acceptance, not an optional extra.

## Open questions and dependencies

Fourteen items are outside the QA feed or still undecided, in priority order, and each gates specific tiles. Everything else in this spec can be built from the feed as it stands.

- [ ] **Retrieval candidates on failed turns.** Log the top retrieved pages even when the model answers Not found or asks for clarification. The retriever already ran, so this costs no new processing, and it removes the attribution bias at source. Gates a complete outcome-by-category view; v1 uses conversation-level attribution and an Unknown row.
- [ ] **Timestamp timezone.** Confirm whether the feed's timestamps are Europe/Dublin local or UTC. Ingest runs on the assumed value with a badge meanwhile. The winter-versus-summer activity test cannot settle it in this dataset because January to April is a different usage regime. If Azure OpenAI diagnostic logging is on, its request logs are in UTC, and comparing hourly volume with the feed for one summer week gives a clean answer; ask OGCIO for that alongside the direct question.
- [ ] **Cost pipeline.** Confirm the Azure Cost Management export: which resources count (generation only, or embeddings, search and hosting), billing currency, billing-day timezone against the feed day, settlement lag and restatement handling, and PTU versus consumption pricing. Gates the Cost tab.
- [ ] **Flagged provenance.** Ask OGCIO to document what sets Flagged and whether that logic changed during the pilot. The Out of scope rule depends on it and its rate quadrupled.
- [ ] **Corpus page list.** Export the canonical URL inventory from the retrieval index. The feed cites 1,872 distinct internal URLs against a public figure of about 1,400, so either the figure or the URL definition is wrong. Gates Coverage and Citation link validity.
- [ ] **Modal rollout dates.** The first Modal rows are from 5 January and 462 Modal conversations (977 turns) precede the May launch. Confirm whether these were a limited rollout or internal use and set the public launch date in configuration; the pre-launch cohort rule handles them meanwhile. Do not delete the rows.
- [ ] **Out-of-scope labelled sample.** Label 300 legacy Flagged rows, including non-English ones, to measure how many Flagged residuals are clarifications or greetings in other languages rather than refusals.
- [ ] **Work-queue grouping acceptance.** Choose the stage 2 similarity method and confirm on the reference CSVs that it meets both the singleton target and the purity sample. If it cannot, ship stage 1 with search and recency only.
- [ ] **DPO questions.** Whether a restricted store of raw search terms may be kept for incident investigation, and whether clustering with Azure embeddings in the existing tenant is a new purpose, a new processor, or both.
- [ ] **Starter-prompt list.** Confirm the current list of chips in the Web and Modal interfaces and the dates each was added or changed. Stored as configuration with effective dates.
- [ ] **Language detector.** Choose an offline library and set the confidence threshold. Until then the Language tile shows script only, labelled as such.
- [ ] **Retention period.** The public page says retention will be published after the pilot. The Explorer's retention behaviour follows that decision.
- [ ] **Latency target.** Agree the target line for the latency chart. The feed suggests 20 s is a reasonable p90 target given the median of 11.7 s.
- [ ] **Suggested follow-up impressions.** The feed records clicks only. If "shown versus clicked" is wanted, the chatbot must log the suggestions it displays.
