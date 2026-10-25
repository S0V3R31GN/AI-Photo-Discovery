# Local verification checkpoint

Anthony supplied an aggregate report from `scripts/verify_workflow.py` created
October 25, 2026 at 08:29:35 UTC (4:29:35 AM Eastern). Windows execution was
performed on his machine. This record summarizes that supplied report; it is not
an independently executed Windows benchmark.

The repository head when this report was received was `00b7a68`. The report does
not capture its own local Git commit, so exact local-source equivalence is not
independently established.

## Batch outcome

| Measure | Observed value |
| --- | ---: |
| Matching files and unique registered photos | 19 |
| Registration failures | 0 |
| Ready records | 19 |
| Pending records | 0 |
| Failed records | 0 |
| New records on the verification rerun | 0 |
| New normal-archive caption attempts on the rerun | 0 |
| Structured sample records | 19 |
| Workflow checks passed | 15 of 15 |
| Overall report status | PASS |

The zero new records and zero new caption attempts show that this rerun retained
the existing archive. It also performed the runner's separate real-regeneration
check on a temporary database copy. Synthetic review/pivot annotations were
confined to that copy, and the archive-unchanged check passed.

## Functional checks

All reported checks passed: folder registration; processing status; indexing of
folder records; ranked query execution; exact event and venue pivots; participant
pivot mapping; removal of deleted participant vectors; corrected searchable text;
stale-save rejection; failure recording without lost fields; real retry with staff
protection; fresh-process persistence; review-decision preservation; and unchanged
archive reviews.

## Timing and environment

Five fixed, unlabelled queries ran after warming the embedding model:

| Measure | Observed value |
| --- | ---: |
| Median search duration | 15.60 ms |
| Maximum search duration | 18.01 ms |

These durations include query embedding and SQLite retrieval over the current
local archive. They exclude browser rendering. Five queries over a small archive
do not establish large-archive performance.

The final rerun has null captioning median/maximum because it performed no new
normal-archive caption attempts. In a preceding separately reported retry, the
formerly failed photo completed in 24.59 seconds: image verification 0.00 s,
vision 16.62 s, metadata 6.56 s, caption rewriting 0.48 s, embedding/save 0.90 s.
These include that process's observed loading conditions; do not present the one
photo as average captioning throughput. The original batch had one ReadTimeout,
followed by metadata output-limit failures before the vision-generation change.
The later successful retry does not retroactively make the first pass flawless.

| Environment item | Reported value |
| --- | --- |
| OS / architecture | Windows / AMD64 |
| Processor identifier | Intel64 Family 6 Model 186 Stepping 2, GenuineIntel |
| Logical CPUs | 16 |
| Python | 3.14.5 |
| torch | 2.14.1 |
| transformers | 5.20.2 |
| sentence-transformers | 6.2.0 |
| sqlite-vec | 0.1.9 |
| streamlit | 1.66.1 |
| pillow-heif | 1.8.1 |

## Claims and limits

This is a functional workflow checkpoint. Caption accuracy, human-judged search
relevance, and participant identity correctness were not assessed. The queries
had no human relevance labels. Event/venue/person tests used controlled synthetic
annotations on local photo records; they do not establish real event recognition
or identity resolution. Persistence was checked in a new Python process, not by
automating a browser restart. Representative HEIC coverage and dataset-scale
performance are not established by this report.

The initial four-image demo visibly included caption hallucinations. Before
presenting quality claims, review representative photos locally, define expected
results before querying, and record observed ranks, errors, and misses.

Raw photos, paths, participant descriptions, the structured sample, and private
diagnostic exports remain local. This document includes only aggregate evidence.
