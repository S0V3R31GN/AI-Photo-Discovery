# Local verification and demonstration

## One-command local verification

Run from the repository root with the tested Windows virtual environment. Substitute
the actual input folder. The command processes all supported images found recursively,
so allow time for one processing attempt per pending photo plus one retry check.

` .\.venv\Scripts\python.exe scripts/verify_workflow.py --folder "C:\Users\antho\Hackathon\Night of 10.24\Testees folder" `

The runner registers originals and processes pending/failed folder photos in the
normal archive. Ready records are retained. It measures five fixed queries over
the entire current archive. It then copies the database and runs controlled
event/venue/person-pivot, correction, deletion, stale-save, failure/retry, and
fresh-process persistence checks in the copy. Synthetic test annotations are not
written to the original archive. A successful run requires at least two ready
photos from the input folder.

Outputs, all local and excluded from Git:

- `outputs/verification-summary.json`: aggregate results; contains no image paths,
  photo IDs, generated descriptions, or private query results.
- `outputs/structured-sample.json`: confidential schema/data sample for the folder.
- `outputs/verification-private-details.json`: confidential diagnostic information.

Inspect the final status. PASS indicates functional checks passed, not that captions
or search relevance are accurate. Failed/skipped checks and errors must be resolved
or disclosed. Raw diagnostics are kept locally; share only the aggregate summary
for remote troubleshooting. The fixed-query timing excludes UI rendering and does
not use human relevance judgments. It cannot establish retrieval accuracy.

## Manually judged retrieval examples

Before searching, choose five to ten queries from viewing the actual photos and
write down the expected relevant photo IDs locally. Include a paraphrase, clothing
plus a held item, a location/activity combination, and one query with no relevant
photo. Then record actual ranks, misses, and false matches. Keep this evaluation
local when it contains confidential annotations. Report the evaluated count and
sample limits instead of generalizing to the full archive.

## Rehearsal

1. Use a small uncaptioned event-photo batch and register it in the workspace.
2. Process locally; show processing status and extracted structured fields.
3. Enter a natural-language query and explain ranked cosine distances.
4. Select a result; demonstrate staff-confirmed event and venue pivots.
5. Select one participant description and pivot; explain that similar descriptions
   do not verify identity.
6. Correct a searchable field, save the review, and show updated retrieval text.
7. Regenerate/reopen to demonstrate that the correction persists.
8. State observed hallucinations, tested sample size, timings, and remaining limits.

## Submission preparation

Include runnable code/setup instructions, the architecture diagram, the controlled
structured output sample, the search/review demonstration, `docs/system-card.md`,
and `docs/data-governance.md`. Verify the intended reviewer can access the submitted
code. Use only authorized channels for sensitive samples and demo media. Complete
Devpost by Sunday October 25 at 10 AM Eastern; aim to finish submission earlier.
No repository merge, permission change, Devpost submission, or disclosure of private
data is performed by the verification runner.
