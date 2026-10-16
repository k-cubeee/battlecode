# Cambridge Battlecode bot development

## Project
- Game rules and API docs are the .md files in the root folder (GameRules.md,
  BotAPIPython.md). Read them before writing bot code. Never guess the API; check the docs.
- Bots live in `bots/vN/src/` (Python). `v1` is the SDK starter bot with a tweaked
  draft: it is the baseline opponent. Higher numbers are our successive versions.
- The current champion (best evaluated version) is recorded at the top of NOTES.md.
- Run a match: `cambc run <bot-a> <bot-b> [--map NAME]` (e.g. `cambc run v3 v1 --map corners`)
- Evaluate a version: `python run_matches.py <candidate> <opponent>... --tag <tag>`
  plays every map in maps/ from both sides and writes `results/<tag>/summary.json`.
  Matches are deterministic, so map x side is the only variety; there are no seeds.

## Workflow
- Each improved version is a new copy: copy the champion to the next free `bots/vN/`
  (numbers are never reused; check `rejected/` too).
- Never edit an older version once it's been evaluated.
- NOTES.md records every version: what changed, win rate, promoted/rejected.
  Read it before proposing new ideas so failed ideas aren't repeated.
- Promote a version only if it wins >= 55% head-to-head against the current champion
  over a full run_matches.py evaluation (and doesn't regress against older versions).
  Rejected versions are moved to `rejected/vN/`, so `bots/` holds only v1 and promoted versions.
- `orchestrator.py` automates the whole loop with the Claude Agent SDK (needs ANTHROPIC_API_KEY).

## Rules for changes
- Make focused, testable changes, not full rewrites.
- After editing a bot, run one match to confirm it doesn't crash.
- Respect any time/compute limits described in the docs (Python: 25x the
  C++ fuel limit per turn; 10x on the first draft turn, 2x on the first play turn).
