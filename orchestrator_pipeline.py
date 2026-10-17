"""
orchestrator_pipeline.py - Team A's bot line (bots/vN, NOTES.md) developed by a pipeline
of three specialist agents, aimed at producing a version that beats the champion.

Each round:
  1. researcher  - studies the champion's evaluations and the rejected attempts against it
                   (which maps they flipped and why) and appends a report to NOTES.md.
  2. designer    - turns the report into one multi-part change plan for the next version
                   and appends it to NOTES.md.
  3. implementer - builds the plan in bots/vN (a fresh copy of the champion) and tests it
                   against the champion with targeted matches.
  4. smoke test, full evaluation vs the pool, promote if >= 55% vs the champion, else
     reject to rejected/vN. Then the oldest unprotected bot moves to archive/.

Hardening (deny list, key-free subprocess env, headless permissions, match runner,
smoke test) comes from orchestrator_hardened.py. Don't run two orchestrators at once.

Run on the host:  python orchestrator_pipeline.py --allow-host
Resume: run it again (progress is in orchestrator_state.json and NOTES.md).
"""

import asyncio
import json
import os
import re
import shutil
import subprocess
import sys

import orchestrator_hardened as oh
from orchestrator_hardened import fmt, log

# ============================ CONFIG ============================
ROOT = oh.ROOT
BOT_DIR = ROOT / "bots"
REJECTED_DIR = ROOT / "rejected"
ARCHIVE_DIR = ROOT / "archive"
RESULTS_DIR = ROOT / "results"
NOTES = ROOT / "NOTES.md"
STATE_FILE = ROOT / "orchestrator_state.json"

ROUNDS = 5                      # versions to build per run
MAX_RUN_COST_USD = 50.00        # API spend cap for one run of this script, all agents
PROMOTE_THRESHOLD = 0.55
POOL_SIZE = 3
BASELINE = "v1"                 # smoke-test opponent; never archived
POOL_EXCLUDE = ("v1", "v2")     # too weak to tell versions apart

MODEL = "claude-opus-5-5"
MAX_TURNS = {"researcher": 90, "designer": 50, "implementer": 120}

READ_TOOLS = ["Read", "Grep", "Glob", "Edit"]          # researcher and designer
IMPL_TOOLS = ["Read", "Write", "Edit", "Grep", "Glob", "Bash"]
# No head/tail/cat: Read covers them, and fewer shell commands means fewer ways around deny rules.
IMPL_AUTO_ALLOW = ["Read", "Write", "Edit", "Grep", "Glob",
                   "Bash(cambc:*)", "Bash(ls:*)", "Bash(wc:*)"]
# Files no agent may write. Researcher and designer may append to NOTES.md only.
PROTECTED = ["orchestrator*.py", "run_matches.py", ".claude/**", "orchestrator_state*.json",
             "CLAUDE.md", "archive/**"]
CHAMPION_RE = re.compile(r"^\*\*Current champion: (v\d+)\*\*$", re.M)
# ================================================================


def deny(patterns, tools=("Edit", "Write")) -> list:
    return [f"{t}({p})" for p in patterns for t in tools]


def version_num(bot: str) -> int:
    return int(bot[1:])


def next_free(state: dict) -> int:
    """Numbers are never reused: skip anything in bots/, rejected/ or archive/."""
    nums = [version_num(p.name) for d in (BOT_DIR, REJECTED_DIR, ARCHIVE_DIR) if d.exists()
            for p in d.iterdir() if re.fullmatch(r"v\d+", p.name)]
    return max([state["next_version"], *(n + 1 for n in nums)])


def load_state() -> dict:
    return json.loads(STATE_FILE.read_text())


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


def append_notes(text: str) -> None:
    with open(NOTES, "a", encoding="utf-8") as f:
        f.write(f"\n{text.strip()}\n")


def set_notes_champion(bot: str) -> None:
    text = NOTES.read_text(encoding="utf-8")
    NOTES.write_text(CHAMPION_RE.sub(f"**Current champion: {bot}**", text, count=1), encoding="utf-8")


def git_commit(message: str, paths: list) -> None:
    """Commit only the named paths (additions and removals), never anything else."""
    if not (ROOT / ".git").exists():
        return
    subprocess.run(["git", "add", "-A", "--", *paths], cwd=ROOT, capture_output=True)
    subprocess.run(["git", "commit", "-m", message, "--", *paths], cwd=ROOT, capture_output=True)


def build_pool(state: dict) -> list:
    recent = [b for b in reversed(state["history"]) if b not in POOL_EXCLUDE][:POOL_SIZE]
    return recent or [BASELINE]


def archive_oldest(state: dict) -> None:
    """Move the oldest bot that is not the baseline, the champion or in the pool to archive/."""
    keep = {BASELINE, state["champion"], *build_pool(state)}
    old = sorted((p.name for p in BOT_DIR.iterdir()
                  if re.fullmatch(r"v\d+", p.name) and p.name not in keep), key=version_num)
    if not old:
        return
    bot = old[0]
    ARCHIVE_DIR.mkdir(exist_ok=True)
    shutil.move(str(BOT_DIR / bot), str(ARCHIVE_DIR / bot))
    log(f"archived {bot} (bots/{bot} -> archive/{bot}).")
    git_commit(f"archive {bot}", [f"bots/{bot}", f"archive/{bot}"])


def attempts_against(champion: str) -> list:
    """Eval folders of rejected versions built after the champion: experiments against it."""
    tags = []
    for p in sorted(REJECTED_DIR.iterdir(), key=lambda p: version_num(p.name)) if REJECTED_DIR.exists() else []:
        if re.fullmatch(r"v\d+", p.name) and version_num(p.name) > version_num(champion):
            if (RESULTS_DIR / f"eval_{p.name}" / "summary.json").exists():
                tags.append(f"eval_{p.name}")
    return tags


# ----------------------------- agent tasks -----------------------------
def researcher_task(champion: str, tags: list) -> str:
    dirs = "\n".join(f"- results/{t}/" for t in tags) or "- (none)"
    return f"""The current champion is `{champion}` (bots/{champion}/src/).

Result folders to study (the champion's own evaluation, then the rejected attempts
against it, whose code is in rejected/<vN>/src/):
{dirs}

Follow your instructions: build the per-map picture, extract the lessons from the
rejected attempts, find what decides the champion's lost games, and append your
research section to the end of NOTES.md. Do not edit anything else."""


def designer_task(champion: str, new_bot: str, research: str) -> str:
    return f"""Design the next version `{new_bot}`, based on the champion `{champion}`
(bots/{champion}/src/). It must beat `{champion}` >= 55% over every map from both sides.

The researcher's report (also the latest research section in NOTES.md):
{research}

Follow your instructions and append your design section for `{new_bot}` to the end of
NOTES.md. Do not edit anything else."""


def implementer_task(champion: str, new_bot: str, design: str) -> str:
    return f"""Build `{new_bot}`. The orchestrator has ALREADY copied the champion `{champion}`
to bots/{new_bot}/. Do not create any other bot folder. Only edit files in bots/{new_bot}/.

The design to implement (also the last section of NOTES.md):
{design}

Follow your instructions: implement every change, check the API in the docs, smoke-test
with `cambc run {new_bot} {champion} --map <map>`, then run the design's test games
(both sides) and tune if needed. Do NOT edit NOTES.md; the orchestrator records the
version entry and the result. Finish with the reply your instructions describe."""


async def agent(name: str, task: str, tools, auto_allow, extra_deny, budget: float):
    return await oh.run_agent(name, task, oh.load_agent_prompt(name, f"You are the {name}."),
                              tools, auto_allow, extra_deny, MODEL, MAX_TURNS[name], budget)


# ----------------------------- one round -----------------------------
async def build_version(state: dict, budget: float) -> float:
    spent = 0.0
    champion = state["champion"]
    num = next_free(state)
    new_bot = f"v{num}"
    new_path = BOT_DIR / new_bot
    log(f"===== building {new_bot} (champion: {champion}) =====")

    # Researcher and designer: read anything, write only NOTES.md (appending is their job).
    read_deny = ["Edit(bots/**)", "Write(bots/**)", "Edit(rejected/**)", "Write(rejected/**)"] + deny(PROTECTED)
    own = [f"eval_{champion}"] if (RESULTS_DIR / f"eval_{champion}" / "summary.json").exists() else []
    tags = [*own, *state["last_results"], *attempts_against(champion)]
    tags = list(dict.fromkeys(tags))
    research, cost = await agent("researcher", researcher_task(champion, tags),
                                 READ_TOOLS, READ_TOOLS, read_deny, budget - spent)
    spent += cost
    if spent >= budget:
        return spent
    design, cost = await agent("designer", designer_task(champion, new_bot, research),
                               READ_TOOLS, READ_TOOLS, read_deny, budget - spent)
    spent += cost
    if spent >= budget:
        return spent

    shutil.copytree(BOT_DIR / champion, new_path,
                    ignore=shutil.ignore_patterns(".cambc", "build", "target", "__pycache__"))
    impl_deny = deny(PROTECTED + ["NOTES.md", "rejected/**"]) + [
        f"{t}(bots/{b}/**)" for b in (p.name for p in BOT_DIR.iterdir() if p.name != new_bot)
        for t in ("Edit", "Write")]
    changes, cost = await agent("implementer", implementer_task(champion, new_bot, design),
                                IMPL_TOOLS, IMPL_AUTO_ALLOW, impl_deny, budget - spent)
    spent += cost

    ok, output = oh.smoke_test(new_bot)
    if not ok and budget - spent > 0:
        log(f"{new_bot}: smoke test failed. Asking the implementer to fix it.")
        _, cost = await agent(
            "implementer",
            f"The bot `{new_bot}` crashed or failed to run in `cambc run {new_bot} {BASELINE}`. "
            f"Output (tail):\n\n{output[-3000:]}\n\nFix the bug. Only edit files in bots/{new_bot}/.",
            IMPL_TOOLS, IMPL_AUTO_ALLOW, impl_deny, budget - spent)
        spent += cost
        ok, output = oh.smoke_test(new_bot)

    state["next_version"] = num + 1
    state["total_cost"] = state.get("total_cost", 0.0) + spent
    commit_paths = [f"bots/{new_bot}", f"rejected/{new_bot}", "NOTES.md", STATE_FILE.name]
    summary_of_changes = changes.strip()[:1500] or "(no reply from the implementer)"

    if not ok:
        log(f"{new_bot} still crashes. Rejecting.")
        shutil.move(str(new_path), str(REJECTED_DIR / new_bot))
        append_notes(f"### {new_bot} — rejected (crashed)\n- Based on: {champion} (pipeline)\n"
                     f"- Changes: {summary_of_changes}\n- Status: rejected, moved to rejected/{new_bot}.")
        save_state(state)
        git_commit(f"{new_bot} rejected (crash)", commit_paths)
        return spent

    opponents = build_pool(state)
    tag = f"eval_{new_bot}"
    summary = oh.run_matches(new_bot, opponents, tag)
    wr = oh.win_rate_vs(summary, champion)
    per_opp = ", ".join(f"{o} {fmt(oh.win_rate_vs(summary, o))}" for o in opponents)
    overall = fmt(summary["overall"]["win_rate"]) if summary else "unknown"
    log(f"{new_bot} vs champion {champion}: {fmt(wr)} | {per_opp} | overall {overall}")

    record = (f"- Based on: {champion} (pipeline: researcher, designer, implementer)\n"
              f"- Changes: {summary_of_changes}\n"
              f"- Evaluation (results/{tag}): {per_opp}; overall {overall}")
    if wr is not None and wr >= PROMOTE_THRESHOLD:
        state["champion"] = new_bot
        state["history"].append(new_bot)
        state["last_results"] = [tag]
        append_notes(f"### {new_bot} — promoted ({fmt(wr)} vs {champion})\n{record}\n"
                     f"- Status: promoted, new champion.")
        set_notes_champion(new_bot)
        save_state(state)
        git_commit(f"{new_bot} promoted ({fmt(wr)} vs {champion})", commit_paths)
        log(f"PROMOTED {new_bot}.")
    else:
        shutil.move(str(new_path), str(REJECTED_DIR / new_bot))
        append_notes(f"### {new_bot} — rejected ({fmt(wr)} vs {champion})\n{record}\n"
                     f"- Status: rejected, moved to rejected/{new_bot}. "
                     f"Lesson: these changes did not beat {champion}.")
        save_state(state)
        git_commit(f"{new_bot} rejected ({fmt(wr)} vs {champion})", commit_paths)
        log(f"REJECTED {new_bot}. Champion stays {champion}.")
    return spent


async def main() -> None:
    if not oh.in_container() and "--allow-host" not in sys.argv:
        sys.exit("Not running inside the container. Pass --allow-host if you really mean "
                 "to run on the host.")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY is not set.")
    REJECTED_DIR.mkdir(exist_ok=True)
    state = load_state()
    log(f"champion {state['champion']} | history {state['history']} | model {MODEL} | "
        f"{ROUNDS} rounds, cap ${MAX_RUN_COST_USD:.0f}")
    spent = 0.0
    for r in range(1, ROUNDS + 1):
        if spent >= MAX_RUN_COST_USD:
            log(f"Cost limit reached (${spent:.2f}). Stopping.")
            break
        log(f"########## Round {r}/{ROUNDS} ##########")
        spent += await build_version(state, MAX_RUN_COST_USD - spent)
        archive_oldest(state)
        log(f"API cost this run so far: ${spent:.2f}")
    log(f"Done. Champion {state['champion']}. Cost this run: ${spent:.2f}.")


if __name__ == "__main__":
    asyncio.run(main())
