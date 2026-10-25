"""Staff photo discovery workspace; SQLite is the only normal source of truth."""
import streamlit as st
from PIL import Image, ImageOps
import db
import search

st.set_page_config(page_title="Photo Discovery", layout="wide")
st.title("Photo Discovery")
st.caption("Local photo search · staff corrections · confirmed groups")
try:
    db.migrate()
except Exception as error:
    st.error(f"Database unavailable: {error}")
    st.stop()


def show_image(record):
    try:
        with Image.open(db.resolve_stored_path(record["path"])) as image:
            st.image(ImageOps.exif_transpose(image).convert("RGB"))
    except Exception as error:
        st.warning(f"Image unavailable: {error}")


with st.sidebar:
    st.header("Archive")
    uploads = st.file_uploader("Choose photos", type=sorted(e[1:] for e in db.IMAGE_EXTENSIONS),
                               accept_multiple_files=True)
    if st.button("Register uploads", disabled=not uploads):
        added = 0
        for upload in uploads:
            try:
                db.register_upload(upload.getvalue(), upload.name)
                added += 1
            except Exception as error:
                st.error(f"{upload.name}: {error}")
        st.success(f"Registered {added} valid uploads. Duplicate content keeps its existing record.")
    batch_limit = st.number_input("Photos per processing batch", min_value=1, max_value=100, value=1)
    retry = st.checkbox("Include failed photos")
    if st.button("Process pending photos"):
        import caption
        with st.spinner("Running local captioning and embedding models…"):
            status = st.empty()
            try:
                summary = caption.process_pending(int(batch_limit), retry,
                    progress=lambda item: status.write(f"{item['id'][:12]}: {item['status']} ({item['seconds']}s)"))
                st.write({key: summary[key] for key in ("ready", "failed", "conflicts")})
                for item in summary["items"]:
                    if item["error"]:
                        st.error(f"{item['id'][:12]}: {item['error']}")
            except Exception as error:
                st.error(str(error))
    if st.button("Rebuild search indexes"):
        try:
            with st.spinner("Rebuilding local vectors…"):
                st.success(f"Indexed {search.rebuild_index()} records")
        except Exception as error:
            st.error(f"Index unchanged: {error}")
    photos = db.list_photos()
    st.write(f"{len(photos)} registered photos")
    for state in ("pending", "ready", "failed"):
        st.caption(f"{state}: {sum(p['processing_status'] == state for p in photos)}")

query = st.text_input("Search photos", placeholder="Someone wearing blue holding balloons")
mode = st.session_state.get("pivot_mode")
if mode:
    st.info(f"Navigation: {mode['label']}")
    if st.button("Return to search / archive"):
        st.session_state.pop("pivot_mode", None)
        st.rerun()
try:
    if mode:
        if mode["type"] == "event":
            results = search.pivot_event(mode["id"])
        elif mode["type"] == "venue":
            results = search.pivot_venue(mode["id"])
        else:
            results = search.pivot_people(mode["id"], mode["person_index"])
    else:
        results = search.semantic_search(query) if query.strip() else photos
except Exception as error:
    st.error(f"Retrieval failed: {error}")
    results = []

st.write(f"{len(results)} results")
if not results:
    st.caption("Search requires structured attributes and vectors. Process pending photos, or rebuild indexes for existing records.")
columns = st.columns(4)
for i, record in enumerate(results):
    with columns[i % 4]:
        show_image(record)
        st.caption(record["caption"] or "Caption pending")
        st.caption(f"{record['processing_status']} · {record['id'][:12]}")
        if "distance" in record:
            st.caption(f"Cosine distance: {record['distance']:.4f} (lower is closer)")
        if st.button("Select", key=f"select_{record['id']}"):
            st.session_state["selected_photo"] = db.get_photo(record["id"])
            st.rerun()

selected = st.session_state.get("selected_photo")
if selected:
    st.divider()
    st.subheader("Review selected photo")
    current = db.get_photo(selected["id"])
    if current is None:
        st.warning("Selected record no longer exists")
        st.stop()
    if current["revision"] != selected["revision"]:
        st.warning("This record changed since selection. Reload before saving; unsaved form edits will be discarded.")
    if st.button("Reload selected record"):
        st.session_state["selected_photo"] = current
        st.rerun()
    st.caption(f"ID: {selected['id']} · revision {selected['revision']} · {current['processing_status']}")
    if current["processing_error"]:
        st.error(current["processing_error"])
    left, right = st.columns([1, 2])
    with left:
        show_image(selected)
        st.write("Protected staff fields:", ", ".join(selected["staff_fields"]) or "None")
        if st.button("Regenerate selected photo"):
            import caption
            with st.spinner("Regenerating locally; protected fields will be retained…"):
                summary = caption.process_pending(limit=1, photo_ids=[selected["id"]])
            if summary["ready"]:
                st.session_state["selected_photo"] = db.get_photo(selected["id"])
                st.rerun()
            for item in summary["items"]:
                st.error(item["error"] or item["status"])
    with right:
        with st.form(f"review_{selected['id']}_{selected['revision']}"):
            fields = {}
            fields["caption"] = st.text_area("Caption (not used for embeddings)", selected["caption"] or "")
            fields["vision_description"] = st.text_area("Vision description (not used for embeddings)", selected["vision_description"] or "")
            for field, label in (("event", "Activity"), ("location", "Setting"),
                                 ("event_group", "Confirmed event group"), ("venue", "Confirmed venue")):
                fields[field] = st.text_input(label, selected[field] or "")
            for field, label in (("people", "Participant descriptions — one per line"),
                                 ("objects", "Objects — one per line"),
                                 ("user_input", "Additional staff notes — one per line")):
                text = st.text_area(label, "\n".join(selected[field]))
                fields[field] = [line.strip() for line in text.splitlines() if line.strip()]
            choices = ["accepted", "edited", "rejected"]
            decision = st.selectbox("Review decision", choices,
                index=choices.index(selected["review_decision"]) if selected["review_decision"] in choices else 0)
            save = st.form_submit_button("Save review")
        if save:
            # Submit actual changes; unchanged generated attributes remain unlocked.
            changed = {key: value for key, value in fields.items()
                       if value != (selected[key] if selected[key] is not None else "")}
            try:
                updated = db.save_review(selected["id"], changed, decision, selected["revision"])
                st.session_state["selected_photo"] = updated
                st.session_state["save_notice"] = "Review and affected vectors saved."
                st.rerun()
            except Exception as error:
                st.error(f"Review not saved: {error}")
    if st.session_state.pop("save_notice", None):
        st.success("Review and affected vectors saved.")
    st.subheader("Navigate from saved attributes")
    st.caption("Participant navigation compares descriptions, not verified identities. Similar clothing can describe different people.")
    event_col, venue_col, people_col = st.columns(3)
    with event_col:
        if st.button("Same confirmed event", disabled=not current["event_group"]):
            st.session_state["pivot_mode"] = dict(type="event", id=selected["id"], label=f"Event: {current['event_group']}")
            st.rerun()
    with venue_col:
        if st.button("Same confirmed venue", disabled=not current["venue"]):
            st.session_state["pivot_mode"] = dict(type="venue", id=selected["id"], label=f"Venue: {current['venue']}")
            st.rerun()
    with people_col:
        if current["people"]:
            index = st.selectbox("Participant description", range(len(current["people"])),
                                 format_func=lambda i: current["people"][i])
            if st.button("Similar participant descriptions"):
                st.session_state["pivot_mode"] = dict(type="people", id=selected["id"], person_index=index,
                    label=f"Similar descriptions: {current['people'][index]}")
                st.rerun()
        else:
            st.caption("No participant descriptions saved.")
