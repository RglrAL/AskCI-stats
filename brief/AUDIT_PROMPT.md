# Prompt for an audit agent (24 Oct 2026)

Paste the text below into a fresh agent session opened in a clone of the repository.

---

You are auditing a public analytics dashboard and the local pipeline that feeds it. Work from a clone of
https://github.com/RglrAL/AskCI-stats at the current `main`. Start by reading `TECH_BRIEF.md` in full; it describes the
whole system, its rules, its files and its definitions, and ends with an audit checklist. Then read
`DASHBOARD_REVISION_BRIEF.md` §72, §75 and §76, and skim its earlier sections as you need them. Treat everything in the
repository as the primary source and the briefs as claims to test.

## The rules you work under

1. You will not have the private inputs (the QA feed exports, the labelling sheets, the prompts, the backend logs);
   they are git-ignored and never leave the analyst's machine. Do not ask for them and do not propose anything that
   needs citizen text, prompt text or backend detail to leave that machine. Every proposal must produce counts, class
   names, public page addresses or version strings, nothing else.
2. Do not claim causes. The system describes what moved and by how much, with intervals, and leaves attribution to
   the reader and the events list. Hold your own findings to the same standard.
3. Do not weaken a guard to make something easier: the feed-text guard, the canary, the small-cell floors, the
   20-match and 200/50 thresholds, the version checks. If you think one is wrong, say so with a reason.
4. Where you cannot verify something without the private inputs, say so and describe the check the analyst should run.

## Part 1: the audit

Go through the twelve-step checklist at the end of `TECH_BRIEF.md`, then go beyond it. Cover:

- **Privacy and the governing rules.** Does any tracked file, report, test fixture, screenshot or commit message carry
  citizen text, prompt text, an identifier or backend detail? Are the ignore rules, the guard, the hook and the
  canary sufficient and consistent? Can the redaction leak through a derived column (a county plus an age plus a
  payment, a rare topic, a rare organisation, a figure)? Are the small-cell floors applied everywhere a row names a
  thing?
- **Correctness of the pipeline.** Read `tools/redact_feed.py`, `tools/make_usage.py`, `tools/make_register.py`,
  `tools/make_findings.py` and `tools/audit_data.py`. Look for double counting, off-by-one on dates and eras,
  de-duplication across overlapping exports, turn-versus-conversation mix-ups, partial-day handling, timezone
  assumptions, regex rules that over- or under-match, and places where a published total cannot be reconciled from its
  parts. Reproduce three published figures from the CSVs by hand.
- **Correctness of the page.** Read the calculation layer in `index.html`: the loaders, `CONFIG`, the per-turn
  statistics, the Wilson and Newcombe intervals, the difference in differences, the standardisation, the trailing
  medians, the era scorecard, the change-report logic, the Ask bar's parsing. Check that every figure's definition
  matches its "copy with definition" text and the brief. Look for state leaking between ranges or sub-views.
- **Statistics and method.** Are the intervals right for the counts they wrap? Are rates computed on the right
  denominators (typed versus all turns, scored versus all, cited versus answers)? Is the before/after design sound
  (equal windows, weekday balance, settling days)? Where are inferences presented with more confidence than the
  method supports? Which caveats on the page are stale and which are missing?
- **Tests, audit and deploy.** Are the 153 audit checks the right checks, and what do they not cover? Are the 311 Ask
  bar cases testing meaning or wording? Is the frozen-data fixture a strength or a trap? Is the workflow
  reproducible from a clean clone? What would break silently?
- **Code and maintainability.** The page is 11,000 lines in one file; the tools share patterns by copy. Say what you
  would restructure, what you would leave, and why, with the constraint that there is no build step and one analyst.
- **Documentation.** Where do the briefs and the code disagree? What does a newcomer need that is not written down?

Report every finding as: what, where (file and line), evidence, severity (blocks trust / misleads a reader /
cosmetic), and the fix. Verified findings first; then plausible ones you could not confirm, marked as such.

## Part 2: improvements, features, and new uses of the data

Propose, in priority order with a rough effort each (hours, a day, a week), under these headings. For every item say
what question it answers for one of the three audiences (the service's owners, the content team, the analyst), what
data it needs, that the data is counts only, and how it would be verified.

- **Methods.** Better measures of answer quality from counts alone; better change detection than equal windows;
  better calibration of the rule-based classes; how to use the labelling sheet once scored; how to measure the
  prompt changes separately from the model changes given the dates coincide.
- **New derivations from the question.** What else can be read from a question as a class and published safely
  (the current layers: intent, form, named scheme, topic, county, age band, household, work, payment on, year, shape).
- **New derivations from the answer.** What else can be read from an answer as a count (the current layers: outcome,
  style, templates, organisations, figures against page snapshots, clarification asks, personalisation).
- **New joins.** The feed against the site's page text, the sitemap, GA4, the cost meters, the events list; what each
  join could show that none shows alone.
- **The register and the content loop.** How the content-gap register should run month to month; closure
  measurement; what the content team needs on the page to act.
- **The page.** Navigation, the overview, the Ask bar, deep links, exports, what to remove. Keep the design system.
- **The pipeline and operations.** Refresh automation on the analyst's machine, the snapshot store, versioning,
  the audit, the tests, the deploy.
- **Governance.** What the privacy design should add, what the exception in §75 should lead to, what to ask the
  AskCI team for first when contact resumes.

Be specific and be sceptical. A proposal that needs text to leave the machine is out. A proposal that claims a cause
from counts is out. A proposal that duplicates what the page already does should say what it adds. Finish with the
five things you would do first and the one thing you would stop doing.

## Deliverable

One report, in Markdown, in two parts as above, written for a reader who knows the domain but did not watch you work.
Lead each part with its conclusions. Keep a list at the end of every command you ran and every file you read, so the
analyst can reproduce your checks.
