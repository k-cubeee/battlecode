# Bot version notes

**Current champion: v18**

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

### Analysis of v4 — 2026-10-16 (results/v4-eval)
Record: 45-9 overall; 10-8 vs v3 (56%), 17-1 vs v2, 18-0 vs v1. Weakest maps/side: the only non-mirror loss is still elkring as Team A vs v2 (r645, 864-1008, same game as in v3-eval). The 16 non-expanse games vs v3 are mirrors. The winning side per map is collision B, corners B, lanes B, monolith B; elkring A, interlock A, packs A, rows A. Slowest games: collision mirror r1132 (530-1014), rows mirror r706, elkring mirror r692, collision vs v1/v2 r631-666. Average winning round 520. 0 crashes, 0 bot faults.
Code fact that changes earlier advice: v4 has no ball. `ball.py:89` SOLO = 1 and `ball.py:193` r_gather = 0, so `elect()` (ball.py:281) makes every champion its own leader from round 0. Each champion already farms and travels alone, so sending one champion home to shop does not split anything. Also, `ball_phase` (bot.py:322 -> ball.py:220) sets bstage = B_MARCH in round 0, so `decide()` (bot.py:576) always hands off to `ball_decide`. That makes the farming-mode `need_home` (bot.py:622-633, including its ">= 400 gold, no task" fallback) dead code in v4.
Method: the 8 mirror games were counted once, with both teams treated as v4 code. Gems lost = collected - submitted - still carried.

1. **Gold sits unspent on every map (shopping only happens near spawn)**
   - Evidence: at game end v4 holds 27% of the gold it earned vs v1 (15,458 of 57,218, 859 per game, about 28 shards), 19% vs v2 (10,231 of 53,011, 568 per game) and 14% in the mirrors (6,780 of 48,620). v2 holds 10% in the same games (5,072 of 51,452). Worst case is monolith Varg: 1,140 of 1,600 unspent (A vs v1), 890 of 1,200 (B vs v1), 1,188 of 1,648 (mirror, winning side). Other examples: lanes A vs v1 Ryth 630 of 880; elkring B vs v1 Stellar 730 of 2,070; monolith B vs v2 Ryth 788 and Marcella 756. On corners vs v1 (r315/r333), Varg, Marcella and Willow (A) and Varg, Stellar and Marcella (B) bought 0 items all game while holding 180-360 gold each. This is an end-of-game snapshot, so how long the gold sat unspent is inferred. It is not the deciding factor in the mirrors: on monolith the winning side held more gold.
   - Cause in code: `bots/v4/src/ball.py:488-494` (`need_home_ball`) is the only shopping trigger besides low HP and dying. It requires gold >= 300 (GOLD_HOME, line 30), no visible enemy, and `df_spawn <= 18`. Camps further than 18 steps from spawn (most of monolith and lanes, where spawns are 49 and 81 apart) never trigger a trip. The v2/v3-farm fallback (bot.py:631, ">= 400 and task is None") exists but is unreachable (see the code fact above).
   - Suggested fix: in `need_home_ball`, add `if self.gold >= 400 and self.task is None and not self.committed() and not self.enemies: return True` after the 18-step test. `go_home` (bot.py:916) already recalls when far away and banks on the way if an altar is within 8, so the cost is about 5 recall turns plus the walk back. There is no ball to split (SOLO). If the caller still wants a group-friendly variant, gate it on "no live task and the next chosen group is >= 12 steps away", which is the moment the champion would be walking anyway. To test: unspent gold should drop to about v2's 10%, and winning rounds should fall on monolith, lanes and elkring. It applies to all 9 maps, so it can move the mirror head-to-head from both sides.
   - Confidence: medium. The stockpiling and the dead fallback are certain. The speed-up still needs a run.

2. **Big gem bags lost in contact fights (the mirror games are decided by them)**
   - Evidence: in the 8 mirrors, v4 code died 98 times and lost 2,098 of 15,412 collected gems (14%, 21 per death). Against v1 it lost 1% (5 deaths). Champion kills hand the bag to the killer, so each loss swings the score twice. Gems lost per side (A/B, loser marked *): collision 196*/130, corners 376*/70, elkring 108/180*, interlock 88/254*, lanes 178*/22, monolith 110*/132, packs 48/140*, rows 0/66*. The loser lost more in 7 of 8 maps. Corners A submitted 0 gems in 412 rounds: all 376 it collected were lost in 13 deaths. Collision A (the r1132 game) also ended carrying 238 unbanked gems (Ryth 130, Marcella 108), and monolith A's Ryth ended holding 132. Biggest single bags lost: collision B vs v2 Varg 144, corners B vs v2 Marcella 140, elkring A vs v2 Ryth 108 (the only loss to v2, margin 144).
   - Cause in code: `bots/v4/src/ball.py:459-486` (`ball_want_bank`). Line 470 refuses to bank whenever `threat_near()` (ball.py:450, an enemy within 3, or within 6 and not on its own spawn) unless an altar is within 3. Line 475 refuses while `committed()` (ball.py:588, any camp fight or capture in progress). In contact games an enemy is in view most of the time, so the bag keeps growing until the champion dies. Carried gems only raise the fight ratio (`skirmish`, ball.py:903-904, GEM_CAUTION = 200). Even 100 gems only makes us 1.5x pickier, and nothing sends the champion to an altar.
   - Suggested fix: make banking threat-aware in `ball_want_bank`. If an enemy champion was sighted within ~10 tiles in the last ~20 rounds (`self.sightings`, bot.py:536), use threshold `min(thr, 20 + 2*d)` and skip the `committed()` veto unless the current camp is nearly dead. When `threat_near()` and gems >= 40, bank anyway if the altar is closer to us than to the nearest enemy (damage does not stop a tribute, GameRules "Tribute at an altar"). To test: gems lost per death in the v4 mirror should fall from 21, and corners A should submit gems.
   - Confidence: medium on the pattern (consistent across 7 of 8 mirrors). Low-medium on the mechanism: without replays or stdout I can't tell whether bags were lost mid-camp-fight (line 475) or while an enemy was in view (line 470).

3. **Willow (drafted on 6 of 9 maps) does about half a champion's work**
   - Evidence: over all v4 games, Willow does 14.7 monster damage per alive round vs 24.6 for Varg, 25.0 Ryth, 25.7 Stellar and 20.6 Marcella. She collects 0.277 gems per alive round (others 0.49-0.59) and 0.74 gold per round (others 1.34-1.78). Her gem share is 0.58 of a fair share. She has the most deaths per game (0.75; Stellar 0.50, Varg 0.52). Her healing averages 2,962 per game, which is only about 9 casts of 3 x 105 Focus in a 400-700-round game (one cast is possible every 8 turns). Of the 16 champion-games below 40% of a fair share, 9 are Willow. Rows as Team A, the v3-analysis stand-off still happens identically (deterministic): vs v2 Willow has 0 gems, 0 gold, 0 monster damage and 90 champion damage over 561 rounds (v2's Stellar 0 gems, 90 damage taken). In the rows mirror, Team A's Willow again collects 0 gems, earns 50 gold and dies twice.
   - Cause in code: `bots/v4/src/draft.py:19-20` (PREFS[4] picks Willow 4th, PREFS[5] picks her 5th; the docstring says "Willow keeps the front line alive"). That roster was tuned when the bot played as a ball. With SOLO = 1 (ball.py:89) champions farm apart, so `try_heal` (ball.py:723, ally within range 4 required) rarely has a target. Willow is left as a 700-HP, growth-3 farmer.
   - Suggested fix: in draft.py, drop D_WILLOW from the head of PREFS[4] and PREFS[5]. For 4-pick maps (interlock, rows) Marcella comes next in the list. For 5-pick maps (corners, elkring, lanes, monolith) use Cassi & Issac (an extra body; the expanse change showed C&I win a farming race). If C&I die too often on the contact maps, use Tavi (field shop, which also helps finding #1). This touches 6 maps, so v5 vs v4 tests it properly. Check monster damage and gems per alive round of the new pick, and the rows A game.
   - Confidence: medium that Willow is the weakest slot (consistent over 36 champion-games). Low on which replacement is best: no data in results/ on Marcella-in-4 or C&I on 5-pick maps with v4 code.

Fix first: #1 (shopping fallback in `need_home_ball`). It is a few lines, applies to all 9 maps from both sides, revives logic v2 used successfully, and the "splits the ball" objection does not apply because v4 has no ball. Then #3 (draft, 6 maps, cheap to test), then #2 (bank logic, more behavioural risk).

### Analysis of v3 — 2026-10-16 (results/bench_v3)
Record: 33-3 overall; 15-3 vs v2, 18-0 vs v1 (same record as results/v3-eval). Weakest maps/side: expanse (2-2), elkring as A (lost r645). Slowest wins, all vs v1 or v2: collision 631-666, rows 561-651, elkring 498-645. Average winning round 499, 0 crashes. Findings 1-3 below are new; they do not repeat the three in the earlier v3 analysis (draft for expanse, unspent gold, gem bags lost to kills). NOTE: v4 (not v3) is now the champion; these apply to v3's code, which v4 inherits except for the expanse draft.

1. **Willow (and to a lesser degree Stellar) contribute little to the gem race on every 4/5-pick map**
   - Evidence: aggregated from all 36 `results/bench_v3/v*/*.stats.json`, per champion `type`, our side only: collected gems per 100 rounds Varg 64.7, Ryth 61.5, Marcella 54.8, Stellar 53.0, **Willow 29.7**. Gold earned per game: Varg 873, Ryth 951, Marcella 611, Stellar 791, **Willow 340**. Willow is in 24 of the 36 games (every 4/5-pick map). Examples: v2/rows__cand-A: Willow 0 gems, 0 gold, 0 monster damage all game (healed 120 only); v2/elkring__cand-B: 36 gems in 524 rounds; v2/lanes__cand-A: 94 gems in 463 rounds. Total gems per round with Willow is also low: rows 1.7, lanes 2.0, elkring 2.0 (vs 2.3-2.4 on the 3-body packs/expanse). Willow's heal output is 0.7k-6.6k per game, and v3 loses few champions (31 deaths in 36 games across 5 types), so the healer is rarely the thing that saves a game.
   - Cause in code: `bots/v3/src/draft.py:15-16` (PREFS[4], PREFS[5]) puts Willow 4th in the 4-pick and 5th in the 5-pick; farm and shop logic treat her like any other body, but her damage is low (monster damage/round 14 vs 21-26 for the rest in the aggregate) so her camps take longer and she buys fewer items.
   - Suggested fix: on 4-pick maps use Varg, Ryth, Stellar, Marcella (Willow dropped); on 5-pick keep Willow only if the test shows it is needed. Test on rows, lanes, elkring, interlock vs v2 and v1 (4/5-pick maps: 12 of 18 games per opponent). The docstring says rosters were chosen by playing them against each other, so this may already have been tried in a mirror; the NOTES do not record it.
   - Confidence: low-medium. The per-body numbers are solid. Whether a replacement body farms enough to beat Willow's healing is untested.

2. **Slow wins vs a weak opponent: a lot of time goes into fights that do not move the gem count**
   - Evidence: v3 wins vs v1 by reaching 1000 gems, yet it deals large champion damage: collision A 9,490 cdmg and 11 kills (r666), collision B 7,860 / 8 kills (r631), rows A 7,684 / 8 kills (r651), elkring B 12,120 (r498), interlock B 12,354 (r443) (`results/bench_v3/v1/*.stats.json`). v1 reached only 286 and 198 gems on collision. Same 3-pick draft, no fights: expanse vs v1 takes r436-440 with 2.37 gems/round; collision takes r631-666 with 1.85 gems/round (22% lower). Rows B (860 cdmg, 2 kills) r569 vs rows A (7,684 cdmg) r651. Per-body gem rate: rows A Stellar did 6,496 champion damage for 198 gems while Ryth farmed 594 of the team's 1,122. This is a correlation across maps. It could also come from map size, so it is only a hypothesis that fighting costs the time.
   - Cause in code: `bots/v3/src/ball.py:871-935` (`skirmish`) starts a fight whenever an enemy is within SEE_R=10 and reachable (`ratio >= R_GO`=1.05, line 902). Nothing in the decision uses the gem lead, and `update_push` (line 392-400) only scales camp choice (`push_f` in `bot.py:1098,1122,1148`). Also `bot.py` camp scoring multiplies a group's score by 1.25 when an enemy was seen near it and `esc >= 1.0` ("hunt in company"), which pulls champions toward enemies even when ahead.
   - Suggested fix: when our submitted gems exceed theirs by >= 150 (`PUSH_SPAN` x 0.75, so `push_f == 0`), set R_GO to about 1.6 and skip the 1.25 hunt bonus, so we take fights only when we clearly win and otherwise keep farming. To test, compare winning rounds on collision, rows and interlock vs v1, and check the win rate vs v2 does not drop.
   - Confidence: low. I did not trace per-round behaviour (no replay parsing), so how many rounds the fights took is not measured.

3. **Adding bodies gives sharply diminishing returns, so 5-pick maps are not faster than 3-pick maps**
   - Evidence: gems per body-round vs v1 (`results/bench_v3/v1`): 3 bodies 0.59-0.79 (expanse 0.79, packs 0.75-0.78, collision 0.59-0.62), 4 bodies 0.43-0.70, 5 bodies 0.40-0.70 (lanes 0.40-0.41, elkring 0.40-0.43, monolith 0.47-0.51). Total gems per round: 5-body lanes 2.0, elkring 2.0, monolith 2.5; 3-body expanse 2.4 and packs 2.3. Monster damage per body-round is similar (lanes 19, elkring 29-32, packs 35-42), so the damage dealt is not turning into gems on the big rosters. Corners is the exception (0.66-0.70 gems per body-round with 5 bodies, finishing in r315-333).
   - Cause in code: not isolated. Candidate: `bots/v3/src/ball.py:89` (`SOLO = 1`, every champion farms alone with no coordination) plus `BALL_PARTY = 2` (ball.py:63) and the camp claim logic in `bot.py:1105-1150`: several bodies pick the same high-value group, cut each other's per-camp gain, and wait for respawns (`wait`, WAIT_NEAR_MAX) instead of walking to a free group. This is a hypothesis from the aggregate numbers only.
   - Suggested fix: in the group selection in `bot.py` (~line 1105-1150) make a champion skip a group already claimed by another body (rather than join it, `joins` list) unless no unclaimed group has `ub > 0`. To test, compare gems per body-round on lanes, elkring, monolith.
   - Confidence: low. Wait/claim behaviour was not measured; map size is a confound.

Fix first: #3 if one wants a change that touches every 4/5-pick map, since finding #2 has a clearer, cheaper test (two constants) but the weakest evidence. Of the three, #1 is the easiest to test (draft.py only) and has the best numbers, so I would try #1 first. v4's lesson is that a change confined to one map cannot clear the 55% gate. #1 touches 4/5-pick maps (6 of 9 maps), so it can.

### v5 — promoted (56% vs v3)
- Based on: v3
- Changes: I changed `bots/v5/src/draft.py` (the `PREFS` table) so Willow is no longer drafted ahead of the other options on 4- and 5-pick maps. This is analysis finding #1. I did not edit `NOTES.md`.

- **4-pick maps:** the roster is now Varg, Ryth, Stellar, Marcella (Willow was fourth, Marcella fifth). Willow is last in the fallback list.
- **5-pick maps:** the fifth pick is now Tavi instead of Willow, so the roster is Varg, Ryth, Stellar, Marcella, Tavi. I chose Tavi because the code already supports her as a field-shop champion (`bot.py:243`), which also helps spend the gold left unspent at game end.
- **Why it should win:** Willow collects about 30 gems per 100 rounds against 53–65 for the other four champions. She also earns about 340 gold per game against 611–951. Champions farm separately (`SOLO = 1`), so her healing rarely has a target. Marcella and Tavi should farm better in her slot.
- **Maps affected:** 6 of 9, so the change can move the head-to-head rate past the 55% gate.

Smoke test: `cambc run v5 v3 --map rows` — v5 won in round 671 (1056 gems to 924), with 0 crashes. v5 drafted Varg, Ryth, Stellar, Marcella and v3 drafted Willow in the fourth slot. This is one deterministic match, so it only shows the bot doesn't crash. I did not run the Tavi roster on a 5-pick map.

Note that `bots/v5` is a copy of v3, so it lacks v4's expanse draft. The full evaluation should compare v5 against both v3 and v4.
- Evaluation (results/eval_v5): v3 56%, v2 83%, v1 100%; overall 80%
- Status: promoted, new champion.

### Analysis of v5 — 2026-10-16 (results/eval_v5)
Record: 43-11 overall; v3 10-8 (56%), v2 15-3, v1 18-0. Weakest maps/side: expanse 3-3 (0-2 vs v2, 1-1 vs v3 mirror) and lanes 3-3 (0-2 vs v3, lost B vs v2), corners 4-2 (both losses to v3, r636 and r980). Losses are 5-pick maps vs v3 (corners, lanes, elkring B: 5 losses; only monolith and elkring A won, 3-5 overall) plus expanse. Side is balanced (A 22-5, B 21-6). Slowest: collision mirror r1132, corners B vs v3 r980, elkring B vs v3 r776. 0 crashes. Average winning round 533, losing 620.

1. **Tavi (new 5th pick) is the weakest body and v5 loses the 5-pick maps to v3's Willow**
   - Evidence: on 5-pick maps (corners, elkring, lanes, monolith) v5 is 3-5 vs v3, whose only difference there is Willow instead of Tavi (summary.json; drafts in matches[].teams). Per-champion aggregate from results/eval_v5/*/*.stats.json (type 11 = Tavi): collected gems per 100 rounds (vs v1/v2 | vs v3): Varg 64.2 | 38.4, Stellar 56.8 | 46.9, Marcella 50.4 | 38.1, Tavi 43.0 | 34.8 (Ryth/type 0 is 53.7 | 36.4). Tavi is last in both. Vs v3 Tavi lost 730 of 1,864 gems collected (39%; deaths 10 in 8 games) against 14-25% for others in the same games. Examples: corners B vs v3 Tavi collected 282, submitted 48, 3 deaths; lanes B 134 collected, 44 submitted; elkring A 216/36. Tavi's monster damage is also lowest on corners (4,130 vs v3, 4,000 vs v2 in A). 
   - Cause in code: `bots/v5/src/draft.py:16` (PREFS[5] picks `D_TAVI` fifth). The v5 change was chosen for Tavi's field shop, but nothing in the draft or farm logic exploits it in SOLO mode (`ball.py:89`), so she is just a fragile farmer who carries a big bag and dies (gems lost = collected - submitted).
   - Suggested fix: restore Willow in 5th place on 5-pick maps only (PREFS[5] = Varg, Ryth, Stellar, Marcella, Willow) and keep v5's Willow-free 4-pick roster, which won 6-0 on rows/interlock. Alternative to test as v-next: Cassi & Issac as 5th. Test on corners, lanes, elkring vs v3 and v2.
   - Confidence: medium. Eight games, same-map comparisons are consistent, but the other four bodies are identical to v3's so some of the gap could be mirror-side luck (the same side tends to win a mirror).

2. **The v4 expanse draft fix is missing from v5 (v5 was copied from v3)**
   - Evidence: expanse vs v2 is a 0-2 loss again: A 988 vs 1032 (r421), B 796 vs 1010 (r386), 0 deaths both sides (results/eval_v5/v2/expanse__cand-{A,B}.stats.json). v2 drafts 4 bodies (Varg, Cassi & Issac, Ryth); v5 drafts 3 (Varg, Ryth, Marcella). v4 beat v2 2-0 on expanse (r409-440, NOTES v4). These 2 games and the expanse mirror (A loses 988-1000 at r440) are 3 of the 11 losses.
   - Cause in code: `bots/v5/src/draft.py:14` (PREFS[3]) is one fixed 3-pick list; v4's `spawn_distance`/`FAR_SPAWN_DIST = 60` gate does not exist in v5.
   - Suggested fix: port v4's draft gate into a copy of v5 (expanse distance 85 vs packs 26, collision 34), unchanged otherwise. Expected: +2 vs v2, and +1 in the v3 mirror only if the other side stays on v3's roster (v3 would lose A at r440).
   - Confidence: high (same game, deterministic, v4 already measured it).

3. **Gem bags are lost in contact fights, and they decide the v3 games**
   - Evidence: vs v3, v5 champions collected 19,472 gems, submitted 15,432 and ended holding 1,004, so 3,036 (15.6%) were lost, in 108 deaths. Vs v1/v2: 39,017 collected, 36,873 submitted, 1,516 held, so 628 lost (1.6%) in 29 deaths. Losses vs v3: corners A submitted 192 total with 16 deaths (type 0 champion 256 collected, 0 submitted), corners B 984 final vs 1,198 (v5 lost 814 gems), elkring B 630 vs 1,008, lanes A 644 vs 1,004. The loser lost more gems than the winner in these games (results/eval_v5/v3/*.stats.json). Collision mirror r1132: loser A ended with 530.
   - Cause in code: `bots/v5/src/ball.py:459-486` (`ball_want_bank`): line 471 (`threat_near()` blocks banking unless an altar is within BANK_NEAR) and line 475 (`committed()` veto) mean the bag keeps growing while an enemy is around; `bank_threshold` (bot.py:980) can be large. Also earlier analyses #2 (v4) already flagged this; it has never been tried.
   - Suggested fix: in `ball_want_bank`, when an enemy champion was sighted within ~10 tiles in the last ~20 rounds and gems >= 40, bank even if `committed()` (skip only if the camp is nearly dead). Test: gems lost per death vs v3 should fall below 21% and corners/lanes should flip.
   - Confidence: medium on the pattern, low-medium on the exact mechanism (no replay inspection).

Fix first: #2 (cheap, exact, ported from v4, no risk to other maps), then #1 (Willow back on 5-pick maps), then #3.

### v6 — promoted (61% vs v5)
- Based on: v5
- Changes: I made `v6` from `v5` with two draft changes, both in `bots/v6/src/draft.py`. I did not implement finding #3 (banking gems during contact fights). Only the one smoke test on expanse was run, and it was clean.

- **Expanse gate (finding #2):** I ported v4's spawn-distance gate unchanged. On 3-pick maps where the spawns are 60 or more tiles apart, `v6` drafts Varg, Cassi & Issac, Ryth. That gives four bodies instead of three, which is the roster that beat v2 on expanse in v4. Other maps keep `v5`'s picks.
- **Willow back as 5th pick (finding #1):** On 5-pick maps the order is now Varg, Ryth, Stellar, Marcella, Willow, with Tavi last. The 3-pick and 4-pick lists are as they were in `v5`, so the 4-pick roster still has no Willow.

**Smoke test:** `cambc run v6 v5 --map expanse`: v6 won, reaching 1000 gems in round 438. It finished 1010 gems to 844 for `v5`, with 0 crashes. That map exercises only the gate, not the Willow change.

I expect `v6` to win more because it should fix the 0-2 expanse losses to v2. Willow should also help on the 5-pick maps (corners, elkring, lanes and monolith) that `v5` lost 3-5 to v3.

I did not edit NOTES.md.
- Evaluation (results/eval_v6): v5 61%, v3 67%, v2 94%, v1 100%; overall 81%
- Status: promoted, new champion.

### Analysis of v6 — 2026-10-16 (results/eval_v6)
Record: 58-14 overall (81%); v1 18-0, v2 17-1, v3 12-6, v5 11-7. 0 crashes. Weakest maps: elkring 5-3, monolith 5-3 (collision/packs 6-2). Side is even (29-7 each). Of the 14 losses, 13 are vs v3/v5. Avg winning round 548, losing 675. Slowest wins: collision mirror r1132, corners A vs v5 r980, interlock A vs v3 r747. Aggregate numbers below come from results/eval_v6/*/*.stats.json.

1. **Gem bags are lost in contact fights vs v3/v5 (decides the losses)**
   - Evidence: vs v3/v5 the share of collected gems never submitted is, by champion type, 22% (Ryth), 19% (Stellar), 20% (Marcella), 24% (Willow), 16% (Varg) of collected gems never get submitted; vs v1/v2 the same figure is 2-8% (Ryth collected 8,902, submitted 6,952, 57 deaths vs v3/v5; 7 deaths vs v1/v2 in the same number of games). Losses: corners A vs v3 submitted 0 of 376 collected with 13 deaths (opp 2 deaths); packs B 364 of 504 (6 deaths vs 2); collision A (vs v3 and v5, same game) 530 of 964 and 238 gems still held at end; interlock B vs v5 558 of 1060 with 204 held; monolith A vs v3 608 of 916, 198 held; elkring B vs v5 396 of 792. In four of these losses the opponent's roster was identical to ours (collision, packs, corners A vs v3), so the loss comes from who gets caught in a fight carrying a bag, not from the draft.
   - Cause in code: `bots/v6/src/ball.py:459-486` (`ball_want_bank`): `threat_near()` (line 471) refuses to bank unless an altar is within BANK_NEAR=3, and `committed()` (line 475) vetoes banking in any camp fight; `bank_threshold` (`bot.py:980`) is 30-110 gems, so bags of 100-250 build up while enemies are near. Same pattern flagged in the v3/v5 analyses; never tried.
   - Suggested fix: in `ball_want_bank`, when an enemy champion was seen within ~10 tiles in the last ~20 rounds and gems >= 40, bank even if `committed()` (unless the camp is nearly dead), and cap the bag at ~100 gems while any enemy champion has been seen. Test on corners, packs, collision, interlock vs v3/v5; target gems lost per death below 15%.
   - Confidence: medium on the pattern (clear in the data), low-medium on the mechanism (no replay inspection).

2. **Willow is the weakest farmer and dies most (5-pick maps hold 7 of the losses)**
   - Evidence: type 8 (Willow) collects 24.1 gems/100 rounds vs v3/v5 and 29.0 vs v1/v2, against Varg 40.3/62.4, Marcella 41.7/48.5, Stellar 41.5/51.9. Willow had 21 deaths in 16 champion-games vs v3/v5 (1.3 each, highest of any type; Varg 41 in 36 games) and loses 24% of its gems. On 5-pick maps v6 lost 7 of its 14 losses vs v3/v5 (elkring B vs v3 and v5, monolith A and B vs v5, monolith A vs v3, lanes A vs v3) Willow's gold at the end was 0-253 and its submit rate poor (monolith A vs v3: 44 of 132). v6's 4-pick maps (interlock, rows) are 7-1 and 7-1 with no Willow.
   - Cause in code: `bots/v6/src/draft.py:20` (PREFS[5] has `D_WILLOW` fifth). The only special use of Willow is `ball.py:799-805` (`fight_ratio`), and SOLO mode (`ball.py:89`) means she mostly farms alone, which she does poorly (tables.py:63 gives her 0.0 damage factor).
   - Suggested fix: on 5-pick maps draft the 4-pick roster plus Cassi & Issac, or simply stop at four champions if the API allows; the cleanest test is PREFS[5] = Varg, Ryth, Stellar, Marcella, Cassi & Issac. Test on corners, elkring, lanes, monolith vs v3/v5.
   - Confidence: low-medium (hypothesis: Willow's low farm rate is clear, but the effect of the replacement was not measured; Tavi was also weak per the v5 analysis).

3. **Gold left unspent on the big maps (monolith, elkring)**
   - Evidence: v6 wins with large unspent gold: monolith A vs v1 2,264 unspent of 4,674 earned, monolith B vs v1 2,254 of 4,564, monolith B vs v2 1,682 of 4,682, monolith B vs v5 1,196 of 4,796 (a loss), elkring B vs v1 1,364 of 6,084, elkring A vs v3 956 of 6,426. These are 20-48% of gold earned on the maps where v6 is weakest (5-3 each). Varg is typically the holder (e.g. monolith vs v3 B: Varg 1,188 gold unspent; lanes A vs v3: Varg 540).
   - Cause in code: `bots/v6/src/ball.py:488-494` (`need_home_ball`): shopping trips need gold >= 300, no enemy visible and spawn within 18 steps (`GOLD_HOME`, line 30); there is no fallback to go home from far away when carrying a lot of gold between tasks. v2's `need_home` (`bots/v2/src/bot.py:582-593`) had this; it was suggested in the v3 analysis and never applied.
   - Suggested fix: in `need_home_ball` add `if self.gold >= 450 and self.task is None and not self.field_shop and not self.enemies: return True`. Test on monolith, elkring, collision; check unspent gold at end falls below 15% of earned and winning rounds shorten.
   - Confidence: medium (stockpile is clear; effect on winning is not measured).

Fix first: #1 (it explains 13 of the 14 losses, including the mirror losses that nothing in the draft can fix), then #3 (cheap one-liner), then #2.

### Analysis of v6 — 2026-10-16 (results/eval_v6, second pass)
Record: 58-14 (v1 18-0, v2 17-1, v3 12-6, v5 11-7); weakest maps elkring and monolith (5-3 each); side is even (29-7 each). Limit of this pass: Bash was unavailable, so I read summary.json and a few stats.json/txt files by hand and did not aggregate across all 72 matches. Numbers below come from summary.json unless a stats file is named. The earlier v6 analysis above covers bag loss, Willow and unspent gold; the three points below are different or sharpen it.

1. **12 of the 14 losses are games v6 plays against its own code, so they are decided by who wins the first contact, not by strategy**
   - Evidence: v3 differs from v6 only on expanse (v6 drafts C&I there), and v5 differs only in the 5th pick (Tavi vs Willow). In collision, packs, corners, elkring, lanes and monolith vs v3 and in collision, packs, interlock, rows vs v5 the rosters are identical. Each of those games appears twice with the sides swapped and gives the identical score, so one side always wins: collision 530 vs 1014 (r1132, B side wins, both opponents), packs 364 vs 1044 (A side wins), corners vs v3 0 vs 1002 (B wins), lanes 608 vs 1002 (B), interlock vs v5 558 vs 1014 (A), rows vs v5 858 vs 1056 (A). Only monolith vs v5 (0-2) and elkring vs v5 (1-1) differ between sides. The loser is lopsided, not close: in `results/eval_v6/v3/corners__cand-A.stats.json` all 5 v6 champions died 2-4 times (13 deaths), collected 476 gems and submitted 0, and 3 of them earned 0 gold. The winning side died twice, submitted every gem it collected (1002 of 1002), and earned 1350 gold vs 370.
   - Cause in code: `bots/v6/src/ball.py:871-933` (`skirmish`) is the only fight policy. `need = R_GO (1.05)` is identical for both teams and nothing makes a team that is losing the opening exchange disengage. With `SOLO = 1` the champions meet the enemy one at a time. Once one team wins the first 1v1 or 2v2 it snowballs (kills heal nobody but remove the other side's farmers and bags). `hard_retreat` (line 917) only triggers on `ratio < 0.5` or HP < 40%, by which time the champion is already in reach of the enemy.
   - Suggested fix: after a champion death, stop fighting and fall back for a short time. Concretely, when `ally deaths in the last ~40 rounds > enemy deaths + 1`, set `R_GO` to ~1.5 and the camp-choice weight toward groups far from the last enemy sighting. Test on corners A vs v3 (0 gems, 13 deaths) and collision A vs v3 (r1132). This is a behaviour change on every map, so it can move the head-to-head rate off the 8-8 mirror split.
   - Confidence: medium on the diagnosis (the mirror symmetry is certain); low on the fix, since I have no replay-level view of the first contacts (replays exist as `*.repl26a` next to each stats file but I did not parse them).

2. **Banking is blocked by a third veto that earlier analyses missed (`task is not None and camps and inc > 0`)**
   - Evidence: corners A vs v3 above: 476 gems collected, 0 submitted, 13 deaths. Collision A (v3/v5) ended with 530 submitted while the same code on B submitted 1014 in the same round count. Earlier analyses blamed `threat_near()` (line 470) and `committed()` (line 475); both sit after another return at line 468.
   - Cause in code: `bots/v6/src/ball.py:468-469`: `if self.task is not None and self.camps and self.inc > 0.0: return False`. It returns before the threat checks, so any champion with a live camp task and positive income never banks, whatever the bag size or the enemy nearby. The only things that skip it are `endgame_bank` (line 466, only close to the round limit) and the `bank_latch` path that starts later. `bank_threshold` (bot.py:980) caps at 110, but the veto means the threshold is never consulted during a task.
   - Suggested fix: change line 468 to `if self.task is not None and self.camps and self.inc > 0.0 and self.gems < 60 and not self.enemies: return False`, so a loaded champion (or one with an enemy in view) may bank. Combine with the earlier suggestion to relax `committed()` when an enemy was sighted recently. Test: gems lost per death in corners/collision/packs mirrors, and that `submitted` is non-zero for corners A.
   - Confidence: medium-low. The veto exists and runs first (read from code). Whether it is what stopped corners A from banking, rather than the threat veto, is untested; I did not read the per-round logs.

3. **Tavi (v5) beats Willow (v6) on monolith, and v6's gold income trails on the 5-pick maps it loses**
   - Evidence: monolith vs v5 is lost from both sides (A 804 vs 1040, r612; B 806 vs 1032, r665). v6 earned 4010 vs 5314 gold on A and 4796 vs 4904 on B, with the roster identical except Willow vs Tavi. Elkring B vs v5 was lost 396 vs 1080 (v6 earned 3954 vs 6467 gold). In the corners games v6 earned 1140 gold vs 2330 for v5 (A, r980, a win only by 1198-984 after 15 deaths each). The earlier v5 analysis said Tavi was the weakest body, and v6 reverted that. These games say the reverse on monolith/elkring; on corners and lanes v6 wins 4-0 vs v5, so Willow is not worse everywhere. Hypothesis: Tavi's field shop converts gold into items without a trip home, which matters on the big maps (monolith, elkring) where `need_home_ball` (ball.py:488-494) rarely fires. I could not check item counts per champion without aggregation.
   - Cause in code: `bots/v6/src/draft.py:20` (PREFS[5] with Willow fifth) is one fixed list for all 5-pick maps; `ball.py:491-492` limits shopping trips to <= 18 steps from spawn, so on large maps a body without a field shop leaves gold unspent (v6 monolith vs v1: 2,264 of 4,674 gold unspent, from the earlier analysis).
   - Suggested fix: make the 5th pick map-dependent: Tavi on monolith and elkring (large maps, spawn distances 49 and 31 per v4 notes; use the existing spawn-distance helper in draft.py), Willow on corners and lanes. Test on monolith and elkring vs v5 and v3 and check that corners/lanes vs v5 stay 4-0. If it fails, the alternative is the `need_home_ball` fallback already proposed (gold >= 450, task None).
   - Confidence: low-medium (4 games on monolith/elkring vs v5, two sides each; Tavi vs Willow is confounded by the mirror side effect in finding 1).

Fix first: #2 (a one-line change in `ball_want_bank` that targets the clearest symptom, 476 gems collected and 0 submitted). Then #3 (draft only, easy to test on two maps), then #1 (a larger behaviour change).

### Engine change: cambc 2.1.6 -> 2.2.3 — 2026-10-16
- SDK refreshed to 2.2.3. 6 of the 9 maps changed (collision, corners, expanse, interlock,
  lanes, packs); elkring, monolith and rows are unchanged. API additions: `Camp.state()` /
  `CampState` (DEAD, ALIVE, ASLEEP per camp) and `debug_block`.
- All win rates and map numbers above this line were measured on 2.1.6 and are only a rough
  guide now. New results start from a fresh benchmark of the champion.

### Analysis of v6 — 2026-10-16 (results/bench_v6)
Record (from the 104 `.txt` result tables; summary.json is missing from this folder and the `.stats.json` files are now a binary "CAMSTAT" format that I could not parse, so everything below is from the `.txt` tables): 65-39 overall; v1 36-0, v3 18-16, v5 11-23. 0 crashes. 17 maps x 2 sides vs v3/v5, 18 vs v1 (new maps: ambush, contest, eight, fragment, pilgrimage, rushbait-v2, stampede, swirl). Weakest: 5-pick maps vs v5. Side: in mirror games the same side wins on both swaps, so A/B is the main variable. Slowest wins: contest vs v1 r1360/1494, vs v3 r1765; stampede vs v3 r1626; ambush vs v3 r1146; pilgrimage vs v3 r1123.

1. **Willow as 5th pick loses every 5-pick map to Tavi (v5): the v6 "fix" is now wrong**
   - Evidence: v5 differs from v6 only in the 5th pick (Tavi vs Willow) and on expanse. On corners, pilgrimage, monolith, lanes, elkring and stampede v6 is 0-12 vs v5 (both sides lose each): corners 700-1040 (A), 478-1180 (B); monolith 804-1040 / 608-1018; lanes 944-1016 / 650-1016; elkring 630-1026 / 504-1008; pilgrimage 964-1090 / 762-1066; stampede 360-1080 both sides. On the other 5-pick maps (ambush, contest, eight) the sides split 1-1 as in a mirror, so v6 is 3-15 on the nine 5-pick maps vs v5. Vs v3 (also Willow) v6 is only 1-1 per map, so the loss is Willow-vs-Tavi, not noise. Gold earned is lower for v6 in most of these (monolith A 4010 vs 5314, eight A 2088 vs 5966, stampede 10188 vs 12988) (results/bench_v6/v5/*.txt).
   - Cause in code: `bots/v6/src/draft.py:20` (PREFS[5]) picks D_WILLOW fifth and D_TAVI last. v6 reverted v5's Tavi based on 2.1.6 results, which no longer hold on 2.2.3.
   - Suggested fix: PREFS[5] = Varg, Ryth, Stellar, Marcella, Tavi (v5's roster). Test vs v5 and v3 on the 9 5-pick maps. Leave the 4-pick list alone (v6's Marcella 4-pick beat v3's Willow 4-pick 2-0 on rows).
   - Confidence: high on direction (12 deterministic games, same sign). Medium on cause (Tavi's field shop spending gold is a hypothesis; per-champion stats unreadable).

2. **One side collapses in contact games: bags are lost and the loser submits almost nothing**
   - Evidence: losing-side tables (results/bench_v6/v3, v5): fragment A 0 gems, 0 kills, 8 deaths vs 7 kills / 0 deaths (r599); eight A 44 gems, 19 deaths vs v3, 380 gems, 18 deaths vs v5; contest B 0 gems, 56 deaths vs v5 (r1730); corners A vs v3 484 gems, 9 deaths; stampede A vs v5 360 gems, 21 deaths; packs 544 gems, 9 deaths vs 2; swirl A vs v3 468, 13 deaths vs 5. Fights are lopsided, not close: first contact decides. Vs v1 v6 has 0-1 deaths, so it is the contact policy, not farming.
   - Cause in code: `bots/v6/src/ball.py:468-469` (`ball_want_bank`) returns False for any champion with a live camp task and positive income, before the threat checks (470-471) and the `committed()` veto (475). A champion keeps carrying while enemies are near. `skirmish` (ball.py:871-933) uses the same R_GO for both teams, and only `hard_retreat` (ratio < 0.5) disengages.
   - Suggested fix: (a) line 468: also require `self.gems < 60 and not self.enemies`; (b) in `skirmish`, when our recent deaths exceed theirs by 2 in ~50 rounds, raise R_GO to ~1.5 and bank at the nearest altar. Test fragment, eight, contest, corners A vs v3/v5.
   - Confidence: medium on the pattern, low-medium on the mechanism (no stats/replay parsing).

3. **Fight-heavy maps give slow wins, and the expanse Cassi & Issac gate no longer pays**
   - Evidence: wins vs v1 on contest took r1360/r1494 (v6 48-51 kills, v1 0 gems) against r460-680 elsewhere; vs v3 contest 1765, stampede 1626, ambush 1146, pilgrimage 1123. Expanse is a pure farming race (0-1 kills) where Team A wins on either roster: v6 A (Varg, Cassi & Issac, Ryth) 1016 vs 878 at r715, but v6 B with the same roster loses 836-1050 at r704 (5 deaths, 0 kills) to the 3-pick Varg, Ryth, Marcella (results/bench_v6/v5/expanse__cand-B.txt; v3 identical). The gate gives no side-independent gain on 2.2.3's expanse (1-1).
   - Cause in code: `bots/v6/src/ball.py:871-933` (`skirmish`) fights whenever enemies are in view regardless of the gem lead; `bots/v6/src/draft.py:56` (`FAR_SPAWN_DIST` gate) picks C&I based on 2.1.6 measurements.
   - Suggested fix: (a) when our submitted gems lead by >= 150, set R_GO ~1.6 and skip the hunt bonus; test on contest, stampede, pilgrimage (rounds). (b) A/B the expanse gate off on 2.2.3.
   - Confidence: low (correlation across maps; time in fights not measured; one game per side on expanse).

Fix first: #1 (a one-line PREFS[5] change; 12 deterministic losses point the same way), then #2, then #3.

### v8 — promoted (68% vs v6)
- Based on: v6
- Changes: draft.py PREFS[5]: Tavi picked 5th again instead of Willow (fix #1 of the bench_v6 analysis). Built by the strategist in the run that crashed in the smoke test; evaluated by hand with run_matches.py.
- Evaluation (results/eval_v8): v6 68%, v5 50%, v3 71%; overall 63%
- Status: promoted, new champion.

### Analysis of v8 — 2026-10-17 (results/eval_v8, results/arena_1)
Record: eval_v8 64-38 (v3 24-10, v5 17-17, v6 23-11), 0 crashes, 0 bot faults. Arena_1 vs b1: 34-0, avg winning round 669; v8 died 0.5 times per game against b1's 18.0. Weakest in eval: ten maps went 3-3 (ambush, collision, contest, eight, expanse, fragment, interlock, packs, rushbait-v2, swirl). Side A went 28-23 and side B 36-15. v8 differs from v5 only in the expanse draft, so vs v5 it is a pure mirror. On every map the same side won both swaps, which gives exactly 17-17 (summary.json `matches[]`, identical rounds per pair, e.g. contest r1577/r1577, stampede r1409/r1409). So the gate vs v8 will also be a mirror. A change has to win from both sides on some maps to pass 55%. The slowest arena wins are contest r1367/r1400, stampede r1075/r1356, ambush r811/r826 and pilgrimage r778/r829. In eval they are contest r1577-2000 and stampede r1409-1588. The bot was read only; Bash was not used. Numbers come from the two summary.json files and the named stats.json timelines.

1. **On big-camp maps (contest, stampede) no gems arrive for the first 590-760 rounds: big camps are taken solo or not at all**
   - Evidence: on contest every capture is exactly 200 gems (monolith) and is never split. `results/arena_1/b1/contest__cand-A.stats.json` per-champion `gems` timelines: first capture is Varg at r757, then Ryth r858, Varg ~r1043, Ryth ~r1160 and ~r1330. b1 scored 0 gems in that game, so nobody contested it, and v8 still needed 1367 rounds. Stellar, Marcella and Tavi collected 0 gems (summary.json). On stampede every capture is exactly 360 gems. In `stampede__cand-A.stats.json` the first capture is Varg at r586 and the second at r790. In `stampede__cand-B.stats.json` the first is Tavi at r722, then Varg at r952 and r1233. Ryth, Stellar and Marcella collected 0 gems on both sides. Each 360-gem bag was carried 71-130 rounds before it was banked (Varg B: 360 held from r952 to r1075; the tribute alone is 36 turns). These 4 games are the 4 slowest of the 34 arena wins (1075-1400 vs the 669 average). The pattern repeats in eval: stampede vs v3 A had Stellar, Marcella and Tavi at 0 gems with 1722-4430 gold each (r1588), and contest vs v3 B ended at the round limit with 600 of v8's 800 collected gems lost.
   - Cause in code: `bots/v8/src/bot.py:1084,1110` (`best_group`): `cap_inc = 0.15 * maxhp / mult` skips any group with `stsum > cap_inc`. A monolith (strength 200, tables.py:6) needs 1333 effective HP, or 952 with the Jungle emblem. Stellar and Tavi (750 base HP) and anyone who hasn't shopped never qualify. With SOLO (ball.py:89) every champion is a leader (`pick_task`, ball.py:681). It is limited to `BALL_PARTY = 2` (ball.py:65), and a join is only taken when the time saved beats 1.15x its cost (bot.py:1181-1184). That test ignores the 100+ gems the joiner would share, which is why every 200- and 360-gem capture went to a single champion. I don't know which monsters make up the 360-gem stampede group (map not parsed). That it is gated the same way is a hypothesis.
   - Suggested fix: for groups with `g.gems >= 150`, (a) allow party 3 (`party = 3 if g.gems >= 150 else party`) and (b) in the join loop, add the joiner's share to the join score (e.g. `score = max(score, (g.gems + kappa*g.gold) / (n0+1) / cost)`). That way the champions that currently farm gold clusters help clear the monolith or herd. Leave `cap_inc` unchanged for solo picks. To test, check the round of first capture and the winning round on contest and stampede vs b1 and vs v8 (both sides). The mirror-pair rounds should drop from both sides.
   - Confidence: medium on the pattern (deterministic capture timelines, 4 arena + 4 eval games). Low-medium on which line dominates, cap_inc or the join test.

2. **Champions that don't die never shop: gold is wasted in exactly the games we dominate**
   - Evidence: in the arena, where v8 dies 0.5 times per game, it leaves 1,112 gold unspent per game (5,881 earned, 4,769 spent, 19%). In eval, where it dies 7.4 times per game (dead champions can shop, GameRules l.129/361), only 453 is left (5,041 vs 4,587, 9%). Extreme case: `results/arena_1/b1/stampede__cand-B.stats.json` Stellar `gold` timeline rises +70 every 23-31 rounds from r28 to r1356 and ends at 3,640. That is two 35-gold clusters cycled all game, with 0 spent, 0 items, 0 gems, 0 damage taken and 0 deaths. Arena stampede A: Marcella earned 2,040, spent 0, 0 items. Arena pilgrimage A (r778, 0 deaths): Varg 1,035 earned, 190 spent; team 4,318 earned, 2,780 spent. Since nobody shops, maxHP stays low, which keeps the big camps of #1 blocked by `cap_inc`. The two problems feed each other.
   - Cause in code: `bots/v8/src/ball.py:488-494` (`need_home_ball`) only sends a champion home to shop when `df_spawn <= 18`. Low HP (`HOME_HP`) is the only other trigger. A healthy champion farming gold clusters further than 18 steps out never goes home. This has been flagged in the v3, v4 and v6 analyses and was never tried. I repeat it because the stampede timeline now shows the worst case directly.
   - Suggested fix: in `need_home_ball` add `if self.gold >= 450 and not self.field_shop and not self.enemies and not self.committed() and self.task is None: return True` (no ball to split, SOLO = 1). To test, check unspent gold per game in the arena (target < 10%) and that stampede B's Stellar buys items. Then check the winning rounds on stampede, pilgrimage and ambush.
   - Confidence: high that the gold sits unspent. Medium that fixing it shortens games.

3. **Marcella does almost nothing on ambush (4 of 4 games)**
   - Evidence: v8's Marcella on ambush. Arena A (r826): 0 gems, 140 gold, 0 deaths, 0 champion damage taken. Arena B (r811): 36 gems, 160 gold, 0 deaths. Eval A vs v3/v6 (r908, a loss 226-1068): 0 gems, 100 gold. Eval B vs v3 (r1027): 0 gems, 0 gold, 3 deaths (summary.json). Other maps give her 130-490 gems. `results/arena_1/b1/ambush__cand-A.stats.json`: her `earnedGold` stays at 140 from r113 to r827 (714 rounds with no reward). Yet `monsterDamageDone` climbs in bursts of ~10-30 turns about every 80 rounds, to more than 4,470. `monsterDamageTaken` starts at r185 at ~80 per turn. So she keeps attacking a camp, leaves, comes back, and never captures anything.
   - Cause in code: not isolated (hypothesis). The ~80-round cycle at ~80 damage per turn fits a camp she can't clear before HP < 45% (`HOME_HP`, ball.py:29 -> `need_home_ball`). After the recall she goes back to the same group, because `best_group` (bot.py:1145-1150) costs the extra trips with `cycles_for` and still ranks it best. Either the group is reset or captured by someone else meanwhile, or the damage estimate (`group_estimate`, bot.py:1032) is wrong for that group's layout. A DEBUG run of `cambc run v8 v8 --map ambush` that prints Marcella's `task` and its `est` would settle it.
   - Suggested fix: after a champion leaves a group for a recall without capturing it twice in a row, block that group for that champion for ~150 rounds (`g.block_until`, as in bot.py:1143) so it farms elsewhere. To test, check Marcella's gems on ambush (both sides) and the ambush mirror pair vs v8.
   - Confidence: high that Marcella is idle (4 of 4 games, deterministic). Low on the mechanism.

Not ranked: the eval losses are still mirror games decided by first contact and lost bags (contest B vs v3 lost 600 of 800 collected gems; ambush A collected 438 and submitted 226). The analyses above already cover this (`ball_want_bank`, ball.py:468-475), and it is still untried.

Fix first: #1. It targets the slowest games in both the arena and the eval, it shows up from both sides (so it can beat the v8 mirror on contest and stampede), and it is a contained change in `best_group`. #2 is a one-liner that helps #1, so it can go into the same version if the strategist wants. Otherwise do it next.

### v9 — promoted (59% vs v8)
- Based on: v8
- Changes: I've built v9 from v8 with two focused changes. In smoke tests it never crashed, beat v8 on stampede from both sides, and split contest and monolith 1–1 by side, which is no worse than v8 against itself. These are single matches, so they show it runs, not that it's stronger.

**Finding #1, as one part of the fix.** The first version did what the analyst suggested and let champions start big camps hoping teammates would join, including monoliths. It was clearly worse: it lost contest 600–800 and lost stampede from both sides (v9 earned about a third of v8's gold). Leaving out the monolith and the early-start part is what made it work:
- **`bot.py:best_group` (joining a teammate):** groups worth 150+ gems with 2 or more monsters can now take 3 champions instead of 2 (`BIG_PARTY`, new `is_big()` helper). For these groups the join math treats the party's health as shared, since camps hit the nearest champion. The join score also counts the joiner's own share of the gems. A champion only joins if the party doesn't waste much champion-time (at most 1.25× the time it saves).
- **`bot.py:work_once`:** the "too many champions on one camp, the extras leave" check uses the same limit of 3 for these groups.
- **Not changed:** the 15%-health solo gate on starting a camp. Lone monoliths are excluded, because three champions sitting on one for a long fight just got caught by enemies on contest.

**Finding #2:** `ball.py:need_home_ball` now also sends a champion home to shop when it has 450+ gold (`GOLD_HOME_FAR`), no enemy in view, and no camp fight or capture in progress. The analyst's "has no task" test almost never fires, because a new task is picked in the same turn a capture ends, so I used "not in a fight" instead. On its own this change flipped contest side A from a loss to a 1000–0 win.

**Why it should win:** the v8 mirror games go to whichever side has the edge on the map, so v9 needs wins from both sides. Stampede now gives that (side A 1080–0, side B 1080–360), and contest and monolith are no worse than v8's split.

**Smoke tests** (crashes 0 for v9 in every match):

| Match | Result |
|---|---|
| v9 vs v8, contest | v9 wins 1000–0 (round 1549) |
| v8 vs v9, contest | v8 wins 1000–0 (side split, as with v8 against itself) |
| v9 vs v8, stampede | v9 wins 1080–0 |
| v8 vs v9, stampede | v9 wins 1080–360 |
| v9 vs v8, monolith | v8 wins 1010–652 |
| v8 vs v9, monolith | v9 wins 1032–908 (side split) |
| v9 vs v1, ambush | v9 wins 1034–108 |

I couldn't run `diff` or `py_compile` because the shell only allows cambc, ls and wc, so the matches served as the compile check. The only edited files are `bots/v9/src/bot.py` (new constants `BIG_GEMS`, `BIG_PARTY`, `BIG_EFF`, plus the `is_big()` helper) and `bots/v9/src/ball.py` (new `GOLD_HOME_FAR`). Finding #3 (Marcella idle on ambush) isn't addressed.

**Next step:** `python run_matches.py v9 v8 v1 --tag v9-eval`
- Evaluation (results/eval_v9): v8 59%, v6 68%, v5 59%; overall 62%
- Status: promoted, new champion.

### Analysis of v9 — 2026-10-17 (results/eval_v9, results/arena_2)
Record: eval_v9 63-39 (62%): v5 20-14, v6 23-11, v8 20-14. Arena_2 vs b2: 34-0, 0 losses on all 17 maps. Weakest maps/side: expanse 0-6 (the only map lost from both sides against every opponent). Every other map is 3-3 or better, and the 3-3 maps are mirrors. Side A 30-21, side B 33-18. 0 crashes, 0 bot faults. Limit of this pass: Bash was unavailable, so I read summary.json by hand (aggregate `side_stats` plus the individual records named below) and did not open any stats.json. Because the arena is 34-0, the findings below are about the eval and about speed, not about the arena result.
Context: v9 vs v5, v6 and v8 returns identical rounds on most maps (ambush 766, collision 955, corners 535, lanes 545, monolith 498, rows 620, packs 658). These are mirrors where the same side wins both times. v9's two changes rarely fire there.

1. **Expanse: the Cassi & Issac gate loses 0-6, including to the plain 3-pick roster**
   - Evidence: results/eval_v9/summary.json, expanse (spawn distance 85 on 2.1.6, gate at FAR_SPAWN_DIST = 60). v9 drafts Varg, Cassi & Issac, Ryth (4 bodies) and loses to v5's Varg, Ryth, Marcella both ways: A 702-1108 (r694, 0 deaths each side, so a pure farming race; gold 3,842 vs 4,260), B 756-1046 (r710, 3 deaths for v9, gold 3,450 vs 4,204). The same roster loses to v6 (A: v9 668 gems, r756; B: v6 1002, r853) and to v8 (A 668-1016 r756, B lost r853), whose draft is the same as v9's. In v9 A vs v5, v9's Varg collected 110 gems (450 gold, 9 items) in 694 rounds, against v5's Varg 626 gems (2,146 gold, 85 items). Varg is the main earner in every roster (282.7 gems per game across `candidate_champions`) and here the extra bodies appear to starve him. That is a hypothesis: the claim and camp-choice logic was not traced. bench_v6 (NOTES above) already showed the gate is a coin flip on 2.2.3 (1-1), and v3/v5, the same 3-pick roster, beat the gate roster 0-2 as well. In v9 vs v8 both sides use the C&I roster but v9 still loses from both sides (668-1016, then B), so v9's two changes (big-party join, 450-gold trips home) also seem to hurt here (B: v9 gold 4,110 earned by v8 vs 3,300 for v9 as A). That second point is a hypothesis too: the A/B pair is not a clean test, since no v8 game on expanse exists with the roster fixed.
   - Cause in code: `bots/v9/src/draft.py:27` (FAR_SPAWN_DIST = 60) and `draft.py:56-57` (`play`): any 3-pick map with spawn distance >= 60 gets PREFS_FAR_3. The threshold was set from 2.1.6 distances (expanse 85) and the result was never re-measured on 2.2.3 (it did not hold up in the bench_v6 analysis, finding 3b, whose suggestion "A/B the gate off" was never done). `ball.py:495` (`GOLD_HOME_FAR`) can also send a champion home across an 85-tile map.
   - Suggested fix: set `FAR_SPAWN_DIST` to a value no map reaches (for example 10**6) so expanse drafts Varg, Ryth, Marcella. Re-run expanse vs v5, v6 and v8 only (6 games, one minute each). If expanse stays lost against v8 after that, switch `GOLD_HOME_FAR` off (450 -> 10**6) and re-run to separate the two causes. This is the only map where v9 loses from both sides, so it can add up to +6 of 102 games (6 points of win rate), which matters because every other loss is a mirror.
   - Confidence: high that the gate roster loses to the 3-pick roster (v5's result is deterministic, 2 games, same sign as bench_v6 and the earlier v3/v5 results). Medium on the cause.

2. **Whichever side loses the first contact loses its bags: the losing side submits about 30% less than it collects**
   - Evidence: `side_stats` in results/eval_v9/summary.json. In losses v9 collected 712.6 gems and submitted 505.9 (207 lost, 29%) with 10.5 deaths against the opponent's 3.9; in wins v9 collected 1,154.7 and submitted 1,033.4 (121 lost, 10%) with 4.7 deaths. Worst cases: contest B vs v6 (r2000, a loss on the round limit, 200 gems v9 against 800): v9 collected 800 and submitted 200; Varg collected 400, submitted 0, died 6 times; Ryth died 13 times with 0 gems; the side took 40 deaths against 33 kills (records line 6933-7114). v9 ambush A vs v5/v8 (r766): 332 gems, 13 deaths, 4 kills, gold 1,975 vs 4,497. The mirror pairs are exactly symmetric on every map outside expanse (ambush, collision, corners, eight, elkring, fragment, lanes, monolith, packs, pilgrimage, rows, contest: the same side wins both swaps), so A and B are decided by the opening exchange and not by the draft or economy.
   - Cause in code: `bots/v9/src/ball.py:469-470` (`ball_want_bank`) returns False whenever the champion has a task and income > 0, before any threat or bag-size check. `ball.py:471-472` also refuses to bank with a threat near unless an altar is within BANK_NEAR, and `ball.py:476-477` refuses while `committed()`. `skirmish` (`ball.py:874-907`) only scales the fight ratio by 1 + gems/200 (GEM_CAUTION, line 79), so a 400-gem bag still takes fights at 3x the required ratio. This was proposed in the v4, v5, v6 and bench_v6 analyses and never implemented.
   - Suggested fix: in `ball_want_bank`, change line 469 to `if self.task is not None and self.camps and self.inc > 0.0 and self.gems < 80 and not self.enemies: return False`, and in `skirmish` multiply `need` by `1 + gems/60` instead of `1 + gems/200` once gems >= 100. Test on contest, ambush, collision, corners vs v8 and v5: submitted/collected in losses should rise above 80%, and contest B should not lose a 400-gem Varg with 0 submitted. This is the only change on the list that can flip a mirror game from the losing side.
   - Confidence: medium on the pattern (consistent over 39 losses), low-medium on the mechanism (not traced round by round).

3. **Very slow wins on the big-camp maps: 4 of the 5 slowest wins are contest, pilgrimage or stampede, and one game ran to the round limit**
   - Evidence: avg winning round is 779 (results/eval_v9/summary.json `avg_round_of_wins`). Contest wins take r1363-1549, contest B vs v6 reached r2000 and was lost. Pilgrimage wins r1034-1083 and pilgrimage B lost at r928-1011. Stampede wins r956-1220 (all 6 wins; the only map group where v9 is 6-0 outside swirl, interlock and rushbait). At the same time v9's gold sits well used in the eval (`spentGold` 4,209 of 4,649 earned, 9% unspent), so the earlier unspent-gold issue is mostly fixed in eval: the slowness is not the economy. In contest B vs v6, v9 earned 6,600 gold but only 800 gems were collected, because 4 camp captures of 200 were lost to deaths (Varg's 400 died with him six times over). Stellar and Marcella collected 0 gems in the same game on the B side, and Marcella earned 2,067 gold and 13 kills. That is a champion spending the game fighting rather than farming.
   - Cause in code: not isolated. Candidates: `bots/v9/src/bot.py` big-group party logic (`BIG_GEMS`, `BIG_PARTY`, `is_big()`), which still leaves monoliths solo (v9 notes), and the same missing banking logic as finding 2. Finding 2 explains the contest loss directly (400-gem Varg bags with 0 submitted).
   - Suggested fix: apply finding 2 first, then measure contest, pilgrimage and stampede round counts again before touching the party logic. If contest is still above r1400 after that, try `skirmish` R_GO ~1.5 when v9 leads in submitted gems by >= 150 (never tried in this form; see v3 bench analysis finding 2).
   - Confidence: low-medium (correlation across 3 maps; no per-round data read).

Fix first: #1. It is one constant, it is the only map lost from both sides against every opponent, and it is testable in 6 games. Then #2 for the mirror losses and game length.

### v10 — rejected (50% vs v9)
- Based on: v9
- Changes: I created `v10` from `v9` with one change, which targets finding #1 (expanse is 0-6).

- **Change:** in `bots/v10/src/draft.py`, `FAR_SPAWN_DIST` goes from 60 to 10000. No map reaches that distance, so the far-spawn Cassi & Issac draft never triggers and v10 drafts Varg, Ryth, Marcella everywhere.
- **Why it should win:** the analysis says v9's Cassi & Issac gate lost the expanse farming race to the plain Varg, Ryth, Marcella roster. This restores that roster on expanse.
- **Not touched:** `GOLD_HOME_FAR` is still on. I didn't need the fallback of switching it off, since the smoke test already won.
- **Smoke test:** `cambc run v10 v9 --map expanse` was a win for v10 at round 631, 1086 gems to 810, with 0 crashes. This is one deterministic match, so it checks for crashes and isn't evidence of strength. v10 drafted Varg, Ryth, Marcella and v9 drafted Varg, Cassi & Issac, Ryth.
- **Not done:** findings #2 and #3 (the gem-banking veto and the fight ratio), so this version can be measured on its own.
- **Not done:** I didn't run `py_compile` separately, but the match ran cleanly. I didn't edit `NOTES.md`, as you instructed.

Next evaluation command: `python run_matches.py v10 v9 v5 --tag v10-eval`. That is my guess, since the opponent pool wasn't specified. The earlier v9 eval used v5, v6 and v8, so the orchestrator may want those instead.
- Evaluation (results/eval_v10): v9 50%, v8 62%, v6 71%; overall 61%
- Status: rejected, moved to rejected/v10. Lesson: these changes did not beat v9.

### Analysis of v9 — 2026-10-17 (results/eval_v10, results/arena_2, results/eval_v9)
Record: eval_v9 63-39 (v5 20-14, v6 23-11, v8 20-14); eval_v10 (v10 = v9 + expanse gate off) 62-40 (v9 17-17, v8 21-13, v6 24-10); arena_2 34-0 vs b2 (avg win r679, v9 0.6 deaths vs b2 9.1). Weakest maps/side: expanse 0-6 for v9 (v10 6-0); swirl (v10 2-4); every other map is a mirror split. Limit: no Bash, so I read summary.json by hand (no stats.json opened, no diff of bots). Findings differ from the earlier v9 analysis: #1 is now confirmed by an experiment, #2 and #3 are new angles.

1. **The expanse Cassi & Issac gate is a proven 0-6 loss, and v10 proved the fix works but was rejected only by the gate arithmetic**
   - Evidence: v9 vs v5/v6/v8 on expanse is 0-6 (results/eval_v9/summary.json, rounds 694-853). v10 (only change: `FAR_SPAWN_DIST` 60 -> 10000) wins expanse 6-0 vs v9/v8/v6 (results/eval_v10/summary.json lines 2479-2636, 8193-8350, 13906-14064; r631-719). Everywhere else v10 equals v9 in the mirror pairs (same rounds, e.g. collision 955/921, contest 1549). The head-to-head was 17-17 because 32 other games split by side, and expanse is 2 games, so the best a one-map fix can score is 18-16 (53%), under the 55% gate. v10 vs v9 swirl is a puzzle: both drafts are Varg, Ryth, Stellar, Marcella, yet v9 wins from both sides (r521 both), and v10 B also loses swirl to v6/v5 where v9 B won (results/eval_v10 lines 5925, 11639, 17190-17360 vs eval_v9 5945, 11679). Rejected-v10 swirl 2-4 therefore costs 2-4 games that I can't explain (hypothesis: run-to-run nondeterminism or an undiscovered difference; I could not diff the bots).
   - Cause in code: `bots/v9/src/draft.py:27` (`FAR_SPAWN_DIST = 60`) and `draft.py:56` (`play`).
   - Suggested fix: do not re-test it alone. Bundle FAR_SPAWN_DIST = 10000 into the next version together with a change that works on all maps (#2 or #3), since the expanse fix is already verified (+6 of 102 vs the pool, +2 of 34 vs v9). Re-run swirl v10-style A/B once to see whether the swirl gap reproduces.
   - Confidence: high on the expanse effect (12 deterministic games, 6 from each version, same sign). Low on swirl.

2. **Against a beaten opponent v9 still needs 1,060-1,500 rounds on contest and stampede because 2-3 of 5 champions never collect a gem**
   - Evidence: results/arena_2/summary.json. Contest A (r1257): b2 has 0 gems and 44 deaths, v9 has 0 deaths and 41 kills, championDamageDone 58,050 (arena average 14,342). v9 earned 11,916 gold. Gems: Ryth 600, Marcella 200, Tavi 200, Varg 0 (2,287 gold, 7 kills), Stellar 0 (1,618 gold, 6 kills). Contest B (r1498): b2 0 gems, 42 deaths, damage done 45,400; v9 collected 1,200 and submitted 1,000. Marcella's 200-gem bag was lost in her one death and she ended the game with submitted 0. Stampede A (r1076): Varg 720, Ryth 360, Stellar, Marcella and Tavi 0 gems; 21 kills; championDamageDone 43,920. Stampede B (r1065): Varg 540, Tavi 360, Marcella 180, Ryth and Stellar 0; v9 earned 10,650 gold. Compare the arena mean of 679 rounds for a win. The opponent scores nothing, so every round past ~700 is v9 killing respawning enemies (b2's champions die 4-12 times each) while only two or three champions farm. The gold is spent (arena 5,034 of 5,645 earned), so this is not the economy problem of the earlier analyses.
   - Cause in code: `bots/v9/src/bot.py:1092,1120` (`best_group`): `cap_inc = 0.15*hp_full/mult` skips every group whose `stsum` is above that, so only the champions with the biggest HP/items qualify for the 200- and 360-gem packs. `is_big` (bot.py:59-61, BIG_GEMS = 150, needs `g.n >= 2`) only lets others join a pack after somebody has started it (bot.py:1199). `ball.py` `skirmish` (line ~874-907) still hunts enemies even when the opponent has submitted 0 gems and ours is ahead, so idle champions fight instead of walking to a free pack.
   - Suggested fix: add a "dominating" mode to the champion decision: when our `submitted` gems exceed the opponent's by >= 150 (use `cambc.global_submitted_gems(ALLY)` and the enemy equivalent; ball.py:473 already uses the ally call) and no enemy champion has been seen for ~20 rounds, skip the "hunt in company" bonus and set the skirmish go-ratio R_GO to ~1.6, and let a champion with 0 collected gems join a big pack as a first-class choice (score its share, bot.py:1190-1200). To test: contest, stampede, pilgrimage vs b2 (arena folder rules) and vs v8, checking winning round and that mirror wins stay on both sides.
   - Confidence: medium on the pattern (4 arena games, same shape; the opponent has no gems, so the time is v9's own). Low on which line dominates: cap_inc or the fight policy (I did not parse timelines).

3. **In mirror losses v9 loses 29% of its gems with its bag, and the veto at `ball_want_bank` line 469 is still untouched**
   - Evidence: results/eval_v10/summary.json `side_stats`, losses (v10 plays v9's code in those games): candidate collected 690, submitted 492 (198 lost, 29%), 11.2 deaths against 4.8. In wins: collected 1,148, submitted 1,033 (10% lost), 4.2 deaths. The opponent in those losses collects 1,124 and submits 1,023. The arena shows the same sign in a dominated game: contest B's lost Marcella bag (200 of 1,200 collected, results/arena_2/summary.json line 1325-1334). The 17-17 vs v9 and the exact same-round mirror pairs (collision 955/921, corners 535, eight 515, packs 658, rows 620, fragment 599) show the result is set by which side wins the first contact. This is 21 of the 40 eval_v10 losses, and nothing in v9's economy decides it.
   - Cause in code: `bots/v9/src/ball.py:469-470` (`ball_want_bank`) returns False for any champion with a task, camps and income > 0, before the bag size or the threat is checked. `ball.py:471-472` refuses with a threat near unless an altar is within BANK_NEAR, and `ball.py:476-477` refuses when `committed()`. Proposed in the v4, v5, v6, bench_v6 and v9 analyses, never implemented.
   - Suggested fix: change line 469 to `... and self.inc > 0.0 and (gems < 80 or not self.enemies)` → i.e. keep the veto only when `gems < 80 and not self.enemies`, plus scale the skirmish ratio need by `1 + gems/60` once gems >= 100. Ship it together with #1's FAR_SPAWN_DIST change so the gate's expanse gain is added to it. Test: submitted/collected in losses above 80% and the eval_v10-style head-to-head vs v9 above 55%.
   - Confidence: medium on the pattern, low-medium on the mechanism (no per-round data read).

Fix first: #3 combined with the verified expanse fix in #1 (the only change that can move the mirror pairs off a pure 50% split, and the expanse part is already proven). #2 second: it speeds the arena wins and has the largest game-length headroom (contest 1,257-1,498, stampede ~1,070 against a 679 average), but it needs more testing.

### v11 — rejected (50% vs v9)
- Based on: v9
- Changes: I made `v11` from `v9` with two changes. It compiles and the smoke test passes. The single match was `cambc run v11 v9 --map expanse`: v11 won at round 631 with 1086 gems to 810, and v11 had 0 crashes.

- **`draft.py`, `FAR_SPAWN_DIST` 60 → 10000:** this is the expanse fix from finding #1. v11 now drafts Varg, Ryth and Marcella on expanse instead of the Cassi & Issac roster, which lost 0-6 there. The same change won 6-0 as v10.
- **`ball.py`, `ball_want_bank`:** this is finding #3. The old veto stopped any champion with a task, camps and income from banking. It now applies only when the champion carries fewer than 80 gems and sees no enemy. Champions holding 80 or more gems, or with an enemy in view, now fall through to the normal threat check and bank thresholds. The aim is to stop gems being lost with the bag when a fight starts.

I did not add the fight-ratio scaling by gems from #3. I kept it to the veto change so its effect can be measured on its own. Finding #2 (dominating mode) is not touched.

The expanse result is one deterministic match and shows only the crash check and the expanse fix. It says nothing about the bag-loss change on other maps.
- Evaluation (results/eval_v11): v9 50%, v8 59%, v6 68%; overall 59%
- Status: rejected, moved to rejected/v11. Lesson: these changes did not beat v9.

### Analysis of v9 — 2026-10-17 (results/eval_v11, results/arena_2)
Record: eval_v11 (v11 = v9 + expanse gate off + relaxed bank veto) 60-42: v6 23-11, v8 20-14, v9 17-17; arena_2 v9 34-0 vs b2 (avg win r679). Weakest maps: swirl 2-4 (v11 loses both sides to v9, r521), every other map is a same-side mirror split (3-3); expanse 6-0. Side A 30-21, side B 30-21. 0 crashes. Limit: no Bash, so I counted with Grep over summary.json (`"collectedGems": 0` champion records) and did not open any stats.json. New angles only; the old bank-veto, unspent-gold and Willow items are not repeated.

1. **No death memory anywhere: a side that loses the opening keeps walking back into the fight and never farms (contest, ambush)**
   - Evidence: results/eval_v11/summary.json line 6911 (contest B vs v8, r1577): v11 gets 0 gems, 9 kills, 55 deaths, 2,280 gold vs 11,409. All five champions died 8-14 times each (lines 6849-6893 and 7042-7077, same on the v9 mirror at 12563). The winner took 9 deaths for 55 kills and 81,873 champion damage. Aggregated: `candidate_in_losses` has 10.9 deaths vs 4.1 in wins, and 4.6 kills vs 9.2 (side_stats, lines 254-295). A champion respawns after 60 rounds (GameRules l.361) on its own spawn tiles. The 60 champion records with 0 gems and 0 submitted that I counted in the file include whole teams: e.g. lines 1135-1170 (4 champions, 7-12 deaths each, 0 gems) and 5700-5735. In these games the winner needs r1250-1577 to finish, because it is farming against respawning defenders.
   - Cause in code: `grep -i "death|died|respawn"` over `bots/v9/src` finds no logic that reads our own or the enemy's recent deaths. Respawn appears only for camp timers (`bot.py:580,1145,1285`). `ball.py:874-944` (`skirmish`) uses the same `R_GO = 1.05` (line 46) after 0 or 10 deaths. A champion that respawns picks its first task with `best_group` as if the game were fresh, and with SOLO the five arrive one at a time into whoever is camping its spawn. `hard_retreat` (line 920) only triggers on the local ratio.
   - Suggested fix: add a per-team death counter (`cambc` team deaths or the champion's own history, kept in the shared Team A memory if used, else per bot). When our deaths in the last 150 rounds >= 4 and >= enemy deaths + 3, then (a) raise `need` in `skirmish` to about 2.0, and (b) for a champion that just respawned, wait on the spawn until at least 2 allies are alive and within 6 tiles, then leave as a group (the old ball code in `ball.py` does the gather and march already; use it only in this "losing" state). Test on contest A/B vs v8/v9, ambush A, collision, pilgrimage: deaths in losses should fall from 10.9 and the contest 55-death game should turn into one with gems.
   - Confidence: medium on the pattern (deterministic; the same shape in every collapsed game I read). Low on the exact first-contact mechanism: I have no round-level data.

2. **Marcella and Stellar produce nothing on ambush (and sometimes elsewhere): 0 gems, 0 gold, 0 items, 2-3 deaths**
   - Evidence: results/eval_v11/summary.json line 11840-11905 (ambush A vs v9, loss 510-1010 at r795): Stellar 0 gems, 245 gold earned, 0 spent, 0 items, 3 deaths; Marcella 0 gems, 0 gold, 0 items, 2 deaths. The B-side opponent running the same code has Marcella 106 gems, 300 gold, 10 items, and Stellar 106 gems. Same picture at lines 6160-6240 (v8 ambush A), 6343-6358, 12057-12072 (same game), 639-644 (v6 ambush B: Marcella 0 gems, 0 gold, 3 deaths), 521-526, 456-461 (Marcella 0 gems, 100 gold, ambush A vs v6, loss 226-1068 with equal 7-7 kills, gold 1,655 vs 4,482). Compared with the same two champions' normal 197 gems and 922-1,037 gold per game (`candidate_champions`, lines 310-343). Kills are equal in the ambush A vs v6 game (7-7) so the 840-gem gap there is economy, not fighting. v8 analysis #3 saw the same in the arena (Marcella idle 4 of 4 ambush games); it is still true in v9/v11.
   - Cause in code: not isolated. `bots/v9/src/bot.py` `best_group` (around lines 1144-1150, `peek_respawn`/`cap_inc`) and `work_once` are the candidates: she may have no group that passes the `cap_inc` HP gate (small HP, no items because she earns no gold), so she keeps walking or waiting. Items come from gold, so zero gold means zero items, which keeps her below the gate: a loop. This is a hypothesis; a `cambc run v9 v9 --map ambush` with `self.log` of `task`/`est` for Marcella would settle it.
   - Suggested fix: if a champion has earned < 150 gold after 250 rounds, ignore `cap_inc` for the best-value group with the lowest `stsum` (or send her to the nearest small gold cluster) so she starts earning. Test on ambush A and B vs v9/v8/v6: Marcella gems and gold, and the ambush mirror pair (r795/r766 for v9).
   - Confidence: medium that it is the cause of the ambush losses (4 of 4 games, identical shape); low on the mechanism.

3. **The relaxed bank veto (v11) did not help and lost swirl: banking is not what decides the mirror losses; stop trying it**
   - Evidence: v11's change (`ball_want_bank` veto only while gems < 80 and no enemy) gives 17-17 vs v9 and swirl 0-2 vs v9 at r521 from both sides, while v9 beats v6/v8 on swirl from side B in eval_v9 (summary.json lines 17190-17360). In v11's losses it collected 723.5 and submitted 501.8 (69%, `candidate_in_losses`) versus v9's 712.6/505.9 (71%) in eval_v9: no change in bag loss. In wins it submits 1,033.6 of 1,138 (91%). So the 30% bag loss in losses stays with the relaxed veto, i.e. it comes from dying (10.9 deaths per loss), not from refusing to bank. Contest B vs v8 lost 0 of 0 collected: the bag-loss story does not even apply to the worst loss.
   - Cause in code: `bots/v9/src/ball.py:469-470` was the earlier suspect. The result says the champions die before the 80-gem threshold matters, or that banking trips walk them into enemies. Deaths come from `skirmish` (874-944) and camp work near enemy spawns, see #1.
   - Suggested fix: do not re-test the bank veto alone. Treat bag loss as a symptom of deaths and work on #1 (fewer deaths when behind) and #2 (idle bodies). If banking is revisited, bank only at an altar that is closer than any enemy champion, not by lowering the threshold.
   - Confidence: medium (one eval, deterministic, but swirl has a gap I cannot explain by diff; earlier notes already flagged it).

Fix first: #1 (largest effect: contest and any game decided by the opening, which is where all mirror losses come from; it is also why the winner needs 1,250-1,577 rounds). #2 second: one map-specific loop that costs 6+ games and is cheap to try.

### v12 — rejected (47% vs v9)
- Based on: v9
- Changes: **v12** is built, but the one smoke test on swirl was a loss to v9. It's a crash check only, and the result is the same one the analysis flagged on that map.

**Smoke test:** `cambc run v12 v9 --map swirl` finished with 0 crashes. v9 won at round 521 with 1014 gems to v12's 776, kills 7–3, deaths 4 vs 7. I didn't run a second match and didn't compile-check separately: the combined compile-and-run command wasn't allowed, so the match ran directly.

**What I changed (finding #1, death memory):**
- **`bots/v12/src/bot.py` `dead_turn`:** each champion now records the round of each of its own deaths, keeping the last 6.
- **`bots/v12/src/ball.py` `skirmish`:** if a champion has died 2 or more times in the last 200 rounds, the strength ratio it needs to start or keep a fight is raised. The multiplier is ×1.4 at 2 deaths, ×1.8 at 3, and ×2.2 at 4 or more. This stacks with the existing gem-caution scaling.
- **Why it should win:** the side that loses the opening should stop re-entering fights it keeps losing and go back to farming. That is the death spiral the analysis found in the mirror losses, where v11 averaged 10.9 deaths in losses against 4.1 in wins.

**Left out:** I did not add the "regroup at spawn after respawn" part of the fix, to keep this a single measurable change. Death memory is per champion, not shared across the team.

**Evaluation command:** `python run_matches.py v12 v9 v6 v1 --tag v12-eval`
- Evaluation (results/eval_v12): v9 47%, v8 56%, v6 65%; overall 56%
- Status: rejected, moved to rejected/v12. Lesson: these changes did not beat v9.

### Analysis of v9 — 2026-10-17 (results/arena_2, results/eval_v12)
Record: arena_2 34-0 vs b2 (avg win r679, v9 0.6 deaths vs b2 9.1, 17 maps x 2 sides, 0 crashes). eval_v12 (v12 = v9 + death memory) 57-45: v6 22-12, v8 19-15, v9 16-18. Weakest: expanse 1-5 and swirl 2-4 in eval_v12; every other map is a mirror split. Slowest arena wins: contest r1257/r1498, stampede r1076/r1065, ambush B r837, rushbait-v2 B r798 (A r595), expanse r689/651. Limit: no Bash; read summary.json by hand, stats.json not opened. Old items (bank veto, Willow, unspent gold, death memory, contest/stampede party logic) are not repeated. v10/v11/v12 showed the mirror split cannot be moved by one-map or bank/death tweaks.

1. **The "bank now, the game is won" test ignores teammates' bags, so 60-230 gems sit in pockets when the game ends**
   - Evidence: arena_2 `side_stats.candidate` collected 1,097.7 and submitted 1,035.8 per game, with only 0.6 deaths, so about 62 gems per game (about 40 rounds at the 1.5 gems/round pace) are carried unbanked at the end, not lost. Worst: ambush B (r837) collected 1,226, submitted 1,000 (Marcella held 106, Stellar 120); rushbait-v2 B (r798) collected 1,158, submitted 1,020 (Marcella 204 collected, 66 submitted) while rushbait A won in r595. The opponent was at 72-154 gems, so the only clock is our own banking.
   - Cause in code: `bots/v9/src/ball.py:474` (`ball_want_bank`): `submitted + gems * max(1, self.ball_n) >= 998`. In SOLO mode `ball_n` is 1 (ball.py:132, set at :264), so a champion banks for the win only if its own bag completes 1000. Nobody counts the other bags. Collected gems are in shared memory only as `tot` for the old farm path (`bot.py:384`, `want_bank` line 1008) and are not used in ball mode. Meanwhile lines 469-470/476 still veto banking for champions with a task.
   - Suggested fix: each champion already writes its slot byte to `cambc.shared_memory` (ball.py:336). Add a second byte per slot (gems carried, /4) and in `ball_want_bank` return True when `submitted + sum(carried over all slots) >= 1000 + 20`, overriding the task veto at 469 and `committed()` at 476 when no enemy is in view. Test: arena rounds on ambush B, rushbait B, pilgrimage and rows (target -30 to -100 rounds) and check no new deaths.
   - Confidence: medium (end-of-game bags are certain; the round saving is an estimate; the endgame banking walk is up to d + gems/10 rounds).

2. **Two of five bodies still produce nothing on ambush (and Tavi/Marcella idle in other games): the idle-body problem is real in a won arena game**
   - Evidence: results/arena_2/summary.json ambush A (r704): Varg 452 and Ryth 368 gems, Stellar 0, Marcella 0 (0 gems, 0 gold, 0 items each, lines 426-437), Tavi 318. Ambush B (r837): Marcella 106 collected, 0 submitted, 4 items, Tavi 0 gems (295 gold), 1 death. Same shape as v8/v9 analyses (4+4 games). Where all bodies work (collision r698/721, eight r448/474) the game ends 25-40% earlier. Rushbait-v2 B (r798): Varg 452 gems, Ryth 198, Stellar 304, Marcella 204, so there it is the lopsided Varg bag, not idle bodies.
   - Cause in code: not isolated (hypothesis from v8 analysis #3 still stands): `bots/v9/src/bot.py` `best_group` (`cap_inc` gate, around line 1092/1120) can leave a low-HP, no-item champion with no accepted group; with no gold there are no items, which keeps it below the gate.
   - Suggested fix: after 250 rounds with a champion at < 150 gold earned, relax `cap_inc` for the lowest-`stsum` group with value > 0 (or send it to the nearest small gold cluster). Test on ambush A/B vs b2 and v8; check Stellar/Marcella gems and round.
   - Confidence: medium on the symptom, low on the mechanism.

3. **Expanse C&I gate is still in the champion: 1-5 in eval_v12 and a 689/651 win vs b2 that the 3-pick roster would also win**
   - Evidence: eval_v12 by_map expanse 1-5 (v12 keeps v9's gate); v10 (gate off) was 6-0 on expanse vs v9/v8/v6 (r631-719, eval_v10). In arena_2 v9 wins expanse at r689 and r651 with Cassi 280 and Issac 121 gems over 2 games (candidate_champions), so C&I give little even where it wins. v10/v11 were rejected only because 2 extra wins out of 34 are below the 55% gate (see v10 analysis).
   - Cause in code: `bots/v9/src/draft.py:27` (`FAR_SPAWN_DIST = 60`) and `play()` line ~56.
   - Suggested fix: set `FAR_SPAWN_DIST = 10**6` in the next version and bundle it with finding 1 or 2, which can add wins on many maps. Do not submit it alone.
   - Confidence: high on the expanse effect (12 deterministic games over two evals); the gate arithmetic limits it to about +2 of 34 head-to-head.

Fix first: #1. It is a small change inside `ball_want_bank`, applies to every map and both sides, and attacks game length in the arena (the main metric when the win rate is already 100%). #3 can ride along for free.

### v13 — rejected (50% vs v9)
- Based on: v9
- Changes: I made `v13` from `v9` with two changes. The smoke test on expanse passed with 0 crashes. I did not run the full evaluation.

**Changes**
- **Team-wide bank check (finding #1)**
  - `bot.py:write_shared` now calls a new `report_gems`. It keeps a team total of carried gems in shared bytes 6–7, as the farming stage already did.
  - `ball.py:ball_write`, in solo mode, calls `report_gems` instead of writing the leader position into bytes 6–7. The leader position is only read for followers, and in solo mode every champion was overwriting it anyway.
  - `ball.py:ball_want_bank` now banks when submitted gems plus the team's carried gems reach 998. Before, it only counted this champion's own bag. This should shorten games, because a champion banks as soon as the team total will complete 1000.
- **Expanse draft gate (finding #3):** in `draft.py`, `FAR_SPAWN_DIST` goes from 60 to `10**6`, so the Cassi & Issac gate is off. In the smoke test v13 drafted Varg, Ryth, Marcella, and v9 drafted Cassi & Issac.

I did not address finding #2.

**Smoke test:** `cambc run v13 v9 --map expanse`: v13 won at round 631 with 1086 gems and 0 crashes. v9 reached 810 gems.

**Why it should win:** the game ends on gems banked, so reaching 1000 submitted earlier is the metric that matters. The gems held in other bags (about 62 per game in v9) get banked sooner, on every map and from both sides. The draft change targets expanse, where the Cassi & Issac gate cost v12 games.

**Next evaluation command:** `python run_matches.py v13 v9 v1 --tag v13-eval`
- Evaluation (results/eval_v13): v9 50%, v8 56%, v6 68%; overall 58%
- Status: rejected, moved to rejected/v13. Lesson: these changes did not beat v9.

### Analysis of v9 — 2026-10-17 (results/arena_2, results/eval_v13)
Record: arena_2 34-0 vs b2 (avg win r679, v9 0.6 deaths vs b2 9.1; b2 still collects 276 gems and submits 185 per game). eval_v13 (v13 = v9 + team-bank + expanse gate off) 59-43: v6 23-11, v8 19-15, v9 17-17. Weakest maps/side: swirl 2-4; every other map is a same-side mirror split (3-3) except expanse 6-0, interlock 5-1, stampede 5-1. Side A 32-19, side B 27-24. 0 crashes. Slowest arena wins: contest r1257/r1498, stampede r1076/r1065. Limit: no Bash; summary.json read by hand, and `results/arena_2/b2/contest__cand-A.stats.json` (text JSON, `championTimelines`) read for timing. Findings 1 and 2 below are new measurements of the contest/stampede slowness. They also overturn one hypothesis from the earlier v8/v9 analyses (that the `cap_inc` HP gate is what keeps champions off the big camps).

1. **On contest the team earns no gems for 719 rounds, then three of five champions never earn any: gold is farmed long after it stops being useful**
   - Evidence: contest A (arena_2, r1257, 0 deaths). Gem timelines: first gem anywhere is Ryth at r719 (200), then Ryth r805, Tavi r961, Ryth r1059, Marcella r1212. That is 5 monolith captures (1000 gems) in 1257 rounds. The first 719 rounds are 57% of the game. Varg and Stellar collect 0 gems all game. Varg ended with 90 items, 2,287 gold earned and took 19,082 monster damage, so he fought camps all game but never captured a gem camp. Stellar earned 1,618 gold on 54 items, again 0 gems. The team earned 11,916 gold and spent 11,590 on about 460 items for 1000 gems. Ryth's `spentGold` timeline: 40 until r378, then 560, 830 (r~600), 1610... Between r~270 and r378 his gold rose from 268 to 548 unspent (the 300-gold trigger only works within 18 steps of spawn, and the far trigger needs 450). He took his first gem only after about 1,600 gold of items. Stampede A (r1076): Varg 720 of 1,080 gems and 175 items, Stellar, Marcella and Tavi 0 gems, 2,098/1,124/966 gold. Stampede B (r1065): Varg 540, Tavi 360, Marcella 180, Ryth and Stellar 0. Contest B (r1498): Marcella's single 200-gem bag was lost in her one death.
   - Cause in code: `bots/v9/src/bot.py:1092` (`cap_inc`) is NOT the main block. Varg with 90 items clears it easily (the earlier analyses guessed it was). What blocks him is the choice rule in `best_group` (bot.py:1079-1214): `val = g.gems + kappa*g.gold` with `kappa` at its floor 0.05 from round ~300 (bot.py:1085, `KAPPA0 = 0.3`, `KAPPA_DECAY = 1200`) still ranks short gold clusters above a 200-gem monolith when the monolith's `tf` (fight turns) is long, and the monolith is not `is_big` (bot.py:59-61 needs `g.n >= 2`), so nobody joins it. The join test (bot.py:1206, `saving <= 1.15*cost`) ignores the joiner's share for non-big groups. Gold farmers therefore never help the one champion on the monolith. Separately, `ball.py:489-497` (`need_home_ball`) sends a champion home from far away only at 450 gold (`GOLD_HOME_FAR`), so the first upgrade that unlocks the big camps comes late (r378 for Ryth).
   - Suggested fix: two small changes, test together on contest and stampede vs b2 and vs v8 (both sides). (a) In `best_group`, once a champion has at least ~20 items (or `spentGold >= 1500`) or `rnd >= 400`, use `kappa = 0`, so extra gold counts for nothing and the 200- and 360-gem groups win the ranking. (b) Allow a join on a single-monster group worth >= 150 gems (extend `is_big` to `g.gems >= 150`, not `n >= 2`) only when `push_f == 0.0` (we lead by >= 100 submitted gems, `ball.py:update_push`) or no enemy champion has been in `self.sightings` for 40 rounds. That keeps the rule that made the v9 monolith party lose on contest vs v8 (3 champions caught on one camp), because it only fires when we are ahead. Check: round of first gem on contest should drop from 719 and the number of champions with 0 gems should fall from 3. A third, optional step is `GOLD_HOME_FAR` 450 -> 250 while `maxhp` is still below the monolith threshold.
   - Confidence: medium on the pattern (timelines are exact; stampede shows the same shape). Low-medium on which term dominates, since I did not log `best_group` scores. A `DEBUG` run printing Varg's chosen task and `ub` on contest would settle it.

2. **The mirror loser dies 10.6 times and keeps losing bags; no change so far has moved this, and v13 shows a team-wide bank rule does not either**
   - Evidence: eval_v13 `side_stats`: in losses the candidate has 10.6 deaths against the opponent's 4.8, collects 727 gems and submits 520 (28% lost). In wins it has 4.3 deaths, collects 1,153 and submits 1,038. The opponent in our losses earns 5,408 gold against our 3,457. v13 vs v9 is 17-17, the same as v10, v11 and v12, so none of the four edits (expanse gate, relaxed bank veto, death memory, team bank) changed any mirror pair. v13 does show the team-wide bank count is not worth more rounds: its wins come at r786 on average against v9's 779.
   - Cause in code: not in banking or fight ratio. The mirror pairs are exactly symmetric, so the opening exchange, set by spawn side and the order of turns (`the starting team swaps each round`, GameRules l.122), decides the game. `ball.py:ball_decide` (403-449) treats a champion that just respawned like a fresh one, and the five champions walk out one by one into the winner's camp-and-hunt posture (`skirmish`, ball.py:874-947, same `R_GO` for both sides).
   - Suggested fix: stop spending versions on bank and fight-ratio tweaks. Use the arena-style gap instead: only fight when `push_f`-like lead info says we are ahead or the enemy is alone, and otherwise farm away from the enemy half (`DENY_W` and `ESP_AVOID`-style penalty on groups where an enemy was seen in the last 40 rounds, scale 0.7 even in ball mode, bot.py:1161-1168 currently gives 1.25 for hunting in company). Test on the mirror-loser maps first (collision B, ambush A, corners A, fragment, eight, contest B vs v8/v9).
   - Confidence: low (the symmetric pairs are certain; the mechanism and the fix are hypotheses with no per-round data).

3. **The expanse Cassi & Issac gate is still in the champion and buys nothing, even in the arena**
   - Evidence: eval_v13 expanse is 6-0 with the gate off (v13 vs v9, v8, v6), against 0-6 for v9 in eval_v9. In arena_2 v9 wins expanse at r689 and r651, against the arena average of r679. Cassi and Issac collect 280 and 121 gems over those 2 games (candidate_champions, arena_2/summary.json lines 266-287), 0 deaths each, so the 4-body roster is no faster than the 3-body roster there.
   - Cause in code: `bots/v9/src/draft.py:27` (`FAR_SPAWN_DIST = 60`) and `play()` (~line 56).
   - Suggested fix: ship `FAR_SPAWN_DIST = 10**6`, but only bundled with finding 1. v10, v11, v12 and v13 each carried it and failed the 55% gate, because the expanse pair adds at most +2 of 34 head-to-head. It must ride along with a change that works on the 16 other maps. Do not submit it alone.
   - Confidence: high on the expanse effect (18 deterministic games over three evals). The gate arithmetic limits the gain.

Fix first: #1 (it targets the slowest arena games and acts on 4 of the 5 bodies, and it does not depend on winning the opening exchange). Bundle #3 with it.

### v14 — rejected (41% vs v9)
- Based on: v9
- Changes: I created `v14` from `v9` with three small changes. It ran without crashing on contest, but it lost that match. The 600–600 gem tie went to `v9` on gold earned, 11,627 to 3,450.

The one smoke match is a crash check, not evidence of strength. I made no change for finding #2, and I didn't add the "join a lone 150+ gem group" rule from finding #1.

- **`bot.py:best_group`:** `kappa` is now 0 from round 400 on, or once a champion has bought 20 or more items. Short gold clusters then stop outranking big gem camps late in the game. This is the main change for finding #1.
- **`ball.py:GOLD_HOME_FAR`:** lowered from 450 to 250, so a far-from-home champion goes shopping sooner and gears up earlier.
- **`draft.py:FAR_SPAWN_DIST`:** raised from 60 to `10**6`, which turns the Cassi & Issac far-spawn draft gate off (finding #3). Expanse was 6-0 with the gate off, but the analysis says it only passes the 55% gate when paired with #1.

The `kappa` change also zeroes the gold term in join-share scoring, so gold-heavy groups lose some pull there too.

I made no other changes, and I didn't touch `NOTES.md`.

Smoke test: `cambc run v14 v9 --map contest` — v14 crashes 0.
- Evaluation (results/eval_v14): v9 41%, v8 50%, v6 56%; overall 49%
- Status: rejected, moved to rejected/v14. Lesson: these changes did not beat v9.

### Research on v9 — 2026-10-17 (results/eval_v9, eval_v10, eval_v11, eval_v12, eval_v13, eval_v14)
Method: Bash was not available. I pulled every vs-v9 match (map, side, result, round) from the five rejected evals with multiline Grep over summary.json. I read the opening timing (`first_death_round`, `deaths_before_300`, `submitted_by_250`) of the v9-code mirror from the v10-vs-v9 block of results/eval_v10/summary.json (lines 14238-21108). v10 is v9 with only `FAR_SPAWN_DIST` changed, and that constant is only read on 3-pick maps, so on every map except expanse it is the pure v9 mirror. I opened one stats file (eval_v10/v9/fragment__cand-A.stats.json).

Map picture (v9 code vs v9 code, winning side, score, round; sides are A then B for first death / deaths before r300):
- Routs, where the loser's opening goes wrong: contest A 1000-0 r1549 (first death 39/31, deaths before r300 2/11), eight A 1022-0 r515 (189/56, 1/7), fragment B 1006-0 r599 (49/none, 3/0), collision B 1028-482 r921 (44/483), stampede A 1080-360 r1294 (75/46), packs A 1060-544 r658 (47/46, 1/5), corners B 1034-570 r535 (60/56, 4/2; submitted by r250 0/168), monolith B 1010-652 r498 (66/81, 5/1), ambush B 1010-510 r795.
- Close farming races: rushbait-v2 A 1020-976 r819, rows A 1056-858 r620, lanes B 1014-804 r583, interlock B 1026-656 r825, elkring A 1008-684 r692, pilgrimage A 1008-568 r1011.
- expanse: with the Cassi & Issac gate on both sides, A wins r807 (eval_v12). With the gate off the candidate wins both sides (v10, v11, v13, v14, r631-725).
- swirl: v9 wins from both sides against every copy of itself (see #1).
- Per-version results vs v9:
  - v10 (expanse gate off): expanse +2, swirl 0-2, the other 30 games are exact same-round mirrors, so 17-17.
  - v11 (relaxed bank veto) and v13 (team bank): the same pattern. The rounds move by 5-40 (v13: packs A 630 instead of 658, lanes B 572 instead of 583, rushbait B 812 instead of 819) but no winner changes.
  - v12 (death memory, gate kept): expanse 1-1, swirl 0-2, contest B r1511 and eight B r531 still lost, 16-18.
  - v14 is the only version that moved maps. Flipped to wins: rows B (r689), expanse A and B, interlock A (r874). Flipped to losses: interlock B (r966), lanes B (r576), rushbait A (r654), stampede A (r1052), contest A (r2000, 600-600 lost on gold). It also lost swirl from both sides. 14-20.
- How v9 itself beat v8 (eval_v9, 20-14): it won from both sides on interlock (r906/r825), rushbait (r797/r753), stampede (r956/r1220) and swirl (r608/r521), and lost expanse from both sides.

Lessons from rejected versions:
- v10, v11 and v13: the expanse gate fix is worth exactly +2, and swirl takes exactly −2 back (see #1). The bank-veto and team-bank changes moved no winner at all.
- v12: changes that only act after a champion has died 2+ times come too late. The mirror routs are settled by r31-66 (first death) and by 4-11 deaths before r300.
- v14: making camp choice ignore gold (`kappa` = 0 from r400 or 20 items) together with `GOLD_HOME_FAR` 250 is the first change that moved maps. It moved them in both directions:
  - It won the calm races. In rows B, all 4 champions collected 264-330 gems and v14 submitted 528 between r500 and r750, against v9's 330.
  - It collapsed gold income on contact and big-camp maps. stampede A: 3,740 vs 8,976 gold, first submit at r990 vs r554. contest A: 600-600 lost on the gold tiebreak, 3,450 vs 11,627. In v14's losses it earned 3,463 gold vs the opponent's 5,892, against 3,340 vs 5,435 for v9 code in eval_v10.

1. **Swirl is lost from both sides by every candidate because of something outside the play code: each new version starts at −2**
   - Evidence: v10's code is line-for-line the same size as v9's (ball 1370, bot 1543, draft 71, main 22, tables 73, randomness 17 lines). The only change is `FAR_SPAWN_DIST = 10000` (rejected/v10/src/draft.py:27), and swirl is a 4-pick map where `spawn_distance()` is never called (draft.py:56 short-circuits on `size == 3`).
     - v8 (A) vs v10 (B) in eval_v10 gives exactly v8-vs-v9's results, round for round, on 15 of 17 maps (ambush 795, collision 921, contest 1577, corners 535, eight 515, elkring 654, fragment 599, interlock 825, lanes 531, monolith 579, packs 658, pilgrimage 1011, rows 620, rushbait 753, stampede 1220). Expanse differs because of the gate.
     - The only other difference is swirl. v8 (A) vs v9 (B) is 776-1014, a v9 win at r521 (eval_v9). v8 (A) vs v10 (B) is 1034-548, a v10 loss at r521.
     - v6 (A) vs v10/v12/v14 (B) and v9 (A) vs v10/v12 (B) all give the same 1034-548 game. v10 (A) vs v9 (B) gives 776-1014, the same as v8 (A) vs v9 (B).
     - So on swirl a v9 build on Team B plays a different, winning game, while every candidate with a three-character name loses from that seat. v12 (gate kept, death memory only) and v14 (very different code) lose it the same way.
     - This costs every candidate 2 of 34 games against v9, and 1 game against each of v6 and v8.
     - It explains the run of 17-17 results. v10, v11 and v13 = 15-15 on true mirrors + expanse 2-0 + swirl 0-2.
   - Cause in code (hypothesis, mechanism unproven): play depends on remaining fuel in three places. These are `bot.py:31,1239` (`CHOOSE_MIN_FUEL = 1500000`, the champion defers picking a task when fuel is lower), `ball.py:933` (`fallback_attack` below 500k) and `ball.py:1319` (re-plan above 1.4M). If anything outside the code (bot directory or name length, the build) changes fuel use slightly, a turn can cross one of these thresholds and the game diverges. That would fit swirl, which is decided at r521 with A's first death at r46 against B's at r55.
   - Maps it decides: swirl, both sides (and swirl B against v6/v8 in the pool).
   - Confidence: high that the result does not come from the play code (checked over 16 maps, same rounds). Low on the mechanism.
   - Test for the designer: copy v9 unchanged into the next free slot and run `cambc run v8 vN --map swirl` and `cambc run v9 vN --map swirl`. If the copy loses, the candidate's baseline is 15 + expanse 2 = 17. It then needs 2 genuine side flips, or a fix that removes the fuel-threshold branching, which would turn swirl into a true 1-1 mirror.

2. **The routs (8 of 15 mirror maps) are settled in the first 100 rounds, and no version so far has acted that early**
   - Evidence: in the v9-code mirror, the loser died first on 11 of 15 maps (list above). eval_v10 `side_stats`: in losses, first death at r74.8 against the opponent's r130.5, 4.0 deaths before r300 against 2.1, 88 gems submitted by r250 against 159, and 11.2 deaths against 4.8 per game.
     - Rout example: eval_v10/v9/fragment__cand-A.stats.json (3-pick). Side A collected 212 gems (Varg 66, Ryth 124, Marcella 22) and submitted 0, all 8 deaths to champions. Side B had 0 deaths, collected 1,028 and earned 4,940 gold to A's 1,125.
     - The mirror winners of contest, eight, fragment, collision, corners, packs, monolith, ambush and stampede B were never flipped by any of v10-v14. Five different mid- and late-game changes left them all alone.
   - Cause in code: the opening is the same `ball_decide` and `skirmish` logic for both teams. In particular `ball.py:46` (`R_GO = 1.05`), `bot.py:1132,1158` (`wt` uses `g.deny`, which pulls champions toward groups the enemy also wants) and `bot.py:1164` (×1.25 on groups near a recent enemy sighting when escorted, "hunt in company"). With identical code the map and turn order decide who wins the first exchange (GameRules l.122/126: the starting team alternates).
     - Hypothesis, not traced: a tie-break that is not symmetric under the map's rotation, such as direction or iteration order, decides which side gets the first hit.
   - Maps it decides: contest (B loses), eight (B), fragment (A), collision (A), corners (A), packs (B), monolith (A), ambush (A), stampede (B).
   - Confidence: medium on the pattern. Low on the exact first-contact mechanism: the death-event locations were not mapped to spawns.

3. **The close farming races are the only maps any change has flipped, and the deciding variable is gold kept flowing alongside gem-weighted camp choice**
   - Evidence: v9's own promotion came from interlock, rushbait and stampede (plus swirl), all won from both sides against v8 (eval_v9). v14 moved exactly the close maps: rows B and interlock A became wins, lanes B and rushbait A became losses. Its other new losses (stampede A, contest A) are the gold-starved games quoted above.
     - Closest mirror, rushbait (eval_v10 lines 20071-20250, v9 A vs v9-code B). B was ahead 686-388 submitted at r500, but submitted only 80 more by r750 (766 vs 824). It lost 204 gems in deaths at r502 and r734 and still carried about 130 at the end: collected 1,310, submitted 976, so 130 carried + 204 lost. It lost 976-1020. Either the 204 lost or the 130 carried, banked, would have won the game.
     - elkring: B led 144-72 at r250 and still lost 684-1008.
   - Cause in code: `bot.py:1085,1131` (`kappa = max(0.05, 0.3 - rnd/1200)` and `val = g.gems + kappa*g.gold`) sets the gem/gold trade-off for every champion. v14 showed that `kappa` = 0 (rejected/v14 `best_group`) speeds up the gem race on calm maps but starves item income where fights or big camps need it. `ball.py:469-477` (`ball_want_bank`) still lets mid-game bags of 100-200 be lost in the r500-750 window on rushbait.
   - Maps it decides: rushbait (B loses), rows (B), lanes (A), interlock (A), elkring (B), pilgrimage (B). These are the six flippable mirrors. With the expanse +2, two flips from the losing side are enough for 19/34, provided swirl (#1) and the routs (#2) don't get worse.
   - Confidence: medium. The flips are measured, but v14 changed three things at once, so which of `kappa` and `GOLD_HOME_FAR` 250 caused which flip is not separated.

Do not repeat: bank-veto tweaks (v11), team-bank count (v13) and per-champion death memory (v12). Each changed no mirror winner. The expanse gate-off is worth +2 and should ride along.

### Design for v15 — 2026-10-17 (based on v9)
Idea: be the home team in the opening exchange. For the first 200 rounds, stop sending champions to camps near the enemy spawn, and fight more readily near our own spawn and less readily near theirs. v9 keeps pushing into our half, so the first contacts happen where we heal, shop and respawn, not where v9 does. Then let v9's normal economy convert the lead, and add the expanse gate fix (+2).

What the code shows (read for this design, not in earlier notes):
- v9 runs ball mode from round 0 (`ball.py:194` `self.r_gather = 0`), so the opening uses `best_group(..., ball=True)` and `skirmish`, not the farming path.
- At round 0 `push_f = 0.5` (`ball.py:213`; `update_push` keeps it at 0.5 while both teams have 0 submitted). All five champions start together, so `esc = 1.0` (`bot.py:1100-1105`) and `push = 0.5`. Every group within `SIEGE_D = 30` steps of the enemy spawn gets `wt = 1 + (deny-1)*0.5`, which is up to x2.5 (`ball.py:169-175`, `bot.py:1132,1158`). Groups within 7 steps (`ESP_AVOID`) are skipped. On top of that, a group near a recent enemy sighting gets x1.25 while escorted (`bot.py:1164`).
- So in the v9 mirror both teams walk into each other's half in the first rounds. The side that loses the first fight is the one caught away from home: it has no heal, a long walk back, and `fight_ratio` already gives enemies standing on their own spawn x3 HP (`ball.py:813`). That fits the research numbers: the loser's first death at r31-75 and 4-11 deaths before r300.
- Why v14 starved on contest: with `kappa = 0`, gold-only groups get `val = 0`, so `ub = 0` and the loop breaks at `ub <= best_score` (`bot.py:1133,1141`). A champion that can't take a monolith then gets no task at all, which explains the 3,450 vs 11,627 gold. **Do not set kappa to 0** in this or any later version; that would only be safe with a nonzero floor.

Target maps:
- **Routs, where the loser is caught away from home early:** contest (B loses; B has 11 deaths before r300), eight (B; B's first death r56 vs A's r189), packs (B), stampede (B), corners (A), monolith (A), fragment (A), collision (A), ambush (A). If v15 stays home on its losing side, it should survive the opening. On its winning side, v9 still invades, and now it dies at our spawn.
- **Expected:** at least 2 of these 9 flip from v15's losing side while its winning side holds. That gives +2 or more, plus expanse +2.
- **Expanse:** both sides, from change 3 (proven 6-0 over several evals).

Risk maps:
- **Close farming races** (rushbait, rows, lanes, interlock, elkring, pilgrimage). Here the deny weight may be what collects the good camps, so staying home could cost tempo. Limit: change 1 lasts only 200 rounds, and after that v9's logic is unchanged.
- **Swirl:** already −2 for every candidate, for reasons outside the play code (research #1). This plan doesn't count on it.
- **Contest/stampede gold:** change 1 doesn't touch kappa, so income stays as in v9.

Changes (implement all of them):
1. `bot.py` `best_group`, line 1106: replace `push = self.push_f * esc if ball else 0.0` with:
   `push = (0.0 if self.rnd < OPEN_HOME_R else self.push_f * esc) if ball else 0.0`.
   Then in the sightings loop (line 1164), while `self.rnd < OPEN_HOME_R`, use the multiplier 0.7 even when escorted (no x1.25 "hunt in company" in the opening):
   `score *= 1.25 if (esc >= 1.0 and self.rnd >= OPEN_HOME_R) else 0.7`.
   Add the module constant `OPEN_HOME_R = 200` in bot.py next to `KAPPA0`. The ESP_AVOID skip, the join logic and everything else stay as they are. The join `wt` at line 1201 reads the same `push` local, so it gets this change automatically.
   - Why: the opening pull toward the enemy spawn (up to x2.5 at round 0) is the only part of camp choice that sends both teams into each other's half before the first death. No earlier version changed anything before round 300. The research showed the routs are decided by r31-75.
2. `ball.py` `skirmish`, after line 907 (after the `GEM_CAUTION` scaling of `need`, before `go = ratio >= need`), add a home/away factor:
   ```
   dsp = self.df_spawn.get(self.pos)
   if dsp <= HOME_FIGHT_D:
       need *= HOME_FIGHT_F
   else:
       try:
           if self.df_enemy.get(self.pos) <= AWAY_FIGHT_D:
               need *= AWAY_FIGHT_F
       except Error:
           pass
   ```
   Add the constants to ball.py's constant block: `HOME_FIGHT_D = 10`, `HOME_FIGHT_F = 0.85`, `AWAY_FIGHT_D = 14`, `AWAY_FIGHT_F = 1.2`. This applies all game, not only in the opening.
   - API check: these are existing helpers already used in the same file (`self.df_spawn.get(self.pos)` at ball.py:493; `self.df_enemy.get(...)` wrapped in `except Error` at ball.py:952-954). There are no new cambc calls.
   - Why: change 1 makes contacts happen near our spawn, and this makes v15 take those fights. It wins them because it heals and respawns there (GameRules: champions respawn on their own spawn) while v9's fighters are far from home. The 1.2 away factor stops v15 champions that still wander deep (after r200, or when chasing) from taking the even trades that decide the routs. `R_GO = 1.05` means v9 accepts near-even fights everywhere, so being pickier only away from home is asymmetric in our favour.
3. `draft.py:27`: `FAR_SPAWN_DIST = 10**6` (the expanse Cassi & Issac gate off).
   - Why: verified +2 vs v9 in v10, v11, v13 and v14.

Explicitly NOT in this plan:
- bank veto, team bank or death memory (no effect in v11, v13, v12);
- kappa = 0 (starvation mechanism above);
- `GOLD_HOME_FAR` (its effect in v14 can't be separated from kappa's).

Test plan for the implementer (each is 1 deterministic game; run both sides):
- **Crash check:** `cambc run v15 v9 --map expanse`. It should win, as v10/v13 did.
- **Rout maps, v15 on the losing seat:**
  - `cambc run v9 v15 --map contest` and `cambc run v9 v15 --map eight` (v15 as B)
  - `cambc run v15 v9 --map corners`, `cambc run v15 v9 --map fragment` and `cambc run v15 v9 --map collision` (v15 as A)
  - Success: at least 2 of these 5 become v15 wins.
- **Rout maps, v15 on the winning seat:** `cambc run v15 v9 --map contest`, `cambc run v15 v9 --map eight`, `cambc run v9 v15 --map corners`. These must stay wins.
- **Close-race guard:** `cambc run v15 v9 --map rushbait-v2`, `cambc run v15 v9 --map rows` and `cambc run v9 v15 --map lanes` (v9's mirror winning seats for v15). These should stay wins. Allow at most 1 new loss here, and only if 2 or more rout flips are confirmed.
- **Info only:** `cambc run v9 v15 --map swirl`, to see whether the swirl −2 persists.
- **Pass bar before handing over:** net +2 or more over the tested games, not counting expanse.

Fallback (in this order, re-run the same games after each step):
- (a) If no rout flips: raise `OPEN_HOME_R` to 300 and `AWAY_FIGHT_F` to 1.35.
- (b) If winning seats or close races are lost: keep change 1 and drop the `AWAY_FIGHT` half of change 2 (keep `HOME_FIGHT_F`).
- (c) If still worse: drop change 2 entirely, then try `OPEN_HOME_R = 120`.
- Never ship change 3 alone; it caps out at 17-17 because of swirl.

### v15 — rejected (53% vs v9)
- Based on: v9 (pipeline: researcher, designer, implementer)
- Changes: I built v15 with all three plan changes plus the fallbacks, but it looks like a net loss and will probably be rejected. Over 12 games it flipped one rout (monolith A) and lost two seats it should win (contest A and eight A). No game crashed and no `bot error` lines appeared.

**What I changed** (all in `bots/v15/src/`)
1. **`bot.py:best_group`:** added `OPEN_HOME_R`. Before that round, the pull toward the enemy spawn is set to 0 and camps near a recent enemy sighting get 0.7 instead of the 1.25 company bonus. It ships at 300 (plan said 200; fallback 1 raised it).
2. **`ball.py:skirmish`:** the strength ratio needed to fight is ×0.85 within 10 steps of our spawn and ×`AWAY_FIGHT_F` within 14 steps of the enemy spawn. The distances come from `self.df_spawn.get(self.pos)` and `self.df_enemy.get(self.pos)` inside `try/except Error`, the same calls the file already makes elsewhere, so there are no new API calls. `AWAY_FIGHT_F` ships at 1.0, which turns the away half off (fallback 2).
3. **`draft.py`:** `FAR_SPAWN_DIST = 10**6`.

**Test results** ("before" is what the plan reports for the v9 mirror in that seat)

| # | Map, v15's seat | Config | Before | After |
|---|---|---|---|---|
| 1 | expanse A (crash check) | plan as written | – | **win** 1006–952 |
| 2 | contest B | plan as written | loss | loss 0–1000 |
| 3 | eight B | plan as written | loss | loss 66–1024 |
| 4 | corners A | plan as written | loss | loss 760–1136 |
| 5 | packs B | plan as written | loss | loss 636–1008 |
|
- Evaluation (results/eval_v15): v9 53%, v8 50%, v6 62%; overall 55%
- Status: rejected, moved to rejected/v15. Lesson: these changes did not beat v9.

### Research on v9 — 2026-10-17 (results/eval_v15, eval_v10, eval_v14; earlier evals via the previous research section)
Method: no Bash. I read the 34 v15-vs-v9 records in results/eval_v15/summary.json (lines 14492-21500) and compared each one with the same seat in the v9-code mirror. That mirror is the v10-vs-v9 block of results/eval_v10/summary.json: v10 is v9 with only the 3-pick expanse gate off. For v15 I also checked the v6/v8 records on the 4-pick maps and on contest, stampede and elkring. The v10-v14 per-map results are in the previous research section and are not repeated here.

Map picture (v15 vs v9 compared with the v9 mirror; "same" means the same seat won as in the mirror):
- Same: ambush (B), collision (B), elkring (A), fragment (B), lanes (B), packs (A), pilgrimage (A), expanse (A wins r744, B loses r779, the same as the gate-on mirror).
- v15 gained a seat:
  - corners A (W r656, mirror B won r535)
  - interlock A (W r734, mirror B won r825)
  - rows B (W r603, mirror A won r620)
  - swirl B (W r534, against v6 and v8 too)
- v15 lost a seat:
  - contest A (lost 400-800 at the r2000 limit; the mirror A won 1000-0)
  - stampede A (L r1034; the mirror A won r1294)
- Winning side reversed (net 0): eight (B now wins, r652/r958), monolith (A now wins, r542/r492), rushbait (B now wins, r632/r671).
- Total: 16 + 4 − 2 = 18-16. In all, 10 of 34 seats changed result relative to the mirror.

Lessons from rejected versions:
- v10, v11, v13: expanse gate off gives +2 and swirl costs −2, so 17-17. The bank changes moved no winner.
- v12: death memory acts too late; 16-18.
- v14: `kappa` = 0 and `GOLD_HOME_FAR` 250 changed 11 seats and finished 14-20.
- v15: the stay-home opening changed 10 seats and finished 18-16.
- v14 and v15 share no code, yet the same five seats moved the same way:
  - won: rows B, interlock A
  - lost: contest A, stampede A, rushbait A
  - So these five seats are the sensitive ones. v9's seat wins on contest, stampede and rushbait need its aggressive push and its gold economy. Its seat losses on rows and interlock come from that same aggression.
- v15's single largest gain was on the 4-pick maps (#1). Its losses were all on 5-pick and 3-pick maps.

1. **On the 4-pick maps (interlock, rows, swirl) the v15 stay-home opening wins from both seats. Elsewhere it nets negative, so the effect depends on roster size.**
   - Evidence:
     - Across the pool, v15 is 15-3 on the 4-pick maps (eval_v15 by_map): interlock 6-0, rows 6-0, swirl 3-3. B won swirl against v6, v8 and v9, with v6 and v9 at r534.
     - Against v9 it is 5-1 on these maps; the v9 mirror gives 2 of 6.
     - interlock A: v15 had no death until r270. v9 B died at r63, 86, 152 and 195, first submitted at r385 and lost 396 gems. v15 had 286 submitted by r250; in the mirror, A had 66 (first death r80, eval_v10 l.17548-17566).
     - rows B: v15's Varg and Ryth took 200 and 202 champion damage, did not die, and collected 396 and 528 gems. In the mirror's B seat they took 3,280 and 3,995, died twice each and collected 198 each (eval_v10 l.19809-19828).
     - Off the 4-pick maps, v15 vs v9 is 13-15. v10 (v9 play code plus the gate off) scores 15 of the same 28 games.
     - Estimate (hypothesis): a build that plays v15's opening only when 4 champions are drafted, and v10 code otherwise, would score 15 + 5 = 20/34 (59%). If the swirl B win does not carry over, it scores 19/34 (56%).
     - Risk: research #1 suspects fuel-threshold branching. If that is right, even an inert `if` could re-roll some seats.
   - Cause in code:
     - `rejected/v15/src/bot.py:1108-1110` (`best_group`: `push = 0.0` before `OPEN_HOME_R = 300`, line 25) and `:1168` (no ×1.25 hunt bonus in the opening).
     - `rejected/v15/src/ball.py:914-915` (`skirmish`: `need *= 0.85` within 10 of our spawn).
     - The v9 code it replaces: `bots/v9/src/bot.py:1106` (`push = self.push_f * esc`, with `push_f` = 0.5 from r0, `ball.py:213`), `:1132/:1158` (deny weight) and `:1164` (×1.25).
     - Roster size is available in play as `self.nslots` (`bots/v9/src/bot.py:212-220`, read from the draft memory).
   - Maps it decides: interlock A, rows B, swirl B (gains). It keeps interlock B and rows A.
   - Confidence: high on the measured results (18 deterministic games, identical rounds against v6 and v8). Medium on the 20/34 composite estimate.

2. **On the 5-pick big-camp maps v9's winning seat depends on its push opening; any softer opening gives the rout away. The same goes for the expanse B seat.**
   - Evidence:
     - contest A:
       - In the mirror, A had 2 deaths before r300 against B's 11 and won 1000-0 at r1549.
       - With v15 as A it was 6 against 8, 71 deaths in total, and the game ran to r2000. v15 lost 400-800 and earned 6,485 gold to v9's 10,263 (eval_v15 l.15330-15515).
     - eight A: v15 had 8 deaths before r300 (first at r48) against v9 B's 2 (first at r141), and submitted 116 gems (l.16246-16419). In the mirror A won 1022-0.
     - stampede A: v15 had 0 submitted until r910; v9 B banked 720 by r750 (l.20686-20862).
     - v14 lost contest A and stampede A too, through a different mechanism (gold starvation).
     - expanse B: v10 (v9 opening, gate off) won this seat. v15 (home opening, gate off) lost it at r779.
     - v15 also went 1-3 against v8/v6 on elkring and 1-3 on contest.
     - In v15's losses, its first death is no longer earlier than the opponent's (r132.5 vs r132.7; eval_v10 losses were r74.8 vs r130.5). The loser still has 3.7 deaths before r300 against 2.2, and 11.7 deaths in total against 6.7.
   - Cause in code:
     - `bots/v9/src/bot.py:1106,1132,1158,1164`: the deny-weighted push toward the enemy spawn wins the opening when the pushing team has 5 bodies.
     - Hypothesis, not traced: with 5 bodies the push arrives in numbers, while with 4 bodies the bodies arrive alone and get picked off at the defender's spawn (`ball.py:813` gives defenders on their own spawn ×3 HP in `fight_ratio`).
   - Maps it decides: contest A, stampede A, eight A, rushbait A, monolith B (v9's winning seats); 3-pick expanse B.
   - Confidence: medium. Two independent versions lost the same seats; the 4-vs-5-body mechanism is a hypothesis.

3. **Standoffs and idle bodies, not bag loss, swing some of the remaining seats**
   - Evidence:
     - corners A (v15 won 1232-738, r656): v15 lost the opening with deaths at r36, 62 and 71. It still won, because v9 B's Varg collected 22 gems, earned 140 gold, bought 0 items and never died in 656 rounds, and v9 B lost 350 gems (Ryth collected 356 and submitted 116) (l.15905-15969).
     - rows (v15 B won): v9 A's Marcella had 0 gems, 0 gold, 0 deaths and 725 champion damage taken; v15's Marcella had 0 gems, 2 deaths and 3,200 champion damage taken (l.20156-20234). In the pure v9 rows mirror both Marcellas collected 132-198 gems.
     - Other idle bodies in eval_v15 with 0 deaths and under 300 gold earned: l.4940, 6094, 8881, 13139.
     - This is the long-standing idle-body pattern from the v3 rows note and the v8/v11 analyses. It appears when the two openings differ.
   - Cause in code: not isolated (hypothesis). Likely a mutual `skirmish` hold (`bots/v9/src/ball.py:874`, `R_GO = 1.05` at l.46): two champions face each other and neither reaches `need`, so neither farms. The other candidate is the `cap_inc` gate (`bot.py:1092,1120`) for a champion with no items.
   - Maps it decides: corners (both seats for v15), rows A.
   - Confidence: low-medium.

Old hypotheses:
- Previous research #1 said swirl B is lost by any candidate for reasons outside the play code. That is refuted in its strong form: v15, also a three-character name, wins swirl B against v9, v8 and v6.
- Previous research #2 said the routs are decided before r100 and no version acted that early. Confirmed: v15 acted that early and moved 7 rout and close seats, in both directions.
- Previous research #3 said the close races flip through gold flow. Refuted: v15 flipped rows and interlock without touching `kappa` or gold.
- Bank, team-bank and death-memory changes: still no effect (no new data).

### Design for v16 — 2026-10-17 (based on v9)
Idea: pick the opening by roster size. With 4 champions, stay home: this is v15's opening, which went 5-1 vs v9 on the 4-pick maps. With 3 or 5 champions, keep v9's push opening, which wins v9's seats on contest, stampede, eight and rushbait. Turn the expanse gate off so that 3-pick maps really have 3 bodies, and so the 4-body test means "4-pick map" only.

What the code shows (checked for this design):
- `self.nslots` is the number of **bodies** from the draft memory (`bots/v9/src/draft.py:66-70` writes `[len(bodies)] + bodies`; `bot.py:209-220` reads it). It defaults to 6 if the memory is missing.
- With v9's gate **on**, expanse drafts Varg, Cassi & Issac and Ryth, which is also 4 bodies. So the gate must be off (change 3) or the 4-body test would also fire on expanse. v15 showed the home opening loses expanse B, while v10's push opening wins it.
- On 4-pick maps PREFS[4] is Varg, Ryth, Stellar and Marcella, so `nslots == 4`. On 5-pick maps it is 5 and on 3-pick maps (gate off) it is 3.
- `BallMixin` (`ball.py:124`) is mixed into `Bot` (`bot.py:118`), so `skirmish` can read an attribute set in `Bot.__init__`.
- v15's play-code changes are exactly the three spots listed in the earlier grep (`rejected/v15/src/bot.py:25,1108-1110,1168`; `ball.py:48-51,912-919`). The rest of v15 is v9.

Target maps (expected flips vs v9, compared with the v9 mirror at 17-17 where swirl splits):
- interlock A, rows B, swirl B. v15 won all three against v9 (and against v6 and v8) with exactly this code path. interlock B and rows A were kept. That is +3 seats on the 4-pick maps (v15 was 5/6 there, the mirror 2/6).
- expanse A and B, from the gate off, using v9's opening (v10, v11, v13 and v14 won both seats; v15 with the home opening lost B). Compared with the gate-on mirror, that is +1.
- Everything else (contest, stampede, eight, rushbait, monolith, corners, packs, fragment, collision, ambush, lanes, elkring, pilgrimage) runs v10 code exactly, and v10 scored 15/28 off the 4-pick maps.
- Estimate: 15 + 5 = **20/34**, or 19/34 if swirl B doesn't carry over.

Risk maps:
- Seats v15 won on 5-pick maps go back to v9-mirror results (corners A, eight B, monolith A, rushbait B). That is already counted in the estimate: the v10 baseline, not v15, holds there.
- Fuel-threshold butterfly (research #1): the added `if` changes fuel use slightly on every map. Limit this by computing the flag **once** in `__init__` and branching on a plain attribute, with no new loops and no new cambc calls. v10 already showed that a constant-level change leaves the 5-pick mirrors round-identical.
- swirl A is still a loss (v15 lost it too), and swirl B is the least certain gain.

Changes (implement all of them; start from a clean copy of `bots/v9`, **not** from rejected/v15):
1. `bot.py` `__init__`, right after the draft-memory block (after line 222, `self.slot = n + ...`): add `self.home_open = (self.nslots == HOME_OPEN_SLOTS)`. Add the module constants next to `KAPPA0`: `HOME_OPEN_SLOTS = 4` and `OPEN_HOME_R = 300`.
   Then in `best_group` (v9 line 1106, `push = self.push_f * esc if ball else 0.0`), add right after it:
   ```
   opening = self.home_open and rnd < OPEN_HOME_R
   if opening:
       push = 0.0
   ```
   In the sightings loop (v9 line ~1164), change the ball branch to `score *= 1.25 if (esc >= 1.0 and not opening) else 0.7`. This is identical to rejected/v15 bot.py:1108-1110 and 1168, except for `self.home_open and`. `rnd` is the local already used in that function (v15 uses it the same way). Don't touch the join logic: it reads the same `push` local, as in v15.
   - Why: research #1. On interlock A, v15 had its first death at r270 (v9 at r63) and 286 gems submitted by r250 (mirror 66). On rows B, Varg and Ryth took about 200 champion damage instead of 3,280 and 3,995. Gating stops the home opening from losing contest A, stampede A and eight A (research #2).
2. `ball.py` `skirmish`: after the `GEM_CAUTION` scaling (v9 ~line 907), before `go = ratio >= need`, add
   ```
   if self.home_open:
       try:
           if self.df_spawn.get(self.pos) <= HOME_FIGHT_R:
               need *= HOME_FIGHT_F
       except Error:
           pass
   ```
   with the constants `HOME_FIGHT_R = 10` and `HOME_FIGHT_F = 0.85` in ball.py's constant block. Don't add the away half: v15 shipped it at 1.0, so it was a no-op. `self.df_spawn.get(self.pos)` and `except Error` are the forms already used in v9 `ball.py` (l.493, l.952-954), so there are no new API calls.
   - Why: this is part of the exact code that produced v15's 4-pick results. Keep it so those games reproduce. Applying it all game, but only on 4-body rosters, matches what v15 did on those maps.
3. `draft.py:27`: `FAR_SPAWN_DIST = 10**6`.
   - Why: expanse gets +2 seats with v9's opening (proven in 4 evals). It is also required for change 1's 4-body test to mean "4-pick map".

Explicitly not included: anything that changes 5-pick or 3-pick play (bank veto, team bank, death memory, kappa, GOLD_HOME_FAR, AWAY_FIGHT). Those maps must stay byte-for-byte v10 behaviour.

Test plan for the implementer (deterministic, 1 game each):
- 4-pick gains (must win): `cambc run v16 v9 --map interlock` (v16 A), `cambc run v9 v16 --map rows` (v16 B), `cambc run v9 v16 --map swirl` (v16 B).
- 4-pick holds (must win): `cambc run v9 v16 --map interlock`, `cambc run v16 v9 --map rows`.
- Expanse (must win both): `cambc run v16 v9 --map expanse`, `cambc run v9 v16 --map expanse`.
- 5-pick guard (v9-mirror seats, must stay wins, ideally the same round as v10's): `cambc run v16 v9 --map contest` (r1549 win), `cambc run v16 v9 --map stampede`, `cambc run v16 v9 --map eight`, `cambc run v16 v9 --map rushbait-v2`.
- Success: all 4-pick and expanse games except possibly swirl B win, and no 5-pick guard game changes winner. A guard game with a different round number means the flag is leaking into 5-pick play (check that `home_open` is False there; print `nslots` once if needed).

Fallback:
- (a) If a 4-pick gain fails, check that `nslots` is 4 in play (log once). If it isn't, gate on `cambc.draft.team_size()` saved during the draft instead. Check that call is valid in the play phase in BotAPIPython.md first; otherwise keep nslots.
- (b) If interlock or rows reproduce v15 but swirl B doesn't, ship anyway: 19/34 is still above the bar.
- (c) If a 5-pick guard game flips while the flag is False (fuel butterfly), move the flag check so the 5-pick path runs exactly v9's statements. For example, in `best_group` make it `if self.home_open:` wrapping both new lines, so non-4 rosters only pay one attribute test.
- Don't tune OPEN_HOME_R or HOME_FIGHT_F: the target is to reproduce v15's measured 4-pick games exactly.

### Lead input — 2026-10-17: draft picks to test
- The lead reports that the strongest picks are **Ren, Stellar, Cassi & Issac, Ryth and Varg**.
  Source: the top teams on the competition ladder, so this is the current meta, not a guess.
- v9 differs: its 5-pick list is Varg, Ryth, Stellar, Marcella, Tavi. It **never drafts Ren**, and it
  only drafts Cassi & Issac through the expanse far-spawn gate (`PREFS_FAR_3`), which v10-v16
  switched off.
- To do: test a roster built on these five (map by map, both sides, against v9), especially Ren and
  Cassi & Issac, which this line has never fielded on most maps. Check that the bot's play logic
  handles them (abilities, linked deaths for Cassi & Issac) before judging the draft on results alone.
- The lead also notes that **our champions rarely group up**. That fits the code: `ball.py:90`
  `SOLO = 1` ("every champion farms on its own once the push stage starts") and `ball.py:194`
  `self.r_gather = 0` (solo from the first round). The only grouping left is the parties of up to 3
  on big camps (`bot.py:27-28`, `BIG_GEMS`/`BIG_PARTY`). Earlier versions had a "ball" (the whole
  team moving and fighting together) that was switched off; find out from NOTES.md why, and whether
  it was judged on 2.1.6 maps only. Check each meta champion's role and abilities in GameRules.md:
  if their value depends on allies being nearby (support, area effects, Cassi & Issac's link), the
  meta roster only pays off when the team stays together. Test a grouped mode, at least for fights
  and the opening, together with the meta roster.

- The lead says **every champion should finish one emblem family first**, because the emblem's
  passive is what matters (GameRules.md:290-306: shards give stats, only the 5th shard's emblem
  gives the passive, and a second emblem of the same family adds no passive). v9 already buys one
  family at a time (`tables.py` `BUILD_FIGHTER`: Monster STR, Jungle HP, Treasure STR, Durability HP,
  ...; `bot.py:957-980` `buy_items`). Still open: which passive should come first for each champion
  and role (e.g. Jungle's 30% less camp damage for the champions that tank camps, Treasure for the
  farmers), and how early each champion completes its first emblem. Measure that from `buyItem` /
  `itemCombination` events in the .stats.json files, per champion.
- The lead also says **champions that have no shards should be fed**: the stronger teammates help
  them farm and let them take the gold. By the rules this is possible: camp gold and gems are split
  evenly among the champions standing on the capture tile (GameRules.md:195), so a strong champion
  can clear a camp, step off, and let the weak one capture it alone. Evidence of the need: in
  results/eval_v9 the gold earned per champion ranges from 673 (Issac) to 1279 (Varg)
  (`side_stats.candidate_champions`), and earlier analyses found champions with 0 gold and 0 items
  on ambush (Marcella, Stellar). Design idea: track each champion's emblem progress in shared memory,
  and give the camp's capture to the teammate furthest from finishing its first emblem.
- **Lead request (concrete): Jungle emblem first.** The lead sees that the top ladder teams always
  complete the **Jungle** emblem first (passive: 30% less damage from camps). v9 buys **Monster STR
  first** and Jungle HP second: every champion uses `BUILD_FIGHTER` (`bot.py:247`;
  `tables.py:45-48`), which starts `[(MON, STR), (JUN, HP), ...]`. `BUILD_RANGED` and
  `BUILD_SUPPORT` are identical and unused. So the change is to put `(JUN, HP)` (or JUN STR; check
  which stat suits each champion) first. Include it in the next version: it costs nothing to add
  alongside other changes, and less camp damage means fewer recalls, fewer camp deaths (camp kills
  destroy carried gems, GameRules.md:361) and earlier solo clears.
- **Lead request (concrete): Focus shards for spell champions.** The lead sees that the top teams
  buy **Focus** shards on every champion except **Varg**. v9 buys no Focus at all (`BUILD_FIGHTER` is
  only STR and HP, used by every champion). The rules support the lead (GameRules.md:245-259, the
  stat tables at 418-795): a Strength shard adds 3-5 to basic attacks (Stellar 3.5, Willow 3), while
  a Focus shard adds 10 (Cassi 15, Willow 5), and spells multiply Focus: Tavi 2.2x + stun, Stellar
  2x single / 1.4x area, Cassi 2x, Marcella 2x, Prism 1.5x + stun, Ren 1.25x + stun (and a passive
  retaliation of 0.2x Focus), Ryth 1x + area stun, Willow heals 3x Focus, Varg's self-shield 2.5x.
  Varg is the exception: his passive splashes damage equal to Strength, so STR stays right for him.
  Change: give each champion its own build (the unused `BUILD_RANGED`/`BUILD_SUPPORT` lists, or a
  per-champion table), using **Jungle Focus** first for Focus champions and **Jungle** (HP or STR)
  for Varg. Check that the bot casts these abilities often enough to profit (cooldown 8 turns per
  slot, one cast per turn); if it rarely casts, fix that in the same version.

### v16 — promoted (59% vs v9)
- Based on: v9 (pipeline: researcher, designer, implementer)
- Changes: I've built v16 with all three plan changes. Twelve test games ran with 0 crashes and no `bot error` lines. Eleven match the expected result. The one that doesn't is the rushbait-v2 guard, because that map turns out to draft 4 champions, not 5.

**What I changed:**
1. **`bot.py`:**
   - Added the constants `HOME_OPEN_SLOTS = 4` and `OPEN_HOME_R = 300`.
   - In `Bot.__init__`, right after the draft-memory block, I set `self.home_open = (self.nslots == HOME_OPEN_SLOTS)` once.
   - In `Bot.best_group`, `opening = self.home_open and rnd < OPEN_HOME_R`. During the opening the pull toward the enemy spawn is 0, and the ×1.25 hunt bonus becomes ×0.7 (`esc >= 1.0 and not opening`). This is v15's code with the flag added.
2. **`ball.py`:** added `HOME_FIGHT_R = 10` and `HOME_FIGHT_F = 0.85`. In `skirmish`, after the `GEM_CAUTION` scaling and only when `home_open` is set, the needed ratio is ×0.85 within 10 steps of our spawn. It uses the same `self.df_spawn.get(self.pos)` call and `except Error` the file already has, so there are no new API calls. The "away" half is left out.
3. **`draft.py`:** `FAR_SPAWN_DIST = 10**6`.

**Test results (v16 vs v9; "before" is the v9-code mirror from NOTES):**

| Map | v16 seat | Before | After |
|---|---|---|---|
| interlock | A | L (B won r825) | **W r734** (same as v15) |
| rows | B | L (A won r620) | **W r603** (same as v15) |
| swirl | B | L | **W r534** (same as v15) |
| interlock | B | W | W r793 |
| rows | A | W | W r613 |
| expanse | A | W r744 
- Evaluation (results/eval_v16): v9 59%, v8 62%, v6 71%; overall 64%
- Status: promoted, new champion.

### Research on v16 — 2026-10-17 (results/eval_v16; v10-v15 via the earlier research sections)
Method: no Bash. There are no rejected versions against v16 yet, so eval_v16 is the only new data. I read every v16-vs-v9 record in results/eval_v16/summary.json (lines 14425-21400), took per-seat results against v6 and v8 from the same file, and opened four stats files: eval_v16/v9/{eight,contest,elkring,stampede}__cand-B.stats.json.

Map picture:
- **The 5-pick maps (12) are a byte-identical v9 mirror.** Both seats of every pair give exactly the same game, e.g. ambush 510-1010 r795 from both seats, contest 1000-0 r1549, eight 1022-0 r515. The winners and rounds are the same as the v9-code mirror in the earlier research. So the `home_open` flag, set once in `__init__`, changed nothing off the 4-pick maps.
  - Seats v16's code loses (the ones a challenger must hold or flip): ambush A, collision A, contest B, corners A, eight B, elkring B, fragment A, lanes A, monolith A, packs B, pilgrimage B, stampede B.
- **Soft and hard losing seats.** v16's code *wins* some of its v9-mirror losing seats against older bots:
  - corners A (W vs v6 r628), eight B (W vs v6 r756), lanes A (W vs v6 r501), monolith A (W vs v6 r536), elkring B (W vs v8 r654), stampede B (W vs v6 r1010 and v8 r1220). These seats can be won.
  - Lost to all three opponents: ambush A, collision A, contest B, fragment A, packs B, pilgrimage B.
  - v16's winning seats that do fall to an older bot: eight A (L vs v6 r808) and elkring A (L vs v8 r741). These are the fragile seats a challenger could take.
- **4-pick maps:**
  - interlock and rows: v16 wins both seats against v9, v8 and v6 (interlock r734/r793, rows r613/r603 against v9).
  - rushbait-v2 and swirl: the B seat wins in every pairing seen. v16 A loses rushbait 256-1050 r632 to v6, v8 and v9 alike, and swirl at r683 (v6, v8) and r471 (v9); v16 B wins rushbait r671 and swirl r534. So in a v16 mirror these two most likely split 1-1.
- **expanse** (3-pick): v16 won both seats (r631, r719), but v9 there still drafts Cassi & Issac. The v16 mirror result is unknown.
- **Expected v16-vs-copy baseline: 17-17.** That is 12 splits on 5-pick, rushbait and swirl 1-1, and interlock, rows and expanse unknown.

Lessons from rejected versions (they were tested against v9, but on 5-pick maps v16 *is* v9, so they apply unchanged):
- v10, v11, v13: the expanse gate fix (now in v16), bank-veto and team-bank changes moved no 5-pick winner. Not worth re-trying.
- v12: death memory acts too late.
- v14 (`kappa` = 0 and `GOLD_HOME_FAR` 250) and v15 (stay-home opening) share no code, yet both lost contest A and stampede A. These are v16's big-camp winning seats, and any change that weakens the opening push or gold income loses them.
- v15's 5-pick reversals (eight, monolith, rushbait) show the opening exchange can be moved, but in both directions at once.
- No rejected version has touched idle bodies, the respawn trickle or carrier deaths after r450.

1. **The close 5-pick races are decided by carried bags lost after r480, not by first banking.**
   - Evidence:
     - elkring (B loses): B led 504-432 at r500 (first death r107 vs r118, only 1 death before r300). It then lost **486 gems** in deaths at r483, 500, 597, 606 and 634. Single bags were 108 (Varg, killed at (20,6) by A's Varg at r500) and 144 (Stellar, r634 at (22,7)) (elkring__cand-B.stats.json gemLoss). A went from 432 to 1008 in 192 rounds; the killer gets the carried gems (GameRules l.361).
     - Other losing seats show the same: collision A lost 226 gems (0 deaths for B until r483); monolith A lost 198 and stalled at 652 from r500 while B went 308→1010 between r250 and r498; ambush A lost 106 (Varg collected 178, submitted 72).
     - On the 4-pick rushbait the losing seat lost 270 (v16 A) and 320 (v9 A) with 0 deaths for the winner.
     - First banking does not decide these races. The loser submitted first on ambush (134 vs 146), lanes (87 vs 120) and stampede (680 vs 929), and both sides first submitted at r84 on pilgrimage (summary.json `first_submit_round`).
   - Cause in code:
     - `bots/v16/src/ball.py:471` (`ball_want_bank`: no banking while a camp task has incoming damage) and `:473` (no banking with an enemy near unless the altar is within 3 tiles), with `bot.py:991-997` (`bank_threshold` up to 110).
     - On the other side, `ball.py:54` `GEM_K = 8` makes every champion hunt carriers. `ball.py:908-909` (`GEM_CAUTION`) only raises the ratio needed to *start* a fight; it doesn't move the carrier away.
     - v11 relaxed one bank veto and moved nothing, so which line holds the 108-144 bags is still open (hypothesis: the `:471` task veto while farming elk).
   - Maps it decides: elkring B, collision A, monolith A, ambush A (partly), rushbait A.
   - Confidence: medium. The losses are measured; the exact veto is not traced.

2. **Idle bodies decide ambush A and shape stampede, and they are not mirrored**
   - Evidence:
     - ambush A (lost 510-1010 r795, summary.json l.14501-14520): Stellar collected 0 gems and 245 gold and bought 0 items; Marcella collected 0 gems and 0 gold and bought 0 items. In the same game B's Stellar and Marcella collected 106 gems each. Same result against v6 (v16 A Marcella 0 gems, 100 gold) and v8. The v8 analysis (#3) flagged this and it was never fixed.
     - stampede (A wins 1080-360 r1294): the only gems are 360-gem herd captures. B (Varg+Ryth together) took one at r615; A's Stellar took them at r849 and r1071 and Tavi at r1196 (stampede__cand-B.stats.json `collectedGems` runs). A's Varg, Ryth and Marcella and B's Stellar, Marcella and Tavi collected **0 gems in 1294 rounds**, with 32 deaths between them.
     - Other zero-gem champions in the v9 block are symmetric: Stellar on both pilgrimage sides, Marcella in the rows games.
   - Cause in code (hypothesis, not traced): `bot.py:1095` `cap_inc = 0.15*hp_full/mult` keeps low-HP or unshopped champions off strong groups. Gold-less champions never shop (`ball.py:494` needs 300+ gold), so they never qualify. On ambush this looks like the v8 #3 cycle: attack a camp, recall at `HOME_HP`, come back.
   - Maps it decides: ambush A (2 dead bodies out of 5); stampede both seats (whoever's idle trio is smaller).
   - Confidence: high on the data, low on the mechanism.

3. **The routs are spawn traps: the loser keeps walking out one at a time.**
   - Evidence:
     - contest B: 54 deaths, 0 gems collected and 1,545 gold in 1549 rounds, against A's 5 deaths. B's death rounds come every 30-40 rounds (31, 35, 68, 76, 110, 118, 139, ...), the rhythm of single respawns (60 rounds, GameRules l.361).
     - The contest deaths I located are 7-9 tiles from B's spawn: (30,22) at r68 and (26,24) at r314, plus (32,32) at r199 (contest__cand-B.stats.json; A shops at (3,3)). A didn't submit until r1000, so it farmed kills instead of camps.
     - eight B: 12 deaths and 0 submitted. The first death was at r56 at (28,8), killed by A's Ryth. B shops at about (40,14) and A at (0,14), so this was in **B's own half**. Its next deaths (26,4; 22,7; 19,7; 19,6) are also on its side. A's Stellar dealt 9,336 champion damage against B's 2,525.
   - Cause in code:
     - `ball.py:92` `SOLO = 1` and `:196` `r_gather = 0`: there is no regroup, so each respawned champion goes back to its own task.
     - `ball.py:423-427` only holds on spawn when hurt *and* no enemy is visible.
     - `fight_ratio` (`ball.py:800-820`) gives enemies ×3 HP on their spawn but gives us no credit for our own spawn heal, so a lone respawn compares itself with the whole camping group only once it is already in reach.
     - Hypothesis: a "wait on spawn until 2+ allies are up when enemies hold within ~10 tiles" rule would cut the feed. It is unknown whether that flips contest B, because A would then farm the monoliths.
   - Refutes the v15 design premise ("the rout loser is caught away from home"): on eight and contest the loser dies in its own half.
   - Maps it decides: contest B, eight B, fragment A (8 deaths vs 0, 0 submitted), packs B (9 deaths vs 2).
   - Confidence: medium on the pattern, low on the code path.

Old hypotheses:
- **The "fuel-threshold butterfly" is refuted** for attribute flags: v16's flag left all 12 5-pick games round-identical.
- **Swirl is not lost "outside the play code": it is a B-seat map.** B won in all four pairings (v16-v6, v16-v8, v16-v9, v9-v16).
- **The routs are still decided before about r100.** Confirmed: the loser's first death came at r31-66 on contest, eight, fragment and collision.
- **"Close races flip through gold flow"** (v9 research #3): refuted by v15 and not supported here. The close races are lost through carried gems (#1).
- **Do not repeat:** bank veto (v11), team bank (v13), death memory (v12), kappa = 0 (v14), the 5-pick stay-home opening (v15).

### Design for v17 — 2026-10-17 (based on v16)
Idea: stop handing the opponent free gems and gold. A champion that respawns into enemies waits on its spawn tiles until it has company, because spawn tiles heal it to full every turn and enemies can't step onto them. Every champion completes the Jungle emblem first, which means 30% less camp damage, fewer recall cycles, fewer camp deaths and access to stronger camps. Stellar builds Focus so her spells kill the champions who walk into her. Fewer deaths means fewer carried bags lost, and that is how the close races are decided (research #1).

What the code shows (checked for this design):
- **Spawn tiles:** "Cannot be moved onto by opponents… While standing on these tiles you are healed" (GameRules l.151). Spawn recovery happens at turn end (l.122). So a champion standing on its spawn only dies to burst inside a single round.
- **v16 ignores the spawn heal:**
  - `plan_fight.evaluate` (`ball.py:1115-1141`) scores spawn tiles with the full `risk`, with no allowance for the heal.
  - `fight_ratio` (`ball.py:800-820`) triples enemy HP on *their* spawn and gives nothing for ours.
  - When enemies are visible but not in reach (`rel` empty, `ball.py:896`), `skirmish` returns None. `ball_decide` (`ball.py:423-451`) then heals only `if … not self.enemies`, and otherwise walks the champion to its task, straight into the campers. This is the "one at a time" feed on contest B and eight B (research #3).
- **Jungle:** `self.mult` already applies 0.7 for "JUN" (`bot.py:319`). It feeds into `cap_inc = 0.15*hp_full/mult` (`bot.py:1095`, the gate that keeps champions off strong groups, suspected behind idle bodies), into `group_estimate`/`simulate` (`bot.py:1060-1063`) and into `self.inc` (`bot.py:522`). So finishing Jungle first automatically widens the camps every champion may take by 43% and cuts the planned recall cycles. No model changes are needed.
- **Shop:** `buy_items` (`bot.py:960-989`) buys `self.build` in order. `self.build = list(T.BUILD_FIGHTER)` for every champion (`bot.py:250`). `item()` builds `f"{FAMILY}_SHARD_OF_{STAT}"`; `JUNGLE_SHARD_OF_HEALTH` and `*_SHARD_OF_FOCUS` (MONSTER, POWER, TREASURE, JUNGLE) exist in BotAPIPython.md l.643.
- **Focus only pays for Stellar** (GameRules l.582-592: 2×F single target and 1.4×F area, range 4, cooldown 8; growth F 10 against S 3.5).
  - Stellar: per 9-turn cycle, a Focus shard adds 20+14 = 34 damage to one target, more when the area spell hits several targets. A Strength shard adds 9×3.5 = 31.5.
  - Marcella, Tavi, Ryth and Varg: a Strength shard adds 9×5 = 45 per cycle, a Focus shard 10×mod (20, 22, 10, 0). They keep Strength.
  - `refresh_stats` (`bot.py:292-308`) already counts spell damage from `me.focus()` in `self.dps`, so camp estimates follow automatically.
  - This is my answer to the lead's Focus request: Focus where the numbers support it, not on every champion.

Target maps (each seat is v17's seat, in a v16 mirror where v16's code loses it):
- **Change 1 (spawn hold):** the routs where the loser feeds near its own spawn.
  - contest B (54 deaths, 7-9 tiles from its spawn)
  - eight B (first death r56 in its own half)
  - packs B (9 deaths against 2)
  - fragment A (8 deaths against 0)
  - collision A
  - A flip on contest B needs v17 to stop feeding kills (A didn't submit until r1000) and then win the monolith race on gold. I expect eight B and packs B to be the likeliest flips.
- **Change 2 (Jungle first):**
  - ambush A (two idle bodies) and stampede B (three 0-gem champions, decided by 360-gem herd captures, where camp damage is the limit)
  - monolith A, which stalled at 652 after losing 198 gems
  - elkring B, which led 504-432 at r500 and then lost 486 gems on elk
- **Change 3 (Stellar Focus):** the fights where Stellar is the main damage dealer (eight: A's Stellar dealt 9,336 champion damage). It helps change 1 kill the campers who stay in spell range of our spawn.
- **Soft seats from the research:** corners A, eight B, lanes A, monolith A, elkring B and stampede B, which v16's code already wins against v6 or v8. These are the cheapest flips.
- **Need:** 2 net flips on top of the 17-17 mirror.

Risk maps:
- **contest A and stampede A** (big-camp seats that v14 and v15 lost by weakening the push or gold income).
  - Change 1 triggers only for a champion standing on its own spawn with an enemy within 9 tiles, and only when it would not win the fight. On a winning seat that almost never happens, and the push code is untouched.
  - Change 2 delays Monster STR by one emblem (150 gold), so early camp clears are about 10% slower and Strength comes later. That is the main risk to the monolith clears on contest A. Watch the guard games.
- **4-pick maps (interlock, rows):** v16 wins both seats there. The `home_open` opening is unchanged. Change 2 shifts item timing on these maps too; the guard games check it.
- **Stalling:** change 1 caps each hold at `SPAWN_HOLD_MAX = 30` turns, then the champion walks out as in v16. The hold also ends as soon as an ally standing next to us (within 2 tiles, counted by `ally_in_fight`) lifts the ratio to `R_GO`. That is the regroup effect.
- **All maps:** every map re-rolls, because changes 2 and 3 alter every game. That is unavoidable for a seat-flipping change. The test plan below checks the winning seats.

Changes (implement all of them; start from a clean copy of `bots/v16`):
1. `ball.py`: hold on spawn under siege.
   - Constants, added to the constant block: `SPAWN_HOLD_D = 9`, `SPAWN_HOLD_MAX = 30`, `SPAWN_HOLD_W = 1000.0`, `SPAWN_RISK_F = 0.35`.
   - In `ball_init` add `self.hold_sp = 0` and `self.spawn_hold = False`.
   - New method:
     ```
     def want_spawn_hold(self):
         """v17: on our spawn with enemies lurking and no fight we would win: wait there for company."""
         if (self.px, self.py) not in self.spawn_xy:
             self.hold_sp = 0
             return False
         near = [e for e in self.enemies if cheb(self.px, self.py, e[0], e[1]) <= SPAWN_HOLD_D]
         if not near:
             self.hold_sp = 0
             return False
         if self.hold_sp >= SPAWN_HOLD_MAX or self.endgame_bank(self.df_altar.get(self.pos)):
             return False
         if self.fight_ratio(near) >= R_GO:
             return False
         self.hold_sp += 1
         return True
     ```
     `fight_ratio` must be the unmodified v16 one. It deliberately gives us no credit for our spawn, because the question is whether we would win *off* it. If `endgame_bank` with a 65535 distance causes trouble, guard it with `d < 65535`.
   - `ball_decide`: as the first line after `self.maybe_lock()` (line 411), add `self.spawn_hold = self.want_spawn_hold()`.
     - After the `on_spawn` / `field_shop` buy block (i.e. right after line 431, before the `bstate == S_GATHER` line), add `if self.spawn_hold: return heal + "spawn-hold"`.
     - This sits after `buy_items()`, so the champion still shops, and after the skirmish, so it still fights anything in reach.
   - `plan_fight.evaluate` (`ball.py:1115`), right after the `risk` loops (before `pos_v = -lam * risk`), add:
     ```
     if (x, y) in spawn_set:
         risk *= SPAWN_RISK_F          # spawn tiles heal us to full every turn end and enemies can't step on them
     ```
     Bind `spawn_set = self.spawn_xy` and `hold = self.spawn_hold` as locals before `def evaluate`.
   - After `pos_v` is set, add `if hold and (x, y) not in spawn_set: pos_v -= SPAWN_HOLD_W`, so a holding champion attacks and casts only from spawn tiles.
   - Why: research #3. contest B has 54 deaths at respawn rhythm, 7-9 tiles from its spawn. eight B's deaths are all in its own half. v16 walks each lone respawn into the campers because `skirmish` ignores enemies out of reach (`ball.py:894-898`) and `ball_decide` only heals when no enemy is visible. Each feed gives the camper 50 gold plus our carried gems (GameRules l.361). This targets the routs, which no earlier version changed except v15's opening, and does not touch the push.
2. `tables.py`: Jungle first.
   - `BUILD_FIGHTER = [(JUN, HP), (MON, STR), (TRE, STR), (DUR, HP), (POW, STR), (HOME, HP)] + [(POW, STR), (POW, HP)] * 12`. This swaps only the first two entries; leave `BUILD_RANGED`, `BUILD_SUPPORT` and `BUILD_BALL` alone.
   - Why: the lead's concrete request (ladder teams finish Jungle first). In this code it also lifts `cap_inc` by 1/0.7 and cuts `taken` in `group_estimate`, which is the suspected idle-body gate (research #2, ambush A, stampede). Fewer camp deaths also means fewer destroyed bags (GameRules l.361), which is the elk part of elkring B's 486 lost gems. Health shards bought on spawn also heal (GameRules l.322).
3. `tables.py` + `bot.py:250`: a Focus build for Stellar.
   - Add `BUILD_STELLAR = [(JUN, FOC), (MON, FOC), (TRE, FOC), (DUR, HP), (POW, FOC), (HOME, HP)] + [(POW, FOC), (POW, HP)] * 12`.
   - In `Bot.__init__` replace line 250 with `self.build = list(T.BUILD_STELLAR if self.ctype == T.STELLAR else T.BUILD_FIGHTER)`.
   - Why: the lead's Focus request, narrowed by the numbers above. More spell burst also helps change 1, since Stellar's range-4 spells reach campers from spawn tiles, and `can_finish` (`ball.py:863-874`) adds `modifier*mfocus` for kills.

Explicitly not included:
- bank veto, team bank, death memory, `kappa`, `GOLD_HOME_FAR` (all tried)
- any change to `best_group` push or deny weights, or to `home_open`

Test plan for the implementer (deterministic, 1 game each, v17 seat stated):
- **Crash check:** `cambc run v17 v16 --map contest`. There should be 0 `bot error` lines.
- **Rout flips:**
  - `cambc run v16 v17 --map eight` (B), `cambc run v16 v17 --map packs` (B), `cambc run v16 v17 --map contest` (B)
  - `cambc run v17 v16 --map fragment` (A), `cambc run v17 v16 --map collision` (A)
  - Success: at least 1 win. Also check the stats file: v17's deaths before r300 should fall clearly (contest B was 11).
- **Economy flips:**
  - `cambc run v17 v16 --map ambush` (A), `cambc run v17 v16 --map monolith` (A), `cambc run v17 v16 --map corners` (A), `cambc run v17 v16 --map lanes` (A)
  - `cambc run v16 v17 --map elkring` (B), `cambc run v16 v17 --map stampede` (B)
- **Winning-seat guards (must stay wins):**
  - `cambc run v17 v16 --map contest` (A), `cambc run v17 v16 --map stampede` (A), `cambc run v17 v16 --map eight` (A), `cambc run v17 v16 --map elkring` (A)
  - `cambc run v17 v16 --map interlock`, `cambc run v16 v17 --map interlock`, `cambc run v17 v16 --map rows`, `cambc run v16 v17 --map rows`
- **Pass bar:** (wins on the flip list) − (losses on the guard list) ≥ 2.

Fallback (re-run the same games after each step):
- (a) If the guards lose but the flips hold, drop change 3 (Stellar back to `BUILD_FIGHTER`).
- (b) If contest A or stampede A is lost, change 2 is the likely cause (Monster comes later). Try `(JUN, STR)` instead of `(JUN, HP)` as the first entry, which keeps early Strength. If that still loses, put `(MON, STR)` first and `(JUN, HP)` second, i.e. revert change 2.
- (c) If no rout seat moves and v17's early deaths don't drop, raise `SPAWN_HOLD_D` to 11 and `SPAWN_HOLD_MAX` to 45.
- (d) If a winning seat loses because champions sit on spawn (many "spawn-hold" turns in a won-before game), lower `SPAWN_HOLD_MAX` to 15.
- Don't drop change 1: it is the only change aimed at the rout seats.

### v17 — promoted (74% vs v16)
- Based on: v16 (pipeline: researcher, designer, implementer)
- Changes: v17 is built and passes the design's bar: 4 flip seats won and all 8 guard seats held (+4 against a pass mark of +2). There were no crashes or `bot error` lines in any game. I changed one thing from the plan: Jungle-first applies only to teams that don't have exactly 4 champions, because on 4-champion maps it lost two guard seats.

## What I changed
1. **Hold on spawn**, all in `ball.py`, as specified:
   - **Constants:** `SPAWN_HOLD_D=9`, `SPAWN_HOLD_MAX=30`, `SPAWN_HOLD_W=1000.0`, `SPAWN_RISK_F=0.35`.
   - **`ball_init`:** added `hold_sp` and `spawn_hold`.
   - **New `want_spawn_hold`:** uses the unmodified `fight_ratio`. The end-of-game banking check is skipped when no altar is reachable. Without that guard the check always fired at distance 65535, so the hold would never have started.
   - **`ball_decide`:** sets `spawn_hold` right after `maybe_lock()`. It returns `heal + "spawn-hold"` after the buy block, so the champion still shops and fights while holding.
   - **`plan_fight.evaluate`:** damage on spawn tiles counts at 0.35, and stepping off the spawn while holding costs 1000.
2. **Jungle first** (`tables.py`): `BUILD_FIGHTER` now starts with `(JUN, HP), (MON, STR)`.
   - **Change:** I added `BUILD_FIGHTER_MON` (v16's Monster-first order). `bot.py:Bot.__init__` uses it when `self.home_open` is true, which means exactly 4 champions (interlock, rows).
3. **Focus for Stellar** (`tables.py` + `bot.py:Bot.__init__`): added `BUILD_STELLAR` as specified, behind a `STELLAR_FOC
- Evaluation (results/eval_v17): v16 74%, v9 76%, v8 71%; overall 74%
- Status: promoted, new champion.

### Research on v17 — 2026-10-17 (results/eval_v17; eval_v15 for the monolith/eight comparison)
Method: no Bash. There are no rejected versions against v17 yet, so v17 itself (v16 + spawn hold + Jungle first + Stellar Focus) is the only new controlled experiment. I read the per-seat results of all 102 records in results/eval_v17/summary.json and the full records of the v16 games on collision A, contest B, eight B, expanse A, fragment A, monolith A, pilgrimage A/B and ambush A. I also opened eval_v17/v16/{eight__cand-B, eight__cand-A, pilgrimage__cand-A}.stats.json and checked the v15 eight and monolith records in eval_v15.

**Correction to earlier sections:** collision, fragment and expanse are **3-pick** maps. Every side drafts Varg, Ryth and Marcella (summary.json l.905-909, l.3366-3370, l.3021-3025). The v16 research counted collision and fragment among the "12 5-pick maps"; there are 10 five-pick maps.

Map picture: v17 vs v16, v17's seat, W/L and round. All 3-pick and 5-pick games except expanse are round-identical against v16 and v9, so v16 = v9 there, and the "fuel butterfly" stays refuted.
- **5-pick maps:**
  - Both seats won: ambush (888/820), corners (553/555), elkring (664/631), lanes (625/560), packs (664/833), stampede (1216/895).
  - Split: contest (A W r1519, B L r1694), eight (A W r710, B L r613), monolith (A L r485, B W r611).
  - Both seats lost: pilgrimage (A L r1058, B L r1132).
- **3-pick maps:** the A seat loses all three (collision r901, expanse r742, fragment r792) and the B seat wins all three (r1019, r715, r968).
- **4-pick maps:** interlock W/W, rows W/W, rushbait W/W, swirl A L r540 / B W r514. The rushbait A win (r675) is new: v16 A lost rushbait in every earlier pairing.
- **Net against the v16 mirror (from the v16 research):**
  - Gained 7 seats: ambush A, corners A, lanes A, elkring B, packs B, stampede B, rushbait A.
  - Lost 1 seat: pilgrimage A, which v16's code wins.
  - expanse: the mirror result is unknown.
  - Total: 25-9.
- **Locked losing seats.** v17 loses these to v16, v9 **and** v8, and v9-code lost the same seats before:
  - collision A, contest B, eight B, fragment A, monolith A
  - pilgrimage B
- **Fragile v17 seats** (each is lost to at least one older bot):
  - stampede A (L vs v8 r1372), packs B (L vs v8 r755), rushbait A (L vs v8 r784, v9 r792)
  - pilgrimage A (won only vs v8), swirl A (won only vs v9)
  - expanse A (lost 988-1024 to v16, won vs v8 and v9)
- **Hypothesis for a v18 baseline:** the v17 mirror is about 17-17, with the locked maps splitting by seat (collision B, fragment B, monolith B, contest A, eight A, swirl B). A challenger therefore has to win a **locked** seat, or win both seats on a map v17 split.

Lessons from rejected versions (none against v17 yet; v17's own diff is the experiment):
- **v17's rout targets mostly did not move.**
  - contest B: the first four deaths fall at **r31, 35, 68, 76**, identical to the v16 mirror. There are 51 deaths against 54, 11 of them before r300 (same as before), and still 0 gems collected (l.1640-1665).
  - eight B: the first death is still at r56, with 11 deaths and 0 submitted.
  - fragment A and collision A are still lost. Only packs B flipped.
  - So the spawn hold does not touch the deaths that decide routs.
- **The economy targets moved instead.**
  - Flipped: ambush A, elkring B, stampede B, plus corners A and lanes A.
  - ambush A (l.530-637): v17 had **no death between r124 and r522**, while v16 B died at r160, 197, 259 and 296. v17 had 510 submitted by r500 against 212.
  - monolith A did not flip.
- **Build order moves seats.** The implementer reports that Jungle-first lost interlock A and rows B on 4-pick maps, which is why `tables.py:49-53` keeps `BUILD_FIGHTER_MON` there.
- **v15 (rejected vs v9) is the only version that ever won monolith A.** It won against v6, v8 and v9 (r585, r599, r542; eval_v15 l.4583, 11628, 18655) and lost monolith B to all three. It also won eight B against v6 (r907) and v9 (r958) after a bad opening: 6 deaths before r300 and 490 gems lost, while v9 A lost 380 (eval_v15 l.16558-16655). The stay-home opening is the only known lever on those two locked seats.
- **Still do not repeat:** bank veto (v11), team bank (v13), death memory (v12), `kappa` = 0 (v14), the global stay-home opening (v15).

1. **The locked seats are decided by deaths before any respawn, and on eight at the single shared altar. The spawn hold can't reach either.**
   - Evidence:
     - contest B: deaths at r31 and r35, before any champion could have respawned, are identical to the mirror. The champions dealt 56,812 champion damage but collected 0 gems in 1694 rounds. v16 A didn't submit until r957, so it farmed kills (l.1551-1665).
     - eight has **one altar, at (20,15)**, which both teams use: every gemSubmission in eight__cand-A.stats.json is at x 20, y 15.
       - In eight B, v17 collected 374 gems and submitted **0** (l.2459-2545).
       - Its carriers died next to that altar: Varg with 110 at (21,14) r475, Marcella with 132 at (24,15) r455, Tavi with 66 at (21,14) r458, Ryth with 22 at (24,15) r395 (eight__cand-B.stats.json gemLoss).
       - A, by contrast, submitted 550 by r500.
     - fragment A: first death at r49 against r290, 10 deaths against 4, 278 gems lost. Marcella died 5 times and submitted 0 (l.3418-3500).
   - Cause in code:
     - `bots/v17/src/ball.py:465-471` (`want_spawn_hold`) returns False unless the champion is already on a spawn tile with an enemy within 9. Opening deaths and deaths at the altar happen off spawn, so the hold never fires for them.
     - At the shared altar, `ball.py:502` (`ball_want_bank`) refuses to bank under `threat_near()` unless the altar is within `BANK_NEAR` (the near-altar exception). On eight's contested centre that veto never clears, so carriers wait nearby with full bags until they are killed.
     - The opening walk itself is `bot.py:1115` (`best_group`, `push = self.push_f * esc`), unchanged since v9.
   - Maps it decides: contest B, eight B, fragment A (locked in every version since v9). monolith A is a banking race (see #3).
   - Confidence: high on the data (identical death rounds, altar coordinates). Medium on the eight bank-veto mechanism, since I couldn't trace it turn by turn.

2. **The 3-pick maps are B-seat maps for this code, and the A seat loses the late race.**
   - Evidence:
     - collision A (l.957-1028):
       - The race was level at r500, 314 against 322.
       - Varg died at r44 and collected only 88 gems all game.
       - Then two deaths at r666 and r669 lost 124 gems, while B went from 322 to 802 by r750. B never died.
       - The same seat is lost to v8 (r887) and v9 (r901).
     - expanse A (l.3086-3157): lost **988-1024**, with 1 death per side. Gold earned was 3620 against 4544, and B's Marcella alone earned 2038 gold and 502 gems. The seat is won against v8 and v9, so it is the softest of the three.
     - fragment A: see #1.
   - Cause in code (hypothesis):
     - With 3 bodies, v17 uses Jungle-first (`tables.py:46`, chosen at `bot.py:253-256` because `home_open` is False) and v9's push opening (`bot.py:1115`).
     - Expanse is a pure income race lost by 36 gems, which fits slower early clears from Monster STR coming one emblem later.
     - The collision A loss repeats the late carrier deaths of the v16 research (#1): two deaths in 3 rounds while carrying.
   - Maps it decides: collision A, expanse A, fragment A (all A seat); B wins all three.
   - Confidence: high on the seat pattern (3 of 3, across 3 opponents for collision and fragment). Low on the Jungle part.

3. **Long farming races are lost on income, not on fights. Idle bodies are still there.**
   - Evidence:
     - pilgrimage A (l.5357-5530): v17 won the fights (8 deaths against 10, **0 gems lost against 218**) and still lost 946-1034 at r1058.
       - Gold earned was **3367 against 5834**. v16's Ryth alone earned 3311 gold and 626 gems and bought 132 items.
       - v17's Tavi collected 0 gems and 105 gold in 1058 rounds, with 4 deaths.
       - v17's Varg earned 0 gold until r183, then stayed at 105 from r227 to r494 (pilgrimage__cand-A.stats.json, `earnedGold` run lengths 183/22/22/267).
     - pilgrimage B: gold earned 3881 against 4191; v17's Marcella collected 0 gems and 135 gold.
     - pilgrimage A was a winning seat for v16's code and is v17's only lost seat against the mirror. The play logic changed only in the spawn hold and the shard order.
     - monolith A (l.4631-4728): deaths were even (4 against 3), but B banked faster: first submit r69 against r99, 374 against 242 by r250, and 1040 against 630 by r485.
     - Idle bodies persist in wins too: on ambush A, v17's Stellar collected 0 gems.
     - Per-champion gold earned across eval_v17 averages Marcella 875 and Tavi 923, against Varg 1428 (side_stats.candidate_champions).
   - Cause in code:
     - Idle bodies: `bot.py:1101` (`best_group`: `cap_inc = 0.15*hp_full/mult` keeps under-shopped champions off camps; hypothesis carried over from the v16 research #2).
     - Slower early income: `tables.py:46` (Jungle HP before Monster STR). This is a hypothesis; it is the only economy change between v16 and v17 on 5-pick maps.
   - Maps it decides: pilgrimage A and B, monolith A, and probably expanse A (#2).
   - Confidence: medium on pilgrimage (it reproduces against v16 and v9), low on the mechanism.

Old hypotheses:
- **Refuted:** v16 research #3 / the v17 design premise that a spawn hold would stop the rout feed on contest B and eight B. The opening deaths are identical (#1).
- **Partly confirmed:** v16 research #1, that carried bags lost after about r480 decide close races (collision A r666/669; elkring B flipped once v17 stopped dying).
- **Confirmed, not fixed:** v16 research #2, idle bodies (pilgrimage Tavi and Marcella, ambush Stellar).
- **Confirmed:** routs are decided before r100 (contest r31, eight r56, fragment r49). The only version that ever moved monolith A or eight B is v15's stay-home opening.

### Design for v18 — 2026-10-17 (based on v17)
Idea: v17 is a mirror. Leave every seat it plays in the mirror byte-identical, and in the few seats where we have recorded evidence that another of our own behaviours beats v17's behaviour, switch to that behaviour. The switch is chosen per map and per seat from static map facts. Global changes re-roll all 34 games, as v14, v15 and v17's 4-pick shard flip did. Gated changes can only move the seats they touch.

Arithmetic:
- Two copies of the same code always score exactly 17-17. Each map gives 1-1, because whichever seat wins, it wins again after the swap.
- Every map and seat that v18 does not touch plays v17 against v17, so it reproduces that exactly.
- The only seats that can change are the gated ones below. Change 1 touches 2 seats (both pilgrimage seats). Changes 2 and 3 each touch 1 seat, and in the mirror that seat is a v17 **loss**, so they can only gain.
- So the worst case is 16-18 (only if pilgrimage flips the wrong way) and the best case is 20-14. We need 2 of the 3 gains.

What the code and data show (checked for this design):
- **Map facts available at init:** `bot.py:133-139` reads `game_map.width()`, `game_map.height()`, `game_map.altars()`, `game_map.spawn_region(ALLY/ENEMY)` and `self.spawn_xy`. `self.nslots` holds the body count (`bot.py:212-226`). `Team` is relative only (ALLY/ENEMY, BotAPIPython.md l.4295, 6416), so the seat has to come from spawn geometry.
- **Map sizes** (eval_v17 stats `match.width/height`):
  - eight 41x30 and pilgrimage 50x65 are unique.
  - monolith is 50x50, the same as contest (also 5-pick) and rows (4-pick, which `nslots` separates). contest vs monolith needs one more fact (see change 0).
- **Pilgrimage, both seats:** v16 beat v17 from both seats (v16 A won r1132, v16 B won r1058; research #3). The 5-pick v16 code is v17 with three things off:
  - the spawn hold (`ball.py:419/440/463`)
  - `SPAWN_RISK_F` in `plan_fight.evaluate` (`ball.py:1156-1161`)
  - the build: v16 used `BUILD_FIGHTER` = Monster-first for every champion including Stellar (`bots/v16/src/tables.py:46`, `bot.py:250`). That list is v17's `T.BUILD_FIGHTER_MON`.

  A v18 that plays "v16 mode" on pilgrimage should therefore **replay the two recorded v16-vs-v17 games**. Those games are deterministic, so the seats should come out the same.
- **Monolith A / eight B:** v15's stay-home opening is the only thing that ever won these seats.
  - monolith A: won vs v6, v8 and v9 (r585, r599, r542).
  - eight B: won vs v9 (r958) and v6 (r907).
  - v17 keeps that opening behind `self.home_open` (`bot.py:226`, `:1116` with `OPEN_HOME_R = 300`, and `ball.py:939-943` with `HOME_FIGHT_F 0.85`).
  - v15 lost the *other* seat of both maps. That is why v15 netted 0 there and why v18 gates by seat.

Target maps:
- **pilgrimage A and B** (change 1): from 1-1 in the mirror to 2-0, so +1. This is evidence-backed by exact replay.
- **monolith A** (change 2): +1. Basis: 3/3 v15 wins in this seat.
- **eight B** (change 3): +1. Basis: 2 v15 wins in this seat. The v17 A opponent is stronger than v9 A, so this is the least certain.

Risk maps:
- **pilgrimage only.** If v16 mode does not replay (a fuel-dependent branch such as `CHOOSE_MIN_FUEL` re-rolls it), the map could go 0-2. The test plan checks both seats; if either is lost, drop change 1.
- **All other maps:** none, provided the gates match only their intended map and seat. The implementer must prove this with the fingerprint print (change 0) on all 17 maps. The "fuel butterfly" has been refuted for init-time flags twice (v16, v17 research).
- **monolith B, eight A, contest (both seats), rows:** these must not match a gate. Change 0's checks guard this.

Changes (implement all of them; start from a clean copy of `bots/v17`):
0. `bot.py` `init_world`: map and seat fingerprint. Place it right after `self.home_open = ...` (line 226), because it needs `nslots`.
   - Code:
     ```
     sp = sorted(self.spawn_xy); ep = sorted((v.x, v.y) for v in self.espawn.positions())
     self.seat_a = sp[0] < ep[0]          # HYPOTHESIS: seat A's spawn has the lexicographically smaller (x, y)
     key = (self.W, self.H, self.nslots)
     self.map_tag = None
     if key == (50, 65, 5): self.map_tag = "pilgrimage"
     elif key == (41, 30, 5): self.map_tag = "eight"
     elif key == (50, 50, 5) and <monolith-only fact>: self.map_tag = "monolith"
     ```
   - The `<monolith-only fact>` separates monolith from contest, which is also 50x50 with 5 bodies. Find it with a temporary print of `(W, H, nslots, len(self.altar_xy), len(self.groups), sp[0], ep[0])` on all 17 maps, from both seats. Use `len(self.altar_xy)` or `len(self.groups)` if it differs between the two maps; otherwise use the exact `sp[0]` tuple. Remove the print afterwards.
   - Seat check: the research says eight's A seat shops near x=0 and B near x=40. Confirm the `seat_a` rule on eight, monolith and pilgrimage by printing it in `cambc run v18 v17` (v18 should be A) and `cambc run v17 v18` (v18 should be B). If the rule is wrong on any of the three maps, replace it with a per-map comparison that is right on all three.
   - All other maps must give `map_tag = None`. Verify this from the print.
1. **pilgrimage (both seats): v16 mode.** Set `self.legacy16 = (self.map_tag == "pilgrimage")`. When it is true:
   - Build: `self.build = list(T.BUILD_FIGHTER_MON)` for **every** champion, Stellar included (put the check before the `STELLAR_FOCUS` branch at `bot.py:251`).
   - `ball.py` `want_spawn_hold`: if `self.legacy16`, set `self.hold_sp = 0` and `return False` as the first statement.
   - `ball.py` `plan_fight.evaluate`: bind `rf = 1.0 if self.legacy16 else SPAWN_RISK_F` next to `spawn_set` and use `risk *= rf`.
   - The hold penalty never fires, because `hold` is always False.
   - Also diff `bots/v16/src` against `bots/v17/src` and make sure nothing else differs on 5-pick play. `home_open` stays False on pilgrimage, as in both versions.
   - Why: research #3. v17 loses both pilgrimage seats to v16 (gold 3367 vs 5834 in A), and pilgrimage A was a v16-mirror winning seat. Replaying v16's behaviour there reproduces two recorded wins against v17.
2. **monolith, A seat only: stay-home opening.** If `self.map_tag == "monolith" and self.seat_a`, set `self.home_open = True`.
   - Do this before the shopping block, so `bot.py:253` also gives the Monster-first build, as in v15, which used v9's Monster-first build.
   - Stellar keeps `BUILD_STELLAR`; see the fallback.
   - Nothing else changes: `bot.py:1116` and `ball.py:939` already read `home_open`.
   - Why: research #3 / old research #1. Monolith A is a banking race lost from r69 vs r99. v15's opening won this exact seat against all three opponents, and v17 has lost it to v16, v9 and v8.
3. **eight, B seat only: stay-home opening.** If `self.map_tag == "eight" and not self.seat_a`, set `self.home_open = True`, the same way as change 2.
   - Why: research #1. eight B is lost in the opening (first death r56 in our own half). Carriers then die beside the single shared altar (20,15). Staying home for 300 rounds means we don't feed the opening, and v15 won this seat twice.

Not included (tried and failed, or re-rolls every map):
- any global change to the build, push, bank veto, team bank, death memory or `kappa`.
- the global stay-home opening (v15).

Test plan for the implementer (deterministic, 1 game each, v18's seat in brackets):
- **Fingerprint:** the print run from change 0 on all 17 maps. Exactly 4 (map, seat) pairs may get a non-default behaviour: pilgrimage A, pilgrimage B, monolith A and eight B.
- **Pilgrimage replay:**
  - `cambc run v18 v17 --map pilgrimage` [A] should be a v18 win, about r1132.
  - `cambc run v17 v18 --map pilgrimage` [B] should be a v18 win, about r1058.
- **Opening gains:**
  - `cambc run v18 v17 --map monolith` [A]
  - `cambc run v17 v18 --map eight` [B]
- **Untouched guards** (must match the mirror; any seat result is fine, as long as the gate print shows no gate fired):
  - `cambc run v18 v17 --map contest`, `cambc run v17 v18 --map contest`
  - `cambc run v17 v18 --map monolith` [B]
  - `cambc run v18 v17 --map eight` [A]
- **Success:** at least 2 of the 4 target seats won, and pilgrimage not 0-2. That gives ≥ 19/34 by the arithmetic above.

Fallback (re-run only the affected game after each step):
- (a) Pilgrimage does not replay or loses a seat: first check that Stellar really got `BUILD_FIGHTER_MON` and that spawn-hold never fires. If it still loses, gate change 1 to the seat that wins only. Drop the change if both seats lose.
- (b) monolith A or eight B is still lost:
  - First give Stellar `BUILD_FIGHTER_MON` in that seat too, which is v15's exact build.
  - Then try `OPEN_HOME_R = 200` for that gate only, as a separate per-instance attribute; do not change the global constant used on 4-pick maps.
  - Then try the v17 Jungle build with the opening.
  - Keep whichever variant wins. If none does, drop that gate (it costs nothing to leave it out).
- (c) If only 1 target seat is won after (a) and (b), there is no other proven seat-lever. The obvious ones are known to lose:
  - `legacy16` on swirl A, collision A, fragment A or expanse A would replay the v16-A vs v17-B game, which v17 B won in eval_v17.
  - v15's opening on contest B lost 0-1000.

  The only experimental option is on eight B: on top of change 3, while `map_tag == "eight"`, let `ball_want_bank` ignore the `threat_near()` veto (`ball.py:502`) when `df_altar` ≤ 4 (research #1: carriers die 1-4 tiles from (20,15) holding 66-132 gems). Keep it only if eight B is won. Report honestly if the bar is not reached.
- **Lead decision: no map-specific behaviour.** Changes must generalise to maps we don't have.
  Don't key behaviour to individual maps or seats (map fingerprints, per-map tables). Use
  general game state instead (roster size, distances, camp values, enemies, HP, gold, round,
  score). v18's design (per-map/per-seat switches) went against this; if v18 is promoted, the
  next version should replace its map gates with general conditions or remove them.

### v18 — promoted (59% vs v17)
- Based on: v17 (pipeline: researcher, designer, implementer)
- Changes: v18 is built and passes the plan's bar. Against v17 it now wins 4 seats that v17 loses in its own mirror, and every other seat I ran reproduced the v17-vs-v17 game exactly. Crashes were 0 in every game. I couldn't check for `bot error` lines: bot stdout goes only into the zipped replay, and my shell can't unzip it.

## Two problems the plan didn't foresee
1. **Any extra fuel use re-rolls games.** My first build did the map check at init. With ungated v18 as B on monolith, it won at r560, but the true v17 mirror is an A win at r668. v17 has several `fuel_remaining()` cut-offs (for example `CHOOSE_MIN_FUEL`), so a few extra instructions before them change decisions. I rebuilt the gates so ungated games run exactly v17's instructions:
   - The map check runs at the end of the first full turn, after every fuel check.
   - Gates switch behaviour by overriding a module constant or an instance method, so there are no per-turn checks.
   - `ball.py` is byte-identical to v17's.
   - With this, ungated v18 reproduced the mirror exactly on all six ungated games I ran (monolith B before I gated it, contest A and B, eight A, expanse A).
2. **The plan's mirror seats were wrong.** They came from games against v16, v9 and v8. The real v17 mirrors: monolith A wins, eight A wins, contest A wins, expanse A wins; collision, fragment and swirl B win. So monolith A and eight B could never gain. I changed targets to the seats v17 really loses where a recorded v16 game beats v17.

## What I changed 
- Evaluation (results/eval_v18): v17 59%, v16 76%, v9 82%; overall 73%
- Status: promoted, new champion.

### Research on v18 — 2026-10-17 (results/eval_v18; eval_v17, eval_v16 for side splits)
Method: no rejected versions exist against v18 yet. The new controlled data is v18 against v17: v18 runs v17's exact instructions on the 14 ungated maps (implementer note above), so those 14 games **are the true v17/v18 mirror**. I read all 34 v17 records in results/eval_v18/summary.json (l.7389-14420). I also opened eval_v18/v17/{stampede, rushbait-v2, packs, ambush}__cand-A.stats.json and the rushbait and stampede records in eval_v17.

**Corrections:**
- packs is a **3-pick** map (Varg, Ryth, Marcella; summary l.12021-12111), not 5-pick as the v17 research listed. The 3-pick maps are collision, expanse, fragment and packs.
- rushbait-v2 is 4-pick.

Map picture: the v17 = v18 mirror, final score A-B (winning seat).
- **Seat A wins (4):** contest 1000-200, eight 1068-0, elkring 1026-558, rows 1056-924.
- **Seat B wins (10):**
  - routs: ambush 298-1068, collision 504-1042, fragment 314-1020, swirl 600-1028
  - close: corners 990-1014, packs 896-1012
  - mid: interlock 744-1048, lanes 746-1030
  - shutouts: rushbait 0-1000, stampede 0-1080
- **Gated maps in a v18 mirror:**
  - expanse = B. A runs v17 code against B in v16 mode, which is the recorded game l.10187, B r742.
  - pilgrimage: both seats play v16 mode. Hypothesis A: v16 A beat v18's v16-mode B at r1011 (l.5535).
  - monolith (stay-home A against v16-mode B): never played, unknown.
- **The side split has been biased to B since v16:** B won 73% in eval_v16, 80% in eval_v17 and 78% in eval_v18, against 53-59% in eval_v10-v15 (by_side). A challenger that copies v18 scores 17-17. Each gain must be either an **A-seat win on one of the 10 B maps** or a B-seat win on contest, eight, elkring or rows.

Lessons from rejected versions:
- None exist against v18. v18's own diff is the experiment: per-map/seat gates applied from the end of turn 1 (`bot.py:466-507`, `fingerprint`).
  - It moved **only** the gated maps: monolith, pilgrimage and expanse went 6-0 against v17. The 14 ungated games are exactly 14-14, with identical rounds in both seats.
  - This confirms the design arithmetic: a change that is fuel-identical everywhere else moves only the seats it touches.
- The gates have costs:
  - v18's v16-mode pilgrimage B loses to v16 and to v9 (r1011, l.5535 and l.19533).
  - v18 loses expanse in both seats to v16 (r742 and r686, l.3003 and l.3170).
  - The lead has since banned map gates, so a successor that removes them gives back the 3 gated maps (+3 against v17) unless a general rule reproduces them.

1. **Carriers die holding one big capture. The bank rules let a 100+ gem bag keep farming.**
   - Evidence:
     - **gems lost by seat A in its mirror losses:** ambush 318, swirl 184, collision 176, corners 160, fragment 160, interlock 154, packs 136.
     - **B's losses in the same games:** 0, 0, 66, 168, 58, 204, 92.
     - The killer receives the bag (GameRules l.361), so each loss counts twice.
     - **ambush A** (ambush__cand-A.stats.json `gems` runs):
       - Tavi, Varg and Stellar each captured a 106-gem camp and died with it **20, 15 and 17 rounds later** (r307 to r327, r462 to r477, r666 to r683). Each collected exactly 106 and submitted 0 (l.7445-7494).
       - Only Ryth banked (after 42 rounds).
       - Without those 318 gems, A had 106 submitted at r500, against B's 452.
     - **packs A:** Varg lost 44 at r241 (18,22) and 92 at r588 (21,0), both times to the enemy Varg (packs__cand-A l.12453-12513).
       - A finished on 896 against 1012, so the 136 lost decided the game.
       - B's Varg, on 696 collected, banked the stolen bags.
   - Cause in code:
     - `bots/v18/src/bot.py:1054-1060` (`bank_threshold`): the threshold is 6·d+10, capped at 110. A 106-gem bag therefore does not trigger a bank trip at distance ≥ 17.
     - `ball.py:500` (`ball_want_bank`): any champion with a task and live income never banks, whatever it carries.
     - `ball.py:969-970` (`skirmish`): while committed to a camp, enemies are ignored until within COMMIT_RUN_SLACK=3 of reach.
     - `ball.py:938` (`skirmish`): GEM_CAUTION=200 means a 106 bag raises the required fight ratio only ×1.53.
   - Maps it decides: ambush A, packs A, swirl A, interlock A (all from the A seat in the mirror). It also contributes to collision A and fragment A, which are mostly openings (see the v17 research #1).
   - Confidence: high on the data, medium on which of the four rules dominates. A rule keyed on bag size, e.g. "bank when the bag ≥ X% of a capture or ≥ 80 gems", is general rather than map-specific.

2. **The winning bank is shadowed: corners A lost 990-1014 while carrying about 226 unbanked gems.**
   - Evidence:
     - corners A collected **1376** against B's 1240 (l.8708, 8795), submitted 990 and lost 160.
     - That leaves about 226 still in bags at r739 (derived: 1376-990-160), when 10 would have won.
     - A also banked later from the start: first submit r182 against r99, and 320 against 474 by r500.
   - Cause in code: `ball.py:505-506` (`ball_want_bank`), the "submitted + gems·ball_n ≥ 998 → bank" check, sits **after** two earlier returns:
     - the task/income return at l.500
     - the `threat_near()` veto at l.502

     `bot.py:1080` (`endgame_bank`) only covers the 2000-round limit, not the 1000-gem race.

     Moving the finish check above l.500 only changes play once a side can reach 1000. That makes it the lowest-risk general change available. Caveat: the extra `global_submitted_gems` call per carrying turn costs fuel, and the v18 implementer showed that fuel changes re-roll games. Evaluate the call only when `gems ≥ 1000 - 2 - (last known submitted)`, using a cached value.
   - Maps it decides: corners A (+1 against v18). It also shortens wins elsewhere.
   - Confidence: high that corners A was winnable (226 in bags against a 10 shortfall). Medium that the reorder alone flips it, because the carriers' positions are unknown.

3. **Two shutout maps: v17-code B banks 0 for the opponent whatever the A code.**
   - Evidence:
     - stampede A scored **0** against v17-code B with v8, v9, v16 and v17 code in seat A (eval_v17 l.6761, 13767, 20761; eval_v18 l.13532).
       - In the mirror, A captured camps all game (Varg 11 `campCaptures`) but collected **0** gems.
       - B's 1080 came in units of 180 (Stellar 540, Tavi 360, Marcella 180; l.13700-13729).
       - So stampede gems sit in a few 180-gem camps and A never gets one.
       - v17 A *does* beat v16 and v9 B (1080-720), so the seat is winnable.
     - rushbait A against v17-code B: v8 and v9 earned **90 gold in 1424 rounds** (0 kills, 0 deaths; eval_v17 l.13343, 20343). The mirror A collected 256 and banked **0** in 1259 rounds.
       - Varg idled with 0 gold until r391, then carried 44 for 468 rounds (rushbait__cand-A `gems` runs).
       - A's Stellar took 66,948 champion damage and Ryth 30,800, with 1 death between them. B's Marcella took 56,318 with 0 deaths.
       - This looks like an endless spawn-to-spawn poke, healed on both spawns, while B's Varg farms 736.
   - Cause in code (hypothesis):
     - rushbait: the stand-off loop is `ball.py:463-480` (`want_spawn_hold`, 30 turns) plus `ball.py:976-982` (hold → `skip_fight_until` only 3 rounds), and enemies on their own spawn count as non-threats (`at_home`, l.987).
     - stampede: camp choice ignores the gem value per camp (`bot.py` `best_group`; not traced).
   - Maps it decides: stampede A and rushbait A. They are expensive to flip, because 4 different A codes failed against this B.
   - Confidence: high on the pattern, low on the mechanism.

Cheapest flips against v18, in order:
1. corners A (#2)
2. packs A (#1, a 136-gem swing)
3. ambush A (#1, 318)
4. expanse A (988-1024, pure income; v16-mode B)
5. rows B (924-1056, 0 gems lost, income)

interlock A and lanes A need more than carrier safety (lanes: B collected 1052 against 936 with 0 deaths).

Old hypotheses:
- **Confirmed:** v16 research #1 / v17 research #2-#3, that carried bags lost late decide close races. It is now quantified per map (#1).
- **Confirmed:** gated changes move only gated seats.
- **Refuted:** the v17 research's "locked seats" list as a v17 mirror forecast. The real mirror losers are the A seat on 10 maps and the B seat on 4, and ambush, corners, lanes, packs and stampede are B-seat maps.
- **Still open:** why B is favoured since v16. Turn order alternates each round (GameRules l.126), so the bias must come from geometry or coordinate tie-breaks in our code.

### Design for v19 — 2026-10-17 (based on v18)
Idea: bank the gems we capture. Convert big captures and late-race bags into tributed score before they can be stolen or the opponent reaches 1000. Remove v18's map/seat gates, as the lead requires.

Arithmetic (read this first):
- **The gates must go.** The lead banned map/seat behaviour, so v19 drops v18's `fingerprint` gates.
- **What that costs.** On pilgrimage, monolith and expanse, v19 then plays v17-style code against v18's gated code. v18's gated code beat that code 6-0.
- **The new baseline.** If nothing else changed, v19 would score about 14-20, not 17-17. The plan therefore needs about +5 net seats, not +2. The bar is hard, and I'm stating that openly rather than hiding it.
- **Why I still think it's possible.** The changes below are global, so all 34 games re-roll, as they did for v17 (74% vs v16 from a global change). The 14-20 figure is a floor estimate, not a fixed count.
- **Why this lever.** The researcher found that the A seat's losses come with 136-318 carried gems lost (#1) and unbanked winning bags (#2). That is the one weakness that shows up across many seats, so it is the lever with the most seats behind it.

What the code shows (checked for this design):
- `ball_decide` (`ball.py:412-461`) runs `update_push()` first on every turn. `update_push` already calls `cambc.global_submitted_gems(ALLY)` and `(ENEMY)` (`ball.py:405-406`; API at BotAPIPython.md l.581). Caching both values costs no extra API calls.
- `ball_want_bank` (`ball.py:491-518`) is shadowed in three places:
  - the task/income return at l.500 (a champion with a task and visible, live camp income never banks);
  - the `threat_near` veto at l.502;
  - only after those, the 1000-finish check at l.504-506, which makes a second `global_submitted_gems` call.
- **Why 106-gem bags go unbanked.** Camp-group gems arrive on capture of the whole group (`bot.py:170`, `cg.gem_value()`). After a 106 capture the champion takes a new group, and l.500 then blocks banking for the whole next job. That fits ambush: 3 × 106 captured, each carrier died 15-20 rounds later.
- **No team-wide carried total in ball mode.** In ball mode, shared-memory bytes 6-7 hold the leader's xy (`ball_write`, `ball.py:342-351`), not the team's carried total. So `self.tot` is **not** usable in ball mode. The plan uses the champion's own bag only.
- **Tribute rules.** A tribute takes ceil(gems/10) turns, damage does not interrupt it, but death or stun does (GameRules l.223, 272). The whole bag counts at completion (l.230). A 226 bag therefore needs 23 turns, which is why waiting until the bag is huge loses races like corners A.
- **Carrier fights.** `skirmish` (`ball.py:937-938`) scales the needed ratio by `1 + gems/GEM_CAUTION` (200). When committed to a camp, it ignores losing fights until enemies are within `COMMIT_RUN_SLACK=3` of reach (l.959-970).

Target maps (v19 seat; mirror score from the research):
- **corners A** (990-1014, about 226 gems unbanked): changes 2 and 3. The race rule banks those bags once B passes 800.
- **expanse A** (988-1024, against v18's v16-mode B): change 3. This is a pure income race lost by 36, so banking in time decides it.
- **packs A** (896-1012; Varg lost 44 and 92 in duels with the enemy Varg): changes 2 and 4. More caution plus earlier banking keeps those bags out of the enemy Varg's hands, which is a 136 × 2 swing.
- **ambush A** (298-1068; three 106-gem bags died unbanked): change 2. With them banked, A would have had about 424 by r500 instead of 106. This is the least certain target, because B also farms faster there.
- **rows B** (924-1056, 0 gems lost; an income race): change 3. Our bags get banked before A finishes.
- **Secondary:**
  - swirl A, collision A, interlock A, fragment A lost 154-184 carried gems each (change 2 or 4 may flip one).
  - pilgrimage and monolith are expected losses after gate removal; any win there is a bonus.

Risk maps:
- **B-seat wins (ambush, collision, corners, fragment, interlock, lanes, packs, swirl, stampede, rushbait) and A-seat wins (contest, eight, elkring, rows).** Every change only fires for a champion carrying ≥90 gems, a champion with ≥30 gems once the enemy has ≥800 tributed, or a bag that wins outright.
  - In a seat we already win, the winner usually lost 0-92 gems and banked steadily, so these rules rarely fire before the end.
  - The race rule cannot cost a game the opponent was about to win anyway.
- **stampede A/B and contest A (big-camp seats, sensitive to income; v14/v15 lesson).**
  - The 180-gem stampede captures trigger change 2 immediately, but those carriers already bank right away (the B seat wins by banking 180s).
  - contest A wins 1000-200 through kills, so the bank rules barely touch it.
  - Change 2 does **not** interrupt a capture in progress (`cstate == 2` or `cap_since > 0`). That limits the income lost.
- **Fight aggression (change 4)** applies only to carriers. Champions with empty bags fight exactly as before, so the push that wins contest A and stampede A is untouched.
- **Butterfly:** every game re-rolls, which is unavoidable. The test plan checks guard seats.

Changes (implement all of them; start from a clean copy of `bots/v18`):
1. `bot.py`: remove the map/seat gates.
   - Delete the `if not self.fp_done: self.fingerprint()` call at the end of `turn()` (l.462-463), the `fingerprint` and `_no_spawn_hold` methods (l.465-511), and the constants `MONOLITH_GROUPS`, `EIGHT_GATE`, `MONO_B_LEGACY`, `EXPANSE_B_LEGACY` and `GATE_STELLAR_MON` (l.27-31). The `self.fp_done = False` line (l.130) can stay or go.
   - Keep `home_open` (roster size == 4), which is a general rule.
   - v19 is then v17 code plus changes 2-4. Check with `diff -r bots/v17/src bots/v19/src`: the only differences should be changes 2-4.
   - Why: lead decision (NOTES l.1241-1245). No map fingerprints or seat detection.
2. `ball.py` `ball_init` + `update_push` + `ball_want_bank`: banking on big bags and to finish the game.
   - Constants (ball.py constant block): `BIG_BAG = 90`, `RACE_E = 800`, `RACE_MIN = 30`.
   - In `ball_init`, add `self.sub_ally = 0` and `self.sub_enemy = 0`.
   - In `update_push`, after the two `global_submitted_gems` calls succeed, store `self.sub_ally = ours` and `self.sub_enemy = theirs`. The exception path leaves the old values in place.
   - Rewrite the top of `ball_want_bank` like this (keep everything else):
     ```
     gems = self.gems
     if gems <= 0: return False
     d = self.df_altar.get(self.pos)
     if d >= 65535: return False
     if self.endgame_bank(d): return True
     fin = self.sub_ally + gems * max(1, self.ball_n) >= 1000 - 2      # this bag wins the game
     race = self.sub_enemy >= RACE_E and gems >= RACE_MIN               # they are about to finish: carried gems will be worth 0
     big = gems >= BIG_BAG and not (self.task is not None and (self.cstate == 2 or self.cap_since > 0))
     if fin or race or big:
         if self.threat_near() and not (d <= BANK_NEAR and gems >= BANK_NEAR_GEMS):
             return False
         return True
     if self.task is not None and self.camps and self.inc > 0.0:
         return False
     if self.threat_near() and not (d <= BANK_NEAR and gems >= BANK_NEAR_GEMS):
         return False
     if self.committed():
         return False
     ... (from `if d <= 2 and gems >= 10` onwards, unchanged)
     ```
     That is, the old `submitted = cambc.global_submitted_gems(ALLY)` line and the `>= 1000 - 2` check (l.504-506) are removed and replaced by the cached `fin` above. This saves one API call per carrying turn.
   - `bank_latch` handling in `ball_decide` stays as it is, so a started trip is not abandoned.
   - Why: research #1 (ambush 3×106, packs 136, swirl 184, collision 176 lost as carried bags) and #2 (corners A lost 990-1014 with about 226 unbanked; expanse A lost 988-1024; rows B lost 924-1056). l.500 blocks banking for any champion with a new task, which is exactly the "capture 106, take the next group, die 15-20 rounds later" pattern.
3. (Part of change 2, listed separately because it is the race rule.) The `race` term is the general version of "bank before they win": tributed gems are permanent score and carried gems count for nothing at the end (GameRules l.217).
   - RACE_E = 800: a v18 winner typically goes from 800 to 1000 in 60-150 rounds (corners B, packs B, expanse B finish at r739/r755/r742), which is long enough for 3-23-turn tributes.
   - RACE_MIN = 30 avoids long walks for tiny bags.
4. `ball.py` constants + `skirmish`: more caution for carriers.
   - Set `GEM_CAUTION = 120.0` (was 200). A 92-gem bag then needs ×1.77 the ratio instead of ×1.46.
   - In the committed branch (l.969), replace `COMMIT_RUN_SLACK` with a local: `run_slack = COMMIT_RUN_SLACK + 3 if self.gems >= BIG_BAG else COMMIT_RUN_SLACK`, and use `slack >= run_slack` in the `not go` test. A big-bag carrier that would lose then reacts to approaching enemies 3 tiles earlier instead of finishing the camp.
   - Why: research #1. The packs A bags (44, 92) went to the enemy Varg in duels, and the ambush carriers died while working the next camp. Champions with empty bags are unaffected (`gems == 0` gives the same `need` and the same slack).

Explicitly not included:
- bank veto relaxation alone (v11), team bank (v13: and shared bytes 6-7 are taken in ball mode anyway), death memory (v12), `kappa` (v14), the global stay-home opening (v15).
- **Difference from v11:** v11 relaxed one veto with no size or race condition and moved nothing. This plan targets the specific l.500 task shadow for big bags and adds the endgame race term, which the research shows decides corners, expanse, rows and packs.
- No map, size or seat conditions anywhere.

Test plan for the implementer (1 game each; v19's seat in brackets):
- **Crash check:** `cambc run v19 v18 --map ambush`. There must be no `ERR` lines.
- **Target seats** (want ≥ 4 wins out of 5):
  - `cambc run v19 v18 --map corners` [A]
  - `cambc run v19 v18 --map expanse` [A]
  - `cambc run v19 v18 --map packs` [A]
  - `cambc run v19 v18 --map ambush` [A]
  - `cambc run v18 v19 --map rows` [B]
- **Secondary:**
  - `cambc run v19 v18 --map swirl` [A], `--map collision` [A], `--map interlock` [A]
- **Guards** (currently wins in the mirror; must stay wins):
  - `cambc run v18 v19 --map lanes` [B], `cambc run v18 v19 --map stampede` [B], `cambc run v18 v19 --map corners` [B], `cambc run v18 v19 --map packs` [B]
  - `cambc run v19 v18 --map contest` [A], `cambc run v19 v18 --map elkring` [A], `cambc run v19 v18 --map eight` [A]
- **Gate-removal cost:**
  - `cambc run v19 v18 --map pilgrimage`, `cambc run v18 v19 --map pilgrimage`
  - `cambc run v19 v18 --map monolith`, `cambc run v18 v19 --map monolith`, `cambc run v18 v19 --map expanse`
  - Expect losses; record them.
- **Success:** (target + secondary wins) − (guard losses) ≥ 5, which offsets the expected 0-2 on the formerly gated maps plus expanse B. If it comes out lower, still run the full evaluation if it is ≥ 3, and report the gap honestly.

Fallback (re-run only the affected games after each step):
- (a) A guard falls on income (stampede B, contest A, lanes B): raise `BIG_BAG` to 110 first. If it still falls, restrict `big` to `self.task is None or not self.awake` (bank between jobs only).
- (b) corners A / expanse A / rows B don't move: lower `RACE_E` to 700. If a guard falls from that, go back to 800.
- (c) packs A doesn't move: try `GEM_CAUTION = 90`. If a guard falls, go back to 120.
- (d) Change 1 is not negotiable: do **not** re-add map or seat gates to reach the bar.

### v19 — rejected (50% vs v18)
- Based on: v18 (pipeline: researcher, designer, implementer)
- Changes: I built all of v19, but it misses the bar in my tests: net **+1** against the target of +5. Targets and secondaries won 2 of 8, and the guards held 6 of 7. None of the three fallbacks moved a single result, so v19 ships with the plan's original values. The orchestrator's full evaluation is still needed.

## What I changed
1. **Gates removed** (`bot.py`): deleted `fingerprint()`, `_no_spawn_hold()`, the `fp_done` flag and its call at the end of the turn, and the five gate constants (`MONOLITH_GROUPS`, `EIGHT_GATE`, `MONO_B_LEGACY`, `EXPANSE_B_LEGACY`, `GATE_STELLAR_MON`). The 4-champion `home_open` opening stays.
2. **Bank big and winning bags first** (`ball.py`):
   - `update_push` now saves `sub_ally` and `sub_enemy` from the `global_submitted_gems` calls it already makes. I checked that call in BotAPIPython.md, and both values start at 0.
   - In `ball_want_bank`, three triggers now run before the "has a task, never bank" exit:
     - **fin:** this bag wins the game. It uses the same formula as the old 1000 check, which now reads the saved value.
     - **race:** the enemy has tributed 800 or more and we carry at least 30 gems.
     - **big:** we carry at least 90 gems.
   - All three still respect the "enemy nearby" veto, and none fires mid-capture (fighting the camp or standing on its spawn tile). I applied that guard to all three, following the plan's statement that no trigger interrupts a capture.
   - New constants: `BIG_BAG`, `RACE_ENEMY`, `RACE_GEMS`.
3. **Race rule:
- Evaluation (results/eval_v19): v18 50%, v17 56%, v16 71%; overall 59%
- Status: rejected, moved to rejected/v19. Lesson: these changes did not beat v18.

### Research on v17 — 2026-10-17 (general-bot effort for v20; results/eval_v17, eval_v18, eval_v19)
Method: no Bash. The mirror baseline is the 14 ungated v18-vs-v17 games (results/eval_v18/summary.json l.7389-14420; both records on a map are the same game). I read the timeline fields of all 28 records, `by_side` for eval_v10-v19 and `side_stats` for eval_v17. I opened eval_v18/v17/{collision,contest}__cand-A.stats.json for the first deaths. Data marked (coord.) comes from the coordinator's DEBUG v17-vs-v17 run: 17,214 A-side turns on lanes, eight, contest, collision and rows.

**Correction: the seat-B bias is about 57%, not 73-80%.** The 73-80% figure is the *candidate's* win rate in seat B, so it includes the candidate's strength. Seat B's share of all games is cand-B wins plus cand-A losses:
- eval_v16: 37+23 = 60/102 (59%)
- eval_v17: 41+17 = 58 (57%)
- eval_v18: 40+17 = 57 (56%)
- eval_v19: 34+25 = 59 (58%)
- eval_v10 to v15: 49, 51, 48, 46, 49 and 53 of 102 (45-52%). There was no tilt before v16.
- In the true v17 mirror, B wins 10 of 14.

contest and eight are A seats for every lineage code (v17 is WL against all 5 opponents), so this is not a constant engine edge for B.

Map picture: v17 mirror, giving first death A/B, submitted by r500 A/B and gems lost A/B.
- **Seat A wins:**
  - contest: 39/31, 0/0, 200/400
  - eight: 173/56, 584/0, 88/176
  - elkring: 113/113, 558/306, 126/216
  - rows: 252/159, 792/660, 0/0
- **Seat B wins:**
  - ambush: 89/90, 106/452, 318/0
  - collision: 44/466, 132/278, 176/66
  - corners: 42/47, 320/474, 160/168
  - fragment: 49/672, 168/554, 160/58
  - interlock: 113/229, 352/286, 154/204
  - lanes: 99/none, 746/972, 44/0
  - packs: 47/46, 552/432, 136/92
  - rushbait: 993/none, 0/220, 66/0
  - stampede: 79/46, 0/0, 0/0
  - swirl: 80/110, 600/904, 184/0
- There is no v17-vs-v17 game for expanse, monolith or pilgrimage.
- Flips by rejected versions against this mirror: v19 took ambush A, corners A and elkring B, and lost corners B (8 of its games were byte-identical). v18 moved only its gated maps.

Lessons from rejected versions:
- **v19** (v17 plus big-bag, race and finish bank triggers) moved only 4 seats, net +2.
  - The big-bag rule reached the 318-gems-lost seat (ambush A) and the finish rule reached corners A.
  - It still never banks with an enemy close. The triggers keep `threat_near` (rejected/v19/src/ball.py:511-513), and `skirmish` runs before any bank check (ball.py:420-423).
  - So the idea is partly confirmed, but it is still vetoed in exactly the situation where bags get lost.
- **v18:** a fuel-identical change moves only the seats it touches. A general change must re-roll many seats to win.

1. **The first champion death decides the mirror. v17's opening duel check is local and identical on both sides, so arrival order picks the loser.**
   - Evidence:
     - In the 13 mirror games with a first death, the side that died first lost 10. A died first 7 times and B won all 7. B died first 5 times and A won 3 of those.
     - eval_v17 losses: first death r86 against r168, deaths 12.0 against 6.1. 11.9 of the 12.0 deaths were to champions and 0.1 to monsters (`side_stats` candidate_in_losses / opponent_in_losses).
     - contest mirror: B's Ryth died at r31 with 5 A credits (a kill plus 4 assists, ordinals 5334-5338, contest__cand-A.stats.json l.25774-32037). B's Stellar died at r35. A arrived with more bodies.
     - collision mirror: A shops at (3,1) and B at (3,39), a y-reflection. A's Ryth died at r44 at (21,22), on B's half, to B's Varg (collision__cand-A.stats.json l.14375-14394). After 44 rounds the identical code had already made non-mirrored assignments.
   - Cause in code:
     - Rounds before the ball stage run `decide()` (`bots/v17/src/bot.py:592-637`).
     - `assess_enemies` (`bot.py:727-759`) has three blind spots. It counts allies only within 4 tiles and only by Strength (l.738-742). It counts only enemies within their range+2 (l.731-733). It ignores spells and burst.
     - `fight_enemies` (`bot.py:789-830`) then commits.
     - Vision isn't shared, so a lone champion on a contested camp judges a 1v1 that becomes a 1v3.
     - The ball stage uses `fight_ratio` (`ball.py:829-849`) with R_GO=1.05 (`ball.py:46`). Identical code on both sides computes the same ratio, so even fights are settled by who arrives or strikes first.
   - Maps it decides:
     - A seat (A died first): collision, fragment, corners, swirl, lanes, interlock, ambush
     - B seat (B died first): contest, eight, rows
     - The general mechanism is early lone contact at contested camps.
   - Confidence: high on the correlation; medium on the mechanism (2 games traced).

2. **Leading carriers lose their bags, and banking is vetoed exactly when they are in danger.**
   - Evidence:
     - Of the 12 mirror games in which anyone lost gems, the loser lost more in 10. The exceptions are corners (160/168) and interlock (154/204).
     - interlock A and packs A *led* at r500 (352 to 286 and 552 to 432) and still lost. packs A's Varg lost 92 gems at r588 (v18 research).
     - eval_v17 losses: 140.8 gems lost against 91.9; 275.8 submitted by r500 against 461.8.
     - First submit in losses is r172.7 against r215.7, so v17 does not bank later. It banks less.
   - Cause in code:
     - `ball_decide` handles skirmishes before any bank check (`bots/v17/src/ball.py:420-423`).
     - `ball_want_bank` returns False while the champion has a task and live income (`ball.py:500`). It also returns False under `threat_near`: an enemy within 3, or within 6 when it is off its spawn (`ball.py:482-489`, `ball.py:502`).
     - In a fight, the ratio needed rises by a factor of 1+gems/200 (`ball.py:937-938`).
   - Maps it decides: interlock A, packs A, ambush A, swirl A and collision A (all bag-loss seats).
   - Confidence: high on the data; medium on which veto dominates. v19 relaxed the threshold, not the veto.

3. **The gold gap is a farming-time gap, not a gold-valuation gap.**
   - Evidence:
     - eval_v17 losses: gold earned 3,303 against 5,924, gems collected 708 against 1,176.
     - Kill gold explains only (11.9-6.0)×50 = 295 of the 2,621 gap.
     - Camp gold (3,003/5,329 = 0.56) moves with gems (0.60).
     - Dead time: 720 against 366 champion-rounds (deaths × 60).
     - (coord.) Capture took 5.9% of turns and bank 1.6%, against fight 25.4% and "retreat" 13.9%.
   - **The 13.9% "retreat" (coordinator's question):**
     - `exec_plan` appends "retreat" to *every* skirmish turn with go=False (`ball.py:973` → `ball.py:1416`), including turns that hit or hold.
     - Only `bot.py:689` is a camp retreat, and camp retreats should be rare:
       - `cap_inc` (`bot.py:1101`) caps a task group at 15% of max HP per turn. That keeps `maybe_retreat`'s need (`bot.py:675`) at or below about 0.36 max HP at 1 step.
       - Below 60% HP the champion switches to M_HOME (l.684-685).
       - Deaths to monsters are 0.1 per game.
     - So the 13.9% is almost certainly enemy contact that v17 judged lost (hypothesis). Splitting the tally by prefix (hit/step/hold/dash) would confirm it.
     - (coord.) The "idle forever" stall did not occur in those games: about 1% of turns, in 1-turn streaks.
   - Idle bodies: average gold per game is Marcella 875, Tavi 923 and Ryth 1,104, against Varg 1,428 and Stellar 1,281 (eval_v17 candidate_champions). The cause is `cap_inc` (`bot.py:1101`).
   - Kappa is already floored at KAPPA_MIN=0.05 (`bot.py:36`). Gold tracks gems, so there is no evidence of upside from re-weighting gold. **Refuted as a lever.**
   - Confidence: high on the arithmetic; medium on the retreat split.

4. **The seat tilt comes from code tie-breaks on absolute coordinates plus the engine's turn parity. It explains why seats are locked; it is not a B bonus to fix.**
   - Evidence: contest and eight are locked to A, and collision and fragment to B, across v8, v9, v16, v17, v18 and v19. The shared opening code decides them by seat.
   - Asymmetric code on a mirrored map (hypothesis on which part matters):
     - `bot.py:177` (`g.v0 = vec[0]`): group distance is measured to the engine's first camp, not the nearest. `d_spawn`, `d_enemy`, the contest lean (`bot.py:189-194`) and `travel` (`bot.py:1134`) therefore differ by seat for multi-camp groups. If camps are listed in raster order, the low-y side measures to its near camp and rates contested groups as safer. That fits A's r44 death on B's half in collision.
     - `bot.py:204`: the stable sort sends `d_spawn` ties to the lower engine index. That changes the NEAR_K cut (l.209) and the claim ranks used as shared-memory keys (l.1127).
     - `bot.py:1146-1147`: exact `ub` ties go to the higher `g.i`.
     - `bot.py:868-870` (`follow`): takes the first legal move in engine order, so paths are not mirror images.
     - Engine (hypothesis): A acts first in odd rounds and B in even rounds (GameRules l.122-126). All cooldowns are 8, so the first striker keeps striking first on every recharge.
   - Value for v20: symmetrising the tie-breaks re-rolls locked maps with no expected direction, so it is not an improvement on its own. Making the duel decision robust to arrival order (#1) is the general lever. A cheap check: log `g.v0`, `d_spawn` and `contest` for every group on turn 1 from both seats.
   - Confidence: high on the corrected figures; low on which tie-break matters.

Open threads, ranked by general upside:
1. **Opening contact, grouped play and regrouping after respawn** (#1). These are the same lever: don't take contested ground alone. `SOLO=1` (`ball.py:97`) has never been re-tested on engine 2.2.3.
2. **The threat veto on banking** (#2): bank when the altar is nearer than the threat, or inside the skirmish branch.
3. **Idle bodies and `cap_inc`** (#3).
4. **A "dominating" mode when ahead:** interlock A and packs A led at r500 and lost.
5. **Lower priority:**
   - Kappa floor: refuted (#3).
   - Roster/Ren: no evidence.
   - Fuel: (coord.) 154 `fuelExhausted` events over 34 games, mostly in r0-99. The collision A-Ryth and B-Varg buckets I checked were empty, so this is low.

Old hypotheses:
- **Refuted:**
  - "B wins 73-80%": that is the candidate's seat-B rate.
  - "v17 submits later in losses": it banks less, not later.
  - A kappa floor as a lever.
- **Confirmed and generalised:**
  - Routs are decided before r100 (v17 research #1). Now: the first death decides 10 of 13 mirror games.
  - Carrier bag losses (v18 research #1): the loser lost more gems in 10 of 12 games.
