# ── Builder stage ────────────────────────────────────────────────────────────
FROM ghcr.io/astral-sh/uv:python3.10-bookworm-slim AS builder

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONDONTWRITEBYTECODE=0

# Build-time system deps (compiler toolchain + headers)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git build-essential cmake ninja-build libxcb1 && \
    rm -rf /var/lib/apt/lists/*

# Install all Python dependencies into a venv so they are easy to copy
RUN uv venv /opt/venv
ENV VIRTUAL_ENV=/opt/venv PATH="/opt/venv/bin:$PATH"

# Install CPU-only torch + torchvision first (avoids pulling the massive CUDA wheels)
RUN uv pip install \
        --index-url https://download.pytorch.org/whl/cpu \
        "torch>=2.0.0" torchvision torchaudio

RUN uv pip install \
        "txtai[pipeline,graph]==8.3.1" \
        "faiss-cpu==1.10.0" \
        trio "httpx>=0.28.1" "pydantic-settings>=2.0" \
        "networkx>=2.8.0" "matplotlib>=3.5.0" "PyPDF2>=2.0.0" \
        "python-docx>=0.8.11" "python-louvain>=0.16.0" \
        "fast-langdetect>=0.1.0" datasets \
        "transformers>=4.30.0" "sentence-transformers>=2.2.0" \
        "beautifulsoup4>=4.10.0" \
        "pandas>=1.3.0" "markdown>=3.3.0" \
        "mcp==1.3.0"

# Install the project itself
COPY . /app/
RUN uv pip install -e .

# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM ghcr.io/astral-sh/uv:python3.10-bookworm-slim AS runtime

WORKDIR /app

# Only runtime system libs (no compiler toolchain)
RUN apt-get update && \
    apt-get install -y --no-install-recommends libxcb1 libgl1 libglib2.0-0 git && \
    rm -rf /var/lib/apt/lists/*

# Copy the venv and app from builder
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app /app

ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app \
    UV_COMPILE_BYTECODE=1

# Make scripts executable
RUN chmod +x /app/docker-entrypoint.sh /app/download_models.py && \
    mkdir -p /data/embeddings

# Model download args (optional bake-in)
ARG HF_TRANSFORMERS_MODELS=""
ARG HF_SENTENCE_TRANSFORMERS_MODELS=""
ARG HF_CACHE_DIR=""

RUN if [ -n "$HF_CACHE_DIR" ] && [ -d "$HF_CACHE_DIR" ]; then \
        mkdir -p /root/.cache/huggingface && \
        ln -s "$HF_CACHE_DIR" /root/.cache/huggingface/hub; \
    fi

RUN if [ -n "$HF_TRANSFORMERS_MODELS" ] || [ -n "$HF_SENTENCE_TRANSFORMERS_MODELS" ]; then \
        python /app/download_models.py \
            --transformers "$HF_TRANSFORMERS_MODELS" \
            --sentence-transformers "$HF_SENTENCE_TRANSFORMERS_MODELS"; \
    fi

# Runtime environment
ENV TXTAI_STORAGE_MODE=persistence \
    TXTAI_INDEX_PATH=/data/embeddings \
    TXTAI_DATASET_ENABLED=true \
    TXTAI_DATASET_NAME=web_questions \
    TXTAI_DATASET_SPLIT=train \
    PORT=8000 \
    HOST=0.0.0.0 \
    TRANSPORT=sse \
    EMBEDDINGS_PATH=/data/embeddings \
    HF_TRANSFORMERS_MODELS=$HF_TRANSFORMERS_MODELS \
    HF_SENTENCE_TRANSFORMERS_MODELS=$HF_SENTENCE_TRANSFORMERS_MODELS

EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
