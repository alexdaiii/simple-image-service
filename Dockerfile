FROM python:3.13-bookworm AS builder
COPY --from=ghcr.io/astral-sh/uv:0.7.11 /uv /uvx /bin/

# Install system dependencies (libavif)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libtiff5-dev libjpeg62-turbo-dev libopenjp2-7-dev zlib1g-dev \
    libfreetype6-dev liblcms2-dev libwebp-dev tcl8.6-dev tk8.6-dev python3-tk \
    libharfbuzz-dev libfribidi-dev libxcb1-dev \
    libavif-dev libaom-dev dav1d rav1e \
    build-essential cmake ninja-build nasm \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./

# Install dependencies globally with uv
RUN uv venv /opt/venv && \
    uv pip install --python /opt/venv/bin/python --no-cache-dir -r requirements.txt

COPY depends /depends

RUN cd /depends && \


RUN uv pip install --python /opt/venv/bin/python --no-cache-dir --upgrade Pillow --no-binary :all: -C avif=enable

FROM python:3.13-slim-bookworm

# Install system dependencies (libavif)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libavif-dev libaom-dev dav1d rav1e \
    && rm -rf /var/lib/apt/lists/*

# Create config and data directories and volumes
RUN mkdir -p /config /data
VOLUME ["/config", "/data"]

COPY --from=builder /opt/venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH"

COPY /app /app

WORKDIR /app

EXPOSE 8000

CMD ["fastapi", "run", "main.py"]