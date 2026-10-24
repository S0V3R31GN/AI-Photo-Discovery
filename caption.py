from transformers import AutoProcessor, AutoModelForImageTextToText
from PIL import Image
import ollama
import json
import os
import hashlib
MODEL_ID = "HuggingFaceTB/SmolVLM-500M-Instruct"
processor = AutoProcessor.from_pretrained(MODEL_ID, size={"longest_edge": 512})
model = AutoModelForImageTextToText.from_pretrained(MODEL_ID)

VISION_PROMPT = """Describe this photo in 2-3 sentences. Include:
- what is happening (activity, event, interaction)
- where it is happening (specific setting or venue)
- what each person is wearing or holding, including costumes, uniforms, face paint, or gear
Do not guess names, ages, race, or identity."""


def describe(path):
    image = Image.open(path).convert("RGB")
    messages = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": VISION_PROMPT}]}]
    prompt = processor.apply_chat_template(messages, add_generation_prompt=True)
    inputs = processor(text=prompt, images=[image], return_tensors="pt")
    out = model.generate(**inputs, max_new_tokens=200, do_sample=False)
    new_tokens = out[:, inputs["input_ids"].shape[1]:]
    return processor.batch_decode(new_tokens, skip_special_tokens=True)[0].strip()


def metadata(desc):
    prompt = f"""Photo description: "{desc}"

Return JSON with keys:
- event: short activity or event name
- location: specific setting (e.g. "school gym", "backyard"), or "unknown"
- people: list of short descriptions of individuals by clothing, costume, and gear only
- objects: list of notable objects
Use only the description. Never include names, ages, race, or identity. Use "unknown" or [] when unsure."""
    res = ollama.generate(model="llama3.2:3b", prompt=prompt, format="json",
                          options={"temperature": 0})
    return json.loads(res["response"])


def rich_caption(desc, meta):
    prompt = f"""Photo description: "{desc}"
Structured metadata: {json.dumps(meta)}

Write 1-2 natural sentences for a searchable photo library: what is happening, where,
and what people are wearing or holding. Use only the information above.
Never include names, ages, race, or identity. Return only the sentences."""
    res = ollama.generate(model="llama3.2:3b", prompt=prompt,
                          options={"temperature": 0})
    return res["response"].strip()


if __name__ == "__main__":
    results = []
    files = sorted(f for f in os.listdir("photos") if f.lower().endswith((".jpg", ".jpeg", ".png")))[:3]

    for i, name in enumerate(files, start=1):
        path = os.path.join("photos", name)
        desc = describe(path)
        meta = metadata(desc)
        results.append({
            "id": hashlib.sha1(name.encode()).hexdigest()[:10],
            "path": path,
            "caption": rich_caption(desc, meta),
            "vision_description": desc,
            "event": meta.get("event", "unknown"),
            "location": meta.get("location", "unknown"),
            "people": meta.get("people", []),
            "objects": meta.get("objects", []),
        })
        print(f"{i}/{len(files)} {results[-1]['id']}")

    with open("captions.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)