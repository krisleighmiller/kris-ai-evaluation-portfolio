#!/bin/bash
# The verifier entrypoint: runs the baked pytest suite and writes the reward.
# Both reward files carry the same literal (Harbor reads reward.json first when
# both exist); 0 is written first so a verifier that crashes still scores 0, 1
# only when pytest exits 0, and 0 again when it does not, so a reward planted
# mid-run cannot survive a failing suite. Never install anything here: the
# verifier runs offline, so verifier dependencies belong in tests/Dockerfile.
#
# Harbor creates /logs/verifier 0777, and unlink() is gated on the directory
# rather than the file, so any uid could otherwise replace a root-owned 0644
# reward file. This suite executes the agent's artifact as uid 1001, so take
# the group and world write bits off the directory before the first reward is
# written. 0755 keeps world read and traverse, which is what the host user
# needs to collect the reward; never drop those.

chmod 0755 /logs/verifier

echo 0 > /logs/verifier/reward.txt
echo '{"reward": 0}' > /logs/verifier/reward.json

if pytest --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -rA; then
    echo 1 > /logs/verifier/reward.txt
    echo '{"reward": 1}' > /logs/verifier/reward.json
else
    echo 0 > /logs/verifier/reward.txt
    echo '{"reward": 0}' > /logs/verifier/reward.json
fi
