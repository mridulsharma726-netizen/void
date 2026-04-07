# VOID - Text-Based Assistant

VOID is a text-based assistant that runs in the terminal, works offline, and uses Ollama locally for AI replies.

## Setup Instructions

1. **Install Python**: Ensure you have Python 3.8+ installed.

2. **Install Dependencies**:
   ```
   pip install -r requirements.txt
   ```

3. **Install Ollama**:
   - Download and install Ollama from [ollama.ai](https://ollama.ai).
   - On Windows, run the installer.

4. **Pull the Model**:
   - Open a terminal and run:
     ```
     ollama pull llama3.2:3b
     ```
   - This downloads the llama3.2:3b model locally.

5. **Start Ollama Server**:
   - Run:
     ```
     ollama serve
     ```
   - Keep this running in the background.

## 🚀 Quick Start (Recommended)

1. **Navigate to VOID directory**
2. **Run launcher** (auto-starts server + UI):
   ```bash
   python launcher.py
   ```
   - ✅ Backend server starts (localhost:8000)  
   - ✅ UI opens in browser → "Online" status
   - ✅ Ollama check (optional for chat)

## Terminal Mode (Advanced)

```bash
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```
Open [UI](ui/index.html) manually.

## Example Commands

- `system info`: Get system information.
- `remember Buy groceries`: Save a note.
- `recall groceries`: Search and recall notes.
- `internet`: Check internet status.
- `exit`: Quit the assistant.
- Any other text: Ask the local LLM.

## Features

- Tool router: Matches commands to tools, else uses LLM.
- Local memory with SQLite.
- Internet check.
- Offline operation.
