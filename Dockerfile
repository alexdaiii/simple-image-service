FROM ubuntu:24.04 AS builder

COPY --from=ghcr.io/astral-sh/uv:0.7.11 /uv /uvx /bin/

# Install all build and runtime deps
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libtiff5-dev libjpeg8-dev libopenjp2-7-dev zlib1g-dev \
    libfreetype6-dev liblcms2-dev libwebp-dev tcl8.6-dev tk8.6-dev \
    libharfbuzz-dev libfribidi-dev libxcb1-dev \
    libavif-dev libaom-dev dav1d rav1e \
    software-properties-common build-essential \
    && rm -rf /var/lib/apt/lists/*


ENV PYTHON_VERSION=3.13

RUN add-apt-repository ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    python${PYTHON_VERSION} python${PYTHON_VERSION}-venv python${PYTHON_VERSION}-dev \
    python${PYTHON_VERSION}-tk python${PYTHON_VERSION}-gdbm \
    && rm -rf /var/lib/apt/lists/*

# Build & install a modern libavif
COPY requirements.txt ./

# Install dependencies globally with uv
RUN uv venv --python=/usr/bin/python${PYTHON_VERSION} /opt/venv && \
    uv pip install --python /opt/venv/bin/python --no-cache-dir -r requirements.txt

RUN uv pip install --python /opt/venv/bin/python --no-cache-dir --upgrade Pillow --no-binary :all: -C avif=enable -C webp=enable -C jpeg=enable -C zlib=enable

FROM ubuntu:24.04

ENV PYTHON_VERSION=3.13

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libtiff6 libjpeg-turbo8 libopenjp2-7 zlib1g \
    libfreetype6 liblcms2-2 libwebp7 libwebpmux3 libwebpdemux2 tcl8.6 tk8.6 \
    libharfbuzz0b libfribidi0 libxcb1 \
    libavif16 libaom3 dav1d rav1e \
    software-properties-common \
    && rm -rf /var/lib/apt/lists/*

RUN add-apt-repository ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    python${PYTHON_VERSION} python${PYTHON_VERSION}-venv \
    && apt-get purge -y software-properties-common && \
    rm -f /etc/apt/sources.list.d/deadsnakes-ubuntu-ppa-*.list && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

# Create config and data directories and volumes
RUN mkdir -p /config /data
VOLUME ["/config", "/data"]

COPY --from=builder /opt/venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH"

COPY /app /app

WORKDIR /app

EXPOSE 8000

CMD ["fastapi", "run", "main.py"]