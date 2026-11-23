"""평가 루프: 에이전트 x 마법사 4명 x 평가 시드 40판.

uv run python eval.py --agents still random flee kite q --q-dir ../results/q-learning --out ../results/eval-step2
"""
import argparse
import csv
from pathlib import Path

import numpy as np

from survivor_rl import bots
from survivor_rl.env import CLASS_NAMES, SurvivorEnv, run_episodes
from survivor_rl.qlearning import QPolicy

EVAL_SEEDS = range(900000, 900040)


def make_policy(name, q_dir):
    if name in bots.BOTS:
        return bots.BOTS[name]()
    if name == "q":
        return QPolicy.load_dir(q_dir)
    raise ValueError(name)


def summarize(rows, max_time):
    t = np.array([r["time"] for r in rows])
    return {"mean_time": t.mean(), "median_time": float(np.median(t)),
            "clear_rate": float(np.mean(t >= max_time - 1e-3)),
            "kills": np.mean([r["kills"] for r in rows]), "damage": np.mean([r["damage"] for r in rows])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agents", nargs="+", default=["still", "random", "flee", "kite"])
    ap.add_argument("--q-dir", default="../results/q-learning")
    ap.add_argument("--out", default="../results/eval")
    ap.add_argument("--max-time", type=float, default=300)
    ap.add_argument("--classes", type=int, nargs="+", default=[0, 1, 2, 3])
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    jobs = [(c, s) for c in args.classes for s in EVAL_SEEDS]
    all_rows, summary = [], []
    with SurvivorEnv(num_envs=40, max_time=args.max_time) as env:
        for name in args.agents:
            rows = run_episodes(env, make_policy(name, args.q_dir), jobs)
            for r in rows:
                r["agent"] = name
            all_rows += rows
            for c in args.classes:
                s = summarize([r for r in rows if r["class"] == c], args.max_time)
                summary.append({"agent": name, "class": c, **s})
                print(f"{name:7s} {CLASS_NAMES[c]}  평균 {s['mean_time']:6.1f}s  완주 {s['clear_rate']*100:5.1f}%  "
                      f"처치 {s['kills']:7.1f}", flush=True)

    with open(out / "games.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["agent", "class", "seed", "time", "dead", "kills", "damage", "level"])
        w.writeheader()
        w.writerows(all_rows)
    with open(out / "summary.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0]))
        w.writeheader()
        w.writerows(summary)

    lines = ["| 에이전트 | " + " | ".join(CLASS_NAMES[c] for c in args.classes) + " |", "|---|" + "---:|" * len(args.classes)]
    for name in args.agents:
        cells = []
        for c in args.classes:
            s = next(x for x in summary if x["agent"] == name and x["class"] == c)
            cells.append(f"{s['mean_time']:.0f}초 / {s['clear_rate']*100:.0f}%")
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    (out / "summary.md").write_text("평균 생존 시간 / 5분 완주율 (마법사당 40판)\n\n" + "\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
