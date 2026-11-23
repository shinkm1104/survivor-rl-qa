"""Rule-based baselines. They see the same observation and use the same 9 actions as the agents."""
import numpy as np

from . import features as F


def still(obs, classes):
    return np.zeros(len(obs), dtype=np.int64)


class RandomBot:
    def __init__(self, seed=0):
        self.rng = np.random.default_rng(seed)

    def __call__(self, obs, classes):
        return self.rng.integers(0, 9, len(obs))


def flee(obs, classes):
    """Run straight away from the nearest enemy."""
    rel, present = F.enemies(obs)
    away = -rel[:, 0]
    away[~present[:, 0]] = 0
    return F.to_action(away)


def _wall(distance):
    return np.where(distance < 10, (10 - distance) / 10, 0)


def kite(obs, classes):
    """Port of the old version's kite bot: dodge the local crowd while circling toward open space,
    stay off walls, and collect XP when nothing is close."""
    rel, present = F.enemies(obs)
    p = F.player(obs)
    d = -rel  # player - enemy
    m = np.linalg.norm(d, axis=2)
    near = present & (m < 7) & (m > 1e-3)
    safe_m = np.where(near, m, 1.0)
    push = np.sum(np.where(near[..., None], d / (safe_m ** 2)[..., None], 0), axis=1)
    threat = np.sum(np.where(near, 1 / safe_m, 0), axis=1)
    h = F.ARENA
    wall = np.stack([_wall(h + p[:, 0]) - _wall(h - p[:, 0]), _wall(h + p[:, 1]) - _wall(h - p[:, 1])], axis=1)

    orb_rel, has_orb = F.orb(obs)
    goal = np.where(has_orb[:, None], orb_rel, -p * 0.05)
    calm = _unit(goal) + wall * 2

    tangent = _unit(np.stack([-push[:, 1], push[:, 0]], axis=1))
    flip = np.sum(tangent * -p, axis=1) < 0
    tangent[flip] *= -1
    danger = _unit(push) + tangent * 0.6 + wall * 1.5

    return F.to_action(np.where((threat < 0.6)[:, None], calm, danger))


def _unit(v):
    n = np.linalg.norm(v, axis=1, keepdims=True)
    return np.where(n > 1e-6, v / np.maximum(n, 1e-6), 0)


BOTS = {"still": lambda: still, "random": lambda: RandomBot(), "flee": lambda: flee, "kite": lambda: kite}
