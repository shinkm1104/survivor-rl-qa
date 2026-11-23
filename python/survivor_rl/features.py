"""Helpers that read the 30-value observation (layout in RlServer.Observe).

  0..15  nearest 8 enemies, relative (x, y) / 32, zero when missing
  16..23 nearest 8 enemies, fast flag
  24, 25 player position / 32
  26     hp ratio
  27, 28 nearest XP orb, relative (x, y) / 32
  29     elapsed time / 300
"""
import numpy as np

ARENA = 32.0
NEAREST = 8
# Unit vectors for actions 0..8 (same order as RlServer.Actions).
DIRS = np.array([[0, 0], [0, 1], [1, 1], [1, 0], [1, -1], [0, -1], [-1, -1], [-1, 0], [-1, 1]], dtype=np.float32)
DIRS[1:] /= np.linalg.norm(DIRS[1:], axis=1, keepdims=True)


def enemies(obs):
    """(N, 8, 2) relative positions in world units and (N, 8) bool for present slots."""
    rel = obs[:, :NEAREST * 2].reshape(-1, NEAREST, 2) * ARENA
    present = np.any(rel != 0, axis=2)
    return rel, present


def player(obs):
    return obs[:, 24:26] * ARENA


def hp(obs):
    return obs[:, 26]


def orb(obs):
    rel = obs[:, 27:29] * ARENA
    return rel, np.any(rel != 0, axis=1)


def to_action(vec):
    """Snap (N, 2) desired directions to the closest of the 8 moves; near-zero vectors mean stop."""
    norm = np.linalg.norm(vec, axis=1)
    scores = vec @ DIRS[1:].T
    act = np.argmax(scores, axis=1) + 1
    return np.where(norm < 1e-6, 0, act)
