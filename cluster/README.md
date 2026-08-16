# Using cluster llama3 (rag-app) as the tutor LLM

The AI Home Tutor splits AI into two roles:

- **Vision** (handwriting OCR) — needs a *vision* model (GPT-4o). llama3 is
  text-only and **cannot** do this. Dictation still works fully (deterministic
  scoring), and homework/typed answers work without vision.
- **Tutor** (hints, explanations, homework scoring) — plain text. **This is the
  part you can point at your cluster llama3.**

So: keep vision on OpenAI (or type answers), and route the tutor to llama3.

## The catch

Your rag-app only exposes an HTML RAG form (`/`, `/upload`, `/history`) — there
is **no JSON/OpenAI API**, and its answers are grounded in HPE support context
(wrong for tutoring). Two ways to get a clean llama3 endpoint:

### Option A — Add an OpenAI-compatible route to rag-app (recommended)

Reuses the already-loaded 8B model (no extra memory). See
[rag_app_openai_endpoint.py](rag_app_openai_endpoint.py) for the drop-in Flask
blueprint and 3-step install. After redeploying, the rag-app serves
`/v1/chat/completions`.

Reach it from your laptop for testing via port-forward:

```bash
kubectl -n rag-app port-forward svc/rag-app-service 8080:80
```

Then run the tutor with:

```env
AI_MODE=auto
TUTOR_BASE_URL=http://localhost:8080/v1
TUTOR_MODEL=llama3.1-8b
TUTOR_API_KEY=not-needed
# Vision: add OPENAI_API_KEY for handwriting OCR, or leave blank and type answers.
```

If you deploy the tutor **inside** the cluster, use in-cluster DNS instead:

```env
TUTOR_BASE_URL=http://rag-app-service.rag-app.svc.cluster.local/v1
```

### Option B — Standalone llama.cpp server (no rag-app change)

Run a dedicated OpenAI-compatible server with the same GGUF (loads the model a
second time, needs the `.gguf` mounted):

```bash
python -m llama_cpp.server \
  --model /models/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf \
  --host 0.0.0.0 --port 8080 --n_ctx 4096
```

Point `TUTOR_BASE_URL=http://<host>:8080/v1`.

## Verify connectivity

```bash
curl http://localhost:8000/api/health        # shows tutor endpoint + mock flags
curl http://localhost:8000/api/health/llm     # live one-token ping to the tutor
```

`/api/health/llm` returns `{"ok": true, "reply": "OK"}` on success, or
`{"ok": false, "error": "..."}` with the failure reason.

## Notes

- llama3 may not support OpenAI JSON mode. The tutor auto-detects a custom
  `TUTOR_BASE_URL` and switches to prompt-based JSON with tolerant parsing, so a
  chatty reply still becomes a valid score/hint (never crashes).
- Force behavior with `TUTOR_JSON_MODE=json|prompt|auto`.
- No secrets belong in `TUTOR_BASE_URL`; only the host/path is shown in health.
