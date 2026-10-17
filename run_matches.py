#!/usr/bin/env python3
"""Run a batch of cambc matches between a candidate bot and one or more opponents.

Usage:
    python run_matches.py CANDIDATE OPPONENT [OPPONENT ...] --tag NAME [options]

Example:
    python run_matches.py my-bot-v2 my-bot starter-python --tag test1

Matches are deterministic (fuel-limited, no RNG seed exposed by cambc), so the
only sources of variety are the map and which side (Team A / Team B) each bot
plays. Each opponent is played on every selected map from both sides; repeating
an identical (map, side) pairing would just reproduce the same result.

Outputs, under results/<tag>/:
    <opponent>/<map>__cand-<A|B>.txt          full cambc stdout/stderr
    <opponent>/<map>__cand-<A|B>.stats.json   cambc --statistics export
    <opponent>/<map>__cand-<A|B>.repl26a      replay (open with `cambc view`)
    summary.json                              per-match records + win rates

With --resume, a match whose .txt and .stats.json are already in results/<tag>/ is not
played again, as long as they were made by the same command and are newer than both
bots' source and the map. An interrupted batch then only replays unfinished matches.
"""

import argparse
import json
import re
import subprocess
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MAPS_DIR = ROOT / "maps"
BOTS_DIR = ROOT / "bots"
RETRIES = 2

# "Team A (v2) wins: reached 1000 gems in round 299"
WIN_RE = re.compile(r"^Team ([AB]) \((.+?)\) wins: (.+)$", re.M)
# "  A    v2   1034     5      0        1560        0  Varg, Cassi & Issac, ..."
ROW_RE = re.compile(
    r"^\s+([AB])\s+(\S+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(.*)$", re.M
)


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("candidate", help="bot under test (name under bots/)")
    p.add_argument("opponents", nargs="+", help="one or more opponent bots")
    p.add_argument("--tag", required=True, help="results go to results/<tag>/")
    p.add_argument("--maps", nargs="*", help="map names (default: every .map26a in maps/)")
    p.add_argument("-n", "--games", type=int,
                   help="matches per opponent (default: every map x both sides). "
                        "Cycles through (map, side) pairs; values above 2*len(maps) only repeat games.")
    p.add_argument("-j", "--jobs", type=int, default=2, help="matches to run in parallel (default 2)")
    p.add_argument("--rounds", type=int, help="pass --rounds to cambc (stop early)")
    p.add_argument("--timeout", type=int, default=600, help="wall-clock seconds per match (default 600)")
    p.add_argument("--force", action="store_true", help="overwrite an existing results/<tag>/")
    p.add_argument("--resume", action="store_true",
                   help="reuse finished matches in results/<tag>/ and only play the rest")
    return p.parse_args()


def schedule(opponents, maps, games):
    """List of (opponent, map, candidate_side) jobs, alternating sides per map."""
    pairs = [(m, side) for m in maps for side in ("A", "B")]
    n = games if games is not None else len(pairs)
    return [(opp, *pairs[i % len(pairs)]) for opp in opponents for i in range(n)]


def parse_output(text):
    info = {"reason": None, "teams": {}}
    m = WIN_RE.search(text)
    if m:
        info["reason"] = m.group(3)
    for row in ROW_RE.finditer(text):
        team, bot, gems, kills, deaths, gold, crashes, draft = row.groups()
        info["teams"][team] = {
            "bot": bot, "gems": int(gems), "kills": int(kills), "deaths": int(deaths),
            "gold_earned": int(gold), "crashes": int(crashes),
            "draft": [s.strip() for s in draft.split(",")],
        }
    return info


def newest_input(bot_a, bot_b, map_name):
    """mtime of the newest file a match result depends on: both bots' source and the map."""
    files = [MAPS_DIR / f"{map_name}.map26a"]
    for bot in (bot_a, bot_b):
        files += [f for f in (BOTS_DIR / bot / "src").rglob("*") if f.is_file()]
    return max(f.stat().st_mtime for f in files)


def finished_match(cmd, txt_path, stats_path, bot_a, bot_b, map_name):
    """Output text of an earlier identical run that is still valid, else None."""
    if not (txt_path.exists() and stats_path.exists()):
        return None
    text = txt_path.read_text()
    header, _, output = text.partition("\n\n")
    if header != " ".join(cmd):
        return None
    if min(txt_path.stat().st_mtime, stats_path.stat().st_mtime) < newest_input(bot_a, bot_b, map_name):
        return None
    return output


def run_match(args, out_dir, opp, map_name, cand_side):
    bot_a, bot_b = (args.candidate, opp) if cand_side == "A" else (opp, args.candidate)
    stem = f"{map_name}__cand-{cand_side}"
    match_dir = out_dir / opp
    match_dir.mkdir(parents=True, exist_ok=True)
    stats_path = match_dir / f"{stem}.stats.json"
    txt_path = match_dir / f"{stem}.txt"
    replay_tmp = match_dir / f".{stem}.replay"

    cmd = ["cambc", "run", bot_a, bot_b, "--map", map_name,
           "-o", str(replay_tmp), "--statistics", str(stats_path), "--json"]
    if args.rounds:
        cmd += ["--rounds", str(args.rounds)]

    rec = {"opponent": opp, "map": map_name, "candidate_side": cand_side,
           "team_a": bot_a, "team_b": bot_b, "result": "error"}
    if args.resume:
        text = finished_match(cmd, txt_path, stats_path, bot_a, bot_b, map_name)
        if text is not None:
            rec["resumed"] = True
            return finish_record(rec, text, stats_path, bot_a, bot_b, cand_side)
    t0 = time.time()
    # Every `cambc run` rebuilds bots/<bot>/.cambc/build/bot.wasm in place, so a parallel
    # match can read a half-written module ("unexpected end-of-file"). Retry runs that
    # produced no statistics; real bot crashes still produce statistics and aren't retried.
    for attempt in range(1 + RETRIES):
        if attempt:
            time.sleep(2 * attempt)
        stats_path.unlink(missing_ok=True)  # never read a stale file from an earlier run
        try:
            proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=args.timeout)
            text = proc.stdout + proc.stderr
            rec["exit_code"] = proc.returncode
        except subprocess.TimeoutExpired as e:
            text = (e.stdout or b"").decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
            text += f"\n[run_matches] TIMEOUT after {args.timeout}s\n"
            rec["error"] = "timeout"
            break
        if stats_path.exists():
            break
    rec["attempts"] = attempt + 1
    rec["seconds"] = round(time.time() - t0, 1)
    txt_path.write_text(" ".join(cmd) + "\n\n" + text)

    # cambc writes the replay into -o with a generated name; give it a stable one.
    if replay_tmp.is_dir():
        for f in replay_tmp.glob("*.repl26a"):
            f.replace(match_dir / f"{stem}.repl26a")
        for f in replay_tmp.iterdir():
            f.unlink()
        replay_tmp.rmdir()

    return finish_record(rec, text, stats_path, bot_a, bot_b, cand_side)


# Per-champion metrics totalled per side in summary.json, so analysts need not open
# every .stats.json. Champion lines keep the most telling subset.
SIDE_METRICS = ["kills", "deaths", "assists", "collectedGems", "submittedGems", "earnedGold",
                "spentGold", "championDamageDone", "championDamageTaken", "monsterDamageTaken",
                "healingDone"]
CHAMPION_METRICS = ["kills", "deaths", "collectedGems", "submittedGems", "earnedGold", "spentGold",
                    "championDamageTaken"]


def load_stats(stats_path):
    try:
        return json.loads(stats_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None  # e.g. binary statistics written without --json


def num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return 0
    return int(f) if f.is_integer() else round(f, 1)


def side_totals(stats):
    """{"A": {...}, "B": {...}}: metric totals and per-champion lines, from cambc >= 2.2 JSON."""
    sides = {}
    for c in stats.get("champions", []):
        side = {"teamA": "A", "teamB": "B"}.get(c.get("team"))
        metrics = c.get("metrics")
        if side is None or not isinstance(metrics, dict):
            continue
        t = sides.setdefault(side, {m: 0 for m in SIDE_METRICS} | {"champions": {}})
        for m in SIDE_METRICS:
            t[m] = num(t[m] + num(metrics.get(m)))
        line = {m: num(metrics.get(m)) for m in CHAMPION_METRICS}
        line["itemsBought"] = sum(num(i.get("quantity")) for i in c.get("itemsBought", []))
        t["champions"][c.get("name", f"id{c.get('id')}")] = line
    return sides


# Timing figures per side from events and timelines; averaged in side_stats (None = no value).
TIMELINE_METRICS = ["first_death_round", "deaths_before_300", "deaths_to_champions",
                    "deaths_to_monsters", "gems_lost", "first_submit_round",
                    "submitted_by_250", "submitted_by_500", "submitted_by_750"]


def side_timeline(stats):
    """{"A": {...}, "B": {...}}: when deaths and banking happened (cambc >= 2.2 JSON)."""
    out = {s: {"death_rounds": [], "deaths_to_champions": 0, "deaths_to_monsters": 0,
               "gems_lost": 0} for s in ("A", "B")}
    side_of = {"teamA": "A", "teamB": "B"}
    for e in stats.get("events", []):
        owner = e.get("owner") or {}
        side = side_of.get(owner.get("team")) if isinstance(owner, dict) else None
        if side is None:
            continue
        for entry in e.get("entries", []):
            rnd = (entry.get("timestamp") or {}).get("round")
            if e["kind"] == "death":
                out[side]["death_rounds"].append(rnd)
                key = "deaths_to_champions" if entry.get("context") == "champion" else "deaths_to_monsters"
                out[side][key] += 1
            elif e["kind"] == "gemLoss":
                out[side]["gems_lost"] += num(entry.get("value"))
    for t in stats.get("teamTimelines", []):
        side = side_of.get(t.get("owner"))
        if side is None or t.get("metric") != "submittedGems":
            continue
        marks, first = {250: 0, 500: 0, 750: 0}, None
        for start, run in _starts(t.get("runs", [])):
            value = num(run.get("value"))
            if value > 0 and first is None:
                first = start
            for m in marks:
                if start <= m:          # banked total in effect at round m
                    marks[m] = value
        out[side]["first_submit_round"] = first
        for m, v in marks.items():
            out[side][f"submitted_by_{m}"] = v
    for side in out.values():
        rounds = sorted(r for r in side["death_rounds"] if r is not None)
        side["death_rounds"] = rounds[:15]
        side["first_death_round"] = rounds[0] if rounds else None
        side["deaths_before_300"] = sum(r < 300 for r in rounds)
    return out


def _starts(runs):
    t = 0
    for run in runs:
        yield t, run
        t += run.get("duration", 0)


def read_stats(stats_path):
    """(outcome, round, bot_faults) from a --statistics file, or None if unreadable.
    cambc >= 2.2 nests these under "match"/"diagnostics"; 2.1 had them at the top level."""
    stats = load_stats(stats_path)
    if stats is None:
        return None
    match = stats.get("match", stats)
    return (match.get("outcome"), match.get("roundsStarted", match.get("round")),
            stats.get("diagnostics", stats).get("botFaults"))


def finish_record(rec, text, stats_path, bot_a, bot_b, cand_side):
    rec.update(parse_output(text))
    full = load_stats(stats_path) if stats_path.exists() else None
    if full:
        sides = side_totals(full)
        if sides:
            timeline = side_timeline(full)
            for side, t in sides.items():
                t["timeline"] = timeline.get(side, {})
            rec["sides"] = sides
    stats = read_stats(stats_path) if stats_path.exists() else None
    if stats is None and stats_path.exists():
        # Fall back to the winner line in cambc's output.
        m = WIN_RE.search(text)
        r = re.search(r"in round (\d+)", m.group(3)) if m else None
        stats = (f"team{m.group(1)}" if m else None, int(r.group(1)) if r else None, None)
    if stats is not None:
        outcome, rec["round"], rec["bot_faults"] = stats
        rec["outcome"] = outcome  # "teamA" / "teamB"
        if outcome in ("teamA", "teamB"):
            winner_side = outcome[-1]
            rec["winner"] = bot_a if winner_side == "A" else bot_b
            rec["result"] = "win" if winner_side == cand_side else "loss"
        else:
            rec["result"] = "draw"
    elif "error" not in rec:
        rec["error"] = text.strip().splitlines()[-1] if text.strip() else "no output"
    return rec


def rate(recs):
    w = sum(r["result"] == "win" for r in recs)
    l = sum(r["result"] == "loss" for r in recs)
    d = sum(r["result"] == "draw" for r in recs)
    e = sum(r["result"] == "error" for r in recs)
    played = w + l + d
    return {"wins": w, "losses": l, "draws": d, "errors": e, "played": played,
            "win_rate": round((w + 0.5 * d) / played, 4) if played else None}


def side_stats(recs):
    """Average per-match totals for the candidate's side and the opponent's side, overall and
    split by wins/losses, plus per-champion averages for the candidate."""
    def avg(rows):
        if not rows:
            return None
        out = {m: round(sum(r[m] for r in rows) / len(rows), 1) for m in SIDE_METRICS}
        for m in TIMELINE_METRICS:
            vals = [r.get("timeline", {}).get(m) for r in rows]
            vals = [v for v in vals if v is not None]
            out[m] = round(sum(vals) / len(vals), 1) if vals else None
        return out | {"matches": len(rows)}

    def pick(rows, mine):
        out = []
        for r in rows:
            side = r["candidate_side"] if mine else ("B" if r["candidate_side"] == "A" else "A")
            if side in r.get("sides", {}):
                out.append(r["sides"][side])
        return out

    wins = [r for r in recs if r["result"] == "win"]
    losses = [r for r in recs if r["result"] == "loss"]
    champs = defaultdict(list)
    for t in pick(recs, True):
        for name, line in t["champions"].items():
            champs[name].append(line)
    keys = CHAMPION_METRICS + ["itemsBought"]
    return {
        "candidate": avg(pick(recs, True)), "opponent": avg(pick(recs, False)),
        "candidate_in_wins": avg(pick(wins, True)), "opponent_in_wins": avg(pick(wins, False)),
        "candidate_in_losses": avg(pick(losses, True)), "opponent_in_losses": avg(pick(losses, False)),
        "candidate_champions": {
            n: {k: round(sum(l[k] for l in ls) / len(ls), 1) for k in keys} | {"matches": len(ls)}
            for n, ls in sorted(champs.items())},
    }


def summarize(args, maps, recs):
    def group(key):
        g = defaultdict(list)
        for r in recs:
            g[key(r)].append(r)
        return {k: rate(v) for k, v in sorted(g.items())}

    wins = [r for r in recs if r["result"] == "win" and r.get("round")]
    losses = [r for r in recs if r["result"] == "loss" and r.get("round")]
    reasons = defaultdict(int)
    for r in recs:
        if r.get("reason"):
            reasons[re.sub(r" in round \d+", "", r["reason"])] += 1
    return {
        "tag": args.tag, "candidate": args.candidate, "opponents": args.opponents, "maps": maps,
        "overall": rate(recs),
        "by_opponent": group(lambda r: r["opponent"]),
        "by_map": group(lambda r: r["map"]),
        "by_side": group(lambda r: r["candidate_side"]),
        "avg_round_of_wins": round(sum(r["round"] for r in wins) / len(wins), 1) if wins else None,
        "avg_round_of_losses": round(sum(r["round"] for r in losses) / len(losses), 1) if losses else None,
        "end_reasons": dict(reasons),
        "candidate_crashes": sum(r["teams"].get(r["candidate_side"], {}).get("crashes", 0) for r in recs),
        # Averages per match from .stats.json (cambc >= 2.2 with --json); see side_stats().
        "side_stats": side_stats(recs),
        "matches": sorted(recs, key=lambda r: (r["opponent"], r["map"], r["candidate_side"])),
    }


def main():
    args = parse_args()
    for bot in [args.candidate, *args.opponents]:
        if not (BOTS_DIR / bot).is_dir():
            sys.exit(f"error: bot not found: bots/{bot}")
    maps = args.maps or sorted(p.stem for p in MAPS_DIR.glob("*.map26a"))
    for m in maps:
        if not (MAPS_DIR / f"{m}.map26a").exists():
            sys.exit(f"error: map not found: maps/{m}.map26a")

    out_dir = ROOT / "results" / args.tag
    if out_dir.exists() and any(out_dir.iterdir()) and not (args.force or args.resume):
        sys.exit(f"error: {out_dir} already exists (use --force, --resume or a new --tag)")
    out_dir.mkdir(parents=True, exist_ok=True)

    jobs = schedule(args.opponents, maps, args.games)
    if args.games and args.games > 2 * len(maps):
        print(f"note: games are deterministic; only {2 * len(maps)} distinct (map, side) "
              f"pairings exist, so extra games will repeat results", file=sys.stderr)
    print(f"{args.candidate} vs {', '.join(args.opponents)}: {len(jobs)} matches, "
          f"{len(maps)} maps, {args.jobs} parallel -> {out_dir.relative_to(ROOT)}")

    recs = []
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futs = [pool.submit(run_match, args, out_dir, *job) for job in jobs]
        for i, fut in enumerate(as_completed(futs), 1):
            r = fut.result()
            recs.append(r)
            detail = r.get("reason") or r.get("error") or ""
            if r.get("resumed"):
                detail += " (resumed)"
            print(f"[{i:>3}/{len(jobs)}] vs {r['opponent']:<16} {r['map']:<12} "
                  f"cand={r['candidate_side']}  {r['result'].upper():<5} {detail}", flush=True)

    summary = summarize(args, maps, recs)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))

    o = summary["overall"]
    print(f"\n{args.candidate}: {o['wins']}W {o['losses']}L {o['draws']}D "
          f"({o['errors']} errors)  win rate {o['win_rate']}")
    for opp, s in summary["by_opponent"].items():
        print(f"  vs {opp:<16} {s['wins']}-{s['losses']}  win rate {s['win_rate']}")
    print(f"summary: {(out_dir / 'summary.json').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
