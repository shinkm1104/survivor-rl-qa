"""Python side of the headless Unity environment (see Assets/Scripts/RL/RlServer.cs).

One Unity process hosts `num_envs` games. `step` advances all of them by one decision (0.1 s).
Reward and episode end are decided here so they live in one place:
  alive step +0.01, death -1 (terminated), reaching max_time (truncated, not a failure).
"""
import socket
import struct
import subprocess
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EXE = ROOT / "Builds" / "Windows" / "SurvivorLab.exe"

OBS_SIZE = 30
NUM_ACTIONS = 9  # 0 stop, 1 up, 2 up-right, 3 right, 4 down-right, 5 down, 6 down-left, 7 left, 8 up-left
DECISION_SECONDS = 0.1
ALIVE_REWARD = 0.01
DEATH_REWARD = -1.0
CLASS_NAMES = ["파동술사", "마탄술사", "바위술사", "박수술사"]  # Simulation classIndex order (balance.json spells)

_RECORD = np.dtype([("obs", "<f4", OBS_SIZE), ("time", "<f4"), ("kills", "<f4"), ("damage", "<f4"),
                    ("hp", "<f4"), ("level", "<f4"), ("dead", "u1")])


class SurvivorEnv:
    def __init__(self, num_envs, max_time=300.0, exe=DEFAULT_EXE, log_dir=None):
        self.num_envs = num_envs
        self.max_time = max_time
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        server.settimeout(60)
        port = server.getsockname()[1]
        log_dir = Path(log_dir or ROOT / "Logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        log = log_dir / f"rl-server-{port}.log"
        self.proc = subprocess.Popen([str(exe), "-batchmode", "-nographics", "--rl-server", f"--port={port}",
                                      "-logFile", str(log)])
        try:
            self.sock, _ = server.accept()
        finally:
            server.close()
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.file = self.sock.makefile("rwb")
        self.classes = np.zeros(num_envs, dtype=np.int32)
        self.seeds = np.zeros(num_envs, dtype=np.int64)

    def _read(self):
        data = self.file.read(_RECORD.itemsize * self.num_envs)
        if len(data) != _RECORD.itemsize * self.num_envs:
            raise ConnectionError("Unity environment closed the connection")
        return np.frombuffer(data, dtype=_RECORD)

    def reset(self, classes, seeds, mask=None):
        """Start new games. Slots where mask is False keep running (their state is returned unchanged)."""
        classes = np.broadcast_to(np.asarray(classes, dtype=np.int32), (self.num_envs,))
        seeds = np.broadcast_to(np.asarray(seeds, dtype=np.int64), (self.num_envs,))
        mask = np.ones(self.num_envs, bool) if mask is None else np.asarray(mask, bool)
        sent = np.where(mask, seeds, -1)
        payload = bytearray(b"R") + struct.pack("<i", self.num_envs)
        for c, s in zip(classes, sent):
            payload += struct.pack("<ii", int(c), int(s))
        self.file.write(payload)
        self.file.flush()
        self.classes[mask] = classes[mask]
        self.seeds[mask] = seeds[mask]
        rec = self._read()
        return rec["obs"].copy(), self._info(rec)

    def step(self, actions):
        actions = np.asarray(actions, dtype=np.uint8)
        self.file.write(b"S" + actions.tobytes())
        self.file.flush()
        rec = self._read()
        dead = rec["dead"].astype(bool)
        terminated = dead
        truncated = (~dead) & (rec["time"] >= self.max_time - 1e-4)
        reward = np.where(dead, DEATH_REWARD, ALIVE_REWARD).astype(np.float32)
        return rec["obs"].copy(), reward, terminated, truncated, self._info(rec)

    @staticmethod
    def _info(rec):
        return {k: rec[k].copy() for k in ("time", "kills", "damage", "hp", "level")}

    def close(self):
        try:
            self.file.write(b"Q")
            self.file.flush()
        except OSError:
            pass
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        self.sock.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def run_episodes(env, policy, jobs, on_step=None):
    """Play every (class, seed) in jobs with policy(obs, classes) -> actions. Returns one dict per job.

    on_step(obs, actions, reward, next_obs, terminated, truncated, classes, active) lets training hook in.
    """
    jobs = list(jobs)
    results = [None] * len(jobs)
    n = env.num_envs
    slot_job = np.full(n, -1)
    next_job = 0
    mask = np.zeros(n, bool)
    classes = np.zeros(n, np.int32)
    seeds = np.zeros(n, np.int64)
    for i in range(min(n, len(jobs))):
        slot_job[i] = next_job
        classes[i], seeds[i] = jobs[next_job]
        mask[i] = True
        next_job += 1
    obs, _ = env.reset(classes, seeds, mask)
    done_count = 0
    while done_count < len(jobs):
        active = slot_job >= 0
        actions = np.where(active, policy(obs, env.classes), 0)
        next_obs, reward, term, trunc, info = env.step(actions)
        if on_step is not None:
            on_step(obs, actions, reward, next_obs, term, trunc, env.classes.copy(), active)
        finished = active & (term | trunc)
        mask = np.zeros(n, bool)
        for i in np.flatnonzero(finished):
            j = slot_job[i]
            cls, seed = jobs[j]
            results[j] = {"class": int(cls), "seed": int(seed), "time": float(info["time"][i]),
                          "dead": bool(term[i]), "kills": int(info["kills"][i]),
                          "damage": float(info["damage"][i]), "level": int(info["level"][i])}
            done_count += 1
            if next_job < len(jobs):
                slot_job[i] = next_job
                classes[i], seeds[i] = jobs[next_job]
                mask[i] = True
                next_job += 1
            else:
                slot_job[i] = -1
        if mask.any():
            obs, _ = env.reset(np.where(mask, classes, env.classes), np.where(mask, seeds, env.seeds), mask)
        else:
            obs = next_obs
    return results
