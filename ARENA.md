# Arena reports: Team A vs Team B

Written by the referee agent. Hidden from both teams.

### Arena 1 — v8 (Team A) vs b1 (Team B) — 2026-10-17
Score: Team A 34-0 Team B (100%); draws/errors: 0. Previous arena: first.
Per map: ambush: A, collision: A, contest: A, corners: A, eight: A, elkring: A, expanse: A, fragment: A, interlock: A, lanes: A, monolith: A, packs: A, pilgrimage: A, rows: A, rushbait-v2: A, stampede: A, swirl: A. Average winning round: A 669, B n/a (no wins).

**Why the winner wins**
- **b1 doesn't really draft. The engine picks its champions at random.** `bots/b1/src/draft.py:play` ends with `cambc.draft.pick(damn)`, and `damn` is never defined, so every draft turn raises a NameError. `main.py:main` catches it with try/except and prints it. By `GameRules.md:86`, if a draft bot crashes without picking, "the remaining selections are randomly selected by the game". That fits the data: b1 fields a different roster on every map, such as Ryth/Marcella/Cassi & Issac/Vesper Vale/Prism on ambush and Willow/Vendetta/Varg on collision. v8 (`bots/v8/src/draft.py:play`) uses fixed priorities: Varg/Ryth/Marcella on 3-pick maps, Varg/Ryth/Stellar/Marcella/Tavi on 5-pick maps, and the Cassi & Issac list for far-apart spawns (`FAR_SPAWN_DIST = 60`). Varg is v8's best farmer, averaging 347.9 gems collected (`candidate_champions.Varg`).
- **b1 throws away its gems and its time.** Per match, b1 collects 198.5 gems but submits only 115.5, and dies 18.0 times against v8's 0.5. v8 gets 10.0 kills per match (`side_stats`). Carried gems go to the killer, and each death costs 60 rounds out of play (`GameRules.md:217,363`). b1 runs `bot.py:play_turn` → `farm_camps`: it banks only after farming, recalls below 35% HP, and attacks whatever enemy is in range first. v8 has `assess_enemies` and `flee` (bot.py:710-764), which simulate the fight with allied DPS added and run home if v8 would lose. It also banks by distance and gem count (`bank_threshold` = 6·d+10, clamped 30-110, plus `endgame_bank`).
- **v8 earns far more gold and spends it better.** Earned gold is 5881 vs 1397 per match, and spent gold 4769 vs 1107. v8's `buy_items` (bot.py:949-978) buys shards in sets of 5 that follow a build order, so it gets the set bonuses. b1's `Bot.buy_items` pours all its gold into one randomly chosen shard type (`below(3)`). b1 also never casts a spell: `bot.py` has no cast call. v8 casts through `cast_enemy_spells`, `cast_shield` and `cast_spells`. Champion damage done is 12068 vs 2263 per match.
- The games end early: all 34 ended at "reached 1000 gems", 18 of them by round 627 or earlier. The fastest were corners (439) and eight (442).

**Where the loser is competitive**
- **Long, fight-heavy maps take v8 much longer.** Contest ended at rounds 1367 and 1400, and stampede at 1075 and 1356. Both are about twice the 669 average. On contest with b1 on side A, b1 had 6 kills and 13846.5 champion damage, and v8 took 6 deaths. That is v8's worst death count in the arena. In both contest games b1 collected 0 gems but still slowed v8. Hypothesis: contest and stampede force champion-on-champion contact even with a random b1 roster.
- None of b1's wins or close results can be credited to its own logic. Its best gem total in any match was 144 (ambush, side A).

**Advice to the lead**
- **Team B: fix the draft before anything else.** Replace `pick(damn)` with a real priority list. Varg first is well supported: in v8's data Varg is the top farmer in every match (`candidate_champions`). After that, b1 should bank when carrying gems near enemies and should stop fighting fights it loses. Losing 83 gems per match on death (198.5 collected − 115.5 submitted) is the cheapest thing to recover. Team B can learn the roster and the banking thresholds from `results/arena_1`, since those files are open to both teams.
- **Team A: v8 has little to learn from b1, so keep developing against Team A's own pool.** The one weak spot this arena shows is contest/stampede, where v8 lost 6 champions and needed about 1400 rounds. Hypothesis: retreat logic there (`flee`, `keep` threshold in `assess_enemies`) could be tuned for a better kill/death trade.
- **The harness can't see caught exceptions.** b1's draft error happens every draft turn, but every match reports `crashes: 0` and `bot_faults` 0, and none of the `.txt` files contains "error". `main.py`'s try/except hides it from the crash counter. Consider surfacing caught `bot error:` lines in the match summary. No fuel or timeout problems appeared: no errors, and every match ended by gem total.

### Arena 2 — v9 (Team A) vs b2 (Team B) — 2026-10-17
Score: Team A 34-0 Team B (100%); draws/errors: 0. Previous arena: Team A 34-0 (v8 vs b1).
Per map: A won both sides on all 17 maps (ambush, collision, contest, corners, eight, elkring, expanse, fragment, interlock, lanes, monolith, packs, pilgrimage, rows, rushbait-v2, stampede, swirl). Average winning round: A 679.3, B n/a (no wins). That is a little slower than arena 1's 669 (`summary.json: avg_round_of_wins`).

**Why the winner wins**
- **Team B's draft is now sensible, but v9 farms more and fights better.** `bots/b2/src/draft.py:play` uses a fixed priority list: Ryth, Marcella, Varg, Vendetta, Vesper Vale, then Ren, Tavi and the rest. `bots/v9/src/draft.py` fields Varg, Ryth, Marcella, Stellar and Tavi (Cassi & Issac on only 2 maps). Per match, v9 collects 1097.7 gems and submits 1035.8. b2 collects 276.4 and submits 185.3 (`side_stats`). Varg averages 332.9 gems collected and Ryth 302.6 (`candidate_champions`).
- **v9 wins the fights.** v9 averages 8.6 kills against 0.6 deaths. b2 averages 0.4 kills against 9.1 deaths. Champion damage is 14341 dealt by v9 against 2596 dealt by b2. b2's fix for dying while recalling (`danger_tiles` and the low-HP branch in `bots/b2/src/bot.py:play_turn`) cut its deaths from about 18 per match to 9.1. It is still a basic-attack-only bot with no spells, and v9 beats it in every fight. v9's `assess_enemies`/`flee` logic and spellcasting are described in the arena 1 report and in `NOTES.md`. Hypothesis: they are still the main edge, because b2 has no equivalent, but I did not re-read v9's source this round.
- **v9 has a large economy lead.** Earned gold is 5645 against 1650, and spent gold is 5034 against 1300 (`side_stats`). v9 spends 89% of what it earns, while b2 spends 79%. v9 buys about 40–58 items per champion in sets that follow a build order. b2 buys fewer, with no set-bonus logic that I could find.
- **Every game ended at 1000 gems.** The fastest were swirl (436 and 485), eight (448 and 474) and monolith (459 and 487). The slowest were contest (1257 and 1498) and stampede (1076 and 1065).

**Where the loser is competitive**
- Contest and stampede take v9 about twice as long as other maps. These are the same two maps that were slow in arena 1, so the weakness has persisted across both opponents. The cause is not visible in the summary. Hypothesis: map geometry forces champion contact and slows farming, so v9 wins on kills rather than on gem speed.
- b2's gems per match are 276 against about 199 for b1 in arena 1. Its submit rate is 67%, up from b1's 58%. The improvement is real but small. It has no wins and no close games, since the game always ended on v9's gem total. I did not look at the final gem gap between the teams, so I can't call any match close.

**Advice to the lead**
- **Team B:** copy v9's banking and farming rules, which are readable from `results/arena_*`. b2 loses about 91 gems per match (276.4 collected, 185.3 submitted), and each death costs 60 rounds out of play. Next, add real retreat logic: simulate the fight and flee if it would be lost, instead of a fixed 35% HP rule. Then add spell use and shop for set bonuses. b2 has no cast calls and no purchase order.
- **Team A:** the gap is large enough that b2 gives little useful signal. Keep tuning against Team A's own pool. The remaining target is contest and stampede (1000–1500 rounds). Look at what slows farming on those two maps, not only at the retreat thresholds.
- **Harness:** there were no crashes, errors or fuel problems (`candidate_crashes` 0, all 34 ended on gems). Arena 1's note still applies: caught exceptions don't show in the crash counters. Team B has fixed the draft crash, so this no longer matters for b2.

### Arena 3 — v9 (Team A) vs b7 (Team B) — 2026-10-17
Score: Team A 34-0 Team B (100%); draws/errors: 0. Previous arena: Team A 34-0 (v9 vs b2).
Per map: A won both sides on all 17 maps (ambush, collision, contest, corners, eight, elkring, expanse, fragment, interlock, lanes, monolith, packs, pilgrimage, rows, rushbait-v2, stampede, swirl). Average winning round: A 680.8, B n/a (no wins). Arena 2 was 679.3 (`summary.json: avg_round_of_wins`).

**Why the winner wins**
- **v9 farms about four times as much and banks more of it.** Per match, v9 collects 1077.5 gems and submits 1039.4 (96%). b7 collects 266.2 and submits 172.4 (65%) (`side_stats`). Arena 2's b2 was at 276.4 collected and 185.3 submitted, so b7 has not improved on farming. Ryth (301 collected) and Varg (339) lead v9's gem income (`candidate_champions`). All 34 games ended at "reached 1000 gems" (`end_reasons`).
- **v9 wins every fight.** Kills and deaths are 8.2 and 0.5 for v9 against 0.3 and 8.5 for b7. Champion damage is 13178 for v9 against 2340 for b7. v9's champions barely take damage (Stellar 264, Tavi 339), so its retreat and spell logic is working. b7's `bot.py` still has no spell casting and no fight simulation. The only fighting changes I found in `NOTES_B.md` are b2's `danger_tiles` and its low-HP retreat. b7 did not touch fighting. I did not re-read the source of either bot for this report.
- **v9 has a much larger economy.** Earned gold is 5567 against 1716, and spent gold is 4947 against 1337. v9 buys 33–54 items per champion (Ryth 53.5, Varg similar). b7's only change, in `buy_items` (`bots/b7/src/bot.py`, ~line 110), swaps Power shards for passive-emblem shards (`Item.TREASURE_SHARD_OF_STRENGTH` / `JUNGLE_SHARD_OF_HEALTH`) (`NOTES_B.md:293-300`). That raises b7's income per gem a little. It can't close a 4× gap in gems farmed.

**Where the loser is competitive**
- b7 is not competitive in any match. It has no wins, and the game always ended on v9 reaching 1000 gems.
- b7 beat b2 only 56% in Team B's own evaluation, and its smoke test on stampede was a tiebreak at 8071 gold to 8008 (`NOTES_B.md`). Its improvements are marginal in its own pool and don't register against v9.
- The slow maps are still v9's weakness: contest ended at rounds 1242 and 1506, and stampede at 1013 and 1204. Every other map ended between 416 and 862. This is the third arena in a row with the same two slow maps.

**Advice to the lead**
- **Team B:** stop tuning shard choices. The gap is in farming and fighting. b7 loses 94 gems per match between collecting and submitting (266 against 172). It also loses 8.5 champions per match, and each death costs about 60 rounds. First fix recall and banking so gems are submitted before engaging. Then add a fight-outcome check before engaging, and use spells.
- **Team A:** b7 gives no useful signal, because v9 wins 34-0 for the third arena running. Spend the effort on contest and stampede, which take 1000–1500 rounds. Compare v9's gem rate on those maps with the rest through the `.stats.json` timelines. The cause is not visible in the summary. Hypothesis: geometry or monsters slow farming.
- **Harness:** `candidate_crashes` is 0 and all 34 games ended on gems, so I saw no rules or fuel problem. `healingDone` is 0.0 for both teams, so nobody uses healing.
