FROM python:3.13-slim-trixie

# The verifier decodes and measures the delivered master with ffmpeg/ffprobe
# (Debian build; apt versions are intentionally not pinned) and does the
# pixel/audio math in numpy. Bake everything here; tests/test.sh must not
# install anything at verify time.
RUN apt-get update && apt-get install -y \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
        pytest==9.1.1 \
        pytest-json-ctrf==0.5.2 \
        numpy==2.5.2

# Harbor does not upload tests/ in separate verifier mode; the verifier image
# must own the test files, the authored ground truth, the spec copies, and
# the input hashes.
COPY . /tests/

# Pre-create parent dirs for top-level artifacts declared in task.toml.
RUN mkdir -p /app/footage
