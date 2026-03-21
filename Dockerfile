FROM mcr.microsoft.com/playwright/python:v1.58.0-noble

RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    cp /root/.local/bin/uv /usr/local/bin/uv

RUN useradd -m -s /bin/bash appuser && \
    mkdir -p /app && \
    chown appuser:appuser /app

WORKDIR /app

USER appuser

COPY pyproject.toml uv.lock ./

RUN uv sync && \
    uv run playwright install chromium

COPY . .

CMD ["uv", "run", "--env-file", ".env", "src/main.py"]
