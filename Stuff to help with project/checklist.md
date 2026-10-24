# Track B — execution checklist

Follow the numbered sections in order. This checklist implements the agreed 19-step photo pipeline.

## How to use this file

- `[x]` means the stated pass condition has evidence. `[ ]` means unfinished or not yet verified.
- Every task names its branch. Owner names below are suggested assignments; agree on them together before starting.
- Start each branch from updated `dev`. Open its PR into `dev`; the other developer reviews it. After merging, start the next dependent branch from updated `dev`.
- A branch is ready when its receiving component can consume its output. A successful script exit alone is insufficient.
- Proposed new filenames are implementation targets, not claims that those files already exist.
- Baseline: source inspected at `dev` commit `7ff7a2d`, plus Anthony's reported import checks. Unchecked items must be verified against newer work before duplicating it. No fresh runtime audit is implied.
- Existing source has two disconnected paths: SQLite registration, and `caption.py` → `captions.json` → `app.py`. The tasks below connect everything through SQLite.

## 0. Lock the data handoffs — do this together first

Purpose: stop the captioner, database, index, and UI from inventing different records.

- [ ] **Branch `docs/pipeline-contract` — Both:** Add `docs/pipeline.md`: photo folder → SQLite registration → SmolVLM description → Llama metadata through Ollama → validation → UPDATE the original SQLite row → text embeddings → FAISS → Streamlit → saved review → refreshed search. **Pass:** both developers can identify the next consumer of every output.
- [ ] **Branch `docs/pipeline-contract` — Both:** Add `docs/metadata-schema.md` with one exact JSON shape for the `metadata` column. Proposed keys: `activity` (string or null), `setting` (string or null), `people` (list of clothing/gear descriptions), `objects` (list of strings), `vision_description` (string). Map the existing model's `event`/`location` outputs to `activity`/`setting`. **Pass:** write one synthetic example that both captioning and UI will support; no unresolved `attributes` versus `people` naming.
- [ ] **Branch `docs/pipeline-contract` — Both:** Define `event_group` as a specific staff-confirmed gathering and `venue` as a staff-confirmed place; leave unknown values NULL. Define participant matches as descriptive similarity, not verified identity. **Pass:** two unrelated birthday parties cannot become the same event just because both have activity `birthday party`.
- [ ] **Branch `docs/pipeline-contract` — Both:** Adopt one stable ID per SQLite photo row. All later operations use it; FAISS positions map to it. **Pass:** captioning and UI do not create replacement IDs from filenames.

## 1. Verify the storage foundation

Purpose: the remaining stages have one dependable source of photo records.

Suggested owner: Anthony. Existing work came from `feature/sqlite`; use the repair branch below only for outstanding tasks.

- [x] **Branch `feature/sqlite` — Existing:** `scripts/setup_db.py` defines `photos(id, path, caption, metadata, event_group, venue)` with a non-null primary key and required path. **Evidence:** inspected repository source.
- [x] **Branch `feature/sqlite` — Existing:** `scripts/import_photos.py` recursively registers JPG/JPEG/PNG paths and assigns UUIDs without copying images. **Evidence:** inspected source and Anthony's successful one-photo import.
- [x] **Branch `feature/sqlite` — Existing:** Reimporting an already registered path adds no row. **Evidence:** Anthony reported first run imported 1, second run imported 0.
- [ ] **Branch `fix/sqlite-foundation` — Anthony:** Verify the actual local database has all six columns; rerunning `CREATE TABLE IF NOT EXISTS` does not repair an old schema. Preserve populated databases using a migration. **Pass:** inspect columns and read the existing photo row successfully.
- [ ] **Branch `fix/sqlite-foundation` — Anthony:** Verify `.gitignore` excludes local images, generated metadata, databases, and indexes, and those files are not already tracked. **Pass:** `git ls-files` contains none of the sensitive/generated assets; source scripts remain tracked.
- [ ] **Branch `fix/sqlite-foundation` — Anthony:** Prepare the same three approved local test photos on both machines and record their intended descriptions for testing. Each developer may have different locally generated UUIDs. **Pass:** both can import the three files, rerun without duplicates, and resolve all stored paths to existing images.

## 2. Connect captioning to the registered photos — first integration gate

Purpose: populate the rows the importer created. Keep the useful model functions in existing `caption.py`.

Suggested owner: Blake. Depends on sections 0–1.

- [ ] **Branch `fix/caption-sqlite` — Blake:** Replace the independent `os.listdir("photos")` scan with reading eligible `id` and `path` values from `data/photos.db`. Resolve relative paths against the repo root. **Pass:** captioning can process a registered image outside the hardcoded `photos/` folder.
- [ ] **Branch `fix/caption-sqlite` — Blake:** Keep SmolVLM as the image-reading stage and Llama through Ollama as the text-structuring stage. Run one local image through both and print the intermediate description and structured result for inspection. **Pass:** both stages return usable output on the actual test machine; no cloud inference is used.
- [ ] **Branch `fix/caption-sqlite` — Blake:** Validate required metadata keys, value types, and a nonempty caption; retain unknowns instead of inventing values. **Pass:** malformed JSON, a wrong field type, or an empty caption produces a clear per-photo failure without saving a successful record.
- [ ] **Branch `fix/caption-sqlite` — Blake:** Save valid captions and JSON metadata using `UPDATE photos ... WHERE id = ?`. Remove filename-derived ID creation and `captions.json` as the application's primary output. Leave `event_group` and `venue` unchanged. **Pass:** the imported row's UUID stays identical and its caption/metadata become populated in SQLite.
- [ ] **Branch `fix/caption-sqlite` — Blake:** Process only untouched records by default; do not overwrite nonempty captions, existing metadata, or later staff edits. Report incomplete records separately rather than silently replacing their fields. Save each completed photo before moving on; continue past a failed photo. **Pass:** rerunning preserves completed values and retries an untouched failed row.
- [ ] **Branch `fix/caption-sqlite` — Both:** Replace the hardcoded `[:3]` production limit with an explicit optional test limit, and document the actual command. **Pass:** test mode processes one eligible photo; the normal command can process all eligible registered photos.
- [ ] **Branch `fix/caption-sqlite` — Both:** Demonstrate importer → captioner → SQLite on all three test photos. **Pass:** three original IDs, three valid captions/metadata records, and zero changes when processing is rerun. Merge only after this handoff works.

## 3. Make the app display SQLite records and accept imports

Purpose: show the database's current contents before adding retrieval complexity. Pipeline steps 1–5 and 16.

Suggested owner: Anthony. Depends on section 2 for populated records; UI layout can start earlier using the agreed synthetic example.

- [ ] **Branch `feat/sqlite-gallery` — Anthony:** Change `app.py` to read SQLite records and decode `metadata` using the agreed keys. Remove the mandatory `captions.json` read and stale `p["attributes"]` access. **Pass:** the app starts with no JSON file and displays the three captioned records.
- [ ] **Branch `feat/sqlite-gallery` — Anthony:** Resolve stored image paths consistently and show useful empty-library, pending-caption, invalid-metadata, and missing-image states. **Pass:** a missing image or empty database does not crash the gallery.
- [ ] **Branch `feat/sqlite-gallery` — Anthony:** Add a selected-photo view keyed by SQLite ID, showing caption, activity, setting, people, objects, event group, and venue. **Pass:** clicking a gallery item opens the matching database record and image.
- [ ] **Branch `feat/sqlite-gallery` — Anthony:** Add a local folder-path input and Import action that calls the existing importer rather than reimplementing it. Explain that the folder must exist on the machine running Streamlit. **Pass:** importing a new photo from the UI creates one database row; repeating it creates none.
- [ ] **Branch `feat/sqlite-gallery` — Anthony:** Add an explicit Process pending photos action connected to section 2, with completion/failure feedback; prevent ordinary Streamlit reruns from launching captioning again. **Pass:** staff can open the app, register a photo, process it, and see its saved caption without manually running Python scripts.

## 4. Build a semantic index from SQLite

Purpose: turn current captions and descriptive metadata into searchable vectors. Pipeline steps 11–12.

Suggested owner: Anthony. Depends on the section 0 contract and captioned rows from section 2.

- [ ] **Branch `feat/semantic-index` — Anthony:** Add Sentence Transformers and FAISS dependencies, choose one exact embedding model, and record its identifier. Add a reusable searchable-text builder in proposed `search.py`. **Pass:** a known SQLite row produces documented text containing its caption and agreed descriptive fields.
- [ ] **Branch `feat/semantic-index` — Anthony:** Embed valid captioned records, build the FAISS index, and save an ordered photo-ID mapping alongside it under ignored `indexes/`. Record model identity and normalization/distance choices. **Pass:** every indexed vector resolves to exactly one existing SQLite ID.
- [ ] **Branch `feat/semantic-index` — Anthony:** Add proposed `scripts/build_index.py` as a documented rebuild command; handle no eligible records cleanly. **Pass:** rebuilding twice produces the expected record count without accumulating duplicate entries.
- [ ] **Branch `feat/semantic-index` — Both:** Test search directly with a natural-language query encoded by the same model and compatible normalization. **Pass:** returned IDs resolve to SQLite rows, and a paraphrased query retrieves an expected test photo without requiring exact word overlap. Record the query and observed results.

## 5. Connect semantic results to the gallery

Purpose: replace keyword counting with the semantic search path. Pipeline steps 13–16.

Suggested owner: Anthony. Depends on sections 3–4.

- [ ] **Branch `feat/semantic-search-ui` — Anthony:** Wire the search box to query embedding → FAISS ranking → SQLite lookup. Preserve ranking when loading records; show current captions and attributes from SQLite. **Pass:** gallery order matches returned ranked IDs, rather than database row order.
- [ ] **Branch `feat/semantic-search-ui` — Anthony:** Add an explicit initial/rebuild-index action and clear feedback for a missing or incompatible index. Newly captioned photos must become searchable after rebuilding. **Pass:** the UI explains an absent index and can create a usable one.
- [ ] **Branch `feat/semantic-search-ui` — Both:** Test the complete import → process → index → query → selected-photo flow using three photos. **Pass:** the same SQLite ID can be traced through every stage; no JSON export is required to operate the app.

## 6. Add the three related-photo actions

Purpose: selecting a photo opens the three discovery routes required by Track B. Pipeline step 17.

Suggested owner: Blake. Depends on sections 3–5. Label-entry controls here feed the unified review-save action in section 7.

- [ ] **Branch `feat/related-photo-pivots` — Blake:** Add Same event using an exact SQLite query on a nonempty confirmed `event_group`. **Pass:** known members of one test event appear; an unrelated event with the same activity does not.
- [ ] **Branch `feat/related-photo-pivots` — Blake:** Add Same venue using an exact SQLite query on a nonempty confirmed `venue`. **Pass:** photos from two events at one confirmed venue appear together; unrelated generic settings do not.
- [ ] **Branch `feat/related-photo-pivots` — Blake:** Add Similar participant descriptions using a selected person's clothing/gear description and candidate participant text, not whole-scene embeddings. Label results as descriptive matches. **Pass:** similar clothing can match across different scenes; sharing only background objects does not drive the match.
- [ ] **Branch `feat/related-photo-pivots` — Blake:** Handle unknown labels and missing participant descriptions without grouping every unknown together; offer return to previous results. **Pass:** each unavailable action explains the missing information and preserves usable navigation.

## 7. Save staff acceptance, corrections, and confirmed groups

Purpose: the app becomes a curation workspace. Pipeline step 18.

Suggested owner: Blake. Depends on section 6.

- [ ] **Branch `feat/staff-review` — Blake:** Add a repeatable SQLite migration for `review_status` with default `unreviewed` and supported values `unreviewed`, `accepted`, `edited`. Update setup for fresh databases too. **Pass:** existing IDs, captions, and metadata survive; both new and existing databases support review status.
- [ ] **Branch `feat/staff-review` — Blake:** Add Accept and Edit/Save actions to the selected-photo view. Let staff correct caption, descriptive fields, event group, and venue; validate fields and write to the selected ID. **Pass:** acceptance persists without altering content; saving an edit updates the intended row and marks it edited.
- [ ] **Branch `feat/staff-review` — Blake:** Connect event/venue entry to the pivot queries and make shared labels reusable across photos. **Pass:** staff assign two photos to one event/venue, then both related-photo actions return the saved group.
- [ ] **Branch `feat/staff-review` — Both:** Restart the app and rerun caption processing after a staff edit. **Pass:** corrections and review status persist; captioning does not replace them.

## 8. Make corrections reach search

Purpose: staff edits change subsequent retrieval. Pipeline step 19.

Suggested owner: Anthony. Depends on sections 4–7.

- [ ] **Branch `fix/search-refresh-after-edits` — Anthony:** After searchable content changes, rebuild searchable text, vectors, and the ID mapping; a complete index rebuild is acceptable. Invalidate cached gallery/search data. Acceptance without content changes needs no vector rebuild. **Pass:** a distinctive corrected description becomes searchable without restarting the app.
- [ ] **Branch `fix/search-refresh-after-edits` — Anthony:** Detect and report a failed refresh; prevent silently presenting stale results as current and provide a rebuild/retry action. **Pass:** an induced refresh failure leaves the correction safely saved and a visible recovery path.
- [ ] **Branch `fix/search-refresh-after-edits` — Both:** Save an edit, search again, restart, and repeat the search. **Pass:** saved text, related-photo groups, and search results consistently reflect the correction, with one current index entry per eligible photo.

## 9. Test the actual collection and measure results

Purpose: establish what the complete system does, rather than what its diagrams promise.

Suggested owner: Both. Depends on section 8; run the larger batch as soon as the three-photo integration works.

- [ ] **Branch `test/end-to-end-retrieval` — Both:** Import and process the supplied local collection, record the actual file count and failures, and remove test-only limits from the normal workflow. **Pass:** each eligible file has a registered row and either usable output or an explicit retryable failure; no invented dataset-size claim.
- [ ] **Branch `test/end-to-end-retrieval` — Both:** Prepare at least five labeled evaluation queries covering activity, setting, participant descriptions, and paraphrases. Measure Precision@5 and query-to-gallery latency; document scoring when fewer than five results exist, hardware, and collection size. **Pass:** results can be reproduced from a written procedure. These are team evaluation targets, not a claimed official five-query requirement.
- [ ] **Branch `test/end-to-end-retrieval` — Both:** Verify same-event and same-venue results against known groups; inspect false participant matches. **Pass:** record observed failures and limitations alongside successful examples.
- [ ] **Branch `test/end-to-end-retrieval` — Both:** Rehearse the full staff flow: open app → import uncaptioned photos → process → index → search → select → demonstrate all three pivots → accept/edit → search corrected content → restart. **Pass:** both developers can complete the workflow from the written setup without manual database repair.

## 10. Package and submit the working system

Purpose: satisfy the challenge deliverables and make the demonstrated system reproducible. Draft these alongside implementation; finalize after section 9.

Suggested owner: Both.

- [ ] **Branch `docs/submission` — Both:** Replace stale `README.txt` instructions with tested environment installation, exact model downloads, setup, processing, indexing, and app-launch commands; document local path behavior and first-run downloads. **Pass:** the other developer follows them successfully on their machine.
- [ ] **Branch `docs/submission` — Both:** Update the architecture/workflow diagram to match the implemented SmolVLM, Llama/Ollama, SQLite, Sentence Transformers, FAISS, and Streamlit handoffs. **Pass:** every depicted connection exists in the demonstrated workflow.
- [ ] **Branch `docs/submission` — Both:** Export a structured sample mapping paths and IDs to caption, activity, setting, person descriptions, confirmed groups, and review status. Use synthetic records for public artifacts; keep any real derived data within the permitted submission channel. **Pass:** the sample matches the implemented schema and is valid JSON/CSV or a usable database sample.
- [ ] **Branch `docs/submission` — Both:** Write a concise system card with exact models, measured results, errors, unknown handling, descriptive-match limits, and bias/privacy limitations. Write a governance note covering local processing, data minimization, no facial recognition, access controls, and post-event custody restrictions. **Pass:** claims match tested behavior and actual operating practices.
- [ ] **Branch `docs/submission` — Both:** Check the organizers' current submission deadline, destination, and required team details; prepare the demo and required assets. **Pass:** one person verifies the submission package against the Problem Case 2 deliverables and event instructions.
- [ ] **Branch `release/mvp` — Both:** Merge the verified integrated `dev` into `main` through review and smoke-test that exact revision. **Pass:** the submitted revision completes the rehearsed flow; prototype limitations are disclosed.

## Stretch — only after the complete MVP and submission essentials work

These tasks are optional enhancements, not substitutes for fixing a broken handoff above.

- [ ] **Branch `feat/hybrid-search` — Owner TBD:** Parse complex queries into filters and apply them before semantic top-k selection. **Pass:** a requested confirmed venue restricts candidates before ranking.
- [ ] **Branch `feat/original-output-history` — Owner TBD:** Preserve original AI output separately and add timestamped reviewer changes. **Pass:** current corrected values and their history remain distinguishable after restart.
- [ ] **Branch `feat/stable-group-ids` — Owner TBD:** Replace free-text event/venue grouping with stable group IDs and editable names. **Pass:** renaming a group preserves membership and photo IDs.
- [ ] **Branch `feat/bulk-curation` — Owner TBD:** Add bulk review/editing and richer retry/progress controls. **Pass:** staff can update a selected batch without changing unselected records.
- [ ] **Branch `perf/incremental-index` — Owner TBD:** Refresh only changed vectors while preserving ID mapping. **Pass:** one edit replaces exactly one indexed representation, with no duplicates.
- [ ] **Branch `test/expanded-evaluation` — Owner TBD:** Expand to 10–20 labeled queries, add Recall@5 with complete relevance labels, and compare retrieval before/after corrections. **Pass:** publish measured outcomes and false-match examples without exposing sensitive data.
