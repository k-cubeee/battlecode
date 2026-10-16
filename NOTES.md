# Bot version notes

**Current champion: v6**

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
