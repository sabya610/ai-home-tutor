# Ollama with the llama3.2:1b model baked in — the tutor's LLM backend.
# Runs an OpenAI-compatible server on :11434 (/v1/chat/completions), so the
# AI Home Tutor can use it with no API key and no runtime model download.
# (1b chosen for CPU speed; change to llama3.2:3b for higher quality on a GPU.)
FROM ollama/ollama:latest

# Serve on all interfaces so the port can be published / reached in-compose.
ENV OLLAMA_HOST=0.0.0.0:11434

# Pre-pull the model into the image layer (self-contained, offline-ready).
# Fail the build if the pull fails, so we never ship an empty image.
RUN bash -c 'ollama serve & pid=$!; \
    for i in $(seq 1 60); do ollama list >/dev/null 2>&1 && break; sleep 1; done; \
    if ! ollama pull llama3.2:1b; then kill $pid; exit 1; fi; \
    ollama show llama3.2:1b >/dev/null || { kill $pid; exit 1; }; \
    kill $pid'

EXPOSE 11434
# Base image ENTRYPOINT already runs "ollama serve".
