# 📚 AI Home Tutor (V1)

A privacy-first study mentor for kids. It watches the notebook **only on demand**
(when a "Check" button is pressed — no continuous recording), reads the
handwriting, grades it, and gives a hint instead of the answer.

> 📐 **Architecture & workflow deep-dive:** see [ARCHITECTURE.md](ARCHITECTURE.md)
> (diagrams, data flow per feature, provider routing, deployment).

## V1 capabilities

- **Dictation tutor** — reads a sentence aloud (browser TTS), the child writes it,
  the camera snapshot is graded: spelling, missing words, capitalization,
  punctuation, overall score. Grading is deterministic (no AI needed).
- **Homework checker** — reads the question + the child's answer, finds the
  mistake, gives one guiding hint and a 0–10 score.
- **Progress** — per-student weak-topic tracking and a daily recommendation.
- **Camera** — laptop/USB webcam via the browser today; Tapo C201 RTSP is wired
  in (`TAPO_RTSP_URL`, needs `requirements-tapo.txt`).
- **Offline mock mode** — runs and is fully testable with no API key.

## Project layout

```
ai-home-tutor/
├─ backend/
│  ├─ app/
│  │  ├─ main.py          FastAPI app + static mount
│  │  ├─ config.py        env settings
│  │  ├─ ai_client.py     OpenAI wrapper + mock
│  │  ├─ vision.py        image → text (+ Tapo RTSP grab)
│  │  ├─ evaluator.py     deterministic dictation scoring
│  │  ├─ db.py            SQLite storage + progress
│  │  └─ routers/         health, students, dictation, homework, tutor
│  ├─ tests/              unit + API tests (mock mode)
│  └─ requirements*.txt
├─ frontend/              webcam UI (index.html, app.js, style.css)
├─ Dockerfile
└─ docker-compose.yml
```

## Run locally (no key needed — mock mode)

```powershell
cd ai-home-tutor\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
$env:AI_MODE = "mock"
uvicorn app.main:app --reload
```

Open http://localhost:8000 → Start camera → try Dictation / Homework.

## Run with real AI

Copy `.env.example` to `.env`, set `AI_MODE=auto` and `OPENAI_API_KEY=...`
(your key from `OPEN_API_KEY.txt`). Then run uvicorn or Docker Compose.

## Use a local Ollama LLM — no API key (recommended)

A self-contained Ollama image with `llama3.2:1b` baked in is published as
`sabya610/ai-home-tutor-ollama:1b`. The whole stack runs offline via compose:

```powershell
cd ai-home-tutor
docker compose up          # starts ollama (llama3.2:1b) + the tutor
```

Or point a dev server at a standalone Ollama container:

```powershell
docker run -d -p 11434:11434 -e OLLAMA_KEEP_ALIVE=-1 sabya610/ai-home-tutor-ollama:1b
```

```env
AI_MODE=auto
TUTOR_BASE_URL=http://localhost:11434/v1
TUTOR_MODEL=llama3.2:1b
TUTOR_API_KEY=not-needed
TUTOR_MAX_TOKENS=220        # cap keeps the CPU-only model responsive
```

Then open the **🗣️ Ask** tab (or say “teach me the 2 times table”). On CPU, 1b
answers in ~15 s; on a GPU box you can rebuild `ollama/Dockerfile` with
`llama3.2:3b` for higher quality. Vision (handwriting) stays mock unless you add
a vision key — type answers or use dictation.

## Use your cluster llama3 (rag-app) as the tutor

The tutor LLM (hints/scoring/explanations) can point at the llama3 served by
your rag-app, while vision (handwriting) stays on OpenAI or you type answers.
See [cluster/README.md](cluster/README.md). Quick version:

```env
AI_MODE=auto
TUTOR_BASE_URL=http://localhost:8080/v1   # rag-app OpenAI endpoint (port-forwarded)
TUTOR_MODEL=llama3.1-8b
TUTOR_API_KEY=not-needed
```

Check it: `GET /api/health` (shows endpoints) and `GET /api/health/llm`
(live one-token ping to the tutor).

## Test

```powershell
cd ai-home-tutor\backend
pytest -q
```

## Docker

```powershell
cd ai-home-tutor
docker build -t sabya610/ai-home-tutor:v5 .
docker run --rm -p 8000:8000 -e AI_MODE=mock sabya610/ai-home-tutor:v5
```

## Push to Docker Hub (run yourself — needs your login)

```powershell
docker login
docker push sabya610/ai-home-tutor:v5
```

## Privacy notes

- No continuous video: frames are captured only on a button press.
- Only the cropped snapshot (or recognized text) is sent to the AI.
- Learning data stays in a local SQLite file (`data/tutor.db`).
