# AskCI Cost and Usage Intelligence: technical brief for audit

Prepared 24 October 2026 at commit `e17abd1` (177 commits); counts and versions refreshed after the audit response of the same day (brief §76, commit 165b383). This is the current description of the whole system for
an agent or a person auditing it. It is written to be read on its own. The dated journal of every decision is
`DASHBOARD_REVISION_BRIEF.md` (§1–§76); this brief points into it rather than repeating it. Three older documents in
`brief/` describe the system as it was in September and are superseded where they differ.

## 1. What the system is

A public, static analytics dashboard for AskCI, the Citizens Information Board's chatbot for Irish public services,
built and run by one analyst. It answers four questions about the service: what it costs, how much it is used, how
well it answers, and what people ask that it cannot answer. It is one HTML page (`index.html`, 11,228 lines, vanilla
JavaScript) reading committed CSV and JSON files, deployed by GitHub Pages at https://rglral.github.io/AskCI-stats/.
Nothing runs on a server; every number on the page is computed in the browser from the files in this repository.

The analyst's machine runs a local pipeline that turns three private inputs into those files:

| Input | Holds | Kept where |
|---|---|---|
| AskCI QA feed exports (`exports/qa-feed_*.csv`) | every conversation turn: the citizen's question, the bot's answer, citations, timestamps, feedback | analyst's machine only, git-ignored |
| Azure Cost Management export (`costs.csv`) | billed cost per meter per day | committed, with the subscription ID and the resource names redacted to role labels |
| GA4 exports (`ga4/*.csv`) | site sessions, searches, and click-throughs from AskCI citation links | committed, aggregate |

## 2. The governing rules

These are design rules, not preferences. An audit should check each holds.

1. **Citizens' text never leaves the analyst's machine.** The question and answer columns are dropped by
   `tools/redact_feed.py` before anything is kept. What leaves is counts, class names, public page addresses and
   version strings. No tracked file holds a question or an answer; no file under `exports/` is tracked.
2. **A model session is not the machine.** `tools/hooks/guard_feed_text.py`, installed by `.claude/settings.json` as a
   PreToolUse hook, denies any Read, Grep or Bash call in a Claude Code session that would print feed text (any
   `qa-feed*.csv`, any labelling sheet, the backend logs). Only the pipeline tools in `tools/` may open those files;
   they print counts; a glob, a shell variable or a substitution under the private folders is denied too.
   `tools/hooks/test_guard.py` has 34 cases. The guard is accident-grade, not a security boundary: the boundary is
   that the private inputs exist only on the analyst's machine. One exception, on 24 October 2026 before the guard
   existed, is logged in brief §75 with what was read and what was published (theme names and counts only).
3. **Prompt text never enters tracked files.** The system prompts live in the git-ignored `ask review/` folder; a
   canary string is checked by the pre-commit hook and the audit. `prompts.json` holds a fingerprint and dates only.
4. **Backend detail from UAT logs stays local.** Architecture learned from logs is in `ask review/` and never in the
   public brief or page.
5. **The page shows figures and claims no causes.** Change reports and the page say what moved and by how much, with
   intervals; attribution is the reader's, done with the events list.
6. **Counts, not suppression, with small-cell rules.** Published rows naming a class of person (a county, an age
   band, a year, a shape), a topic or an organisation need five or more, "(all)" rows included; topic keywords need
   20 or more matching questions; fixed-wording sentences need 200 or more answers and 50 or more conversations
   before they are named. Rows naming a public page are not floored: a page is not a person.
8. **The deploy enforces the rules it can.** The audit sweeps every tracked CSV, JSON and Markdown file for a
   text-column header, a long free-text cell outside the known prose columns, identifier patterns and a production
   resource name, and fails the deploy on a hit, reporting file and rule only.
7. **Every derivation is versioned**, and the version travels in the files: outcome rules, style, safety, intent, the
   lexicon, and one `derivation_version` bundling the topic layer, the response rules and the template list.

## 3. Repository layout

```
index.html                      the dashboard (page, calculation layer, Ask bar, tests hooks)
*.csv, *.json (root)            the published data files the page reads (section 5)
ga4/                            GA4 aggregates: sessions, searches, categories, click-throughs
events.json                     model, prompt, chip, launch and content events with status and evidence
question-lexicon.json           page slugs and aliases (1,617 phrases), expected outcome per intent, topic layer (114 topics)
answer-templates.json           the bot's 18 fixed sentences and the 39 organisations list
register-config.json            thresholds, kinds, teams and owners for the content-gap register
register-themes.json            seeded register rows from the housing read (replaced as the topic layer computes them)
content-gaps.csv                the register's evidence rows (rebuilt at deploy)
content-gaps-status.csv         the register's status file (created once, edited by people, never overwritten)
site-pages.csv                  the site's own page list from its sitemap (3,749 pages, LastMod)
costs.csv                       Azure cost export, subscription ID redacted
tools/                          the pipeline (section 4); tools/hooks/ the pre-commit hook and the feed-text guard
tests/                          Ask bar regression cases (311) and the frozen-data commit reference
reports/                        generated at deploy, git-ignored: fact sheet, change reports, incidents, findings
.github/workflows/publish.yml   the deploy: audit, test, stamp, reports, register, Pages
DASHBOARD_REVISION_BRIEF.md     the dated journal, §1–§76
brief/                          September documents: AGENT_BRIEF.md (system), COST_BRIEF, the dashboard spec
exports/ (git-ignored)          raw feeds, redacted review folders, labelling sheets, page-text snapshots
ask review/ (git-ignored)       prompts, UAT logs, the log parser, backend notes, the independent review
```

## 4. The pipeline

Run on the analyst's machine, in this order, at each data refresh. Each step is one command; the guard allows all of
them.

| Step | Tool | Reads | Writes | Version it carries |
|---|---|---|---|---|
| 0 | `make_site_pages.py` (occasional) | a saved sitemap | `site-pages.csv` | — |
| 1 | `make_lexicon.py --topic-counts FEEDS` | `site-pages.csv`, the raw feeds (counts only) | `question-lexicon.json`; refuses to write while any topic keyword matches under 20 questions | lexicon 2026.10.24-6, derivation 2026.10.24-7 |
| 2 | `fetch_pages.py` | `pages-cited.csv`, `site-pages.csv`, the public site (curl) | `exports/site-text/<hash>__<LastMod>.txt`, one dated snapshot per cited page per change | — |
| 3 | `redact_feed.py FEEDS --out-dir DIR --force` | raw feeds, lexicon, snapshots | redacted feeds: the text columns dropped, 60-odd derived columns added (section 6) | rules 2026.10.23-2, style 2026.10.23-2, safety 2026.10.24-1, intent 2026.10.24-2, derivation 2026.10.24-7 |
| 4 | `make_usage.py REDACTED --out-dir DIR` | redacted feeds, lexicon hubs and topics | 29 aggregate CSVs (section 5) | — |
| 5 | `cache_coverage.py`, `next_step.py` | raw or redacted feeds | `repeat-questions-monthly.csv`, `answer-next-daily.csv` | — |
| 6 | `collect_aggregates.py DIR` | the review folder | copies every aggregate CSV into the repo root, never a feed | — |
| 7 | `audit_data.py DIR` (recount) or `--files-only` | repo files, optionally the redacted feeds | pass/fail: 153 checks files-only, more with the recount | — |
| 8 | `make_register.py`, `make_findings.py`, `change_report.py --events`, `incidents.py`, `make_facts.py` | published files | `content-gaps.csv`, `reports/*` | — |
| 9 | `test_ask.py` | `index.html` + data at `tests/ask_fixture_ref` | pass/fail, 311 cases | — |
| 10 | `refresh.py` writes `VERSIONS.json` | the tools' constants, the recount's result, the aggregates | the manifest: every version string, the recount date and counts, a hash and row count per aggregate file | — |
| 11 | commit, push | | the deploy workflow repeats 7, 8 (files-only) and 9, checks the committed aggregates against the manifest's hashes, stamps the page with the page and data commits, publishes | |

**`tools/refresh.py FEEDS`** runs steps 1 to 10 in order and stops at the first failure, keeping the tools' output in
the review folder's `refresh.log` and printing each step's last line (counts and versions). It is the normal way to
refresh; the single commands remain for repairs.

Also local, not part of a refresh: `make_label_sample.py` and `score_labels.py` (the labelling sheet and its scoring,
section 9), `answer_templates.py --discover` and `--org-counts` (finding fixed sentences and counting organisations,
counts only), `prompt_fingerprint.py` and `check_rules_vs_prompts.py` (the prompts, local), `same_question.py`,
`make_clicks.py` (GA4 click exports to the two click files), `redact_costs.py` (run by the workflow too).

**The derivation changelog** (one line per bump, in `redact_feed.py`): 2026.10.24-1 topic layer, housing; -2 fixed
wording; -3 organisations; -4 figures against snapshots; -5 five more topic tables; -6 layer 2 (situation, asks,
personalisation, letters); -7 the ten smaller categories. `make_lexicon.py` carries the same constant and the
redaction refuses to run if the lexicon's does not match.

## 5. The published data files

All are counts or public addresses. The audit's schema table (`tools/audit_data.py`, `SCHEMA`) is the authoritative
column list; this is the map.

**Volume and cost.** `usage.csv` (day: questions, sessions, outcomes, errors by source and chip, rules version),
`usage-hours.csv`, `costs.csv`, `latency-buckets-daily.csv`, `script-outcomes-daily.csv` (by query script).

**Outcomes and categories.** `category-outcomes-daily.csv` (by the category of the page cited; `unknown` when none),
`categories.csv`, `categories-daily.csv`, `outcome-rules-daily.csv` (which phrase decided each outcome),
`answer-style-daily.csv` (the wording fingerprint), `answer-next-daily.csv` (what people do next), `conversations-daily.csv`,
`journeys-monthly.csv`, `starter-prompts-monthly.csv`, `repeat-questions-monthly.csv`, `safety-daily.csv`.

**Pages.** `citations-monthly.csv` (page, month: citations, answers, partial, dislikes), `citations-intent-monthly.csv`,
`pages-cited.csv` (page: first and last cited, LastMod, answers after LastMod), `asked-pages-monthly.csv` and
`asked-pages-weekly.csv` (pages the question named, and whether the answer cited them), `ga4/clicks-daily.csv`,
`ga4/clicks-pages-daily.csv`.

**What people ask (the question side).** `question-intent-daily.csv` (intent × chip flag, with form flags and the
named-scheme cuts), `question-topics-daily.csv` (category the question named, for turns whose answer carried none),
`question-topics-monthly.csv` (category, topic from the lexicon's topic layer), `question-categories-monthly.csv`
(category by how the turn entered it: cited / page / topic / none, the "broad cut"), `question-intent-category-monthly.csv`,
`intent-journeys-monthly.csv`, `setback-intents-monthly.csv`, `question-situation-monthly.csv` (county, age band,
household, work, payment on, year, shape; never crossed with each other).

**The response side.** `answer-templates-daily.csv` (the fixed sentences per day), `answer-signposts-monthly.csv`
(organisations named, by category, with `(any)`, `(external)` and `(none)` rows), `answer-figures-monthly.csv`
(figures quoted, matched / unmatched / unverifiable, by cited page), `clarification-asks-monthly.csv` (what a
clarification asked for and whether the question had given it), `answer-personalisation-monthly.csv`.

**Reference and configuration.** `events.json` (20 events: 3 confirmed model changes, 3 candidate prompt changes
dated by the fixed wording, 4 candidate chip changes, launches and observed changes), `question-lexicon.json`,
`answer-templates.json`, `prompts.json`, `site-pages.csv`, `register-config.json`, `register-themes.json`,
`content-gaps.csv`, `content-gaps-status.csv`.

## 6. The definitions that matter

- **Outcome** of an answer, by rule on its wording (`redact_feed.py` `RULES`, version 2026.10.23-2): Cited answer,
  Not found, Clarification, Error (empty), Out of scope, Greeting, Uncited answer. **Partial**: a cited answer that
  also says something is missing. The rules were checked against the system prompts of 28 August (brief §60) and are
  unvalidated against a reader since 14 September; the page says so wherever an outcome figure appears. The partial
  series changed what it measures on 1 July, when the deciding phrase moved from "does not provide" to "could not
  find" with that day's wording change and the count quadrupled (brief §76); Answer wording shows partials by phrase.
- **Typed**: a question a person typed. Chip flag 0 typed, 1 a starter prompt, 2 a model-written suggested follow-up,
  which is never counted as typed (brief §71).
- **Intent**, by rule on the question: status, contact, documents, apply, rate, eligibility, timing, statement,
  definition, other (version 2026.10.24-2). The lexicon carries the outcome the design expects per intent (all
  "cited"); **unexpected** = not found, uncited, or a clarification on a question that named a scheme.
- **Named a scheme**: the question contains a lexicon phrase (a page slug or alias); the page and category it
  names are recorded. A citation of a page beneath a named hub counts as a hit.
- **Topic**: the longest matching generic keyword from the lexicon's topic layer; a topic marked general applies only
  when no specific one does. **Category Source**: page if the question named a page, topic if its topic placed it,
  blank otherwise. The **broad cut** of a category is cited-a-page-in-it OR named-a-page-in-it OR topic-places-it;
  a turn can sit in two categories; the published definition states the three tests and their counts.
- **The residue**: typed questions no test places in a category: 9,600 (9.1%) at this commit.
- **Situation flags** (layer 2): county, age band (16–24, 25–44, 45–65, 66+), household (children, partner, alone),
  work status, a payment already received (first-person receiving phrase plus a social-welfare page named), the year
  asked about, shape (pasted letter: 80+ words with letter markers; more than one question; a link). **Asks**: what a
  clarification asked for (county, age, payment, status, household, employment, dates, scheme); **given** when the
  question already carried that class.
- **Fixed wording**: 18 sentences the prompt prescribes, found as sentences in 200+ answers and 50+ conversations;
  a month-on-month step in a sentence's share of answers dates a wording change, read against the model events.
- **Organisations**: 39 bodies, helplines and professionals matched by name in the answer; `(external)` = outside
  Citizens Information's own centre, phone line and MABS.
- **Figures**: euro amounts, percentages and years in an answer, normalised; **matched** on a usable snapshot of a
  cited page (LastMod on or before the answer date), **unverifiable** when a cited page changed after the answer or
  has no snapshot or nothing was cited, **unmatched** otherwise. Unmatched is an upper bound on error and is not
  called accuracy until the labelling calibrates it.
- **Events and eras**: confirmed model or prompt events cut the eras the scorecard and `next_step.py` use; the change
  day and the event's settling days belong to no era. Candidate events draw nothing until confirmed.
- **The register** (`make_register.py`, `register-config.json`): kinds retrieval (named 30+ times a month, not found
  10%+ or reached under 60%), detail (100+ answers, partial share 30%+ and 1.5× typical; or a topic at 25%+ and 1.5×),
  stale (100+ answers, LastMod before 2025-01-01), missing-page (a topic with 100+ typed questions and 10%+ not
  found), signpost (seeded only), unknown (not found with no scheme named). Priority = asks × the rate that raised it.
- **Findings** (`make_findings.py`): thirteen measured items recomputed at deploy against the figures §72 recorded,
  with a status (steady, moved, fixed); baselines live in its `BASE` dictionary.

## 7. The page

- **Stack**: Chart.js 4.4.1 and PapaParse 5.4.1 from cdnjs, lucide 1.49.0 from unpkg (pinned), DM Sans and DM Mono
  from Google Fonts. No build step, no framework, no server calls other than fetching the data files.
- **Groups and sub-views** (`TAB_GROUPS`): Overview; Cost (Summary, Services, Models); Usage (Volume, Quality,
  Before / after, Reach, Conversations, Categories, Click-throughs, Pages, Answer wording, What people ask); Scenario
  planner. A sub-view opens from a link as `#tab=<sub id>` (for example `#tab=asked`); range and theme also travel
  in the hash.
- **CONFIG** (near line 2054): version 2026.10.23-1, the resource-group filter, the meter classification (fixed /
  variable / unclassified, reported never silently bucketed), and two null fields the labelling fills:
  `intent_measured` and `outcome_rules_measured`.
- **The Ask bar**: a natural-language question answered from the loaded files, entirely in the browser; no API key,
  no network. Entities include day, week, month, category, page, prompt, journey, kinds of question, pages people
  named, and subjects within a category; a quick-list and a command palette sit beside it.
- **Browser storage**: theme, range, personal event markers, a spend target; nothing else.
- **The data-quality strip** under the header prints every version string the files carry, the join window, rows
  de-duplicated and excluded, and the caveats ("unvalidated from 14 Sep", "agreement not yet measured").
- **The build stamp**: a meta tag `askci-build` the workflow sets to the page commit and the data commit; the
  "copy with definition" footer carries it.

## 8. Verification

| Check | Where | Count at this commit |
|---|---|---|
| Data audit, files-only (schema, cross-file sums, bounds, floors, versions, lexicon, register, canary, privacy sweep, cost labels) | `tools/audit_data.py --files-only`, run by the workflow | 157 pass |
| Data audit with the feed recount | `tools/audit_data.py DIR`, local | more checks; run before each refresh is committed |
| Ask bar regression | `tools/test_ask.py`, headless Chrome, data frozen at `tests/ask_fixture_ref` (54dc360); fails without a browser unless `--allow-skip` | 311 pass |
| Feed-text guard | `tools/hooks/test_guard.py` | 34 cases |
| Refresh manifest | `VERSIONS.json`, written by `tools/refresh.py`; the audit checks its versions against the files and its aggregate hashes against the committed files | one per refresh |
| Pre-commit | `tools/hooks/pre-commit` (`git config core.hooksPath tools/hooks`): canary, costs redaction, Ask bar test on the staged page | |
| Deploy | `.github/workflows/publish.yml`: redact costs, audit, test, stamp, fact sheet, change reports, incidents, findings, register, Pages | every step green at `e17abd1` |

Visual checks are screenshots from headless Chrome against a local `http.server`; the headless `--dump-dom` path
does not render the panes.

## 9. The labelling sheet (the one step that gives ground truth)

`exports/labelling-2026-10-24/`: 122 answers, a second sheet of 24, drawn by `make_label_sample.py` stratified by rule
outcome in two periods either side of 14 September, plus strata for matched and unmatched figures, questions with a
personal detail, pasted letters and topic-placed questions. The labeller fills eight columns (what kind, answered,
detail on page, what asked, scheme page, category, topic, figure match). `score_labels.py` prints agreement per rule
class weighted to the real mix, the "not found that did answer" figure, intent and page agreement, category agreement,
topic overlap and the figures calibration, and the three `CONFIG` entries, with no text. The analyst fills the sheet;
no session reads it. Until it is scored, every outcome figure since 14 September, every topic row and the figures
bound are inferences and the page says so.

## 10. Known limitations

- The outcome rules, intents and topics are rules written by the analyst, pruned by counts, not yet reader-checked.
- The page snapshots began on 24 October; the back history is checkable only against pages unchanged since the answer,
  so half of all figures are unverifiable (78% in January, 29% in October) and the share falls from here.
- 186 pages the answers have cited now return 404; nearly all those citations are from January and February.
- The clarification "asks" classes and the situation classes are regex; the household and work classes carry most of
  the "asked for what was given" signal and are the ones to check first.
- The Ask bar test's frozen data means new files are absent in tests until the reference moves; it is moved on purpose.
- The register's status file has no content-side owner yet; every row reads "raised, no owner".
- Prompt and model changes coincide on 9–10 March, 30 June–1 July and 14 September; the data cannot separate them
  without the labelling and the AskCI team's confirmation.

## 11. Open items and owners

- **Analyst**: fill and score the labelling sheet; put its figures into `CONFIG`; the October close (refresh,
  register review, change report on a full month).
- **AskCI team** (contact parked since 23 October): confirm the three candidate prompt events and the four chip
  events; supply the current prompt set and where brief mode is used; a log extract one week either side of
  14 September; the governance question in brief §75 (the model provider as a processor, or not).
- **Content team**: a name in `content-gaps-status.csv`; the register rows.

## 12. Suggested audit checklist

1. Clone, run `python3 tools/audit_data.py --files-only` and `python3 tools/test_ask.py`; both should pass as above.
2. Confirm no tracked file holds citizen text: `git ls-files` against `.gitignore`; grep the tracked CSVs for free
   text columns; check `exports/` and `ask review/` are ignored; check the canary rule in the hook and the audit.
3. Read `redact_feed.py` top to bottom: the dropped columns, every rule set and its version, the derivation changelog,
   and that `check_figures`, `answer_templates`, `answer_orgs` and `situation_of` emit only classes and counts.
4. Read `make_usage.py`'s header docstring (the file catalogue) against `audit_data.py`'s `SCHEMA` and against the
   page's loaders in `index.html` (search `loadCSV(` and `loadM(`); every file read should be in all three.
5. Check the small-cell rules: `min_turns`, `min_answers` and the 5-row floors in the row writers; the 20-match check
   in `make_lexicon.py`; the 200/50 thresholds in `answer_templates.py`.
6. Check the guard: `python3 tools/hooks/test_guard.py`; try a denied call in a session.
7. Check the deploy stamp on the live page matches `git log` for `index.html` and for the data files.
8. Read `events.json`: every confirmed event has evidence; candidates draw nothing; the era cuts in `next_step.py`
   and the scorecard use only confirmed model and prompt events.
9. Pick three figures on the page and recompute them from the CSVs by hand (the "copy with definition" footer gives
   the definition and the files).
10. Read brief §72 and §76 and check each measured item against `reports/findings.md` from the latest deploy.
