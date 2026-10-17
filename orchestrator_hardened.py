"""
orchestrator_hardened.py - hardened version of orchestrator.py (Cambridge Battlecode).

Same loop as the original:
  analyse champion -> strategist builds bots/vN -> smoke test
  -> evaluate vs pool -> promote or reject -> log -> repeat

What is different (search for "HARDENING" to see every change):
  1. Refuses to run outside the container unless you pass --allow-host.
  2. Analyst has no Bash. Strategist's Bash is limited to a small allow-list.
  3. Deny rules block secrets paths, /mnt (Windows drives), network tools,
     env dumps and git push.
  4. Subprocesses we start (run_matches.py, cambc) do NOT get ANTHROPIC_API_KEY,
     so agent-written bot code can't read it.
  5. git commits only add bots/, rejected/ and NOTES.md, not everything.

Limits you should know about:
  - Deny and allow patterns are a seatbelt, not a wall. The container is the wall.
  - The agents' own `claude` process still needs the API key, so use a
    dedicated key with a spend limit set in the Anthropic Console.
  - Tool-rule syntax can differ between SDK versions. Run once with
    ITERATIONS = 1 and watch the output for "permission denied" messages.

Interactive CLI:
  By default the script also opens an interactive `claude` session in a second
  terminal, in this project folder, with the same deny rules. Pass --no-cli to
  skip it. It opens in a Windows Terminal tab when run from WSL, in a tmux split
  when run inside tmux, and otherwise just prints the command for you to run.
  That session is separate from the orchestrator's agents and asks before it
  acts. Don't edit bots/ or NOTES.md from it while the orchestrator is running.

Run on the host:  python orchestrator_hardened.py --allow-host
Run in Docker:    ./run_contained.sh   (the CLI is skipped inside the container)
Resume: just run it again (progress is saved in orchestrator_state.json)
"""

import asyncio
import json
import os
import re
import shlex
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

from run_matches import parse_output, read_stats

# ============================ CONFIG ============================
ROOT = Path(__file__).resolve().parent
BOT_DIR = ROOT / "bots"
BASELINE = "v1"

ITERATIONS = 5
PROMOTE_THRESHOLD = 0.55
POOL_SIZE = 3
MATCH_JOBS = 2  # each match peaks ~1.75 GB and ~2.7 cores; WSL has 8 GB / 4 cores

ANALYST_MODEL = "claude-sonnet-5-5"
STRATEGIST_MODEL = "claude-sonnet-5-5"
MAX_TURNS_ANALYST = 60
MAX_TURNS_STRATEGIST = 100
MAX_TOTAL_COST_USD = 50.00

MATCH_BATCH_TIMEOUT_S = 60 * 60
SMOKE_TEST_TIMEOUT_S = 10 * 60

RESULTS_DIR = ROOT / "results"
REJECTED_DIR = ROOT / "rejected"
NOTES = ROOT / "NOTES.md"
STATE_FILE = ROOT / "orchestrator_state.json"
CHAMPION_RE = re.compile(r"^\*\*Current champion: (v\d+)\*\*$", re.M)

# ---- HARDENING: tool permissions ----
# Analyst: read-only plus Edit (it must append to NOTES.md). No Bash.
ANALYST_TOOLS = ["Read", "Grep", "Glob", "Edit"]
ANALYST_DENY_EXTRA = ["Edit(bots/**)", "Write(bots/**)"]   # never touch bot code

# Strategist: file tools plus a short list of shell commands.
STRATEGIST_TOOLS = ["Read", "Write", "Edit", "Grep", "Glob", "Bash"]
STRATEGIST_AUTO_ALLOW = [
    "Read", "Write", "Edit", "Grep", "Glob",
    "Bash(cambc:*)",      # smoke tests
    "Bash(ls:*)", "Bash(head:*)", "Bash(tail:*)", "Bash(wc:*)",
]
# Any Bash command not matched above is denied (the script runs headless,
# so there is nobody to approve it). Add commands here if the strategist needs them.

# Denied for every agent, whatever else is allowed.
DENY_ALWAYS = [
    # secrets and personal files
    "Read(~/.ssh/**)", "Read(~/.aws/**)", "Read(~/.config/**)", "Read(~/.gnupg/**)",
    "Read(**/.env)", "Read(**/.env.*)", "Read(/etc/**)", "Read(/proc/**)",
    # Windows drives mounted into WSL
    "Read(/mnt/**)", "Edit(/mnt/**)", "Write(/mnt/**)",
    # network and exfiltration tools
    "Bash(curl:*)", "Bash(wget:*)", "Bash(ssh:*)", "Bash(scp:*)", "Bash(nc:*)",
    "Bash(ncat:*)", "Bash(socat:*)", "Bash(ftp:*)", "WebFetch", "WebSearch",
    # environment dumps (would reveal the API key)
    "Bash(env:*)", "Bash(printenv:*)", "Bash(export:*)", "Bash(set:*)",
    # destructive or privileged
    "Bash(sudo:*)", "Bash(su:*)", "Bash(rm -rf:*)", "Bash(git push:*)",
]
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


def clean_env() -> dict:
    """HARDENING: environment for subprocesses, without the API key.

    run_matches.py and cambc execute bot code that an agent wrote, so that code
    must not be able to read the key from its environment.
    """
    env = dict(os.environ)
    for key in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN"):
        env.pop(key, None)
    return env


def in_container() -> bool:
    return os.environ.get("ORCH_IN_CONTAINER") == "1" or Path("/.dockerenv").exists()


CLI_PRIMER = ("The orchestrator (orchestrator_hardened.py) is running in this folder and its "
              "agents are editing bots/ and NOTES.md. Do not edit those, or run matches, "
              "unless I ask. Ask before making any change.")


def open_cli() -> None:
    """Open an interactive Claude Code session in a second terminal.

    It is a normal session: it asks before acting, and it gets the same deny rules
    as the orchestrator's agents. It is separate from them, so it doesn't share
    their context. Failure to open it never stops the orchestrator.
    """
    if in_container():
        log("CLI: skipped (inside the container).")
        return
    claude_bin = shutil.which("claude")
    if not claude_bin:
        log("CLI: `claude` not found on PATH, so no CLI window was opened.")
        return

    # Prompt first, then the variadic flag, so the flag doesn't swallow the prompt.
    cmd = shlex.join([claude_bin, CLI_PRIMER, "--disallowedTools", *DENY_ALWAYS])
    # A small launcher script avoids fragile quoting when handing the command to
    # another terminal. It contains no secrets. The terminal it opens does not
    # inherit ANTHROPIC_API_KEY, so the CLI uses your normal `claude` login.
    script = Path(tempfile.mkdtemp(prefix="claude_cli_")) / "launch.sh"
    script.write_text(f"#!/usr/bin/env bash\ncd {shlex.quote(str(ROOT))} || exit 1\nexec {cmd}\n")
    script.chmod(0o700)

    try:
        distro = os.environ.get("WSL_DISTRO_NAME")
        if distro and shutil.which("wt.exe"):
            subprocess.Popen(["wt.exe", "-w", "0", "new-tab", "--title", "Claude CLI",
                              "wsl.exe", "-d", distro, "--", "bash", str(script)])
            log("CLI: opened in a new Windows Terminal tab.")
        elif os.environ.get("TMUX") and shutil.which("tmux"):
            subprocess.Popen(["tmux", "split-window", "-h", f"bash {shlex.quote(str(script))}"])
            log("CLI: opened in a tmux split.")
        else:
            log(f"CLI: couldn't open a terminal automatically. Run this in another terminal: "
                f"bash {script}")
            return
    except OSError as exc:
        log(f"CLI: failed to open ({exc}). Run this in another terminal: bash {script}")
        return
    log("CLI: it shares this folder with the agents. Don't edit bots/ or NOTES.md from it "
        "while the orchestrator runs.")


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
    history = sorted((p.name for p in BOT_DIR.iterdir()
                      if re.fullmatch(r"v\d+", p.name) and version_num(p.name) <= version_num(champion)),
                     key=version_num)
    return {
        "champion": champion,
        "history": history,
        "next_version": max(existing_versions()) + 1,
        "total_cost": 0.0,
        "last_results": [],
    }


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


def append_notes(text: str) -> None:
    if not NOTES.exists():
        NOTES.write_text(f"# Bot version notes\n\n**Current champion: {BASELINE}**\n\n", encoding="utf-8")
    with open(NOTES, "a", encoding="utf-8") as f:
        f.write(f"\n{text.strip()}\n")


def git_commit(message: str) -> None:
    """HARDENING: stage only the paths this script manages, never `git add -A`."""
    if not (ROOT / ".git").exists():
        return
    paths = [p for p in ("bots", "rejected", "NOTES.md") if (ROOT / p).exists()]
    if not paths:
        return
    subprocess.run(["git", "add", "--", *paths], cwd=ROOT, capture_output=True)
    subprocess.run(["git", "commit", "-m", message], cwd=ROOT, capture_output=True)


def build_pool(state: dict) -> list[str]:
    recent = list(reversed(state["history"]))[:POOL_SIZE]
    return list(dict.fromkeys(recent + [BASELINE]))


def fmt(wr: float | None) -> str:
    return f"{wr:.0%}" if wr is not None else "unknown"


# ----------------------------- matches -----------------------------
def run_matches(bot: str, opponents: list[str], tag: str) -> dict | None:
    cmd = [sys.executable, "run_matches.py", bot, *opponents, "--tag", tag,
           "-j", str(MATCH_JOBS), "--resume"]
    log("Running matches: " + " ".join(cmd[1:]))
    try:
        subprocess.run(cmd, cwd=ROOT, timeout=MATCH_BATCH_TIMEOUT_S, env=clean_env())
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
    cambc = shutil.which("cambc") or "cambc"
    with tempfile.TemporaryDirectory() as tmp:
        stats_path = Path(tmp) / "stats.json"
        try:
            proc = subprocess.run(
                [cambc, "run", bot, BASELINE, "-o", tmp, "--statistics", str(stats_path), "--json"],
                cwd=ROOT, capture_output=True, text=True,
                timeout=SMOKE_TEST_TIMEOUT_S, env=clean_env(),
            )
        except subprocess.TimeoutExpired:
            return False, "Smoke test timed out."
        output = (proc.stdout or "") + (proc.stderr or "")
        if not stats_path.exists():
            return False, output
        stats = read_stats(stats_path)
    faults = (stats[2] if stats else None) or {}
    # cambc >= 2.2: {"teamA": n, "teamB": n}; 2.1: [a, b]. The bot under test is team A.
    faults_a = faults.get("teamA", 0) if isinstance(faults, dict) else (faults[0] if faults else 0)
    crashes = parse_output(output)["teams"].get("A", {}).get("crashes", 0)
    return (crashes == 0 and faults_a == 0), output


# ----------------------------- agents -----------------------------
async def run_agent(label, prompt, system_prompt, tools, auto_allow, extra_deny,
                    model, max_turns, budget_usd):
    options = ClaudeAgentOptions(
        system_prompt=system_prompt,
        tools=tools,                                  # tools that exist for this agent
        allowed_tools=auto_allow,                     # tools/commands that run without asking
        disallowed_tools=DENY_ALWAYS + extra_deny,    # HARDENING: always blocked
        cwd=str(ROOT),
        permission_mode="acceptEdits",                # anything not allowed is denied (headless)
        max_turns=max_turns,
        max_budget_usd=budget_usd,
        model=model,
        setting_sources=["project"],
    )
    final_text, cost, said = "", 0.0, []
    try:
        async for msg in query(prompt=prompt, options=options):
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock) and block.text.strip():
                        said.append(block.text.strip())
                        print(f"   [{label}] {block.text.strip()[:200]}", flush=True)
            elif isinstance(msg, ResultMessage):
                final_text = msg.result or ""
                cost = msg.total_cost_usd or 0.0
    except Exception as e:  # e.g. ResultError for max turns or budget; don't end the whole run
        reason = getattr(e, "subtype", None) or type(e).__name__
        log(f"{label} stopped early ({reason}): {str(e)[:200]}")
        if not final_text:
            # The result message of a failed run has no text: pass on what the agent said so far.
            final_text = "(The agent stopped early; its notes so far:)\n" + "\n".join(said)[-6000:]
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
- Shell access is limited to cambc, ls, head, tail and wc. Use Read/Grep/Glob for everything else.
- Do NOT edit NOTES.md; the orchestrator records the version entry and result.

Finish with a short summary: what you changed (file:function) and why it should win."""


def strategist_deny(new_bot: str) -> list[str]:
    """HARDENING: the strategist may only write inside its own bot folder."""
    return ["Edit(NOTES.md)", "Write(NOTES.md)", "Edit(orchestrator*.py)", "Write(orchestrator*.py)",
            "Edit(run_matches.py)", "Write(run_matches.py)", "Edit(.claude/**)", "Write(.claude/**)"]


# ----------------------------- main loop -----------------------------
async def main() -> None:
    if not in_container() and "--allow-host" not in sys.argv:
        sys.exit("Not running inside the container. Use ./run_contained.sh, "
                 "or pass --allow-host if you really mean to run on the host.")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY is not set.")
    if not (ROOT / "run_matches.py").exists():
        sys.exit("run_matches.py not found in the project root.")

    if "--no-cli" not in sys.argv:
        open_cli()

    state = load_state()
    analyst_prompt = load_agent_prompt("analyst", DEFAULT_ANALYST_PROMPT)
    strategist_prompt = load_agent_prompt("strategist", DEFAULT_STRATEGIST_PROMPT)
    REJECTED_DIR.mkdir(exist_ok=True)
    log(f"Champion: {state['champion']} | history: {state['history']}")

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

        # 1. Analyse
        analysis, cost = await run_agent(
            "analyst", analyst_task(champion, state["last_results"]),
            analyst_prompt, ANALYST_TOOLS, ANALYST_TOOLS, ANALYST_DENY_EXTRA,
            ANALYST_MODEL, MAX_TURNS_ANALYST, remaining,
        )
        state["total_cost"] += cost
        save_state(state)

        # 2. Build the new version from a copy of the champion
        if new_path.exists():
            shutil.rmtree(new_path)
        shutil.copytree(BOT_DIR / champion, new_path,
                        ignore=shutil.ignore_patterns(".cambc", "build", "target", "__pycache__"))

        changes, cost = await run_agent(
            "strategist", strategist_task(new_bot, champion, analysis),
            strategist_prompt, STRATEGIST_TOOLS, STRATEGIST_AUTO_ALLOW,
            strategist_deny(new_bot),
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
                strategist_prompt, STRATEGIST_TOOLS, STRATEGIST_AUTO_ALLOW,
                strategist_deny(new_bot),
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

        # 4. Evaluate
        opponents = build_pool(state)
        tag = f"eval_{new_bot}"
        summary = run_matches(new_bot, opponents, tag)
        wr = win_rate_vs(summary, champion)
        per_opp = ", ".join(f"{o} {fmt(win_rate_vs(summary, o))}" for o in opponents)
        overall = fmt(summary["overall"]["win_rate"]) if summary else "unknown"
        log(f"{new_bot} vs champion {champion}: {fmt(wr)} | {per_opp} | overall {overall}")

        # 5. Promote or reject
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
