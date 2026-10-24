import json
import streamlit as st

st.set_page_config(page_title="Photo Search", layout="wide")
st.title("Photo Search")

with open("captions.json", encoding="utf-8") as f:
    photos = json.load(f)

def search(query, k=10):
    words = query.lower().split()
    scored = []
    for p in photos:
        text = " ".join([p["caption"], p["event"], p["location"], *p["attributes"]]).lower()
        score = sum(w in text for w in words)
        if score:
            scored.append((score, p))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in scored[:k]]

query = st.text_input("Search photos", placeholder="children celebrating indoors")

results = search(query) if query else photos
cols = st.columns(4)
for i, p in enumerate(results):
    with cols[i % 4]:
        st.image(p["path"])
        st.caption(p["caption"])