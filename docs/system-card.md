# Photo Discovery system card

## Purpose and scope

Anthony's independent Case 2, Track B prototype helps Dreams Come True staff
find photos using natural language, correct generated descriptions, and navigate
confirmed event/venue groups and similar participant descriptions. It runs on
one local machine and is a hackathon prototype, not a production service.

## Models and retrieval

- Vision: `HuggingFaceTB/SmolVLM-500M-Instruct` through Transformers.
- Metadata/caption proposals: `llama3.2:3b` through Ollama at `127.0.0.1:11434`.
- Text embeddings: `sentence-transformers/all-MiniLM-L6-v2`, normalized float32.
- Vector store: two SQLite `vec0` indexes, for combined structured attributes and
  individual participant descriptions. Actual dimension/model/version are stored.
- General searchable fields: activity, setting, people, objects, and staff notes.
  Caption and vision description are excluded from embeddings.
- Group pivots: exact equality on staff-saved event group and venue.

Model weights must be cached before offline operation. Inference is local;
model downloads on first use require network access. Photo metadata is not sent
to a hosted inference service. Exact installed versions can vary because
requirements are not frozen; retain the tested local environment for the demo.

## Human control and reliability

Staff can accept, edit, or reject a review, with a saved decision and timestamp.
Actual form edits become protected fields, including cleared values. Unchanged
fields are not automatically locked by acceptance. Regeneration retains protected
values. Model output types are validated. Failed records are visible and retryable.
Ollama metadata generation is constrained by a JSON schema and a 512-token output
limit. Caption rewriting is limited to 128 output tokens, with a 2,048-token context
for both requests. Output cut off by the token limit is rejected rather than saved
as complete. Per-stage timings identify which operation failed; the 180-second
Ollama request timeout remains. These controls do not guarantee a wall-clock bound
or improve the truthfulness of descriptions by themselves.
Revision checks reject stale writes. Record changes and affected vectors commit
atomically. Rejected reviews remain searchable; rejection is not deletion.

## Known limitations and distribution shifts

Observed on the initial four-image local test: captions invented a field in a
plain-background clothing image, and described imaginary people in a diagram.
Diagrams, artwork, unusual composition, occlusion, and poor visibility require
review. The prototype does not automatically detect or reject out-of-distribution
images. Invalid/undecodable image files are rejected, but plausible hallucinations
can pass type validation. This is an accuracy limit, not a schema-validation bug.

The two-stage text pipeline can preserve or amplify a vision error. Caption and
vision prose may remain inconsistent with corrected searchable fields; automatic
contradiction repair is not implemented. The absence of an attribute does not
guarantee a semantic model will exclude a photo for a related query.

Search returns up to ten nearest photos without a relevance cutoff. Cosine
distance is not calibrated confidence. Similar clothing may refer to different
people. Participant retrieval never verifies identity; the candidate scan is
capped at 4,096 person vectors. No archive-scale latency claim is established.
Events/venues require staff group assignment; no automatic grouping is implemented.
Animated/multipage images use the first frame. Windows HEIC coverage is not yet
established for representative files.

## Bias, privacy, and deployment risks

Models can misdescribe people, attire, setting, and objects. Prompts discourage
names, ages, race, identity, relationships, and clinical inferences. Regex text
normalization cannot guarantee that sensitive or biased descriptions are absent.
Staff review remains necessary. The system implements no face embeddings,
biometric registry, facial recognition, or identity tracking.

Local files, metadata, vectors, and backups still require controlled custody.
The app does not provide authentication, encryption, role-based access, or a
retention/deletion interface. Loopback binding reduces network exposure but does
not provide a complete production security boundary.

## Evidence and remaining evaluation

The initial Windows run reported Python 3.14.5, torch 2.14.1+cpu, Transformers
5.20.2, successful local Ollama access, and one completed processing attempt at
46.76 seconds. That single measurement includes the observed startup conditions;
it is not a throughput estimate. The four-image query for a green jacket ranked
the corresponding clothing image first. This is a small example, not an accuracy
benchmark. Anthony reported that the subsequent workflow checks passed.

Automated Linux tests use synthetic images, real SQLite/sqlite-vec, Streamlit
AppTest, deterministic test embeddings, and mocked inference. They test persistence,
correction protection, stale writes, atomic rollback, group pivots, and participant
vector replacement. They do not evaluate model quality.

`scripts/verify_workflow.py` adds real local processing and retrieval timing,
plus isolated correction/pivot/retry checks. Read its aggregate report for actual
local outcomes. Its fixed queries have no human relevance labels, so the report
does not claim accuracy, precision, recall, or identity correctness. A manually
judged query set and representative event-photo review remain necessary.
