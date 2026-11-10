# Dental Clinic RAG Chatbot — Starter Project

## What this starter includes
- Python backend
- Gradio browser chat UI
- ChromaDB persistent local vector database
- Editable clinic knowledge in `data/clinic_knowledge.md`
- Hugging Face Inference Providers for answer generation

## Requirements
- Windows 10/11
- Python 3.11 or 3.12 recommended
- Internet access for package installation, embedding-model download on first run, and Hugging Face inference
- Hugging Face token with inference permissions

## Setup on Windows PowerShell

1. Open this folder in VS Code.
2. Create a virtual environment:

   ```powershell
   py -3.11 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   If PowerShell blocks activation, run this for the current terminal only:
   `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`
   Then activate the environment again.

3. Install packages:

   ```powershell
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. Copy `.env.example` to `.env`, then replace the placeholder with your Hugging Face token. Never share or commit `.env`.

5. Review and edit `data/clinic_knowledge.md`. The included content is sample data, not verified clinic information.

6. Build or rebuild the vector database:

   ```powershell
   python build_kb.py
   ```

7. Start the chat:

   ```powershell
   python app.py
   ```

8. Open the local URL printed in the terminal, usually `http://127.0.0.1:7860`.

## Updating clinic data
1. Edit `data/clinic_knowledge.md`.
2. Stop the app with Ctrl+C.
3. Run `python build_kb.py` to rebuild the database.
4. Run `python app.py` again.

The build script replaces the existing demo collection. Keep a backup of your knowledge file.

## Model and free-tier note
Hugging Face Inference Providers have limited free monthly credits and limits can change. This is not guaranteed to be free for unlimited use. Check current pricing and model/provider availability before relying on it. You can change `HF_MODEL` in `.env`.

## Important production gaps
This is a learning prototype, not a production-ready clinical system. Before real patient use, add authentication where appropriate, HTTPS, rate limits, logging controls, monitoring, privacy and consent notices, access controls, backups, robust tests, and a reviewed clinical safety workflow. Do not store patient health details in logs or send real patient data to a third-party model without clinic approval and appropriate privacy/security review.
