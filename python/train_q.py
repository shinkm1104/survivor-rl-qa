"""2단계 학습: 마법사 한 명의 Q 표를 학습한다.

uv run python train_q.py --class 0 --episodes 2000
"""
import argparse
import csv
import json
import time
from pathlib import Path

import numpy as np

from survivor_rl.env import CLASS_NAMES, SurvivorEnv, run_episodes
from survivor_rl.qlearning import QLearner

TRAIN_SEED_MAX = 900000  # 평가 시드(900000~)와 겹치지 않게


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--class", dest="cls", type=int, required=True)
    ap.add_argument("--episodes", type=int, default=2000)
    ap.add_argument("--envs", type=int, default=16)
    ap.add_argument("--alpha", type=float, default=0.1)
    ap.add_argument("--gamma", type=float, default=0.99)
    ap.add_argument("--eps-start", type=float, default=1.0)
    ap.add_argument("--eps-end", type=float, default=0.05)
    ap.add_argument("--eps-fraction", type=float, default=0.5)
    ap.add_argument("--chunk", type=int, default=50, help="episodes between epsilon updates and log lines")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="../results/q-learning")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(args.seed + 1000 * args.cls)
    learner = QLearner(args.alpha, args.gamma, seed=args.seed + args.cls)
    curve = []
    done = 0
    start = time.perf_counter()
    with SurvivorEnv(num_envs=args.envs) as env:
        while done < args.episodes:
            n = min(args.chunk, args.episodes - done)
            progress = done / (args.eps_fraction * args.episodes)
            eps = max(args.eps_end, args.eps_start + (args.eps_end - args.eps_start) * min(1.0, progress))
            seeds = rng.integers(0, TRAIN_SEED_MAX, n)
            jobs = [(args.cls, int(s)) for s in seeds]

            def on_step(obs, actions, reward, next_obs, term, trunc, classes, active):
                learner.update(obs, actions, reward, next_obs, term, active)

            rows = run_episodes(env, lambda o, c: learner.act(o, eps), jobs, on_step=on_step)
            done += n
            times = [r["time"] for r in rows]
            curve.append({"episodes": done, "epsilon": round(eps, 4), "mean_time": float(np.mean(times)),
                          "clear_rate": float(np.mean(np.array(times) >= 300 - 1e-3)),
                          "visited_states": int((learner.visits.sum(axis=1) > 0).sum())})
            c = curve[-1]
            print(f"[{CLASS_NAMES[args.cls]}] {done:5d}판 ε={eps:.2f} 평균 {c['mean_time']:6.1f}s "
                  f"완주 {c['clear_rate']*100:5.1f}% 방문 상태 {c['visited_states']} "
                  f"({time.perf_counter() - start:.0f}s)", flush=True)

    np.save(out / f"q_class{args.cls}.npy", learner.q)
    np.save(out / f"visits_class{args.cls}.npy", learner.visits)
    with open(out / f"curve_class{args.cls}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(curve[0]))
        w.writeheader()
        w.writerows(curve)
    (out / f"config_class{args.cls}.json").write_text(json.dumps(vars(args), indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
