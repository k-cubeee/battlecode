"""
orchestrator.py - automated self-improvement loop for Cambridge Battlecode.

Loop:  analyse champion -> strategist builds bots/vN -> smoke test
       -> evaluate vs pool -> promote or reject -> log -> repeat

Requirements:
  pip install claude-agent-sdk
  ANTHROPIC_API_KEY set in this terminal
  run_matches.py working as:
      python run_matches.py <bot> <opponent1> <opponent2> ... --tag <tag>
  which writes results/<tag>/summary.json with "overall" and "by_opponent"
  win rates (0.0 - 1.0)

Conventions (see CLAUDE.md):
  - Bots live in bots/vN/src/. v1 is the baseline (starter bot).
  - bots/ holds only the baseline and promoted versions; rejected versions
    are moved to rejected/vN.
  - The champion is the "**Current champion: vN**" line at the top of NOTES.md.

Run:     python orchestrator.py
Resume:  just run it again (progress is saved in orchestrator_state.json)
Reset:   delete orchestrator_state.json (the champion is re-read from NOTES.md)
"""

import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query,
)

from run_matches import parse_output

# ============================ CONFIG ============================
ROOT = Path(__file__).resolve().parent
BOT_DIR = ROOT / "bots"         # folder that contains v1/, v2/, ...
BASELINE = "v1"                 # starter bot, always included as an opponent

ITERATIONS = 5                  # improvement cycles per run
PROMOTE_THRESHOLD = 0.55        # head-to-head win rate vs the champion needed to promote
POOL_SIZE = 3                   # number of recent champions to test against
MATCH_JOBS = 5                  # parallel matches inside run_matches.py

ANALYST_MODEL = "claude-sonnet-5-5"
STRATEGIST_MODEL = "claude-sonnet-5-5"
MAX_TURNS_ANALYST = 30
MAX_TURNS_STRATEGIST = 60
MAX_TOTAL_COST_USD = 20.00      # hard stop for API spending

MATCH_BATCH_TIMEOUT_S = 60 * 60 # max time for one run_matches.py call
SMOKE_TEST_TIMEOUT_S = 10 * 60

RESULTS_DIR = ROOT / "results"
REJECTED_DIR = ROOT / "rejected"
NOTES = ROOT / "NOTES.md"
STATE_FILE = ROOT / "orchestrator_state.json"
CHAMPION_RE = re.compile(r"^\*\*Current champion: (v\d+)\*\*$", re.M)
# ================================================================

DEFAULT_ANALYST_PROMPT = """You are a Battlecode strategy analyst. You read match
logs, results, and bot source code, and identify concrete, exploitable weaknesses.
Always cite evidence. Check the game docs in the project root for the real rules.
You never edit bot code."""

DEFAULT_STRATEGIST_PROMPT = """You are an expert Battlecode bot developer. You
implement focused, testable strategy improvements. Always check the game docs in
the project root for the correct API. Read NOTES.md so you don't repeat ideas that
already failed. Never edit any bot folder except the one you are assigned."""


# ----------------------------- helpers -----------------------------
def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def load_agent_prompt(name: str, default: str) -> str:
    """Use .claude/agents/<name>.md as the system prompt (without frontmatter)."""
    path = ROOT / ".claude" / "agents" / f"{name}.md"
    if path.exists():
        text = path.read_text(encoding="utf-8")
        text = re.sub(r"^---.*?---\s*", "", text, flags=re.DOTALL).strip()
        if text:
            return text
    return default


def version_num(bot: str) -> int:
    return int(bot[1:])


def existing_versions() -> list[int]:
    """Version numbers used so far, including rejected ones (never reuse a number)."""
    nums = []
    for d in (BOT_DIR, REJECTED_DIR):
        if d.exists():
            nums += [version_num(p.name) for p in d.iterdir() if re.fullmatch(r"v\d+", p.name)]
    return nums


def notes_champion() -> str:
    m = CHAMPION_RE.search(NOTES.read_text(encoding="utf-8")) if NOTES.exists() else None
    return m.group(1) if m else BASELINE


def set_notes_champion(bot: str) -> None:
    text = NOTES.read_text(encoding="utf-8")
    NOTES.write_text(CHAMPION_RE.sub(f"**Current champion: {bot}**", text, count=1), encoding="utf-8")


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    champion = notes_champion()
    # bots/ only holds the baseline and promoted versions, so they form the history.
    history = sorted((p.name for p in BOT_DIR.iterdir()
                      if re.fullmatch(r"v\d+", p.name) and version_num(p.name) <= version_num(champion)),
                     key=version_num)
    return {
        "champion": champion,
        "history": history,      # all promoted champions, oldest first
        "next_version": max(existing_versions()) + 1,
        "total_cost": 0.0,
        "last_results": [],      # result tags the analyst should read
    }


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


def append_notes(text: str) -> None:
    if not NOTES.exists():
        NOTES.write_text(f"# Bot version notes\n\n**Current champion: {BASELINE}**\n\n", encoding="utf-8")
    with open(NOTES, "a", encoding="utf-8") as f:
        f.write(f"\n{text.strip()}\n")


def git_commit(message: str) -> None:
    if not (ROOT / ".git").exists():
        return
    subprocess.run(["git", "add", "-A"], cwd=ROOT, capture_output=True)
    subprocess.run(["git", "commit", "-m", message], cwd=ROOT, capture_output=True)


def build_pool(state: dict) -> list[str]:
    """Champion + recent previous champions + baseline, without duplicates."""
    recent = list(reversed(state["history"]))[:POOL_SIZE]
    return list(dict.fromkeys(recent + [BASELINE]))


def fmt(wr: float | None) -> str:
    return f"{wr:.0%}" if wr is not None else "unknown"


# ----------------------------- matches -----------------------------
def run_matches(bot: str, opponents: list[str], tag: str) -> dict | None:
    """Run the batch and return summary.json, or None if it failed."""
    cmd = [sys.executable, "run_matches.py", bot, *opponents, "--tag", tag,
           "-j", str(MATCH_JOBS), "--force"]
    log("Running matches: " + " ".join(cmd[1:]))
    try:
        subprocess.run(cmd, cwd=ROOT, timeout=MATCH_BATCH_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        log("run_matches.py timed out.")
        return None

    summary = RESULTS_DIR / tag / "summary.json"
    if not summary.exists():
        log(f"No summary found at {summary}. Check run_matches.py.")
        return None
    return json.loads(summary.read_text())


def win_rate_vs(summary: dict | None, opponent: str) -> float | None:
    if not summary:
        return None
    return summary["by_opponent"].get(opponent, {}).get("win_rate")


def smoke_test(bot: str) -> tuple[bool, str]:
    """One match vs the baseline. Fails on a cambc error or any bot crash/fault."""
    cambc = shutil.which("cambc") or "cambc"
    with tempfile.TemporaryDirectory() as tmp:
        stats_path = Path(tmp) / "stats.json"
        try:
            proc = subprocess.run(
                [cambc, "run", bot, BASELINE, "-o", tmp, "--statistics", str(stats_path)],
                cwd=ROOT, capture_output=True, text=True, timeout=SMOKE_TEST_TIMEOUT_S,
            )
        except subprocess.TimeoutExpired:
            return False, "Smoke test timed out."
        output = (proc.stdout or "") + (proc.stderr or "")
        if not stats_path.exists():
            return False, output                      # build error, missing bot, ...
        faults = json.loads(stats_path.read_text()).get("botFaults", [0, 0])
    crashes = parse_output(output)["teams"].get("A", {}).get("crashes", 0)
    return (crashes == 0 and faults[0] == 0), output


# ----------------------------- agents -----------------------------
async def run_agent(label, prompt, system_prompt, tools, model, max_turns, budget_usd):
    options = ClaudeAgentOptions(
        system_prompt=system_prompt,
        tools=tools,                   # tools the agent can use at all
        allowed_tools=tools,           # ...and they run without permission prompts
        cwd=str(ROOT),
        permission_mode="acceptEdits",
        max_turns=max_turns,
        max_budget_usd=budget_usd,
        model=model,
        setting_sources=["project"],   # loads CLAUDE.md from the project
    )
    final_text, cost = "", 0.0
    async for msg in query(prompt=prompt, options=options):
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock) and block.text.strip():
                    print(f"   [{label}] {block.text.strip()[:200]}", flush=True)
        elif isinstance(msg, ResultMessage):
            final_text = msg.result or ""
            cost = msg.total_cost_usd or 0.0
    log(f"{label} finished (cost ${cost:.2f})")
    return final_text, cost


def analyst_task(champion: str, result_tags: list[str]) -> str:
    dirs = "\n".join(f"- results/{t}/" for t in result_tags) or "- (none yet)"
    return f"""The current champion bot is `{champion}` (source: bots/{champion}/src/).

Recent match results (each folder has summary.json, per-match .txt logs and
.stats.json exports):
{dirs}

Previous attempts and lessons are in NOTES.md. Game rules and docs are the .md
files in the project root.

Find the top 3 concrete weaknesses of `{champion}` with evidence, following your
instructions, and append your analysis section to the end of NOTES.md. Do not edit
anything under bots/. Finish by repeating the three findings in your reply."""


def strategist_task(new_bot: str, champion: str, analysis: str) -> str:
    return f"""Create the next bot version `{new_bot}`.

The orchestrator has ALREADY done steps 1-2 of your instructions: bots/{new_bot}/ exists
and is an exact copy of the champion `{champion}`. Do not create any other bot folder.

Analysis of the champion's weaknesses (also appended to NOTES.md):
{analysis}

Rules:
- Only edit files inside bots/{new_bot}/.
- Check the game docs for correct API usage. Never guess the API.
- Implement the most promising change(s), keeping them focused.
- Smoke test with: cambc run {new_bot} {champion}   and fix any crash.
- Do NOT edit NOTES.md; the orchestrator records the version entry and result.

Finish with a short summary: what you changed (file:function) and why it should win."""


# ----------------------------- main loop -----------------------------
async def main() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY is not set in this terminal.")
    if not (ROOT / "run_matches.py").exists():
        sys.exit("run_matches.py not found in the project root.")

    state = load_state()
    analyst_prompt = load_agent_prompt("analyst", DEFAULT_ANALYST_PROMPT)
    strategist_prompt = load_agent_prompt("strategist", DEFAULT_STRATEGIST_PROMPT)
    REJECTED_DIR.mkdir(exist_ok=True)
    log(f"Champion: {state['champion']} | history: {state['history']}")

    # Initial benchmark so the analyst has data to study
    if not state["last_results"]:
        champ = state["champion"]
        tag = f"bench_{champ}"
        opponents = [b for b in build_pool(state) if b != champ] or [BASELINE]
        summary = run_matches(champ, opponents, tag)
        log(f"Baseline: {champ} overall win rate = "
            f"{fmt(summary['overall']['win_rate'] if summary else None)}")
        state["last_results"] = [tag]
        save_state(state)

    for _ in range(ITERATIONS):
        remaining = MAX_TOTAL_COST_USD - state["total_cost"]
        if remaining <= 0:
            log(f"Cost limit reached (${state['total_cost']:.2f}). Stopping.")
            break

        champion = state["champion"]
        new_bot = f"v{state['next_version']}"
        new_path = BOT_DIR / new_bot
        log(f"===== Building {new_bot} (champion: {champion}) =====")

        # 1. Analyse (the analyst appends its findings to NOTES.md itself)
        analysis, cost = await run_agent(
            "analyst", analyst_task(champion, state["last_results"]),
            analyst_prompt, ["Read", "Grep", "Glob", "Bash", "Edit"],
            ANALYST_MODEL, MAX_TURNS_ANALYST, remaining,
        )
        state["total_cost"] += cost
        save_state(state)

        # 2. Build the new version from a copy of the champion's source
        if new_path.exists():                 # leftover from an interrupted run
            shutil.rmtree(new_path)
        shutil.copytree(BOT_DIR / champion, new_path,
                        ignore=shutil.ignore_patterns(".cambc", "build", "target", "__pycache__"))

        changes, cost = await run_agent(
            "strategist", strategist_task(new_bot, champion, analysis),
            strategist_prompt, ["Read", "Write", "Edit", "Grep", "Glob", "Bash"],
            STRATEGIST_MODEL, MAX_TURNS_STRATEGIST,
            MAX_TOTAL_COST_USD - state["total_cost"],
        )
        state["total_cost"] += cost

        # 3. Smoke test, with one fix attempt
        ok, output = smoke_test(new_bot)
        if not ok:
            log("Smoke test failed. Asking the strategist to fix it.")
            _, cost = await run_agent(
                "strategist-fix",
                f"The bot `{new_bot}` crashed or failed to run in "
                f"`cambc run {new_bot} {BASELINE}`. Output (tail):\n\n"
                f"{output[-3000:]}\n\nBot stdout/stderr for the latest match is in "
                f"the newest .cambc/match-*/team-a.stdout.\n"
                f"Fix the bug. Only edit files in bots/{new_bot}/. Do not edit NOTES.md.",
                strategist_prompt, ["Read", "Write", "Edit", "Grep", "Glob", "Bash"],
                STRATEGIST_MODEL, MAX_TURNS_STRATEGIST,
                MAX_TOTAL_COST_USD - state["total_cost"],
            )
            state["total_cost"] += cost
            ok, output = smoke_test(new_bot)

        state["next_version"] += 1

        if not ok:
            log(f"{new_bot} still crashes. Rejecting.")
            shutil.move(str(new_path), str(REJECTED_DIR / new_bot))
            append_notes(f"### {new_bot} — rejected (crashed)\n- Based on: {champion}\n"
                         f"- Changes: {changes}\n- Status: rejected, moved to rejected/{new_bot}.")
            save_state(state)
            git_commit(f"{new_bot} rejected (crash)")
            continue

        # 4. Evaluate against champion, recent champions, and baseline
        opponents = build_pool(state)
        tag = f"eval_{new_bot}"
        summary = run_matches(new_bot, opponents, tag)
        wr = win_rate_vs(summary, champion)
        per_opp = ", ".join(f"{o} {fmt(win_rate_vs(summary, o))}" for o in opponents)
        overall = fmt(summary["overall"]["win_rate"]) if summary else "unknown"
        log(f"{new_bot} vs champion {champion}: {fmt(wr)} | {per_opp} | overall {overall}")

        # 5. Promote or reject (gate: head-to-head vs the champion)
        record = (f"- Based on: {champion}\n- Changes: {changes}\n"
                  f"- Evaluation (results/{tag}): {per_opp}; overall {overall}")
        if wr is not None and wr >= PROMOTE_THRESHOLD:
            state["champion"] = new_bot
            state["history"].append(new_bot)
            state["last_results"] = [tag]
            append_notes(f"### {new_bot} — promoted ({fmt(wr)} vs {champion})\n{record}\n"
                         f"- Status: promoted, new champion.")
            set_notes_champion(new_bot)
            save_state(state)
            git_commit(f"{new_bot} promoted ({fmt(wr)} vs {champion})")
            log(f"PROMOTED: {new_bot} is the new champion.")
        else:
            shutil.move(str(new_path), str(REJECTED_DIR / new_bot))
            state["last_results"] = (state["last_results"] + [tag])[-2:]
            append_notes(f"### {new_bot} — rejected ({fmt(wr)} vs {champion})\n{record}\n"
                         f"- Status: rejected, moved to rejected/{new_bot}. "
                         f"Lesson: these changes did not beat {champion}.")
            save_state(state)
            git_commit(f"{new_bot} rejected ({fmt(wr)} vs {champion})")
            log(f"REJECTED: {new_bot}. Champion stays {champion}.")

        log(f"Total API cost so far: ${state['total_cost']:.2f}")

    log(f"Done. Champion: {state['champion']} | "
        f"Total cost: ${state['total_cost']:.2f}")


if __name__ == "__main__":
    asyncio.run(main())
