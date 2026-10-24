# First six articles: human review queue

All six were **imported from user-saved HTML on 2026-10-24; AI content review passed**.
The [archived final review](reviews/DATA_REVIEW_FINAL_20261024.md) records the
six frozen versions. Their body, snapshot and source URL bindings matched the
current corpus before retrieval development. The user confirms reviewing the
**entire Change your Apple Account password page**, with no issue, not merely one
section. This does not establish full human review of all six documents.
The six legacy `human_review: pending` fields remain unchanged to preserve the
frozen corpus; user review and AI review are recorded here separately. T02 is
accepted for this development stage and does not block T03-T04.
Original filenames were preserved; canonical URLs and h1 titles match the seeds.
The three-document pilot passed before expansion to six. Automated comparison
passed for 152 paragraphs, 52 headings, 59 ordered steps and 33 distinct-per-document
links. This is not team approval of the procedures. Active snapshot/text paths
and hashes are in `data/sources.jsonl` and `evidence/manual_six_20261024.json`;
per-document comparisons are in `evidence/corpus_quality_20261024.json`.

Those corpus/evidence paths are local records, absent from the public source tree.
A new checkout needs its own permitted saved pages and import.

| Article ID / topic | Official title and URL | Required human checks |
|---|---|---|
| 118428 / Subscriptions | [Cancel a subscription from Apple](https://support.apple.com/en-us/118428) | Device branches and ordered steps; already-cancelled condition; trial deadlines; billing provider |
| 101567 / Apple Account | [Change your Apple Account password](https://support.apple.com/en-us/101567) | Trusted device prerequisites; device headings; security delay; child-account conditions |
| 108366 / iCloud | [How to back up your iPhone or iPad with iCloud](https://support.apple.com/en-us/108366) | Manual vs automatic sections; Wi-Fi/power/locked screen; storage warning; older OS exception |
| 118223 / Subscriptions | [Request a refund for apps or content that you bought from Apple](https://support.apple.com/en-us/118223) | Conditional eligibility; pending/unpaid purchases; regional limits; update time vs funds arrival |
| 102656 / Apple Account | [If you forgot your password and can’t sign in to your Apple Account](https://support.apple.com/en-us/102656) | Recovery factors; with/without trusted device; prerequisites; no invented immediate recovery guarantee |
| 118574 / Apple Account | [What to expect during account recovery](https://support.apple.com/en-us/118574) | Wait and confirmation timing; OS-dependent device use; cancellation triggers; support limits |

For every imported article, record: reviewer, review date, doc_id, content hash,
source URL, raw/clean paths, headings/step comparison, important conditions,
absence of navigation/error/feedback content, and pass/fail with corrections.
Additional team review remains optional and should name the reviewer and version;
do not convert AI review into a human signature. The user-confirmed full-page
check above supersedes the earlier blanket statement that no human review exists.
