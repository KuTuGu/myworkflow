FROM ubuntu:22.04

RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

RUN pip install uv

WORKDIR /app

COPY pyproject.toml .
RUN uv sync

COPY . .

CMD ["uv", "run", "src/main.py"]
