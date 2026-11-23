"""1단계 완료 기준 확인: 관측·행동·보상 형식, 결정론, 헤드리스 속도."""
import time

import numpy as np

from survivor_rl.env import NUM_ACTIONS, OBS_SIZE, SurvivorEnv, run_episodes
from survivor_rl import bots


def main():
    with SurvivorEnv(num_envs=4) as env:
        obs, _ = env.reset([0, 1, 2, 3], [900000] * 4)
        assert obs.shape == (4, OBS_SIZE), obs.shape
        for a in range(NUM_ACTIONS):
            obs, reward, term, trunc, info = env.step([a] * 4)
        assert obs.shape == (4, OBS_SIZE)
        assert np.allclose(reward[~term], 0.01), reward
        assert np.all(np.abs(info["time"] - 0.9) < 1e-3), info["time"]
        print("PASS format: obs", obs.shape, "actions", NUM_ACTIONS, "reward", reward)

    jobs = [(c, 900000 + i) for c in range(4) for i in range(2)]
    with SurvivorEnv(num_envs=len(jobs)) as env:
        a = run_episodes(env, bots.kite, jobs)
        start = time.perf_counter()
        b = run_episodes(env, bots.kite, jobs)
        elapsed = time.perf_counter() - start
    for x, y in zip(a, b):
        assert x == y, (x, y)
    print("PASS determinism:", [(r["class"], round(r["time"], 1), r["kills"]) for r in a])
    game_seconds = sum(r["time"] for r in b)
    print(f"SPEED {len(jobs)} games, {game_seconds:.0f} game-seconds in {elapsed:.1f}s "
          f"= {game_seconds / elapsed:.0f}x real time ({game_seconds / 0.1 / elapsed:.0f} decisions/s)")


if __name__ == "__main__":
    main()
