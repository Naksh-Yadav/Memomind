# MemoMind

MemoMind turns study material into a grounded memory aid. It identifies the core facts and their relationships, chooses an appropriate mnemonic technique, explains the mapping, and builds a short active recall quiz. It is a study aid, not a substitute for checking critical details against the original source.

## Features

- Paste notes or upload PDF, DOCX, and TXT files with a preview of extracted text.
- Technique selection based on the source (for example, a story for a process or chunking for numbers).
- Mnemonic breakdown, mapped key facts, content-specific memory tips, and accuracy notes.
- Five-question recall quiz with multiple choice, fill-in-the-blank, and short-answer checks.
- Responsive light and dark themes, copy actions, and source-preserving regeneration.
- Server-side Gemini API key, configurable upload/text limits, basic per-process request throttling, and friendly error handling.

## Requirements

- Windows 11 (also works on other Python platforms)
- Python 3.11.9 (or compatible Python 3.11)
- A Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey)

No virtual environment or database is required. A compatible Gemini model and quota are required for AI generation. Google may change model availability and free-tier quotas; check the AI Studio page for current details.

## Install and run on Windows

Open PowerShell in this project folder and run:

```powershell
python --version
python -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
python app.py
```

Paste your AI Studio key after `GEMINI_API_KEY=` in `.env`, save it, then start (or restart) `python app.py`. On this PC, open <http://127.0.0.1:5000>. The server also listens on the local network, so another device on the same Wi-Fi can open `http://<this-PC's-IPv4-address>:5000` (for example, `http://192.168.1.31:5000`). If Windows Firewall asks, allow Python on **Private networks only**. Keep `.env` private; it is excluded from Git.

The project dependencies are Flask, the official `google-genai` SDK, PyMuPDF, python-docx, and python-dotenv. If you use a different Python installation, use `py -3.11 -m pip install -r requirements.txt` and `py -3.11 app.py`.

## Configuration

The `.env.example` file documents the available settings:

- `GEMINI_API_KEY`: server-side Gemini key; never put this in browser code.
- `GEMINI_MODEL`: model name; defaults to `gemini-2.5-flash`.
- `GEMINI_FALLBACK_MODEL`: model used automatically if the primary returns a temporary overload or deadline error; defaults to `gemini-3.5-flash-lite`.
- `MAX_UPLOAD_MB`: upload cap (default 12 MB).
- `MAX_TEXT_CHARS`: source and extracted text cap (default 30,000 characters).
- `RATE_LIMIT_REQUESTS` and `RATE_LIMIT_WINDOW_SECONDS`: per-process IP request limit.
- `GEMINI_TIMEOUT_MS`: model request timeout in milliseconds (default 120,000).
- `GEMINI_PRIMARY_TIMEOUT_MS`: time allowed for the primary model before trying the fallback (default 25,000).

## API

- `GET /api/health` — server status and whether an API key is configured (never returns the key).
- `POST /api/extract` — multipart form upload with `file`; returns extracted text and counts.
- `POST /api/generate` — JSON body `{ "text": "..." }`; returns a validated learning guide.

Uploaded files are read into the request and are not kept in an uploads directory. Text is sent to Google Gemini only when generation is requested.

## Limitations and troubleshooting

- Image-only or scanned PDFs need OCR first; MemoMind reports this rather than inventing extracted text.
- DOCX paragraph text and tables are extracted. Complex layouts, embedded images, and some unusual document structures may not preserve their original visual arrangement.
- Generation depends on network access, Gemini service availability, API key permissions, supported model names, and per-account quotas. On a quota error, wait and retry or review AI Studio. Free quotas can change and are not unlimited.
- If the site says “Setup needed,” add the key to `.env` and restart Flask. If generation times out, try a smaller section. Split sources that exceed the configured text limit.
- The built-in rate limit is process-local and intended for a local MVP, not a multi-worker public deployment. Do not expose Flask's development server directly to the public internet.

## Tests

Run the standard-library tests with:

```powershell
python -m unittest discover -s tests -v
```

The suite tests source validation, model output validation, PDF/DOCX/TXT extraction, and Flask API validation/error paths. Gemini calls are not made by the offline test suite.
