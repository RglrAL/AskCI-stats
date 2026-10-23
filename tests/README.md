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
