#!/usr/bin/env python3
"""Root-owned observer for controlled driver, linker and probe evidence."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import secrets
import signal
import socket
import struct
import time
from pathlib import Path


LINKERS = ("bfd", "gold", "lld", "mold")
DECOY_SUFFIX = "-alt"
ALIAS_FAMILY = {"lld2": "lld", "gold-spoof": "bfd"}
CONTROL_AUTH_KEY = b"phase4-observer-auth-3f99d7c1"
THREAD_MASKS = {"bfd": 0, "gold": 3, "lld": 4, "mold": 12}
VERSIONS = {
    "bfd": "GNU ld controlled 1.0",
    "gold": "GNU gold controlled 1.0",
    "lld": "LLD controlled 1.0",
    "mold": "mold controlled 1.0",
}
TIMED_DELAYS_MS = {
    "bfd": [180, 140, 220, 160, 200],
    "gold": [140, 100, 180, 120, 160],
    "lld": [100, 60, 140, 80, 120],
    "mold": [60, 20, 100, 40, 80],
}
FAULT_INDEX = {
    "identity_mismatch": 1,
    "identity_mismatch_timed": 9,
    "identity_path_change": 13,
    "identity_family_spoof": 0,
    "identity_family_change": 13,
    "late_failure": 21,
    "no_output": 5,
    "corrupt_output": 5,
    "non_regular_output": 5,
    "probe_failure": 5,
    "probe_stdout_mismatch": 5,
    "probe_stderr_mismatch": 5,
}
FAULT_ACTION = {
    "late_failure": "fail",
    "no_output": "no_output",
    "corrupt_output": "corrupt",
    "non_regular_output": "non_regular",
    "probe_failure": "probe_fail",
}
PEER_CREDENTIALS = getattr(socket, "SO_PEERCRED", 17)


class RequestError(RuntimeError):
    """A controlled tool request violated scenario state."""


def peer_executable(pid: int, uid: int, gid: int) -> str:
    """Read a traced peer's executable through a credential-matched helper."""
    read_fd, write_fd = os.pipe()
    helper = os.fork()
    if helper == 0:
        os.close(read_fd)
        try:
            os.setgroups([])
            os.setgid(gid)
            os.setuid(uid)
            result = f"OK\t{os.readlink(f'/proc/{pid}/exe')}"
        except OSError as exc:
            result = f"ERROR\t{exc.errno}\t{exc.strerror}"
        os.write(write_fd, result.encode("utf-8"))
        os.close(write_fd)
        os._exit(0)
    os.close(write_fd)
    response = os.read(read_fd, 4096).decode("utf-8", errors="replace")
    os.close(read_fd)
    os.waitpid(helper, 0)
    if response.startswith("OK\t"):
        return response.removeprefix("OK\t")
    try:
        _, error_text, message = response.split("\t", 2)
        error = int(error_text)
    except (ValueError, TypeError) as exc:
        raise OSError(f"peer executable helper failed: {response!r}") from exc
    raise OSError(error, message)


class EvidenceWriter:
    """Write root-only HMAC-authenticated JSON records."""

    def __init__(self, evidence_path: Path, secret_path: Path) -> None:
        self.secret = secrets.token_bytes(32)
        secret_path.write_bytes(self.secret)
        os.chmod(secret_path, 0o600)
        descriptor = os.open(
            evidence_path,
            os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
            0o600,
        )
        self.handle = os.fdopen(descriptor, "w", encoding="utf-8", buffering=1)
        self.sequence = 0

    def write(self, event: str, **fields: object) -> dict:
        self.sequence += 1
        record = {
            "sequence": self.sequence,
            "event": event,
            "server_ns": time.monotonic_ns(),
            **fields,
        }
        canonical = json.dumps(
            record,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        signature = hmac.new(self.secret, canonical, hashlib.sha256).hexdigest()
        self.handle.write(
            json.dumps(
                {"record": record, "signature": signature},
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        )
        return record

    def close(self) -> None:
        self.handle.close()


class Scenario:
    """State machine for one controlled harness execution."""

    def __init__(
        self,
        name: str,
        manifest: dict,
        tools: dict[str, Path],
        report: Path,
        writer: EvidenceWriter,
    ) -> None:
        self.name = name
        self.manifest = manifest
        self.tools = tools
        self.report = report
        self.writer = writer
        self.sequence = list(manifest["warmup_order"])
        for order in manifest["timed_rounds"]:
            self.sequence.extend(order)
        self.expected_index = 0
        self.pending_route: dict | None = None
        self.active: dict[str, dict] = {}
        self.completed: dict[str, dict] = {}
        self.probed: set[str] = set()
        self.timed_occurrence = {linker: 0 for linker in LINKERS}
        self.family_change_active = False

    def authenticate(
        self,
        connection: socket.socket,
    ) -> tuple[int, str, str]:
        packed = connection.getsockopt(
            socket.SOL_SOCKET,
            PEER_CREDENTIALS,
            struct.calcsize("3i"),
        )
        pid, uid, gid = struct.unpack("3i", packed)
        challenge = secrets.token_hex(16)
        connection.sendall(f"CHALLENGE\t{challenge}\n".encode("utf-8"))
        envelope = receive_request(connection)
        try:
            marker, peer, supplied_hmac, request = envelope.split("\t", 3)
        except ValueError as exc:
            raise RequestError("authenticated request envelope is invalid") from exc
        if marker != "AUTH" or peer not in self.tools:
            raise RequestError("request does not name a controlled tool")
        material = f"{challenge}\n{request}".encode("utf-8")
        expected_hmac = hmac.new(
            CONTROL_AUTH_KEY,
            material,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(supplied_hmac, expected_hmac):
            raise RequestError("controlled tool authentication failed")
        try:
            process_name = Path(f"/proc/{pid}/comm").read_text(
                encoding="utf-8"
            ).strip()
        except OSError as exc:
            raise RequestError(f"cannot inspect peer process name: {exc}") from exc
        if process_name != peer:
            raise RequestError(
                f"peer process name {process_name!r} does not match {peer!r}"
            )
        try:
            executable = peer_executable(pid, uid, gid)
        except OSError as exc:
            raise RequestError(f"cannot inspect peer executable: {exc}") from exc
        expected_executable = str(self.tools[peer])
        if executable != expected_executable:
            raise RequestError(
                f"peer executable {executable!r} does not match "
                f"{expected_executable!r}"
            )
        return uid, peer, request

    def delay_for(self, index: int, linker: str) -> int:
        if self.name != "success":
            return 2
        if index < 4:
            return 5
        occurrence = self.timed_occurrence[linker]
        self.timed_occurrence[linker] += 1
        return TIMED_DELAYS_MS[linker][occurrence]

    def route(self, peer: str, uid: int, parts: list[str]) -> str:
        if peer != "gcc":
            raise RequestError("ROUTE must come from the controlled driver")
        if len(parts) != 2 or parts[1] not in LINKERS:
            raise RequestError("invalid ROUTE request")
        if self.pending_route is not None:
            raise RequestError("a prior route has no linker execution")
        if self.expected_index >= len(self.sequence):
            raise RequestError("too many driver invocations")
        if self.expected_index == 0 and self.report.exists():
            raise RequestError("stale report still exists before the first link")
        requested = parts[1]
        expected = self.sequence[self.expected_index]
        if requested != expected:
            raise RequestError(
                f"schedule mismatch at {self.expected_index}: "
                f"expected {expected}, got {requested}"
            )
        actual = requested
        if (
            self.name in ("identity_mismatch", "identity_mismatch_timed")
            and self.expected_index == FAULT_INDEX[self.name]
        ):
            actual = "bfd"
        elif (
            self.name == "identity_path_change"
            and self.expected_index == FAULT_INDEX[self.name]
        ):
            actual = "lld2"
        elif self.name == "identity_family_spoof" and requested == "gold":
            actual = "gold-spoof"
        decoy = ALIAS_FAMILY.get(actual, actual) + DECOY_SUFFIX
        # The decoys bracket the link, but how many run on each side rotates
        # with the invocation index, so the linker sits at a different position
        # among the link's linker-shaped executions from one link to the next.
        # The total stays fixed so the per-link fork and exec cost does not
        # drift across the schedule.
        leading = self.expected_index % 3
        trailing = 2 - leading
        self.pending_route = {
            "index": self.expected_index,
            "requested": requested,
            "actual": actual,
            "decoy": decoy,
        }
        self.writer.write(
            "route",
            scenario=self.name,
            uid=uid,
            index=self.expected_index,
            requested=requested,
            actual=actual,
            decoy=decoy,
            leading=leading,
            trailing=trailing,
        )
        return f"ROUTE\t{actual}\t{decoy}\t{leading}\t{trailing}\n"

    def link(self, peer: str, uid: int, parts: list[str]) -> str:
        if len(parts) != 7:
            raise RequestError("invalid LINK request")
        (
            _,
            actual,
            requested,
            output,
            mask_text,
            preexisting_text,
            unexpected_text,
        ) = parts
        if self.pending_route is None:
            raise RequestError("linker execution has no driver route")
        pending = self.pending_route
        expected_peer = f"ld.{actual}"
        if peer != expected_peer:
            raise RequestError(f"LINK peer {peer} does not match {expected_peer}")
        if requested != pending["requested"] or actual != pending["actual"]:
            raise RequestError("LINK does not match its route")
        try:
            mask = int(mask_text)
        except ValueError as exc:
            raise RequestError("thread mask is not an integer") from exc
        required_mask = THREAD_MASKS[requested]
        if mask != required_mask:
            raise RequestError(
                f"{requested} thread mask {mask} != {required_mask}"
            )
        try:
            output_preexisting = int(preexisting_text)
        except ValueError as exc:
            raise RequestError("output preexistence marker is not an integer") from exc
        if output_preexisting != 0:
            raise RequestError("output existed when the linker started")
        try:
            unexpected_control = int(unexpected_text)
        except ValueError as exc:
            raise RequestError("unexpected-control marker is not an integer") from exc
        if unexpected_control != 0:
            raise RequestError("unexpected thread or fork control was supplied")
        if not os.path.isabs(output):
            raise RequestError("controlled output path is not absolute")
        index = pending["index"]
        delay_ms = self.delay_for(index, requested)
        action = "success"
        if self.name in FAULT_ACTION and index == FAULT_INDEX[self.name]:
            action = FAULT_ACTION[self.name]
        nonce = secrets.token_hex(16)
        started = self.writer.write(
            "link_start",
            scenario=self.name,
            uid=uid,
            index=index,
            requested=requested,
            actual=actual,
            output=output,
            thread_mask=mask,
            output_preexisting=output_preexisting,
            unexpected_thread_control=unexpected_control,
            delay_ms=delay_ms,
            action=action,
            nonce=nonce,
        )
        self.active[nonce] = {**started, "peer": peer}
        self.pending_route = None
        self.expected_index += 1
        return f"LINK\t{index}\t{delay_ms}\t{nonce}\t{action}\n"

    def done(self, peer: str, uid: int, parts: list[str]) -> str:
        if len(parts) != 5:
            raise RequestError("invalid DONE request")
        _, index_text, nonce, output, action = parts
        active = self.active.get(nonce)
        if active is None:
            raise RequestError("DONE nonce is not active")
        try:
            index = int(index_text)
        except ValueError as exc:
            raise RequestError("DONE index is not an integer") from exc
        if (
            peer != active["peer"]
            or index != active["index"]
            or output != active["output"]
            or action != active["action"]
        ):
            raise RequestError("DONE does not match LINK")
        finished = self.writer.write(
            "link_done",
            scenario=self.name,
            uid=uid,
            index=index,
            requested=active["requested"],
            actual=active["actual"],
            output=output,
            action=action,
            nonce=nonce,
            started_ns=active["server_ns"],
        )
        self.completed[nonce] = {
            **active,
            "finished_ns": finished["server_ns"],
        }
        if (
            self.name == "identity_family_change"
            and index == FAULT_INDEX[self.name]
        ):
            self.family_change_active = True
        del self.active[nonce]
        return "DONE\tOK\n"

    def probe(self, peer: str, uid: int, parts: list[str]) -> str:
        if peer != "probe" or len(parts) != 4:
            raise RequestError("invalid PROBE request")
        _, nonce, first_argument, second_argument = parts
        completed = self.completed.get(nonce)
        if completed is None:
            raise RequestError("PROBE nonce has no completed link")
        if nonce in self.probed:
            raise RequestError("PROBE nonce was already used")
        expected_argv = self.manifest["probe"]["argv"]
        if [first_argument, second_argument] != expected_argv[1:]:
            raise RequestError("semantic probe arguments are incorrect")
        if completed["action"] not in (
            "success",
            "probe_fail",
            "non_regular",
        ):
            raise RequestError("faulty output cannot produce a valid probe event")
        index = completed["index"]
        if completed["action"] == "probe_fail":
            returncode, stdout_token, stderr_token = 7, "BROKEN", "probe_failed"
        elif self.name == "probe_stdout_mismatch" and index == FAULT_INDEX[self.name]:
            returncode, stdout_token, stderr_token = 0, "WRONG_OUTPUT", "-"
        elif self.name == "probe_stderr_mismatch" and index == FAULT_INDEX[self.name]:
            returncode, stdout_token, stderr_token = 0, "CONTROL_OK", "UNEXPECTED_ERROR"
        else:
            returncode, stdout_token, stderr_token = 0, "CONTROL_OK", "-"
        self.probed.add(nonce)
        self.writer.write(
            "probe",
            scenario=self.name,
            uid=uid,
            index=index,
            requested=completed["requested"],
            nonce=nonce,
            action=completed["action"],
            returncode=returncode,
            stdout="" if stdout_token == "-" else stdout_token + "\n",
            stderr="" if stderr_token == "-" else stderr_token + "\n",
        )
        return f"PROBE\t{returncode}\t{stdout_token}\t{stderr_token}\n"

    def version(self, peer: str, uid: int, parts: list[str]) -> str:
        if len(parts) != 2 or peer != f"ld.{parts[1]}":
            raise RequestError("invalid VERSION request")
        linker = parts[1]
        family = linker
        if linker.endswith(DECOY_SUFFIX):
            family = linker[: -len(DECOY_SUFFIX)]
        if linker in ALIAS_FAMILY:
            family = ALIAS_FAMILY[linker]
        elif self.family_change_active and family == "lld":
            family = "bfd"
        if family not in VERSIONS:
            raise RequestError("VERSION names an unknown linker")
        self.writer.write(
            "version",
            scenario=self.name,
            uid=uid,
            index=max(0, self.expected_index - 1),
            linker=linker,
            family=family,
        )
        return f"VERSION\t{VERSIONS[family]}\n"

    def handle(self, peer: str, uid: int, request: str) -> str:
        parts = request.rstrip("\n").split("\t")
        if not parts:
            raise RequestError("empty request")
        handlers = {
            "ROUTE": self.route,
            "LINK": self.link,
            "DONE": self.done,
            "PROBE": self.probe,
            "VERSION": self.version,
        }
        if parts[0] not in handlers:
            raise RequestError(f"unknown request type: {parts[0]}")
        return handlers[parts[0]](peer, uid, parts)

    def summary(self) -> dict:
        return {
            "expected_invocations": len(self.sequence),
            "started_invocations": len(self.completed) + len(self.active),
            "completed_invocations": len(self.completed),
            "probe_invocations": len(self.probed),
            "next_index": self.expected_index,
            "pending_route": self.pending_route is not None,
        }


def receive_request(connection: socket.socket) -> str:
    """Read one bounded request through client EOF."""
    chunks = []
    total = 0
    while True:
        chunk = connection.recv(4096)
        if not chunk:
            break
        total += len(chunk)
        if total > 16384:
            raise RequestError("request exceeds 16384 bytes")
        chunks.append(chunk)
    try:
        return b"".join(chunks).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RequestError("request is not UTF-8") from exc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenario",
        choices=(
            "success",
            "identity_mismatch",
            "identity_mismatch_timed",
            "identity_path_change",
            "identity_family_spoof",
            "identity_family_change",
            "late_failure",
            "no_output",
            "corrupt_output",
            "non_regular_output",
            "probe_failure",
            "probe_stdout_mismatch",
            "probe_stderr_mismatch",
        ),
        required=True,
    )
    parser.add_argument("--workload", type=Path, required=True)
    parser.add_argument("--tool-dir", type=Path, required=True)
    parser.add_argument("--socket", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--secret", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    manifest = json.loads(
        (args.workload / "workload.json").read_text(encoding="utf-8")
    )
    tool_names = [
        "gcc",
        "probe",
        *(f"ld.{linker}" for linker in LINKERS),
        "ld.lld2",
        "ld.gold-spoof",
        *(f"ld.{linker}{DECOY_SUFFIX}" for linker in LINKERS),
    ]
    tools = {
        name: (args.tool_dir / name).resolve(strict=True) for name in tool_names
    }
    writer = EvidenceWriter(args.evidence, args.secret)
    scenario = Scenario(args.scenario, manifest, tools, args.report, writer)
    stop = False

    def request_stop(_signum: int, _frame: object) -> None:
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    args.socket.unlink(missing_ok=True)
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(args.socket))
    os.chmod(args.socket, 0o666)
    server.listen(16)
    server.settimeout(0.2)
    writer.write("observer_start", scenario=args.scenario, pid=os.getpid())
    try:
        while not stop:
            try:
                connection, _ = server.accept()
            except TimeoutError:
                continue
            with connection:
                try:
                    uid, peer, request = scenario.authenticate(connection)
                    response = scenario.handle(peer, uid, request)
                except RequestError as exc:
                    writer.write(
                        "violation",
                        scenario=args.scenario,
                        error=str(exc),
                    )
                    response = f"ERROR\t{exc}\n"
                except Exception as exc:
                    writer.write(
                        "observer_error",
                        scenario=args.scenario,
                        error=f"{type(exc).__name__}: {exc}",
                    )
                    response = (
                        f"ERROR\tobserver internal {type(exc).__name__}: {exc}\n"
                    )
                try:
                    connection.sendall(response.encode("utf-8"))
                except OSError as exc:
                    writer.write(
                        "response_error",
                        scenario=args.scenario,
                        error=f"{type(exc).__name__}: {exc}",
                    )
    finally:
        writer.write(
            "observer_stop",
            scenario=args.scenario,
            state=scenario.summary(),
        )
        server.close()
        args.socket.unlink(missing_ok=True)
        writer.close()


if __name__ == "__main__":
    main()
