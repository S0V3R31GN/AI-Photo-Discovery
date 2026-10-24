from transformers import BlipProcessor, BlipForConditionalGeneration
from PIL import Image
import ollama, json

processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")

def caption(path):
    image = Image.open(path).convert("RGB")
    inputs = processor(image, return_tensors="pt")
    out = model.generate(**inputs, max_new_tokens=40)
    return processor.decode(out[0], skip_special_tokens=True)

def metadata(cap):
    prompt = f"""Caption: "{cap}"
Return JSON with keys: event, location, attributes (list).
Use "unknown" if the caption doesn't say."""
    res = ollama.generate(model="llama3.2:3b", prompt=prompt, format="json")
    return json.loads(res["response"])

cap = caption("photos/test.jpg")
print(cap)
print(metadata(cap))
