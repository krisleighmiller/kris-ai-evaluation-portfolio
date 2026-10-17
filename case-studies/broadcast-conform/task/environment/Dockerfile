# Agent environment: a plain media workstation. ffmpeg (Ubuntu 24.04 build,
# includes libzimg/zscale and libx264) plus python3 with numpy for scripting.
# The seed footage and the two authoritative JSON files live under /app.

FROM ubuntu:24.04

WORKDIR /app

RUN apt-get update && apt-get install -y \
        ffmpeg \
        python3 \
        python3-numpy \
    && rm -rf /var/lib/apt/lists/*

COPY data/footage /app/footage
COPY data/delivery_spec.json /app/delivery_spec.json
COPY data/timeline.json /app/timeline.json
