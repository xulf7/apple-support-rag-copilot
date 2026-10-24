"""One Flask application, process-local RAG resources, no import-time work."""
import argparse

from flask import Flask, jsonify, render_template, request

from src.generation import GenerationSettings
from src.service import InvalidQuestion, RagService, ResourcesUnavailable, response


def create_app(config=None, *, service=None, service_factory=None):
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.update(MAX_CONTENT_LENGTH=16384)
    if config:
        app.config.update(config)
    startup = None
    if service is None:
        factory = service_factory or RagService.from_local
        try:
            service = factory()
        except ResourcesUnavailable as exc:
            startup = {"code": exc.code, "message": exc.message, "commands": exc.commands}
        except Exception:
            startup = {"code": "startup_failed", "message": "Backend initialization failed. Check local resources and restart.",
                       "commands": ["python -B -m src.check_environment", "python -B -m src.retrieval inspect"]}
    app.extensions["rag_service"] = service
    app.extensions["rag_startup_error"] = startup

    @app.after_request
    def headers(result):
        result.headers["X-Content-Type-Options"] = "nosniff"
        result.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"
        result.headers["Cache-Control"] = "no-store"
        return result

    @app.get("/")
    def home():
        return render_template("index.html")

    @app.get("/api/status")
    def status():
        if service is None:
            return jsonify({"retrieval": "unavailable", "startup_error": startup,
                            "generation": GenerationSettings.from_env().public_state()}), 503
        return jsonify(service.status())

    @app.post("/api/chat")
    def chat():
        if not request.is_json:
            return jsonify(response("invalid_request", "Use application/json.", code="unsupported_media")), 415
        body = request.get_json(silent=True)
        if not isinstance(body, dict) or set(body) != {"question"} or not isinstance(body["question"], str):
            return jsonify(response("invalid_request", "Send a JSON object with one string question field.", code="invalid_payload")), 400
        if not body["question"].strip():
            return jsonify(response("invalid_request", "Question must not be empty.", code="invalid_question")), 400
        if len(body["question"]) > 2000 or any(ord(c) < 32 and c not in "\n\t" for c in body["question"]):
            return jsonify(response("invalid_request", "Use up to 2000 characters without control characters.", code="invalid_question")), 400
        if service is None:
            result = response("service_unavailable", startup["message"], code=startup["code"])
            result["repair_commands"] = startup["commands"]
            return jsonify(result), 503
        try:
            result = service.ask(body["question"])
        except InvalidQuestion as exc:
            return jsonify(response("invalid_request", str(exc), code="invalid_question")), 400
        except Exception as exc:
            app.logger.warning("Retrieval request failed (%s)", type(exc).__name__)
            return jsonify(response("service_unavailable", "Retrieval failed. Check resources and restart the application.", code="retrieval_failed")), 503
        http_status = 200
        if result["status"] == "generation_failed":
            code = result["error"]["code"]
            http_status = 504 if code == "generation_timeout" else 503 if code == "generation_busy" else 502
        return jsonify(result), http_status

    @app.errorhandler(413)
    def too_large(error):
        return jsonify(response("invalid_request", "Request body exceeds 16 KB.", code="request_too_large")), 413

    @app.errorhandler(405)
    def wrong_method(error):
        return jsonify(response("invalid_request", "Use POST /api/chat for questions.", code="method_not_allowed")), 405

    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()
    create_app().run(host="127.0.0.1", port=args.port, debug=False, load_dotenv=False,
                     use_reloader=False, threaded=True)


if __name__ == "__main__":
    main()
