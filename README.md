# MemoMind

MemoMind turns study material into a grounded memory aid. It identifies the core facts and their relationships, chooses an appropriate mnemonic technique, explains the mapping, and builds a short active recall quiz. It is a study aid, not a substitute for checking critical details against the original source.

## Features

- Paste notes or upload PDF, DOCX, and TXT files with a preview of extracted text.
- Technique selection based on the source (for example, a story for a process or chunking for numbers).
- Mnemonic breakdown, mapped key facts, content-specific memory tips, and accuracy notes.
- Five-question recall quiz with multiple choice, fill-in-the-blank, and short-answer checks.
- Responsive light and dark themes, copy actions, and source-preserving regeneration.
- Complete browser, Apple, and Android icons; installable web app manifest; Open Graph and X card previews; and native link sharing.
- Server-side Gemini API key, configurable upload/text limits, basic per-process request throttling, and friendly error handling.
- Production WSGI serving on Windows with Waitress, security headers, secure production cookie settings, and a required production secret.

## Requirements

- Windows 11 (also works on other Python platforms)
- Python 3.11.9 (or compatible Python 3.11)
- A Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey)
- Waitress is installed from `requirements.txt` for production serving.

No virtual environment or database is required. A compatible Gemini model and quota are required for AI generation. Google may change model availability and free-tier quotas; check the AI Studio page for current details.

## Install and run on Windows

Open PowerShell in this project folder and run:

```powershell
python --version
python -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

Paste your AI Studio key after `GEMINI_API_KEY=` in `.env`, save it, then start (or restart) `python app.py`. On this PC, open <http://127.0.0.1:5000>. The server also listens on the local network, so another device on the same Wi-Fi can open `http://<this-PC's-IPv4-address>:5000` (for example, `http://192.168.1.31:5000`). If Windows Firewall asks, allow Python on **Private networks only**. Keep `.env` private; it is excluded from Git.

For local development, run `python app.py`. For a production-style Windows run, configure `APP_ENV=production` as described below and run `python app.py`; it then uses Waitress instead of Flask's development server. If you use a different Python installation, use `py -3.11 -m pip install -r requirements.txt` and `py -3.11 app.py`.

## Configuration

The `.env.example` file documents the available settings:

- `GEMINI_API_KEY`: server-side Gemini key; never put this in browser code.
- `GEMINI_MODEL`: model name; defaults to `gemini-3.8-flash`.
- `GEMINI_FALLBACK_MODEL`: model used automatically if the primary returns a temporary overload or deadline error; defaults to `gemini-3.5-flash-lite`.
- `MAX_UPLOAD_MB`: upload cap (default 12 MB).
- `MAX_TEXT_CHARS`: source and extracted text cap (default 30,000 characters).
- `RATE_LIMIT_REQUESTS` and `RATE_LIMIT_WINDOW_SECONDS`: per-process IP request limit.
- `GEMINI_TIMEOUT_MS`: model request timeout in milliseconds (default 120,000).
- `GEMINI_PRIMARY_TIMEOUT_MS`: time allowed for the primary model before trying the fallback (default 25,000).
- `APP_ENV`: use `production` to serve with Waitress and enable secure production settings.
- `FLASK_SECRET_KEY`: required in production. Generate one with `python -c "import secrets; print(secrets.token_urlsafe(48))"` and store it only in `.env`.
- `PUBLIC_BASE_URL`: canonical public HTTPS origin, such as `https://memomind.example.com`; used for canonical and share-preview URLs. Leave empty for local development.
- `HOST` and `PORT`: listener address and port (defaults `0.0.0.0` and `5000`).

### Production setup

1. Set `APP_ENV=production`, `FLASK_SECRET_KEY`, and the Gemini settings in `.env`.
2. Set `PUBLIC_BASE_URL` to the HTTPS domain that will serve the site. Social preview crawlers cannot fetch a private `192.168.x.x` address.
3. Install dependencies with `python -m pip install -r requirements.txt`, then start with `python app.py`. Waitress serves the app on the configured host and port.
4. Put the service behind an HTTPS reverse proxy or managed platform before making it public. Keep `.env` out of source control.

The built-in request limiter is in-memory and intended for one server process. The application has no accounts or saved learning sessions. For a public multi-instance launch, add a shared rate-limit store, monitoring, backups for any future data, and an abuse plan before opening access broadly.

## Deploy or redeploy on Vercel

This repository includes a Vercel Flask entry point, Python 3.12 selection, and a 300-second function duration. Vercel serves the files in `public/static` from its CDN; the Flask app uses the same folder for local runs.

1. Commit and push the project to the GitHub `main` branch. In Vercel, choose **Add New → Project**, import `Naksh-Yadav/Memomind`, and deploy from the repository root. Vercel detects Flask from `app.py` and `requirements.txt`; leave Build Command and Output Directory at their defaults.
2. In the Vercel project, open **Settings → Environment Variables** and add the variables below for Production. Use Vercel's secret field for `GEMINI_API_KEY` and `FLASK_SECRET_KEY`; never commit `.env`.
3. Set `MAX_UPLOAD_MB` to `4` on Vercel because Vercel Functions cap request bodies at 4.5 MB. The upload UI reads the server limit automatically. Local `.env` can keep its 12 MB setting.
4. Set `PUBLIC_BASE_URL` to the deployed HTTPS origin (for example, `https://your-project.vercel.app`) and redeploy after changing environment variables.

Required Vercel environment variables:

```text
APP_ENV=production
FLASK_SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_urlsafe(48))">
GEMINI_API_KEY=<your Google AI Studio key>
GEMINI_MODEL=gemini-3.8-flash
GEMINI_FALLBACK_MODEL=gemini-3.5-flash-lite
GEMINI_PRIMARY_TIMEOUT_MS=25000
GEMINI_TIMEOUT_MS=120000
MAX_UPLOAD_MB=4
MAX_TEXT_CHARS=30000
RATE_LIMIT_REQUESTS=8
RATE_LIMIT_WINDOW_SECONDS=60
PUBLIC_BASE_URL=https://your-project.vercel.app
```

After the first deploy, Vercel assigns a project URL; update `PUBLIC_BASE_URL` to that URL and redeploy to activate the canonical/share-card URL. If the GitHub repository is already connected to Vercel, pushing to `main` creates the production deployment. You can also use the Vercel dashboard's **Deployments → Redeploy** action or the CLI command `vercel --prod` from this project.

Vercel's current Python runtime uses Python 3.12 by default. Its function request/response body limit is 4.5 MB, and the configured 300-second function duration covers MemoMind's Gemini fallback path.

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
