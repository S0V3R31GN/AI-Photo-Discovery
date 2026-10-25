import sqlite3
import numpy as np
import sqlite_vec
from sentence_transformers import SentenceTransformer

print("Loading embedding model...", flush=True)
model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

texts = [
    "A person in blue holding balloons at a celebration.",
    "A mechanic repairing a car engine in a garage.",
]
vectors = model.encode(texts, normalize_embeddings=True)
query = model.encode(
    "Someone carrying balloons while wearing blue",
    normalize_embeddings=True,
)

assert np.isfinite(vectors).all()
assert np.isfinite(query).all()
dimension = vectors.shape[1]
print(f"PASS: embeddings generated; dimension={dimension}", flush=True)

connection = sqlite3.connect(":memory:")
try:
    connection.enable_load_extension(True)
    sqlite_vec.load(connection)
    connection.enable_load_extension(False)

    connection.execute(
        f"CREATE VIRTUAL TABLE demo USING vec0("
        f"embedding float[{dimension}] distance_metric=cosine)"
    )

    for i, vector in enumerate(vectors, start=1):
        connection.execute(
            "INSERT INTO demo(rowid, embedding) VALUES (?, ?)",
            (i, sqlite_vec.serialize_float32(vector.tolist())),
        )

    results = connection.execute(
        "SELECT rowid, distance FROM demo "
        "WHERE embedding MATCH ? AND k = ? ORDER BY distance",
        (sqlite_vec.serialize_float32(query.tolist()), 2),
    ).fetchall()

    for photo_id, distance in results:
        print(f"{distance:.4f}: {texts[photo_id - 1]}")

    assert results[0][0] == 1, "Expected balloons first"
    print("PASS: SQLite semantic retrieval works")
finally:
    connection.close()