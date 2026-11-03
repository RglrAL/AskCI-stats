# AskCI Analytics Dashboard: system and data brief

Prepared 29 Sep 2026. Context for an agent working on the redesign of the AskCI admin Analytics Dashboard.

## 1. The system

AskCI is the Citizens Information Board's public chatbot for Irish public services and entitlements. Public description: https://www.citizensinformation.ie/en/about/about-askci/

- Retrieval-then-generation over citizensinformation.ie content only (about 1,400 pages, 15 topic areas). Generation uses Azure OpenAI, hosted in Azure North Europe. The public page does not use the term "RAG", but that is the architecture.
- Pilot since December 2025. Standalone site at askcitizensinformation.ie ("Web" source). Since May 2026 also a pop-up chat on every citizensinformation.ie page ("Modal" source).
- Features: answers with links to source pages, suggested follow-up questions, replies in the user's language (English, Irish, others), like/dislike/report feedback, PDF/text export, fair-usage rate limits, no login.
- Positioning: general information only, not personalised advice. Complements the phone service and local centres.
- Built with the Office of the Government Chief Information Officer (OGCIO). Data controller is the Citizens Information Board.

## 2. The existing dashboard

Internal "AskCI Admin" app, version 1.1.0-Pilot. Current tiles: Chatbot Activity Trend (sessions, questions), Cost Trend (tokens and USD, per-model pricing), Category Distribution, Common Words, LLM-written Trend Insights, Source Distribution (Web vs Modal), Question Complexity (word-count histogram), Citation Usage (rate, avg per answer, top cited URLs), Hourly Activity.

Known defects in the current build: Source Distribution labels the question count as "Total Sessions"; donut legend shows raw values 0/1 instead of Web/Modal; Short/Long Questions counters read 0 despite histogram data; Total Citations reads 0 despite an 86.9% citation rate; Trend Insights quotes figures from a different period than the tiles above it; "Hourly Activity Heatmap" is a bar chart; awkward axis ticks (0.85/1.7/2.55, 550/1100/1650). The goal is a substantial redesign that makes better use of the available data, not a patch.

## 3. The data: two CSV exports

Files in the working directory (same schema, no overlapping rows, safe to concatenate):

| File | Rows (turns) | Conversations | Period |
|---|---|---|---|
| qa-feed_20260929_113454.csv | 57,345 | 26,850 | 1 Jan – 30 Jun 2026 |
| qa-feed_20260929_113634.csv | 56,065 | 29,515 | 30 Jun – 28 Sep 2026 |
| Union | 113,410 | 56,365 | 271 days |

Grain: one row per turn. A conversation (session) is identified by Conversation ID; turns are numbered from 1. Files are ~92 MB and ~102 MB; multi-line quoted fields, so use a proper CSV parser.

### Columns

| Column | Notes |
|---|---|
| Conversation ID | UUID. 56,365 distinct. |
| Turn # | 1 to 52. Mean 2.0 turns per conversation; 54% of conversations are single-turn. |
| User Query | Free text. Median 11 words, mean 13.5, max 657. |
| Assistant Response | Markdown with inline links. Median 167 words. Empty in 1,732 rows (errors, see below). 36% end with "Thanks for using Citizens Information". |
| Timestamp | Format "Mon DD, YYYY HH:MM". Minute precision, no seconds, no timezone stated. Always populated. |
| Question Type | new_topic (53%), user_followup (24%), suggested_followup (21%), blank (1.6%, mostly error rows). Turn 1 is almost always new_topic. |
| Categories | Comma-separated citizensinformation.ie top-level slugs (social-welfare, housing, employment, moving-country, money-and-tax, travel-and-recreation, health, birth-family-relationships, returning-to-ireland, education, justice, consumer, death, about, government-in-ireland, environment, my-situation, all-categories). Derived from the citation URLs: matches the cited URL paths in 96% of rows. Contains repeated values ("social-welfare, social-welfare, social-welfare") that must be de-duplicated. Blank in 17% of rows, almost always because there were no citations. |
| Response Time (ms) | Median 11.7 s, p90 18.2 s, p99 37.7 s. 0 ms on the 1,732 error rows. |
| Feedback | like (400) or dislike (151), blank otherwise. 0.5% of turns. |
| Flagged | "Yes" on 7,289 rows (6.4%), blank otherwise. Not moderation: it marks turns with zero citations where the bot asked for clarification (64%), gave a greeting or chit-chat (17%), or refused as out of scope (18%). Flag rate has risen every month, 2.5% in Jan to 9.8% in Sep. |
| Report Subject / Report Description | User-submitted reports. Populated on 6 rows total. Effectively unused. |
| Citations | Comma-separated URLs. Mean 1.46 per turn, max 13. Zero in 13.9% of turns. 2,122 distinct URLs; 91% on citizensinformation.ie, remainder gov.ie, irishimmigration.ie, revenue.ie, hse.ie, susi.ie, mywelfare.ie. Most cited: fuel-allowance, illness-benefit, state-pension-contributory, disability-allowance, jobseekers-allowance, carers-allowance, maternity-benefit. |
| Source | Modal (72%), Web (28%), Others (2 rows). Modal appears from March, dominates from May. |

Not in the export: token counts, model name, cost, user or device identifiers, language, retrieval scores, page-level context beyond the citation URLs. The current Cost Trend tile cannot be rebuilt from these files.

### Derived outcome classification (from response text plus citations)

| Outcome | Share of turns |
|---|---|
| Answered with citations | 86.1% |
| "Couldn't find specific information" | 5.2% |
| Asked user to clarify | 4.2% |
| Answered without citations | 1.8% |
| Error (empty response, 0 ms) | 1.5% |
| Greeting / chit-chat | 1.1% |

Detection patterns: not_found matches "couldn't find / could not find / wasn't able to find / no specific information"; clarify matches "could you clarify / what you mean / more details"; greeting matches "hello / how can I help / you're welcome".

## 4. Facts already established from the data

- Monthly turn volume: Jan 5.8k, Feb 4.5k, Mar 5.2k, Apr 5.2k, May 14.5k, Jun 22.2k, Jul 18.0k, Aug 18.2k, Sep 19.9k. Daily median 323, max 1,094.
- Weekday traffic is about 2.5x weekend. Peak hours 10:00 to 14:00. Web traffic drops harder at weekends than Modal.
- Latency incident: median response time 7.5 s in Jan, 14.2 s in Mar, 20.9 s in Apr (20% of April turns over 30 s), back to ~11.5 s from May. Latency scales with answer length and citation count.
- Six starter-prompt chips ("what is auto-enrolment", "can i get help with low pay", "how much is maternity benefit", "what are the housing assistance payment (hap) limits", "how do i renew my passport", "how do i apply for the back to school clothing and footwear allowance") account for 6% of first turns. Separate them from organic queries in any topic analysis.
- Conversations starting with a not_found answer average 1.4 turns; cited answers 2.0; clarification 2.6.
- 26% of conversations use at least one suggested follow-up. 15% of conversations span more than one category.
- Language: about 8% of queries contain non-ASCII characters. Roughly 310 Cyrillic-script and 190 Arabic-script queries; Portuguese/Spanish, Polish and Romanian visible among Latin-script queries; about 50 in Irish.
- Feedback: 551 total across 9 months; dislikes concentrate on social-welfare and housing answers, and on cited answers rather than refusals.

## 5. Working notes

- pandas is not installed system-wide. A venv with pandas 3.0.6 exists in the session scratchpad; recreate with `python3 -m venv venv && venv/bin/pip install pandas` if needed.
- Read with `dtype=str, keep_default_na=False`; parse Timestamp with format `%b %d, %Y %H:%M`.
- Reset the index after concatenating the two files.
- Screenshot of the current dashboard: `final 3 (2).png` in the working directory.
