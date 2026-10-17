#!/bin/bash
set -euo pipefail

install -m 0755 "$(dirname "$0")/linkbench.py" /app/linkbench

test -f /app/linkbench
test -x /app/linkbench
test "$(stat -c '%s' /app/linkbench)" -le 1048576
