# Cambridge Battlecode bot development

## Project
- Game rules and API docs are the .md files in the root folder (GameRules.md,
  BotAPIPython.md). Read them before writing bot code. Never guess the API; check the docs.
- Bots live in `bots/vN/src/` (Python). `v1` is the SDK starter bot with a tweaked
  draft: it is the baseline opponent. Higher numbers are our successive versions.
- `bots/starter-python` and `bots/starter-cpp` are the current SDK starter bots from `cambc init`
  (cambc 3.0.4). They're references, not part of the version line, and the orchestrators ignore them.
- The engine is cambc 3.0.4 (`cambc.toml`). GameRules.md and BotAPIPython.md were exported for 2.2.3:
  read the version notice at the top of each, and treat `sdk/python/` as the source of truth for the API.
- The current champion (best evaluated version) is recorded at the top of NOTES.md.
- Run a match: `cambc run <bot-a> <bot-b> [--map NAME]` (e.g. `cambc run v3 v1 --map corners`)
- Evaluate a version: `python run_matches.py <candidate> <opponent>... --tag <tag>`
  plays every map in maps/ from both sides and writes `results/<tag>/summary.json`.
  Matches are deterministic, so map x side is the only variety; there are no seeds.

## Workflow
- Each improved version is a new copy: copy the champion to the next free `bots/vN/`
  (numbers are never reused; check `rejected/` and `archive/` too).
- Never edit an older version once it's been evaluated.
- NOTES.md records every version: what changed, win rate, promoted/rejected.
  Read it before proposing new ideas so failed ideas aren't repeated.
- Promote a version only if it wins >= 55% head-to-head against the current champion
  over a full run_matches.py evaluation (and doesn't regress against older versions).
  Rejected versions are moved to `rejected/vN/`, so `bots/` holds only v1 and promoted versions.
  After each new version the orchestrator moves the team's oldest bot to `archive/`
  (never v1, the champion or a bot in the evaluation pool).
- `orchestrator_hardened.py` automates the analyst/strategist loop with the Claude Agent SDK
  (needs ANTHROPIC_API_KEY). It also provides the shared agent runner, match runner and smoke test.

## Specialist pipeline
- `orchestrator_pipeline.py` develops the same line (`bots/vN`, `NOTES.md`,
  `orchestrator_state.json`) with three agents per version, all on Opus:
  `researcher` (studies evaluations and the rejected attempts against the champion),
  `designer` (writes a 2-4 part change plan meant to flip whole maps) and
  `implementer` (builds and tests it in `bots/vN`). Each appends to NOTES.md; the
  orchestrator evaluates, promotes or rejects, and archives the oldest bot.
- Run it with `python orchestrator_pipeline.py --allow-host`. Don't run two orchestrators at once,
  and don't run matches by hand while one is running.
- Team B (`bN` bots, its arena and referee) was retired on 2026-10-17; everything is in
  `archive/team_b/`.

## Rules for changes
- Make focused, testable changes, not full rewrites.
- After editing a bot, run one match to confirm it doesn't crash.
- Respect any time/compute limits described in the docs (Python: 25x the
  C++ fuel limit per turn; 10x on the first draft turn, 2x on the first play turn).
