FROM mcr.microsoft.com/playwright/python:v1.58.0-noble

RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    cp /root/.local/bin/uv /usr/local/bin/uv

RUN useradd -m -s /bin/bash appuser && \
    mkdir -p /app && \
    chown appuser:appuser /app

WORKDIR /app

USER appuser

COPY --chown=appuser:appuser pyproject.toml uv.lock ./

RUN uv sync --frozen && \
    uv run playwright install chromium

COPY --chown=appuser:appuser . .
