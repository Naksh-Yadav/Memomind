"""MemoMind Flask application."""
from collections import defaultdict, deque
from threading import Lock
import logging
import os
import time

from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import RequestEntityTooLarge

from config import Config
from services.document_service import extract_document
from services.gemini_service import generate
from services.validation_service import InputError, validate_source

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("memomind")


def create_app(config_override=None):
    app = Flask(__name__, static_folder="public/static", static_url_path="/static")
    app.config.from_object(Config)
    if config_override:
        app.config.update(config_override)
    requests_by_ip = defaultdict(deque)
    rate_lock = Lock()

    @app.errorhandler(InputError)
    def input_error(error):
        return jsonify({"error": str(error)}), error.status_code

    @app.errorhandler(RequestEntityTooLarge)
    def too_large(_error):
        return jsonify({"error": f"That file is too large. The upload limit is {app.config['MAX_FILE_BYTES'] // (1024 * 1024)} MB."}), 413

    @app.errorhandler(Exception)
    def unexpected_error(error):
        logger.exception("Unhandled request error", exc_info=error)
        return jsonify({"error": "Something went wrong while processing your request. Please try again."}), 500

    def check_rate_limit():
        now = time.monotonic()
        ip = request.remote_addr or "unknown"
        with rate_lock:
            bucket = requests_by_ip[ip]
            while bucket and now - bucket[0] > app.config["RATE_LIMIT_WINDOW_SECONDS"]:
                bucket.popleft()
            if len(bucket) >= app.config["RATE_LIMIT_REQUESTS"]:
                return False
            bucket.append(now)
        return True

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/health")
    def health():
        configured = bool(app.config["GEMINI_API_KEY"])
        return jsonify({
            "status": "ok",
            "ai_configured": configured,
            "model": app.config["GEMINI_MODEL"] if configured else None,
            "max_upload_bytes": app.config["MAX_FILE_BYTES"],
        })

    @app.context_processor
    def sharing_metadata():
        site_url = app.config["PUBLIC_BASE_URL"] or request.url_root.rstrip("/")
        return {
            "site_url": site_url,
            "canonical_url": site_url + request.path,
            "social_image_url": site_url + "/static/assets/og-card.png",
        }

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'; object-src 'none'; "
            "img-src 'self' data:; script-src 'self'; style-src 'self' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; connect-src 'self'",
        )
        if request.path.startswith("/api/") or request.path == "/":
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.post("/api/extract")
    def extract():
        if not check_rate_limit():
            return jsonify({"error": "Too many requests. Wait a minute and try again."}), 429
        uploaded = request.files.get("file")
        if uploaded is None:
            raise InputError("Choose a file to upload.")
        data = uploaded.read(app.config["MAX_FILE_BYTES"] + 1)
        if len(data) > app.config["MAX_FILE_BYTES"]:
            raise InputError("That file is too large. Choose a smaller document.", 413)
        return jsonify(extract_document(uploaded.filename or "", data, app.config["MAX_TEXT_CHARS"]))

    @app.post("/api/generate")
    def generate_route():
        if not check_rate_limit():
            return jsonify({"error": "Too many requests. Wait a minute and try again."}), 429
        source = validate_source((request.get_json(silent=True) or {}).get("text"), app.config["MAX_TEXT_CHARS"])
        if not app.config["GEMINI_API_KEY"]:
            return jsonify({"error": "AI generation is not configured yet. Add GEMINI_API_KEY to the local .env file and restart MemoMind."}), 503
        try:
            result = generate(
                source,
                app.config["GEMINI_API_KEY"],
                app.config["GEMINI_MODEL"],
                app.config["GEMINI_TIMEOUT_MS"],
                app.config["GEMINI_FALLBACK_MODEL"],
                app.config["GEMINI_PRIMARY_TIMEOUT_MS"],
            )
            return jsonify(result)
        except Exception as exc:
            error_name = type(exc).__name__.lower()
            message = str(exc).lower()
            if any(s in error_name + message for s in ("429", "resource_exhausted", "quota", "rate limit")):
                return jsonify({"error": "Gemini's free-tier quota or rate limit has been reached. Wait before retrying or check your Google AI Studio quota."}), 429
            if any(s in error_name + message for s in ("401", "403", "api key", "permission denied", "unauthenticated")):
                return jsonify({"error": "Gemini could not authenticate this API key. Check GEMINI_API_KEY in .env."}), 503
            if any(s in error_name + message for s in ("timeout", "deadline")):
                return jsonify({"error": "Gemini took too long to respond. Try a shorter section or retry in a moment."}), 504
            logger.warning("Gemini generation failed (%s)", type(exc).__name__)
            return jsonify({"error": "MemoMind could not generate a result right now. Check your connection and model settings, then retry."}), 502

    return app


app = create_app()

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "5000"))
    if app.config["APP_ENV"] == "production":
        from waitress import serve
        serve(app, host=host, port=port, threads=8, channel_timeout=240)
    else:
        app.run(host=host, port=port, debug=False)
