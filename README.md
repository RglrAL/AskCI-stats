# AskCI cost and usage dashboard

The public dashboard for AskCI, the Citizens Information chatbot: <https://rglral.github.io/AskCI-stats/>.
It shows figures from published aggregates only. Citizens' questions and answers never enter this repository.

| Folder | What is in it |
|---|---|
| `index.html` | the dashboard: one page, no build step (Chart.js, PapaParse and lucide from pinned CDN versions) |
| `data/` | every file the page reads: daily and monthly aggregates, the Azure cost export, GA4 aggregates in `data/ga4/`, events, the lexicon and the refresh manifest |
| `tools/` | the pipeline that builds `data/` from the feed exports on the analyst's machine, and the checks (`tools/hooks/`) |
| `tests/` | the Ask bar regression cases |
| `docs/` | the technical brief (`docs/TECH_BRIEF.md`), the dated revision journal (`docs/DASHBOARD_REVISION_BRIEF.md`), and `docs/brief/`, the September documents (the dashboard spec, the cost brief, the superseded agent brief, the audit prompt) |
| `.github/` | the deploy workflow (`workflows/publish.yml`) |
| `.claude/` | settings for Claude Code sessions: the guard that keeps feed text out of a session's tool output |

On the analyst's machine only (git-ignored, never published):

| Folder | What is in it |
|---|---|
| `exports/` | the raw feed exports, the redacted review folders each refresh writes, labelling sheets, and the saved text of cited pages (`exports/site-text/`) |
| `ask review/` | the system prompts, UAT logs, backend notes and the independent review |
| `reports/` | what the tools write each refresh: fact sheet, change reports, incidents, findings |
| `docs/reviews/` | the UI and audit review reports |
| `screenshots/` | before and after captures from the UI work |
| `pilot evaluation/` | the content team's quality-evaluation workbook and the monthly Q&A samples (temporary) |

**Viewing it locally.** The page fetches its data, so it needs a server: `python3 -m http.server` in the repo, then
open <http://localhost:8000/>. Opened straight from disk it offers to load files from the computer instead.

**Publishing.** A push to `main` runs `.github/workflows/publish.yml`: it moves a root `costs.csv` into `data/` and
removes the Azure subscription ID, audits the data files and runs the Ask bar test, and deploys to GitHub Pages only
if both pass.

**A new Azure cost export** goes to `data/costs.csv`. One uploaded to the repo root is moved there by the deploy.

**A data refresh** runs on the analyst's machine with `tools/refresh.py`, given the feed exports (see
`docs/TECH_BRIEF.md`, section 4). The feed exports and review folders under `exports/` are git-ignored.

**Checks before a commit.** Once per clone: `git config core.hooksPath tools/hooks`. The hook refuses a costs file
that still carries a subscription ID, runs the Ask bar test when the page changes, and refuses any file carrying the
system-prompt canary line.
