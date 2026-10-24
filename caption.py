from transformers import BlipProcessor, BlipForConditionalGeneration
from PIL import Image
import ollama
import json

processor = BlipProcessor.from_pretrained(
    "Salesforce/blip-image-captioning-base"
)
model = BlipForConditionalGeneration.from_pretrained(
    "Salesforce/blip-image-captioning-base"
)


def caption(path):
    image = Image.open(path).convert("RGB")
    inputs = processor(image, return_tensors="pt")
    out = model.generate(**inputs, max_new_tokens=40)
    return processor.decode(out[0], skip_special_tokens=True)


def metadata(cap):
    prompt = f"""Caption: "{cap}"
Return JSON with keys: event, location, attributes (list).
Use "unknown" if the caption doesn't say."""
    res = ollama.generate(
        model="llama3.2:3b",
        prompt=prompt,
        format="json"
    )
    return json.loads(res["response"])


if __name__ == "__main__":
    import os

    results = []
    files = sorted(f for f in os.listdir("photos") if f.lower().endswith((".jpg", ".jpeg", ".png")))

    for i, name in enumerate(files, start=1):
        path = os.path.join("photos", name)
        cap = caption(path)
        meta = metadata(cap)
        results.append({
            "id": name,
            "path": path,
            "caption": cap,
            "event": meta.get("event", "unknown"),
            "location": meta.get("location", "unknown"),
            "attributes": meta.get("attributes", []),
        })
        print(f"{i}/{len(files)} {name}: {cap}")

    with open("captions.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)