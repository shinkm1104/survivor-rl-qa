using System;
using System.Collections.Generic;
using System.IO;
using System.Net.Sockets;
using UnityEngine;

namespace SurvivorLab {
    // Headless RL environment server. Python listens on a local TCP port and this player connects to it.
    // One process hosts many simulations so one round trip advances all of them.
    //
    // Python -> Unity (little endian)
    //   'R' int32 count, count x (int32 classIndex, int32 seed)   reset; seed < 0 keeps that slot as is
    //   'S' count x byte action                                    advance every live slot by one decision
    //   'Q'                                                         quit
    // Unity -> Python, after R and S: count x record
    //   record = float32[ObsSize] observation, float32 time, kills, damageTaken, hp, level, byte dead
    public static class RlServer {
        public const int NearestEnemies = 8;
        public const int ObsSize = NearestEnemies * 3 + 6; // 30
        public const int TicksPerDecision = 2;
        public const float TickSeconds = 0.05f;
        public static readonly Vector2[] Actions = {
            Vector2.zero, Vector2.up, new Vector2(1,1).normalized, Vector2.right, new Vector2(1,-1).normalized,
            Vector2.down, new Vector2(-1,-1).normalized, Vector2.left, new Vector2(-1,1).normalized };

        public static void Run(Balance balance, int port) {
            using (var client = new TcpClient()) {
                client.NoDelay = true;
                client.Connect("127.0.0.1", port);
                var stream = client.GetStream();
                var reader = new BinaryReader(new BufferedStream(stream));
                var writer = new BinaryWriter(new BufferedStream(stream));
                var sims = new List<Simulation>();
                var obs = new float[ObsSize];
                var scratch = new List<KeyValuePair<float, Enemy>>();
                while (true) {
                    byte command = reader.ReadByte();
                    if (command == (byte)'Q') return;
                    if (command == (byte)'R') {
                        int count = reader.ReadInt32();
                        while (sims.Count < count) sims.Add(null);
                        if (sims.Count > count) sims.RemoveRange(count, sims.Count - count);
                        for (int i = 0; i < count; i++) {
                            int cls = reader.ReadInt32(), seed = reader.ReadInt32();
                            if (seed >= 0 || sims[i] == null) sims[i] = new Simulation(balance, Mathf.Clamp(cls, 0, 3), Mathf.Max(seed, 0));
                        }
                    } else if (command == (byte)'S') {
                        for (int i = 0; i < sims.Count; i++) Advance(sims[i], reader.ReadByte());
                    } else throw new InvalidDataException("Unknown command " + command);
                    foreach (var s in sims) {
                        Observe(s, obs, scratch);
                        foreach (float v in obs) writer.Write(v);
                        writer.Write(s.time); writer.Write((float)s.kills); writer.Write(s.damageTaken);
                        writer.Write(s.hp); writer.Write((float)s.level); writer.Write((byte)(s.dead ? 1 : 0));
                    }
                    writer.Flush();
                }
            }
        }

        // Holds the action for two game ticks. Level-up offers pause the clock and are picked by the
        // rule-based chooser, so those calls do not count as ticks.
        public static void Advance(Simulation s, int action) {
            Vector2 input = Actions[Mathf.Clamp(action, 0, Actions.Length - 1)];
            int ticks = 0, guard = 0;
            while (ticks < TicksPerDecision && !s.Done && guard++ < 200) {
                float before = s.time;
                s.Step(input, TickSeconds, true);
                if (s.time > before) ticks++;
            }
        }

        public static void Observe(Simulation s, float[] obs, List<KeyValuePair<float, Enemy>> scratch) {
            float h = s.b.arenaHalfExtent;
            scratch.Clear();
            foreach (var e in s.enemies) if (e.hp > 0) scratch.Add(new KeyValuePair<float, Enemy>((e.pos - s.player).sqrMagnitude, e));
            scratch.Sort((a, b) => a.Key != b.Key ? a.Key.CompareTo(b.Key) : a.Value.id.CompareTo(b.Value.id));
            for (int i = 0; i < NearestEnemies; i++) {
                if (i < scratch.Count) {
                    var e = scratch[i].Value; Vector2 rel = (e.pos - s.player) / h;
                    obs[i * 2] = rel.x; obs[i * 2 + 1] = rel.y; obs[NearestEnemies * 2 + i] = e.fast ? 1 : 0;
                } else { obs[i * 2] = 0; obs[i * 2 + 1] = 0; obs[NearestEnemies * 2 + i] = 0; }
            }
            int k = NearestEnemies * 3;
            obs[k] = s.player.x / h; obs[k + 1] = s.player.y / h;
            obs[k + 2] = s.maxHp > 0 ? Mathf.Clamp01(s.hp / s.maxHp) : 0;
            var orb = s.NearestXp();
            Vector2 orbRel = orb != null ? (orb.pos - s.player) / h : Vector2.zero;
            obs[k + 3] = orbRel.x; obs[k + 4] = orbRel.y;
            obs[k + 5] = s.time / 300f;
        }
    }
}
