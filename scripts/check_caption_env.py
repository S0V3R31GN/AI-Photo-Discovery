"""Check imports and the local Ollama model; optionally load SmolVLM weights."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--load-vision', action='store_true', help='Also download/cache and load SmolVLM')
    args = parser.parse_args()
    import torch
    import transformers
    from transformers import AutoProcessor, AutoModelForImageTextToText
    import caption
    print(f'PASS: Python {sys.version.split()[0]}; torch {torch.__version__}; transformers {transformers.__version__}', flush=True)
    print('PASS: AutoProcessor and AutoModelForImageTextToText imports', flush=True)
    response = caption.get_ollama().list()
    names = [item.model for item in response.models]
    print(f'Local Ollama models: {names}', flush=True)
    if caption.OLLAMA_MODEL not in names:
        raise RuntimeError(f'Missing {caption.OLLAMA_MODEL}. Run: ollama pull {caption.OLLAMA_MODEL}')
    print(f'PASS: {caption.OLLAMA_MODEL} available at {caption.OLLAMA_HOST}', flush=True)
    if args.load_vision:
        caption.get_vision_model()
        print(f'PASS: loaded {caption.MODEL_ID}', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(f'FAIL: {type(error).__name__}: {error}', file=sys.stderr)
        raise SystemExit(1)
