# backend/server.py
import os
import inspect
import importlib
import importlib.util
import json
from flask import Flask, request, jsonify
from flask_cors import CORS

# fallback uploaded file path (your uploaded backup)
UPLOADED_APP_PATH = "/mnt/data/f784105b-88b4-4ab0-9913-96cb20a4bea7.py"

def load_chat_response():
    try:
        mod = importlib.import_module("app")
        if hasattr(mod, "chat_response"):
            return mod.chat_response
    except Exception:
        pass

    try:
        spec = importlib.util.spec_from_file_location("uploaded_app", UPLOADED_APP_PATH)
        if spec and spec.loader:
            uploaded = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(uploaded)
            if hasattr(uploaded, "chat_response"):
                return uploaded.chat_response
    except Exception as e:
        raise ImportError(f"Couldn't import chat_response from app or uploaded path: {e}")

    raise ImportError("chat_response not found in app module nor in uploaded file.")

try:
    chat_response = load_chat_response()
    load_error = None
except Exception as exc:
    chat_response = None
    load_error = str(exc)

app = Flask(__name__)
CORS(app)

def safe_metadata(obj):
    """
    Convert metadata to something JSON-serializable.
    Prefer to json.dumps with default=str, then json.loads to keep structure.
    If that fails, return a short string representation.
    """
    try:
        # json.dumps with default=str will convert non-serializable objects using str()
        dumped = json.dumps(obj, default=str)
        return json.loads(dumped)
    except Exception:
        try:
            return {"_metadata_str": str(obj)}
        except Exception:
            return {"_metadata_error": "unserializable"}

@app.route("/api/chat", methods=["POST"])
def api_chat():
    if chat_response is None:
        return jsonify({"error": "server configuration error", "detail": load_error}), 500

    data = request.get_json(force=True, silent=True) or {}
    message = data.get("message", "")
    session_id = data.get("session_id")
    model_name = data.get("model")
    token_limit = data.get("token_limit")

    if not message:
        return jsonify({"error": "message is required"}), 400

    try:
        sig = inspect.signature(chat_response)
        params = sig.parameters

        kwargs = {}
        if "message" in params:
            kwargs["message"] = message
        else:
            return jsonify({"error": "chat_response signature missing 'message' parameter"}), 500

        if "session_id" in params:
            kwargs["session_id"] = session_id
        if "model_name" in params:
            kwargs["model_name"] = model_name
        if "token_limit" in params:
            kwargs["token_limit"] = token_limit

        result = chat_response(**kwargs)

        if not isinstance(result, dict):
            try:
                result = dict(result)
            except Exception:
                return jsonify({"error": "chat_response returned non-dict result", "detail": str(result)}), 500

        # Safely convert metadata (avoid passing model objects directly to jsonify)
        raw_meta = result.get("metadata", {})
        metadata_safe = safe_metadata(raw_meta)

        return jsonify({
            "reply": result.get("reply", ""),
            "model": result.get("model", model_name or ""),
            "metadata": metadata_safe,
            "sources": result.get("sources", [])
        })

    except TypeError as te:
        return jsonify({"error": "server error", "detail": f"TypeError calling chat_response: {te}"}), 500
    except Exception as e:
        return jsonify({"error": "server error", "detail": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=True)
