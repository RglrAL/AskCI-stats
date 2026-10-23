# Ask bar regression test

`python3 tools/test_ask.py` runs every question in `ask_cases.json` through the real page in headless
Chrome and checks each answer. It takes a few seconds.

- **Frozen data.** The page under test is the current `index.html`; the data files come from the git
  commit named in `ask_fixture_ref`, so refreshing the data never changes the expected answers. Move the
  ref forward only on purpose, and re-check the expectations when you do.
- **Cases.** Each case has a question `q`, optional follow-ups `then` (asked without a reset, as a person
  would), `expect` (text the answer must contain) and `not` (text it must not contain). Cases with a
  `note` answered a different question before the Ask bar audit (brief §29) and guard against that coming
  back; the `bleed` group checks that an unrelated question does not inherit the previous one's dates.
- **Adding cases.** Add `{"q": "…"}`, run `python3 tools/test_ask.py --record` to fill in `expect` from the
  current answer, then check the recorded text says what the answer should say.
- **Pre-commit.** `tools/hooks/pre-commit` runs the test on the staged `index.html` when it, or a test
  file, is in the commit (`git config core.hooksPath tools/hooks` once per clone). `SKIP_ASK_TESTS=1`
  skips it for one commit. Without Chrome the test reports "skipped" and passes.
- **CI.** The publish workflow runs this test before every deploy, so a web upload that breaks an answer is
  not published (brief §38).
- **Independent review, 23 Oct 2026.** `review-2026-10-23/ask_cases_review.json` holds the reviewer's 42
  cases as delivered, kept as the record. They encode intended behaviour with proposed wording; adapted
  versions (our wording, the same figures) are in `ask_cases.json`, group `review`, each `note` naming its
  finding. The fixes are in brief §41–45.
- **Browser-free runner.** `tools/test_ask_node.js`, contributed with the review, runs the same cases in jsdom
  (Chart.js and lucide stubbed) without Chrome: `npm install jsdom@24 papaparse@5.4.1`, then
  `node tools/test_ask_node.js [--cases FILE] [-k text] [--show] [--page FILE]`. It tests text only and
  matches case-insensitively. It has not been run on this repository's maintainer machine (no Node there);
  `tools/test_ask.py` remains the reference.
- **Typing cases.** A case with `"type"` types that text into the box (after any `q`/`then`) and checks the
  suggestion dropdown: its preview line, its options, `aria-expanded` and `aria-activedescendant`. With
  `"keys"` (e.g. `["ArrowDown", "Enter"]`) it presses them; with Enter it checks the answer instead. `"q": ""`
  makes a typing-only case.
- **Copy cases.** A case with `"copy": true` appends what *Copy answer* would put on the clipboard (the plain
  Markdown form) after ` || COPY `, so the definition, caveats, re-ask link and footer can be pinned.
- **Tags.** `"lists": [...]` puts a case in a built-in question list (brief §50): `monthly` is "Monthly management
  questions", `facts` is the fact sheet that `tools/make_facts.py` writes at each deploy (brief §51). Their answers
  and declines are pinned here, so a list can't drift without a failing case. A fact case asks for "last month", and
  the sheet runs it for the month in hand.
- **Re-ask links.** Every run also opens a `#ask=` link whose question is markup; it must arrive as plain text.
- **Suggestions.** Every suggestion the dropdown can offer is asked through the page on every run; any that
  gives a "not understood" card fails the run, as does a suggestion template whose backing case is not in
  `ask_cases.json`.
