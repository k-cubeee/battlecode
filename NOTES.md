# Bot version notes

**Current champion: v3**

Baseline: v1. Chronological log below: version entries and analyses are appended
at the end. Promotion gate: >= 55% head-to-head vs the current champion over a full
run_matches.py evaluation (every map, both sides). Rejected versions move to rejected/.

### v1 — baseline
- SDK starter bot with a modified draft.py.

### v2 — promoted
- Evaluation (results/test1): 6-0 vs v1 on corners, lanes and rows, both sides.
  Won every game by reaching 1000 gems (average round 442). 0 crashes.
- Status: promoted (superseded by v3).

### v3 — promoted (83% vs v2)
- Adds ball.py; larger bot.py/tables.py. Change details were not recorded.
- Evaluation (results/v3-eval, 9 maps x both sides): 15-3 vs v2 (83%), 18-0 vs v1.
  Losses to v2: elkring (as Team A, round 645) and expanse (both sides, rounds 386/421).
  0 crashes.
- Status: promoted, new champion.
