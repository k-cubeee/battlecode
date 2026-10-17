"""
orchestrator_arena.py - two independent teams of agents, plus a referee.

  Team A: bots/vN, NOTES.md,   orchestrator_state.json   (the existing line, champion v6)
  Team B: bots/bN, NOTES_B.md, orchestrator_state_b.json (its own line, started from v1)

Each round:
  1. Team A cycle: analyst -> strategist builds vN -> smoke test -> evaluate vs Team A's
     pool -> promote if >= 55% vs Team A's champion, else reject.
  2. Team B cycle: the same, with Team B's agents, notes and pool.
  3. Arena: Team A's champion vs Team B's champion on every map from both sides
     (results/arena_<n>/). The referee agent reads the results and both bots and
     writes a report, appended to ARENA.md and printed here. That report is for the
     lead (the interactive Claude session or you), not for the teams.

Team isolation: each team's agents are denied reading the other team's bots, notes,
state and evaluation results. Both teams may read results/arena_*/ (scores and stats,
no code), so they can adapt to each other. ARENA.md is hidden from both teams.
As in orchestrator_hardened.py, deny rules are a seatbelt and the container is the wall.

All the hardening (deny list, key-free subprocess env, headless permissions) comes
from orchestrator_hardened.py, which this script imports. Don't run both scripts at once.

Run on the host:  python orchestrator_arena.py --allow-host
Resume: run it again (progress is in the two team state files and arena_state.json).
"""

import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import orchestrator_hardened as oh
from orchestrator_hardened import fmt, log

# ============================ CONFIG ============================
ROOT = oh.ROOT
BOT_DIR = ROOT / "bots"
REJECTED_DIR = ROOT / "rejected"
ARCHIVE_DIR = ROOT / "archive"     # old bots moved out of bots/ by archive_oldest()
ARENA_NOTES = ROOT / "ARENA.md"
ARENA_STATE = ROOT / "arena_state.json"

ROUNDS = 5                      # rounds of (Team A cycle, Team B cycle, arena) per run
MAX_RUN_COST_USD = 50.00        # API spend cap for one run of this script, all agents
PROMOTE_THRESHOLD = 0.55
POOL_SIZE = 3
SHARED_BASELINE = "v1"          # both teams' fallback opponent (b1 is a copy of it)

TEAM_MODEL = "claude-sonnet-5-5"
REFEREE_MODEL = "claude-sonnet-5-5"
MAX_TURNS_REFEREE = 50

ANALYST_TOOLS = ["Read", "Grep", "Glob", "Edit"]
STRATEGIST_TOOLS = ["Read", "Write", "Edit", "Grep", "Glob", "Bash"]
# No head/tail/cat: they would get around the Read deny rules that keep the teams apart.
STRATEGIST_AUTO_ALLOW = ["Read", "Write", "Edit", "Grep", "Glob",
                         "Bash(cambc:*)", "Bash(ls:*)", "Bash(wc:*)"]
REFEREE_TOOLS = ["Read", "Grep", "Glob"]

# Files no team agent may write, whichever team it is on.
PROTECTED = ["NOTES.md", "NOTES_B.md", "ARENA.md", "orchestrator*.py", "run_matches.py",
             ".claude/**", "orchestrator_state*.json", "arena_state.json"]
# ================================================================


@dataclass
class Team:
    key: str            # "A" or "B"
    prefix: str         # bot folder prefix: v1, v2 ... or b1, b2 ...
    notes: Path
    state_file: Path
    first_bot: str      # start of the line, used when there is no state yet
    analyst: str        # .claude/agents/<name>.md
    strategist: str
    eval_prefix: str    # results/<eval_prefix><bot>/
    bench_prefix: str
    hidden: list        # paths this team may not read (the other team's work)
    pool_exclude: tuple = ()  # bots never used as evaluation opponents for this team


TEAM_A = Team(
    key="A", prefix="v", notes=ROOT / "NOTES.md", state_file=ROOT / "orchestrator_state.json",
    first_bot="v1", analyst="analyst", strategist="strategist",
    eval_prefix="eval_", bench_prefix="bench_",
    hidden=["bots/b*/**", "rejected/b*/**", "archive/b*/**", "NOTES_B.md", "ARENA.md", "orchestrator_state_b.json",
            "arena_state.json", "results/evalB_*/**", "results/benchB_*/**"],
    pool_exclude=("v1", "v2"),  # too weak to tell Team A's versions apart; saves eval time
)
TEAM_B = Team(
    key="B", prefix="b", notes=ROOT / "NOTES_B.md", state_file=ROOT / "orchestrator_state_b.json",
    first_bot="b1", analyst="teamb-analyst", strategist="teamb-strategist",
    eval_prefix="evalB_", bench_prefix="benchB_",
    hidden=["bots/v*/**", "rejected/v*/**", "archive/v*/**", "NOTES.md", "ARENA.md", "orchestrator_state.json",
            "arena_state.json", "results/eval_*/**", "results/bench_*/**",
            "results/v*-eval/**", "results/test1/**"],
)
TEAMS = [TEAM_A, TEAM_B]

CHAMPION_RE = re.compile(r"^\*\*Current champion: ([a-z]\d+)\*\*$", re.M)
NOTES_B_HEADER = """# Team B bot notes

**Current champion: b1**

Team B develops its own line of bots (bots/bN) independently of Team A (bots/vN).
b1 is a copy of v1, the SDK starter bot. Promotion gate: >= 55% head-to-head vs Team B's
current champion over a full evaluation (every map, both sides). Rejected versions move
to rejected/. Cross-team arena results are in results/arena_*/ (Team A is the candidate there).

### b1 — baseline
- Copy of v1 (SDK starter bot with a modified draft). Start of Team B's line.
"""


# ----------------------------- helpers -----------------------------
def deny(patterns: list, tools=("Read", "Edit", "Write")) -> list:
    return [f"{t}({p})" for p in patterns for t in tools]


def version_num(bot: str) -> int:
    return int(bot[1:])


def next_free(team: Team, state: dict) -> int:
    """Numbers are never reused: skip anything in bots/, rejected/ or archive/, even if unevaluated."""
    nums = [version_num(p.name) for d in (BOT_DIR, REJECTED_DIR, ARCHIVE_DIR) if d.exists()
            for p in d.iterdir() if re.fullmatch(rf"{team.prefix}\d+", p.name)]
    return max([state["next_version"], *(n + 1 for n in nums)])


def load_state(team: Team) -> dict:
    if team.state_file.exists():
        return json.loads(team.state_file.read_text())
    return {"champion": team.first_bot, "history": [team.first_bot], "next_version": 2,
            "total_cost": 0.0, "last_results": []}


def save_state(team: Team, state: dict) -> None:
    team.state_file.write_text(json.dumps(state, indent=2))


def append_notes(path: Path, text: str) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"\n{text.strip()}\n")


def set_notes_champion(team: Team, bot: str) -> None:
    text = team.notes.read_text(encoding="utf-8")
    team.notes.write_text(CHAMPION_RE.sub(f"**Current champion: {bot}**", text, count=1),
                          encoding="utf-8")


def git_commit(message: str, paths: list) -> None:
    """Commit only the named paths, never anything else in the working tree."""
    if not (ROOT / ".git").exists():
        return
    paths = [str(p) for p in paths if (ROOT / p).exists()]
    if not paths:
        return
    subprocess.run(["git", "add", "--", *paths], cwd=ROOT, capture_output=True)
    subprocess.run(["git", "commit", "-m", message, "--", *paths], cwd=ROOT, capture_output=True)


def archive_oldest(team: Team, state: dict) -> None:
    """After each new version, move the team's oldest bot out of bots/ into archive/.
    Never moves the shared baseline, the champion or a bot in the evaluation pool."""
    keep = {SHARED_BASELINE, state["champion"], *build_pool(team, state)}
    old = sorted((p.name for p in BOT_DIR.iterdir()
                  if re.fullmatch(rf"{team.prefix}\d+", p.name) and p.name not in keep),
                 key=version_num)
    if not old:
        return
    bot = old[0]
    ARCHIVE_DIR.mkdir(exist_ok=True)
    shutil.move(str(BOT_DIR / bot), str(ARCHIVE_DIR / bot))
    log(f"Team {team.key}: archived {bot} (bots/{bot} -> archive/{bot}).")
    if (ROOT / ".git").exists():
        paths = [f"bots/{bot}", f"archive/{bot}"]
        subprocess.run(["git", "add", "-A", "--", *paths], cwd=ROOT, capture_output=True)
        subprocess.run(["git", "commit", "-m", f"Team {team.key}: archive {bot}", "--", *paths],
                       cwd=ROOT, capture_output=True)


def build_pool(team: Team, state: dict) -> list:
    recent = [b for b in reversed(state["history"]) if b not in team.pool_exclude][:POOL_SIZE]
    return [b for b in dict.fromkeys(recent + [SHARED_BASELINE]) if b not in team.pool_exclude]


def load_arena() -> dict:
    if ARENA_STATE.exists():
        return json.loads(ARENA_STATE.read_text())
    return {"next_arena": 1, "played": {}, "history": [], "total_cost": 0.0}


def save_arena(arena: dict) -> None:
    ARENA_STATE.write_text(json.dumps(arena, indent=2))


def latest_arena_tag(arena: dict):
    return arena["history"][-1]["tag"] if arena["history"] else None


# ----------------------------- agent tasks -----------------------------
def isolation_note(team: Team) -> str:
    return ("Team isolation: you are on Team " + team.key + ". Do not read the other team's "
            "work: " + ", ".join(team.hidden) + ".")


def arena_note(team: Team, arena_tag) -> str:
    if not arena_tag:
        return ""
    side = ("your champion is the candidate" if team.key == "A" else
            "Team A's champion is the candidate and your champion is the opponent, so a "
            "'loss' in summary.json is a win for you")
    return (f"\nCross-team arena vs the other team's champion: results/{arena_tag}/ ({side}). "
            "Beating the other team is the main goal; the promotion gate is still your own champion.\n")


def analyst_task(team: Team, champion: str, tags: list, arena_tag) -> str:
    dirs = "\n".join(f"- results/{t}/" for t in tags) or "- (none yet)"
    return f"""You are Team {team.key}'s analyst. The current Team {team.key} champion is
`{champion}` (source: bots/{champion}/src/).

Recent results of Team {team.key} (each folder has summary.json, per-match .txt logs and
.stats.json exports):
{dirs}
{arena_note(team, arena_tag)}
Previous attempts and lessons are in {team.notes.name}. Game rules and docs are
GameRules.md and BotAPIPython.md.

{isolation_note(team)}

Find the top 3 concrete weaknesses of `{champion}` with evidence, following your
instructions, and append your analysis section to the end of {team.notes.name}. Do not
edit anything under bots/. Finish by repeating the three findings in your reply."""


def strategist_task(team: Team, new_bot: str, champion: str, analysis: str) -> str:
    return f"""Create Team {team.key}'s next bot version `{new_bot}`.

The orchestrator has ALREADY copied the champion: bots/{new_bot}/ exists and is an exact
copy of `{champion}`. Do not create any other bot folder.

Analysis of the champion's weaknesses (also in {team.notes.name}):
{analysis}

Rules:
- Only edit files inside bots/{new_bot}/.
- Check the game docs for correct API usage. Never guess the API.
- Implement the most promising change(s), keeping them focused.
- Smoke test with: cambc run {new_bot} {champion} --map <map>   and fix any crash.
- Shell access is limited to cambc, ls and wc. Use Read/Grep/Glob for everything else.
- Do NOT edit {team.notes.name}; the orchestrator records the version entry and result.
- {isolation_note(team)}

Finish with a short summary: what you changed (file:function) and why it should win."""


def referee_task(n: int, a: str, b: str, tag: str) -> str:
    return f"""Arena {n}: Team A's champion `{a}` (bots/{a}/src/) played Team B's champion
`{b}` (bots/{b}/src/) on every map from both sides. Results: results/{tag}/
(the candidate is {a}, the opponent is {b}). Today is {date.today():%Y-%m-%d}.
Earlier arena reports are in ARENA.md, if it exists.

Write your report following your instructions. Reply with the report only."""


# ----------------------------- one team cycle -----------------------------
async def team_cycle(team: Team, state: dict, budget: float, arena_tag) -> float:
    """Build, test, evaluate and promote/reject one new version. Returns the API cost."""
    spent = 0.0
    champion = state["champion"]
    num = next_free(team, state)
    new_bot = f"{team.prefix}{num}"
    new_path = BOT_DIR / new_bot
    hidden = deny(team.hidden)
    log(f"===== Team {team.key}: building {new_bot} (champion: {champion}) =====")

    analysis, cost = await oh.run_agent(
        f"{team.key}:analyst", analyst_task(team, champion, state["last_results"], arena_tag),
        oh.load_agent_prompt(team.analyst, oh.DEFAULT_ANALYST_PROMPT),
        ANALYST_TOOLS, ANALYST_TOOLS,
        ["Edit(bots/**)", "Write(bots/**)"] + hidden,
        TEAM_MODEL, oh.MAX_TURNS_ANALYST, budget - spent,
    )
    spent += cost

    shutil.copytree(BOT_DIR / champion, new_path,
                    ignore=shutil.ignore_patterns(".cambc", "build", "target", "__pycache__"))
    strat_prompt = oh.load_agent_prompt(team.strategist, oh.DEFAULT_STRATEGIST_PROMPT)
    strat_deny = deny(PROTECTED, ("Edit", "Write")) + hidden
    changes, cost = await oh.run_agent(
        f"{team.key}:strategist", strategist_task(team, new_bot, champion, analysis),
        strat_prompt, STRATEGIST_TOOLS, STRATEGIST_AUTO_ALLOW, strat_deny,
        TEAM_MODEL, oh.MAX_TURNS_STRATEGIST, budget - spent,
    )
    spent += cost

    ok, output = oh.smoke_test(new_bot)
    if not ok and budget - spent > 0:
        log(f"Team {team.key}: smoke test failed. Asking the strategist to fix it.")
        _, cost = await oh.run_agent(
            f"{team.key}:strategist-fix",
            f"The bot `{new_bot}` crashed or failed to run in `cambc run {new_bot} {SHARED_BASELINE}`. "
            f"Output (tail):\n\n{output[-3000:]}\n\nFix the bug. Only edit files in bots/{new_bot}/. "
            f"{isolation_note(team)}",
            strat_prompt, STRATEGIST_TOOLS, STRATEGIST_AUTO_ALLOW, strat_deny,
            TEAM_MODEL, oh.MAX_TURNS_STRATEGIST, budget - spent,
        )
        spent += cost
        ok, output = oh.smoke_test(new_bot)

    state["next_version"] = num + 1
    state["total_cost"] += spent
    commit_paths = [f"bots/{new_bot}", f"rejected/{new_bot}", team.notes.name, team.state_file.name]

    if not ok:
        log(f"Team {team.key}: {new_bot} still crashes. Rejecting.")
        shutil.move(str(new_path), str(REJECTED_DIR / new_bot))
        append_notes(team.notes, f"### {new_bot} — rejected (crashed)\n- Based on: {champion}\n"
                                 f"- Changes: {changes}\n- Status: rejected, moved to rejected/{new_bot}.")
        save_state(team, state)
        git_commit(f"Team {team.key}: {new_bot} rejected (crash)", commit_paths)
        return spent

    opponents = build_pool(team, state)
    tag = f"{team.eval_prefix}{new_bot}"
    summary = oh.run_matches(new_bot, opponents, tag)
    wr = oh.win_rate_vs(summary, champion)
    per_opp = ", ".join(f"{o} {fmt(oh.win_rate_vs(summary, o))}" for o in opponents)
    overall = fmt(summary["overall"]["win_rate"]) if summary else "unknown"
    log(f"Team {team.key}: {new_bot} vs champion {champion}: {fmt(wr)} | {per_opp} | overall {overall}")

    record = (f"- Based on: {champion}\n- Changes: {changes}\n"
              f"- Evaluation (results/{tag}): {per_opp}; overall {overall}")
    if wr is not None and wr >= PROMOTE_THRESHOLD:
        state["champion"] = new_bot
        state["history"].append(new_bot)
        state["last_results"] = [tag]
        append_notes(team.notes, f"### {new_bot} — promoted ({fmt(wr)} vs {champion})\n{record}\n"
                                 f"- Status: promoted, new champion.")
        set_notes_champion(team, new_bot)
        save_state(team, state)
        git_commit(f"Team {team.key}: {new_bot} promoted ({fmt(wr)} vs {champion})", commit_paths)
        log(f"Team {team.key}: PROMOTED {new_bot}.")
    else:
        shutil.move(str(new_path), str(REJECTED_DIR / new_bot))
        state["last_results"] = (state["last_results"] + [tag])[-2:]
        append_notes(team.notes, f"### {new_bot} — rejected ({fmt(wr)} vs {champion})\n{record}\n"
                                 f"- Status: rejected, moved to rejected/{new_bot}. "
                                 f"Lesson: these changes did not beat {champion}.")
        save_state(team, state)
        git_commit(f"Team {team.key}: {new_bot} rejected ({fmt(wr)} vs {champion})", commit_paths)
        log(f"Team {team.key}: REJECTED {new_bot}. Champion stays {champion}.")
    return spent


def bench(team: Team, state: dict) -> None:
    """First run only: results for the champion, so the analyst has data."""
    champ = state["champion"]
    opponents = [b for b in build_pool(team, state) if b != champ] or [SHARED_BASELINE]
    tag = f"{team.bench_prefix}{champ}"
    summary = oh.run_matches(champ, opponents, tag)
    log(f"Team {team.key} baseline: {champ} overall win rate = "
        f"{fmt(summary['overall']['win_rate'] if summary else None)}")
    state["last_results"] = [tag]
    save_state(team, state)


# ----------------------------- arena + referee -----------------------------
async def arena_round(arena: dict, a: str, b: str, budget: float) -> float:
    """Play Team A's champion vs Team B's champion and have the referee report.
    Matches are deterministic, so a pairing that was already played is skipped."""
    key = f"{a}|{b}"
    if key in arena["played"]:
        log(f"Arena: {a} vs {b} already played ({arena['played'][key]}); no new champions, skipping.")
        return 0.0
    n = arena["next_arena"]
    tag = f"arena_{n}"
    log(f"===== Arena {n}: Team A {a} vs Team B {b} =====")
    summary = oh.run_matches(a, [b], tag)
    if not summary:
        log("Arena: no summary; skipping the referee.")
        return 0.0
    wr = oh.win_rate_vs(summary, b)
    s = summary["by_opponent"].get(b, {})
    score = f"Team A {s.get('wins', '?')}-{s.get('losses', '?')} Team B"
    log(f"Arena {n}: {score} (Team A win rate {fmt(wr)})")

    report, cost = "", 0.0
    if budget > 0:
        report, cost = await oh.run_agent(
            "referee", referee_task(n, a, b, tag),
            oh.load_agent_prompt("referee", "You are a neutral Battlecode referee."),
            REFEREE_TOOLS, REFEREE_TOOLS, [], REFEREE_MODEL, MAX_TURNS_REFEREE, budget,
        )
    if not report.strip():
        report = (f"### Arena {n} — {a} (Team A) vs {b} (Team B) — {date.today():%Y-%m-%d}\n"
                  f"Score: {score} ({fmt(wr)}). No referee report (budget or agent failure).")
    if not ARENA_NOTES.exists():
        ARENA_NOTES.write_text("# Arena reports: Team A vs Team B\n\nWritten by the referee agent. "
                               "Hidden from both teams.\n", encoding="utf-8")
    append_notes(ARENA_NOTES, report)
    print("\n" + report.strip() + "\n", flush=True)

    arena["played"][key] = tag
    arena["history"].append({"arena": n, "a": a, "b": b, "tag": tag,
                             "a_win_rate": wr, "score": score, "date": f"{date.today():%Y-%m-%d}"})
    arena["next_arena"] = n + 1
    arena["total_cost"] += cost
    save_arena(arena)
    git_commit(f"Arena {n}: {a} vs {b}, {score}", ["ARENA.md", "arena_state.json"])
    return cost


# ----------------------------- main loop -----------------------------
async def main() -> None:
    if not oh.in_container() and "--allow-host" not in sys.argv:
        sys.exit("Not running inside the container. Pass --allow-host if you really mean "
                 "to run on the host.")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY is not set.")
    if not (BOT_DIR / TEAM_B.first_bot).is_dir():
        sys.exit(f"bots/{TEAM_B.first_bot} not found. Create it as a copy of bots/v1.")

    REJECTED_DIR.mkdir(exist_ok=True)
    if not TEAM_B.notes.exists():
        TEAM_B.notes.write_text(NOTES_B_HEADER, encoding="utf-8")
    states = {t.key: load_state(t) for t in TEAMS}
    arena = load_arena()
    spent = 0.0
    for t in TEAMS:
        log(f"Team {t.key}: champion {states[t.key]['champion']} | history {states[t.key]['history']}")
        if not states[t.key]["last_results"]:
            bench(t, states[t.key])

    spent += await arena_round(arena, states["A"]["champion"], states["B"]["champion"],
                               MAX_RUN_COST_USD - spent)
    for r in range(1, ROUNDS + 1):
        log(f"########## Round {r}/{ROUNDS} ##########")
        for t in TEAMS:
            if spent >= MAX_RUN_COST_USD:
                break
            spent += await team_cycle(t, states[t.key], MAX_RUN_COST_USD - spent,
                                      latest_arena_tag(arena))
            archive_oldest(t, states[t.key])
        if spent >= MAX_RUN_COST_USD:
            log(f"Cost limit reached (${spent:.2f}). Stopping.")
            break
        spent += await arena_round(arena, states["A"]["champion"], states["B"]["champion"],
                                   MAX_RUN_COST_USD - spent)
        log(f"API cost this run so far: ${spent:.2f}")

    last = arena["history"][-1] if arena["history"] else None
    log(f"Done. Team A champion {states['A']['champion']}, Team B champion "
        f"{states['B']['champion']}. Latest arena: "
        f"{last['score'] + ' (' + last['tag'] + ')' if last else 'none'}. "
        f"Cost this run: ${spent:.2f}. Reports: ARENA.md")


if __name__ == "__main__":
    asyncio.run(main())
