# Data governance note

## Data flow and access

Photos remain on the operator's machine. Registration validates images, hashes
their bytes for stable content IDs, and stores originals under `data/photos`.
SQLite stores local paths, generated text, staff corrections/notes, review decisions,
and text embeddings. Inference uses locally downloaded SmolVLM/MiniLM and loopback
Ollama. No photo, caption, or participant annotation is sent to cloud generative AI
by the application. Model weights may be downloaded before local/offline use.

Bind Streamlit to `127.0.0.1` for the demo. The operator must control access to the
computer, operating-system account, backups, and output folders. The prototype has
no application authentication or encryption and is not ready for public hosting.

## Minimization and human judgment

The application generates descriptive text for search. It implements no facial
recognition, facial/biological embeddings, voiceprints, identity registry, or
psychological/clinical assessment. Participant vectors encode clothing/held-item
descriptions, and must not be represented as identity matches. Staff-supplied
notes can still contain sensitive information; enter only what is necessary and
authorized. Prompts and regex normalization reduce some unwanted wording but do
not guarantee anonymization or absence of sensitive inference.

Staff edits and decisions are preserved. Generated descriptions remain proposals;
people/setting/object hallucinations and biased descriptions require review.
Current revision/staff-protection fields are not a complete historical audit log.

## Exports and verification artifacts

Git ignores originals, SQLite files, embeddings, and `outputs/`/`exports/`.
The structured sample and `verification-private-details.json` can contain photo
paths, content IDs, participant descriptions, or other confidential annotations.
Keep them local and share only through an organizer-approved controlled process.
Git ignore rules do not prevent manual copying, prior commits, or accidental upload.

The verification summary contains aggregate counts, timings, environment information,
and check outcomes. The runner performs synthetic correction tests in a temporary
database copy and deletes that copy afterward. It does not overwrite archive staff
corrections with test values. Registration and real captioning intentionally persist
in the normal archive. Raw inference failures are written to the local private
detail file rather than the aggregate summary.

## Post-event custody

The provided challenge data and derived annotations remain subject to the
organizers' restrictions after the event. Keep them confidential and frozen for
authorized handover/review; do not reuse them for portfolios, research, marketing,
or other external projects without explicit written permission. Follow organizer
instructions for retention, controlled transfer, or deletion, including originals,
SQLite databases, vector indexes, exports, and backups. This prototype does not
automate that custody process. Technical access is not consent to redistribute.
