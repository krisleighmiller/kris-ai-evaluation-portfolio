FROM ubuntu@sha256:33ceb71981b602c1a7443a53469e4dba065f7503eab3078a2d7a57a2ab987517

# Terminal agents drive the container through tmux, so the image must include it.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        binutils \
        binutils-gold \
        build-essential \
        ca-certificates \
        lld \
        mold \
        python3 \
        strace \
        tmux \
    && rm -rf /var/lib/apt/lists/*

COPY generate_workload.py workload-format.md /opt/linkbench-generator/
RUN python3 /opt/linkbench-generator/generate_workload.py \
        --output /app/workload \
        --workload-id visible-104729 \
        --seed 104729 \
        --units 640 \
        --functions 56 \
        --archives 12 \
        --compile-jobs 2 \
        --response-layout one-per-line \
        --format-doc /opt/linkbench-generator/workload-format.md \
    && rm -rf /opt/linkbench-generator

COPY starter-linkbench.py /app/linkbench
COPY lab/ /app/lab/
RUN mkdir -p /app/lab/bin \
    && gcc -O2 -std=c11 -Wall -Wextra -Werror \
        /app/lab/control_linker.c \
        -o /app/lab/control_linker \
    && rm /app/lab/control_linker.c \
    && ln -s ../control_linker /app/lab/bin/gcc \
    && ln -s ../control_linker /app/lab/bin/ld.bfd \
    && ln -s ../control_linker /app/lab/bin/ld.bfd-alt \
    && ln -s ../control_linker /app/lab/bin/ld.gold \
    && ln -s ../control_linker /app/lab/bin/ld.gold-alt \
    && ln -s ../control_linker /app/lab/bin/ld.gold-helper \
    && ln -s ../control_linker /app/lab/bin/ld.lld \
    && ln -s ../control_linker /app/lab/bin/ld.lld-alt \
    && ln -s ../control_linker /app/lab/bin/ld.mold \
    && ln -s ../control_linker /app/lab/bin/ld.mold-alt \
    && chmod 0755 \
        /app/linkbench \
        /app/lab/audit_run.py \
        /app/lab/control_linker \
    && chmod -R a+rX /app/workload /app/lab

WORKDIR /app
