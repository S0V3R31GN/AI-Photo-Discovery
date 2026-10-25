"""Local semantic retrieval and transaction-safe replacement of photo vectors."""
from functools import lru_cache
import numpy as np
import sqlite_vec
import db

MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
INDEX_VERSION = 1


@lru_cache(maxsize=1)
def get_encoder():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(MODEL_ID)


def embed(texts):
    vectors = np.asarray(get_encoder().encode(texts, normalize_embeddings=True), dtype=np.float32)
    if vectors.ndim != 2 or vectors.shape[0] != len(texts) or not np.isfinite(vectors).all():
        raise ValueError("Encoder returned invalid vectors")
    if np.any(np.linalg.norm(vectors, axis=1) == 0):
        raise ValueError("Encoder returned a zero vector")
    return vectors


def build_search_text(record):
    parts = []
    for field, label in (("event", "Activity"), ("location", "Setting"),
                         ("people", "People"), ("objects", "Objects"),
                         ("user_input", "Staff notes")):
        value = record[field]
        if isinstance(value, list):
            value = ", ".join(value)
        if value and value.strip() and value.strip().lower() != "unknown":
            parts.append(f"{label}: {value}.")
    return "\n".join(parts)


def prepare_photo(record, previous=None):
    text = build_search_text(record)
    people = record["people"]
    with db.connect() as connection:
        indexed = _has_index(connection) and connection.execute(
            "SELECT 1 FROM indexed_photos WHERE photo_id=?", (record["id"],)
        ).fetchone() is not None
    general_changed = previous is None or not indexed or build_search_text(previous) != text
    people_changed = previous is None or not indexed or previous["people"] != people
    texts = ([text] if general_changed and text else []) + (people if people_changed else [])
    result = {"text": text, "general": None, "people": [], "dimension": None,
              "general_changed": general_changed, "people_changed": people_changed}
    if texts:
        vectors = embed(texts)
        has_general = general_changed and bool(text)
        result.update(general=vectors[0] if has_general else None,
                      people=list(vectors[1:] if has_general else vectors) if people_changed else [],
                      dimension=vectors.shape[1])
    return result


def _blob(vector):
    return sqlite_vec.serialize_float32(vector.tolist())


def _has_index(connection):
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='search_index_meta'"
    ).fetchone() is not None


def ensure_schema(connection, dimension):
    dimension = int(dimension)
    if dimension <= 0:
        raise ValueError("Invalid embedding dimension")
    connection.execute("""CREATE TABLE IF NOT EXISTS search_index_meta (
        singleton INTEGER PRIMARY KEY CHECK(singleton=1), model_id TEXT NOT NULL,
        dimension INTEGER NOT NULL, version INTEGER NOT NULL)""")
    meta = connection.execute("SELECT * FROM search_index_meta WHERE singleton=1").fetchone()
    expected = (MODEL_ID, dimension, INDEX_VERSION)
    if meta and (meta["model_id"], meta["dimension"], meta["version"]) != expected:
        raise RuntimeError("Embedding index configuration changed. Run scripts/reindex.py.")
    if not meta:
        connection.execute("INSERT INTO search_index_meta VALUES(1, ?, ?, ?)", expected)
    connection.execute(f"""CREATE VIRTUAL TABLE IF NOT EXISTS photo_vectors USING vec0(
        photo_id TEXT PRIMARY KEY, embedding float[{dimension}] distance_metric=cosine)""")
    connection.execute("""CREATE TABLE IF NOT EXISTS person_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT, photo_id TEXT NOT NULL REFERENCES photos(id),
        person_index INTEGER NOT NULL, description TEXT NOT NULL)""")
    connection.execute("CREATE INDEX IF NOT EXISTS person_entries_photo ON person_entries(photo_id)")
    connection.execute(f"""CREATE VIRTUAL TABLE IF NOT EXISTS person_vectors USING vec0(
        embedding float[{dimension}] distance_metric=cosine)""")
    connection.execute("""CREATE TABLE IF NOT EXISTS indexed_photos (
        photo_id TEXT PRIMARY KEY REFERENCES photos(id), revision INTEGER NOT NULL,
        search_text TEXT NOT NULL)""")


def refresh_photo(connection, record, prepared):
    """Caller owns the transaction; this function never commits or calls a model."""
    if prepared["dimension"] is not None:
        ensure_schema(connection, prepared["dimension"])
    elif not _has_index(connection):
        return
    if prepared["general_changed"]:
        connection.execute("DELETE FROM photo_vectors WHERE photo_id=?", (record["id"],))
        if prepared["general"] is not None:
            connection.execute("INSERT INTO photo_vectors(photo_id, embedding) VALUES(?, ?)",
                               (record["id"], _blob(prepared["general"])))
    if prepared["people_changed"]:
        old = connection.execute("SELECT id FROM person_entries WHERE photo_id=?", (record["id"],)).fetchall()
        for row in old:
            connection.execute("DELETE FROM person_vectors WHERE rowid=?", (row["id"],))
        connection.execute("DELETE FROM person_entries WHERE photo_id=?", (record["id"],))
        for index, vector in enumerate(prepared["people"]):
            cursor = connection.execute(
                "INSERT INTO person_entries(photo_id, person_index, description) VALUES(?, ?, ?)",
                (record["id"], index, record["people"][index]))
            connection.execute("INSERT INTO person_vectors(rowid, embedding) VALUES(?, ?)",
                               (cursor.lastrowid, _blob(vector)))
    connection.execute("INSERT OR REPLACE INTO indexed_photos VALUES(?, ?, ?)",
                       (record["id"], record["revision"] + 1, prepared["text"]))


def _check_query_index(connection, dimension):
    if not _has_index(connection):
        return False
    meta = connection.execute("SELECT * FROM search_index_meta WHERE singleton=1").fetchone()
    if not meta or (meta["model_id"], meta["dimension"], meta["version"]) != (MODEL_ID, dimension, INDEX_VERSION):
        raise RuntimeError("Embedding index configuration changed. Run scripts/reindex.py.")
    return True


def _ranked_photos(connection, pairs):
    results = []
    seen = set()
    for photo_id, distance in pairs:
        if photo_id in seen:
            continue
        seen.add(photo_id)
        record = db.decode_photo(connection.execute("SELECT * FROM photos WHERE id=?", (photo_id,)).fetchone())
        if record:
            record["distance"] = float(distance)
            results.append(record)
    return results


def semantic_search(query, k=10):
    if not isinstance(query, str) or not query.strip():
        return []
    k = max(1, min(int(k), 100))
    # Empty archive shouldn't load an embedding model.
    with db.connect() as connection:
        if not _has_index(connection):
            return []
    vector = embed([query.strip()])[0]
    with db.connect() as connection:
        if not _check_query_index(connection, len(vector)):
            return []
        rows = connection.execute(
            "SELECT photo_id, distance FROM photo_vectors WHERE embedding MATCH ? AND k=? ORDER BY distance",
            (_blob(vector), k)).fetchall()
        return _ranked_photos(connection, [(r["photo_id"], r["distance"]) for r in rows])


def _pivot_group(photo_id, field):
    if field not in {"event_group", "venue"}:
        raise ValueError(field)
    with db.connect() as connection:
        selected = connection.execute(f"SELECT {field} FROM photos WHERE id=?", (photo_id,)).fetchone()
        if selected is None:
            raise KeyError(photo_id)
        value = selected[field]
        if not value or not value.strip():
            return []
        rows = connection.execute(
            f"SELECT * FROM photos WHERE {field}=? AND id<>? ORDER BY id", (value, photo_id)).fetchall()
        return [db.decode_photo(row) for row in rows]


def pivot_event(photo_id):
    return _pivot_group(photo_id, "event_group")


def pivot_venue(photo_id):
    return _pivot_group(photo_id, "venue")


def pivot_people(photo_id, person_index, k=10):
    selected = db.get_photo(photo_id)
    if selected is None:
        raise KeyError(photo_id)
    if not isinstance(person_index, int) or not 0 <= person_index < len(selected["people"]):
        raise ValueError("Choose an existing participant description")
    vector = embed([selected["people"][person_index]])[0]
    k = max(1, min(int(k), 100))
    with db.connect() as connection:
        if not _check_query_index(connection, len(vector)):
            return []
        total = connection.execute("SELECT COUNT(*) FROM person_entries").fetchone()[0]
        count = min(total, max(k * 2, 20), 4096)
        if not count:
            return []
        while True:
            rows = connection.execute("""SELECT e.photo_id, v.distance FROM person_vectors v
                JOIN person_entries e ON e.id=v.rowid
                WHERE v.embedding MATCH ? AND k=? ORDER BY v.distance""", (_blob(vector), count)).fetchall()
            pairs = [(r["photo_id"], r["distance"]) for r in rows if r["photo_id"] != photo_id]
            results = _ranked_photos(connection, pairs)
            if len(results) >= k or count >= min(total, 4096):
                return results[:k]
            count = min(total, count * 2, 4096)


def rebuild_index():
    """Encode first, then replace both indexes atomically if the snapshot is current."""
    records = db.list_photos()
    prepared = [prepare_photo(record) for record in records]
    dimension = next((p["dimension"] for p in prepared if p["dimension"] is not None), None)
    if dimension is None:
        dimension = embed(["dimension check"])[0].shape[0]
    with db.connect() as connection:
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            current = dict(connection.execute("SELECT id, revision FROM photos").fetchall())
            if current != {r["id"]: r["revision"] for r in records}:
                raise db.RevisionConflict("Photos changed during reindex. Retry.")
            for table in ("photo_vectors", "person_vectors", "person_entries", "indexed_photos", "search_index_meta"):
                connection.execute(f"DROP TABLE IF EXISTS {table}")
            ensure_schema(connection, dimension)
            for record, item in zip(records, prepared):
                refresh_photo(connection, record, item)
                connection.execute("UPDATE indexed_photos SET revision=? WHERE photo_id=?",
                                   (record["revision"], record["id"]))
    return len(records)
