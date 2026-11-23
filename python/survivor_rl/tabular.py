"""Discretize the observation into 648 states for tabular Q-learning (design doc section 4).

  nearest enemy direction 8  x  distance 3  x  wall 9  x  hp 3  = 648
"""
import numpy as np

from . import features as F

NEAR_DISTANCE = 3.0     # closer than this: near
MID_DISTANCE = 7.0      # closer than this: mid, else far (also when no enemy)
WALL_MARGIN = 6.0       # within this distance of a wall counts as near that wall
HP_LOW, HP_MID = 1 / 3, 2 / 3
NUM_STATES = 8 * 3 * 9 * 3


def state(obs):
    rel, present = F.enemies(obs)
    nearest = rel[:, 0]
    has = present[:, 0]
    angle = np.arctan2(nearest[:, 1], nearest[:, 0])
    direction = np.round(angle / (np.pi / 4)).astype(np.int64) % 8
    dist = np.linalg.norm(nearest, axis=1)
    dist_bin = np.where(~has, 2, np.where(dist < NEAR_DISTANCE, 0, np.where(dist < MID_DISTANCE, 1, 2)))
    direction = np.where(has, direction, 0)

    p = F.player(obs)
    edge = F.ARENA - WALL_MARGIN
    wx = np.where(p[:, 0] < -edge, 0, np.where(p[:, 0] > edge, 2, 1))
    wy = np.where(p[:, 1] < -edge, 0, np.where(p[:, 1] > edge, 2, 1))
    wall = wx * 3 + wy

    h = F.hp(obs)
    hp_bin = np.where(h < HP_LOW, 0, np.where(h < HP_MID, 1, 2))
    return ((direction * 3 + dist_bin) * 9 + wall) * 3 + hp_bin
