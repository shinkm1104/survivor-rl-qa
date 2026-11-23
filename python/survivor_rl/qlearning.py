"""2단계: 표 기반 Q-learning (이동 정책). 마법사마다 Q 표 하나 (648 상태 x 9 행동)."""
from pathlib import Path

import numpy as np

from .env import NUM_ACTIONS
from .tabular import NUM_STATES, state


class QLearner:
    def __init__(self, alpha=0.1, gamma=0.99, seed=0):
        self.q = np.zeros((NUM_STATES, NUM_ACTIONS), dtype=np.float64)
        self.visits = np.zeros((NUM_STATES, NUM_ACTIONS), dtype=np.int64)
        self.alpha, self.gamma = alpha, gamma
        self.rng = np.random.default_rng(seed)

    def greedy(self, s):
        # Random tie-break so the untouched all-zero rows do not always pick action 0.
        noise = self.rng.random((len(s), NUM_ACTIONS)) * 1e-9
        return np.argmax(self.q[s] + noise, axis=1)

    def act(self, obs, epsilon):
        s = state(obs)
        a = self.greedy(s)
        explore = self.rng.random(len(s)) < epsilon
        a[explore] = self.rng.integers(0, NUM_ACTIONS, explore.sum())
        return a

    def update(self, obs, actions, reward, next_obs, terminated, active):
        """One-step Q-learning. Truncated games (time limit) still bootstrap from the next state."""
        s, s2 = state(obs)[active], state(next_obs)[active]
        a, r, term = actions[active], reward[active], terminated[active]
        target = r + self.gamma * np.where(term, 0.0, self.q[s2].max(axis=1))
        np.add.at(self.q, (s, a), self.alpha * (target - self.q[s, a]))
        np.add.at(self.visits, (s, a), 1)


class QPolicy:
    """Greedy policy that picks each game's Q table by class."""

    def __init__(self, tables):
        self.tables = tables

    @classmethod
    def load_dir(cls, directory):
        directory = Path(directory)
        return cls({c: np.load(directory / f"q_class{c}.npy") for c in range(4) if (directory / f"q_class{c}.npy").exists()})

    def __call__(self, obs, classes):
        s = state(obs)
        actions = np.zeros(len(obs), dtype=np.int64)
        for c, table in self.tables.items():
            m = classes == c
            if m.any():
                actions[m] = np.argmax(table[s[m]], axis=1)
        return actions
