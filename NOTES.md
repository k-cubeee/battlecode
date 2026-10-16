# Bot version notes

**Current champion: v4**

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

### Analysis of v3 — 2026-10-16 (results/v3-eval)
Record: 33-3 overall; 15-3 vs v2 (83%), 18-0 vs v1. Weakest maps/side: expanse (2-2; lost to v2 from both sides, r421 as A and r386 as B), elkring as Team A (lost to v2, r645). Slowest wins: collision (631-666), rows (561-651), elkring (498-524). Average winning round 499. 0 crashes, 0 bot faults.

1. **Fewer bodies than v2 in a no-contact farming race (expanse)**
   - Evidence: both expanse games vs v2 had 0 champion damage either way, so it was a pure farming race (results/v3-eval/v2/expanse__cand-{A,B}.stats.json). v3 drafts 3 bodies (Varg, Ryth, Marcella). v2 drafts 4 (Varg, Cassi & Issac, Ryth). v3's bodies farm better (monster damage per champion-round 24.2 vs 21.3 in A), but v2's extra body wins on total: monster damage 35,900 vs 30,599 (A) and 31,690 vs 26,709 (B); gems collected 1054 vs 988 by r421 (A) and 1010 vs 796 by r386 (B). On the 3-pick maps where the spawns meet (collision, packs), Cassi & Issac die often (Cassi/Issac D3-D6 per game) and v3 wins 4-0 there. The draft.py docstring's reason for dropping C&I ("costs more deaths") is right for those maps but not for expanse.
   - Cause in code: `bots/v3/src/draft.py:13-17` (PREFS) and `play()` (line 21): one fixed 3-pick list (Varg, Ryth, Marcella) for every 3-pick map, whatever the map layout.
   - Suggested fix: in `draft.play()`, on 3-pick maps use the map view the draft bot already has (GameRules "Shared draft memory") to compute the walking distance between the spawns. When the spawns are far apart (threshold just below expanse's value and above collision/packs; print the three values once to set it), draft Varg, Cassi & Issac, Ryth instead. Leave every other map unchanged. To test, re-run expanse, collision and packs vs v2.
   - Confidence: medium-high for expanse (2 of the 3 losses). The distance gate is an assumption: I did not measure the spawn distances from the binary map files.

2. **Gold is left unspent (slower farming, especially on big maps)**
   - Evidence: at game end v3 still holds 19% of all gold it earned vs v2 (10,301 of 52,921) and 26% vs v1. v2 holds 9% (4,442 of 51,092). Examples: monolith vs v1 2,264/2,254 gold unspent (Varg 1,140 of 1,600 earned); monolith B vs v2 1,682 (Ryth 788, Marcella 756); collision ~870-900 vs v1. On expanse B, Varg ended with 270 gold and 0 items all game, and Marcella with 90 gold and 0 items. v3 bought 25/20 shard items on expanse vs v2's 34/38. This is a snapshot at the end of the game, so how long the gold sat unspent is inferred.
   - Cause in code: `bots/v3/src/ball.py:488-494` (`need_home_ball`): with `r_gather = 0` and `SOLO = 1` every turn goes through `ball_decide`. That only sends a champion home to shop when gold >= 300 (GOLD_HOME, line 30), the spawn is <= 18 steps away and no enemy is visible. A rich champion farming far from home never shops. v2's `need_home` (bots/v2/src/bot.py:582-593) also goes home from anywhere at >= 400 gold when it has no task. v3 dropped that fallback in ball mode.
   - Suggested fix: in `need_home_ball`, add v2's fallback: `if self.gold >= 400 and self.task is None and not self.field_shop and not self.enemies: return True` (between tasks only, so no camp fight is abandoned). To test, check that average unspent gold drops and that winning rounds fall on monolith, collision and rows.
   - Confidence: medium. The stockpiling is clear in the data. How much it speeds up wins needs a run.

3. **Large gem bags lost to enemy kills decide close games (elkring A)**
   - Evidence: elkring as Team A vs v2 (results/v3-eval/v2/elkring__cand-A.stats.json). v3 lost only 2 champions all game but lost 144 carried gems with them: Ryth collected 180, tributed 72, carried 0, so 108 were lost in his one death; Varg lost 36. Both were killed by champions (v2 Ryth and Stellar 1 kill each), so v2 picked those gems up. The final score was 864 vs 1008. With those 144 gems tributed, v3 would have been at about 1008 itself. That is 72 gems per death, against v3's average of about 30 per death vs v2 (836 gems in 28 deaths over 18 games). What v2 does better on elkring: it farms more per living body (monster damage per alive champion-round 30.5 vs 24.9 in A, 29.0 vs 25.7 in B), and its Ryth snowballs (2,147 gold, 85 items vs v3 Ryth 774 / 30). v3's Marcella and Willow farm elk poorly (A: 216 and 108 gems; Willow's collected-gem share over all games is 0.58 of a fair share).
   - Cause in code: `bots/v3/src/ball.py:459-486` (`ball_want_bank`) never banks while `committed()` (line 475, any camp fight or capture in progress). With an enemy near it banks only if an altar is <= 3 away (line 470). The threshold itself can reach 110 gems (`bots/v3/src/bot.py:980-986` `bank_threshold`, capped at 30+3d in the push at line 483). Elk camps give 36 gems, so a champion chaining elk groups can carry 108 gems, exactly Ryth's bag. Carried gems only raise the fight threshold (`skirmish`, line 904, GEM_CAUTION). They never make the champion bank early.
   - Suggested fix: make the bank threshold aware of threats. In `ball_want_bank`, when an enemy champion was seen within ~10 tiles in the last ~20 rounds (`self.sightings`) and gems >= 50, return True even if `committed()` is set, unless the current camp is nearly dead (reuse the `left <= dps*2` test from `maybe_retreat`). To test, check elkring A and gems lost per death overall.
   - Confidence: low-medium. The 144-gem swing equals the losing margin, but I can't see from the stats whether Ryth died mid-camp-fight or on the way to an altar. That part is a hypothesis.

Side observation (not ranked): in rows A vs v2, Willow did nothing all game (0 gems, 0 gold, 0 monster damage, 90 champion damage). v2's Stellar did the same (0 gems, took exactly 90 champion damage), which suggests a whole-game stand-off between the two. Worth a DEBUG run of `skirmish` (ball.py:871) on rows.

Fix first: #1 (draft for expanse). It targets 2 of the 3 losses with a change limited to draft.py, then #2 for game length.

### v4 — promoted (56% vs v3)
- Based on: v3. Addresses analysis finding(s): #1 Fewer bodies than v2 in a no-contact farming race (expanse)
- Changes: draft.py:play / spawn_distance (new) / PREFS_FAR_3 (new): on 3-pick maps the draft bot computes the walking distance between the spawn regions once (DistanceField from our spawn, walls|holes|altars blocked, min over enemy spawn tiles; about 360k fuel on the 10x first draft turn, then cached). If it is >= FAR_SPAWN_DIST = 60 it drafts Varg, Cassi & Issac, Ryth (4 bodies, v2's farming roster), otherwise v3's Varg, Ryth, Marcella. Measured distances: packs 26, collision 34 (3-pick); expanse 85 (3-pick); elkring 31, corners 40, interlock 41, monolith 49, rows 73, lanes 81 (4/5-pick, unaffected). So only expanse changes. Finding #2 (go-home-at-400-gold fallback in need_home_ball) was not done: sending one champion home alone splits the ball, so it is not a small change, and leaving it out keeps #1 measurable on its own.
- Smoke test: v4 vs v3 on expanse: Team A (v4) wins, reached 1000 gems in round 438 (1010 vs 844, draft Varg, Cassi & Issac, Ryth), crashes 0. v4 vs v3 on collision: draft unchanged (Varg, Ryth, Marcella), Team B (v3) wins r1132 (530 vs 1014), crashes 0. This is the same result as v3 vs v3 on collision, so it is the mirror-match side effect and not a regression.
- Evaluation (results/v4-eval, 9 maps x both sides): 10-8 vs v3 (56%), 17-1 vs v2 (v3: 15-3), 18-0 vs v1.
  Expanse now 2-0 vs v3 and v2 (rounds 409-440). On the 8 unchanged maps v4 vs v3 is a mirror match:
  the same side wins both games, so they split 8-8. The only remaining loss to v2 is elkring as Team A (r645).
  0 crashes. Average winning round 520.
- Status: promoted, new champion.
- Lesson: a change confined to one map can score at most 10/18 head-to-head (8-8 mirrors plus 2), so the
  55% gate only just passes. Changes affecting every map are needed to move the head-to-head rate further.
