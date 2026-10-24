1. Install Ollama from https://ollama.com/download/windows
2. In PowerShell, run ollama pull llama3.2:3b
3. Put all test photos in photos folder. Because we're working with sensitive datasets, every time you pull a branch on GitHub, the photos folder is empty due to it being in the .gitignore. You'll need to put your own test photos in every time.
4. In PowerShell, to test captioning, run .\.venv\Scripts\python.exe caption.py