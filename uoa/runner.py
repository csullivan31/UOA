"""Linux foreground-command adapter with an unreaped leader as ownership proof.

The leader stays waitable until its original process group has been signalled.
No PID/path rediscovery or signaling after reaping is used. This is supervision,
not a sandbox; processes that leave the session/group are outside this adapter.
"""

import hashlib
import os
import selectors
import signal
import sys
import time

from .domain import BoundaryError

EXCERPT_BYTES = 4096
DRAIN_SECONDS = 1.0


def run_command(argv, cwd, timeout):
    if sys.platform != "linux" or not hasattr(os, "pidfd_open"):
        raise BoundaryError("unsupported_host", "Initial execution adapter requires Linux with pidfd support")
    pipes = [os.pipe() for _ in range(4)]  # stdout, stderr, handshake, launch gate
    started = time.monotonic()
    try:
        pid = os.fork()
    except BaseException:
        for pair in pipes:
            for fd in pair:
                os.close(fd)
        raise
    if pid == 0:
        try:
            for read_fd, _ in pipes[:3]:
                os.close(read_fd)
            os.close(pipes[3][1])
            os.setsid()
            os.write(pipes[2][1], b"R")
            if os.read(pipes[3][0], 1) != b"G":
                os._exit(127)
            os.close(pipes[3][0])
            os.chdir(cwd)
            stdin = os.open(os.devnull, os.O_RDONLY)
            os.dup2(stdin, 0)
            os.dup2(pipes[0][1], 1)
            os.dup2(pipes[1][1], 2)
            os.close(stdin)
            os.close(pipes[0][1])
            os.close(pipes[1][1])
            os.execvp(argv[0], argv)
        except BaseException as error:
            try:
                os.write(pipes[2][1], b"E")
                os.write(2, str(error).encode("utf-8", "replace")[:EXCERPT_BYTES])
            finally:
                os._exit(127)

    for _, write_fd in pipes[:3]:
        os.close(write_fd)
    os.close(pipes[3][0])
    gate_fd = pipes[3][1]
    selector = selectors.DefaultSelector()
    streams = {name: {"sha256": hashlib.sha256(), "bytes": 0, "excerpt": bytearray()}
               for name in ("stdout", "stderr")}
    ready = False
    launch_failed = False
    stopped = False
    cancelled = False
    timed_out = False
    exit_observed = None
    drain_deadline = None
    incomplete = False
    pidfd = None

    def consume(fd, name):
        nonlocal ready, launch_failed, gate_fd
        try:
            chunk = os.read(fd, 65536)
        except BlockingIOError:
            return
        if not chunk:
            selector.unregister(fd)
            os.close(fd)
        elif name == "handshake":
            ready = ready or b"R" in chunk
            launch_failed = launch_failed or b"E" in chunk
            if ready and gate_fd is not None:
                try:
                    os.write(gate_fd, b"G")
                except BrokenPipeError:
                    pass
                os.close(gate_fd)
                gate_fd = None
        else:
            stream = streams[name]
            stream["sha256"].update(chunk)
            stream["bytes"] += len(chunk)
            stream["excerpt"].extend(chunk[:max(0, EXCERPT_BYTES - len(stream["excerpt"]))])

    def stop():
        nonlocal stopped, drain_deadline
        # Read a late handshake before deciding which identity we own.
        handshake_fd = pipes[2][0]
        if handshake_fd in selector.get_map():
            consume(handshake_fd, "handshake")
        try:
            if ready:
                os.killpg(pid, signal.SIGKILL)
            else:
                os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        stopped = True
        drain_deadline = time.monotonic() + DRAIN_SECONDS

    usage = None
    status = None
    try:
        for (read_fd, _), name in zip(pipes, ("stdout", "stderr", "handshake")):
            os.set_blocking(read_fd, False)
            selector.register(read_fd, selectors.EVENT_READ, name)
        pidfd = os.pidfd_open(pid)
        selector.register(pidfd, selectors.EVENT_READ, "exit")
        while selector.get_map():
            try:
                now = time.monotonic()
                if not stopped and now - started >= timeout:
                    timed_out = True
                    stop()
                if drain_deadline is not None and now >= drain_deadline:
                    incomplete = any(k.data != "exit" for k in selector.get_map().values())
                    break
                deadline = drain_deadline if stopped else started + timeout
                for key, _ in selector.select(max(0, deadline - now)):
                    if key.data == "exit":
                        exit_observed = time.monotonic()
                        selector.unregister(key.fd)
                        if not stopped:
                            stop()
                    else:
                        consume(key.fd, key.data)
            except KeyboardInterrupt:
                cancelled = True
                if not stopped:
                    stop()
    finally:
        # Keep the leader unreaped until the final group signal. Also runs on
        # adapter failures; normal completion has already signalled the group.
        previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT, signal.SIGTERM})
        try:
            if status is None:
                if not stopped:
                    stop()
                _, status, usage = os.wait4(pid, 0)
            for key in list(selector.get_map().values()):
                selector.unregister(key.fd)
                os.close(key.fd)
                if key.fd == pidfd:
                    pidfd = None
            if pidfd is not None:
                os.close(pidfd)
            if gate_fd is not None:
                os.close(gate_fd)
            selector.close()
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)

    exit_code = os.waitstatus_to_exitcode(status)
    outcome = ("cancelled" if cancelled else "timeout" if timed_out else
               "output_incomplete" if incomplete else "launch_failed" if launch_failed else
               "ok" if exit_code == 0 else "nonzero_exit")
    return {
        "status": outcome, "exit_code": exit_code,
        "wall_ms": 1000 * ((exit_observed or time.monotonic()) - started),
        "cpu_ms": 1000 * (usage.ru_utime + usage.ru_stime),
        "wait4_max_rss_bytes": usage.ru_maxrss * 1024,
        "cleanup": "original_process_group_signalled_before_leader_reap" if ready else "leader_signalled_before_reap",
        "stdout": _output(streams["stdout"], not incomplete),
        "stderr": _output(streams["stderr"], not incomplete),
    }


def _output(stream, complete):
    return {"sha256": stream["sha256"].hexdigest(), "bytes": stream["bytes"],
            "excerpt": stream["excerpt"].decode("utf-8", "replace"),
            "excerpt_truncated": stream["bytes"] > len(stream["excerpt"]),
            "complete": complete}
