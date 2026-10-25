AI Photo Discovery — Anthony's independent Track B implementation
Repository: S0V3R31GN/AI-Photo-Discovery
Working branch: feature/sqlite-pipeline
Submission deadline: Sunday October 25, 2026 at 10 AM Eastern.

Run each command separately in PowerShell FROM THE REPOSITORY ROOT.
The existing Windows environment is .\.venv\Scripts\python.exe.

1. Install dependencies (or retain your already tested environment):
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check

2. Check the two local inference prerequisites:
ollama list
.\.venv\Scripts\python.exe scripts/check_caption_env.py

If llama3.2:3b is missing, run ollama pull llama3.2:3b. If the service is
unreachable, start the Ollama application (or run ollama serve in a second
terminal). Captioning explicitly uses http://127.0.0.1:11434.

Optional: load/download the vision weights before processing any photos:
.\.venv\Scripts\python.exe scripts/check_caption_env.py --load-vision

3. Create/expand SQLite without removing existing rows:
.\.venv\Scripts\python.exe scripts/setup_db.py

4. Register images. Replace C:\Photos\Test with your actual folder:
.\.venv\Scripts\python.exe scripts/import_photos.py "C:\Photos\Test"

5. Process ONE pending record first:
.\.venv\Scripts\python.exe caption.py --limit 1

Inspect the output and the UI before increasing the batch. The first run may
need model downloads. Originals are stored under data/photos, named by SHA256.
Registration validates and fully decodes the first image frame. Reimporting
identical bytes keeps the same row; existing staff corrections are retained.
HEIC/HEIF support depends on pillow-heif and the actual codec/file. Windows HEIC
runtime validation remains pending. Animated/multipage images use the first frame.

Retry failed records (also includes other pending records):
.\.venv\Scripts\python.exe caption.py --retry-failed --limit 10

Regenerate one explicit record, retaining all protected staff fields:
.\.venv\Scripts\python.exe caption.py --photo-id REPLACE_WITH_FULL_SHA256 --limit 1

6. Open the staff workspace:
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1

Use Register uploads, then Process pending photos. Search uses the structured
activity, setting, participants, objects, and additional staff notes. Caption
and vision description are displayed/editable but excluded from embeddings.

Select a photo, change fields, choose accepted/edited/rejected, and Save review.
Only actual changes made in the form become protected staff fields. The shared
save API also protects explicitly submitted empty values. Saving records and
vectors is atomic. A concurrent modification raises a visible conflict; reload
the selected record before retrying. Ordinary gallery startup loads no vision
model. Unchanged searchable data is retained after an inference failure.

Event and venue navigation use exact staff-saved values, excluding the selected
photo. Participant navigation compares individual descriptions and deduplicates
photos. It is NOT verified identity matching. Distances are cosine distances,
not confidence scores. The participant candidate scan is capped at 4,096 person
vectors; this is a demo-scale workflow, not an archive-scale performance claim.
Rejected reviews remain in the archive/search; the decision is recorded, not a
delete operation. No automated grouping or caption-contradiction repair is implemented.

Rebuild both indexes if model configuration changes or importing old attributes:
.\.venv\Scripts\python.exe scripts/reindex.py

The rebuild encodes before acquiring a database write lock, then replaces both
indexes in one transaction after verifying record revisions. Records and staff
edits are preserved. No JSON seeding or automatic legacy-ID conversion is included.
Additive schema migration retains older rows; captioning explicitly rejects a
row whose content does not match its SHA256 ID. Resolve old UUID/filename-hash
records deliberately; do not delete an edited database to bypass that error.

Verification:
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts/check_env.py

Automated tests exercise real SQLite/sqlite-vec and Streamlit AppTest, with
synthetic images and deterministic test embeddings; VLM/Ollama calls are mocked.
They verify atomic rollback, stale writes, protected empty corrections, retry,
participant-vector removal, group filters, and persistence across UI sessions.
They do not establish caption accuracy or real MiniLM retrieval quality.

Models: HuggingFaceTB/SmolVLM-500M-Instruct; llama3.2:3b through local Ollama;
sentence-transformers/all-MiniLM-L6-v2. Index model ID, actual dimension, and
schema version are saved in SQLite. Model downloads require internet on first
use; cache all weights first for offline operation. In a new PowerShell session,
set $env:HF_HUB_OFFLINE="1" and $env:TRANSFORMERS_OFFLINE="1" after caching to
require local Hugging Face files. No remote inference API is used.

Confidential images, generated metadata, database files, vectors, and exports
must remain local and excluded from Git. The existing .gitignore excludes these
paths. This app does not implement authentication, encryption, retention/deletion
controls, or production access management. Run it on loopback for the demo.
Regex normalization and prompts do not guarantee privacy, correctness, or removal
of sensitive inferences. Staff review is required.

Architecture and verification limits: docs/architecture.md
