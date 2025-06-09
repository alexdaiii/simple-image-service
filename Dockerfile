FROM python:3.13-slim-bookworm AS builder
COPY --from=ghcr.io/astral-sh/uv:0.7.11 /uv /uvx /bin/

COPY requirements.txt ./

# Install dependencies globally with uv
RUN uv venv /opt/venv && \
    uv pip install --python /opt/venv/bin/python --no-cache-dir -r requirements.txt

FROM python:3.13-slim-bookworm

# Create config and data directories and volumes
RUN mkdir -p /config /data
VOLUME ["/config", "/data"]

COPY --from=builder /opt/venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH"

COPY /app /app

WORKDIR /app

EXPOSE 8000

CMD ["fastapi", "run", "main.py"]