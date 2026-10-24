1. Install Ollama from https://ollama.com/download/windows
2. In PowerShell, run ollama pull llama3.2:3b
3. Put all test photos in photos folder. Because we're working with sensitive datasets, every time you clone from GitHub, the photos folder is empty due to it being in the .gitignore. You'll need to put your own test photos with each fresh clone. Besides that, your own photos will persist locally on your own machine.
4. In PowerShell, to test captioning, run:
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
The current test expects photos/test.jpg