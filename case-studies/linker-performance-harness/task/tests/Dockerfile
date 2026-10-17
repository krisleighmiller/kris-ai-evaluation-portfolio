FROM ubuntu@sha256:33ceb71981b602c1a7443a53469e4dba065f7503eab3078a2d7a57a2ab987517

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        binutils \
        binutils-gold \
        build-essential \
        libssl-dev \
        lld \
        mold \
        python3 \
        python3-venv \
        strace \
        util-linux \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir \
        pytest==9.1.1 \
        pytest-json-ctrf==0.5.2

COPY . /tests/

RUN mkdir -p /app /opt/control/bin /opt/control/libexec /opt/workloads \
    && cc -O2 -Wall -Wextra -Werror \
        /tests/control_tool.c -lcrypto -o /tmp/control-tool \
    && install -m 0111 /tmp/control-tool /opt/control/libexec/control-tool \
    && for name in gcc probe ld.bfd ld.bfd-alt ld.gold ld.gold-alt ld.gold-helper ld.gold-spoof ld.lld ld.lld-alt ld.lld2 ld.mold ld.mold-alt; do \
        ln -s ../libexec/control-tool "/opt/control/bin/$name"; \
       done \
    && rm /tmp/control-tool \
    && cp -a /tests/controlled-workload /opt/workloads/controlled \
    && python3 /tests/generate_native.py --output /opt/workloads/native \
    && chmod -R a+rX /opt/workloads \
    && chmod 0711 /opt/control /opt/control/bin /opt/control/libexec \
    && chmod 0111 /opt/control/libexec/control-tool \
    && chmod -R go-rwx /tests

ENV PATH="/opt/verifier-venv/bin:/usr/bin:/bin"
