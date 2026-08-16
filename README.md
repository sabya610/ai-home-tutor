# 📚 AI Home Tutor (V1)

A privacy-first study mentor for kids. It watches the notebook **only on demand**
(when a "Check" button is pressed — no continuous recording), reads the
handwriting, grades it, and gives a hint instead of the answer.

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
docker build -t sabya610/ai-home-tutor:v3 .
docker run --rm -p 8000:8000 -e AI_MODE=mock sabya610/ai-home-tutor:v3
```

## Push to Docker Hub (run yourself — needs your login)

```powershell
docker login
docker push sabya610/ai-home-tutor:v3
```

## Privacy notes

- No continuous video: frames are captured only on a button press.
- Only the cropped snapshot (or recognized text) is sent to the AI.
- Learning data stays in a local SQLite file (`data/tutor.db`).
