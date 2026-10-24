## MVP

Build order: ingestion and captions → search and gallery → related-photo pivots → staff review and refreshed search → evaluation and submission.

Completed statuses and ownership below are carried over from the previous checklist; new tasks remain unassigned.

### 1. Setup and ingestion

- [Done] Agree on initial MVP metadata schema and task ownership
- [Done] Set up shared repo
- [Done] Set up shared Python environment
- [Anthony- done] Exclude photos, metadata, databases, and indexes from Git
- [Blake- in progress] Document dependencies and setup
- [Anthony- done] Import JPG/JPEG/PNG photos with stable IDs
- [Anthony- done] Store metadata and photo paths in SQLite
- [Anthony- done] Skip already registered photo paths without overwriting existing records

### 2. Local captions and structured attributes

- [Blake -in progress] Confirm a vision-capable local model (HuggingFaceTB/SmolVLM-500M-Instruct) and document its exact model name and runtime; llama3.2:3b is text-only and outputs main json
- [Blake- in progress] Generate captions and non-biometric attributes locally
- [Blake- in progress] Allow unknown values instead of forced guesses
- [Done- pending changes] Agree on structured metadata keys for activity, setting, and descriptive participant attributes
- [Blake- Done] Update existing photo rows by ID; preserve existing captions, metadata, staff edits, event_group, and venue
- [Blake- in progress ] Validate model output before saving; report failed photos without marking them successfully processed


### 3. Semantic search and gallery

- [ ] Generate Sentence Transformers embeddings from current captions and descriptive metadata; build a FAISS index mapped to photo IDs
- [ ] Encode natural-language queries with the same embedding model and return ranked photo IDs
- [ ] Display a ranked Streamlit photo gallery
- [ ] Show a selected photo and its caption, attributes, event group, and venue

### 4. Related-photo pivots

- [ ] Support staff-editable event_group and venue values; distinguish a specific event/venue from generic activity/setting descriptions
- [ ] Pivot to all photos in the same staff-confirmed event group
- [ ] Pivot to all photos at the same staff-confirmed venue
- [ ] Pivot using descriptive participant attributes rather than the whole scene; label results as descriptive matches, not verified identity
- [ ] Handle unknown event groups, venues, and participant attributes without grouping unrelated unknown records together

### 5. Staff review and persistence

- [ ] Add persistent review_status values: unreviewed, accepted, edited
- [ ] Accept an unchanged record or edit its caption, attributes, event group, and venue; persist the decision and current values in SQLite
- [ ] Refresh embeddings/index after saved edits so subsequent searches use the corrected record; a full rebuild is acceptable for MVP
- [ ] Verify records, review status, corrections, and usable search results persist after restart, rebuilding the index if needed

### 6. Evaluation and submission

- [ ] Test one complete workflow: import uncaptioned photos → caption → search → select photo → demonstrate all three pivots → accept/edit → search again → restart
- [ ] Create at least 5 representative queries with manually labeled relevant photos, including activity, setting, and participant-description queries
- [ ] Report Precision@5 and measured query-to-results latency on the test set; state dataset size and test hardware
- [ ] Test event and venue pivots against known groups and inspect participant-description false matches
- [ ] Demonstrate at least one correction changing subsequent retrieval results; report the observed effect
- [ ] Prepare README with install, model download, processing, indexing, and app-launch commands
- [ ] Update the architecture diagram to match the implemented models, runtime, fields, and correction workflow
- [ ] Prepare a non-sensitive structured sample mapping photo IDs/paths to captions, activity, setting, participant attributes, event groups, venues, and review status; use synthetic/example records for public artifacts
- [ ] Prepare a system card: model choices, measured results, limitations, unknown/out-of-distribution handling, and bias/privacy risks
- [ ] Prepare a governance note: local processing, no biometric identity tracking, Git exclusions, and post-event data custody/use restrictions
- [ ] Rehearse the end-to-end demo, explain operational value for staff, and submit required deliverables

## Stretch — Full Architecture Using the Same Stack

Start after the MVP workflow and submission essentials work.

### Search and schema

- [ ] Combine structured filters with semantic ranking; filter eligible records before limiting to top results
- [ ] Parse complex queries into attribute filters
- [ ] Migrate to the full schema as needed: explicit activity/setting fields, structured attributes, and stable event/venue IDs; preserve existing photo IDs and staff corrections
- [ ] Preserve original AI output separately from current staff-reviewed values
- [ ] Add review timestamps and timestamped edit history

### Processing and staff workflow

- [Anthony] Verify caption processing can be rerun without overwriting completed records
- [ ] Add batch editing and bulk review
- [ ] Add processing progress, per-photo error details, and retry controls
- [ ] Resume interrupted caption batches and retry failed photos without regenerating completed records
- [ ] Refresh only changed embeddings, maintaining exactly one current vector per indexed photo
- [ ] Improve previews, sorting, and navigation

### Expanded evaluation

- [ ] Expand evaluation to 10–20 labeled queries
- [ ] Add Recall@5 using complete relevance labels for the evaluation collection
- [ ] Compare retrieval quality before and after staff corrections across the test set
