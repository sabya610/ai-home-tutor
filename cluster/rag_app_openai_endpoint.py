"""OPTIONAL add-on for the HPE rag-app (llama.cpp + Flask).

Exposes the ALREADY-LOADED llama3 model as an OpenAI-compatible endpoint so
external tools (e.g. AI Home Tutor) can reuse it WITHOUT loading the 8B model
a second time. It calls ``current_app.llama.create_chat_completion(...)``
directly (no RAG retrieval), so tutoring prompts are answered by the raw model.

How to enable in the rag-app repo (rag_app1/rag_app):
  1. Copy this file to  app/routes/llm_openai_routes.py
  2. In app/__init__.py -> create_app(), after the existing blueprint is
     registered, add:

         from app.routes.llm_openai_routes import llm_bp
         app.register_blueprint(llm_bp)

  3. Rebuild + push the image, then bump the rag-app deployment.

The rag-app Service is ClusterIP :80 -> targetPort 5000, so once enabled the
endpoint is reachable in-cluster at:
    http://<release>-service.<namespace>.svc.cluster.local/v1
"""

from __future__ import annotations

import time
import uuid

from flask import Blueprint, current_app, jsonify, request

llm_bp = Blueprint("llm_openai", __name__)


@llm_bp.route("/v1/models", methods=["GET"])
def list_models():
    return jsonify(
        {
            "object": "list",
            "data": [
                {"id": "llama3.1-8b", "object": "model", "owned_by": "rag-app"}
            ],
        }
    )


@llm_bp.route("/v1/chat/completions", methods=["POST"])
def chat_completions():
    body = request.get_json(force=True, silent=True) or {}
    messages = body.get("messages")
    if not messages:
        return jsonify({"error": "messages required"}), 400

    kwargs = {
        "messages": messages,
        "max_tokens": int(body.get("max_tokens", 512)),
        "temperature": float(body.get("temperature", 0.2)),
    }
    if body.get("top_p") is not None:
        kwargs["top_p"] = float(body["top_p"])
    # Pass response_format through only if the caller asked (llama.cpp supports
    # {"type": "json_object"} on recent builds; older builds may reject it).
    if isinstance(body.get("response_format"), dict):
        kwargs["response_format"] = body["response_format"]

    llama = getattr(current_app, "llama", None)
    if llama is None:
        return jsonify({"error": "llama model not loaded"}), 503

    result = llama.create_chat_completion(**kwargs)

    # llama-cpp-python already returns an OpenAI-shaped dict; fill identifiers.
    result.setdefault("id", "chatcmpl-" + uuid.uuid4().hex[:24])
    result.setdefault("object", "chat.completion")
    result.setdefault("created", int(time.time()))
    result["model"] = body.get("model", "llama3.1-8b")
    return jsonify(result)
