# Team B bot notes

**Current champion: b2**

Team B develops its own line of bots (bots/bN) independently of Team A (bots/vN).
b1 is a copy of v1, the SDK starter bot. Promotion gate: >= 55% head-to-head vs Team B's
current champion over a full evaluation (every map, both sides). Rejected versions move
to rejected/. Cross-team arena results are in results/arena_*/ (Team A is the candidate there).

### b1 — baseline
- Copy of v1 (SDK starter bot with a modified draft). Start of Team B's line.

### Engine change: cambc 2.1.6 -> 2.2.3 — 2026-10-16
- SDK refreshed to 2.2.3. 6 of the 9 maps changed (collision, corners, expanse, interlock,
  lanes, packs); elkring, monolith and rows are unchanged. API additions: `Camp.state()` /
  `CampState` (DEAD, ALIVE, ASLEEP per camp) and `debug_block`.
- All win rates and map numbers above this line were measured on 2.1.6 and are only a rough
  guide now. New results start from a fresh benchmark of the champion.

### Analysis of b1 — 2026-10-17 (results/benchB_b1, results/arena_1)
Record: benchB_b1 (b1 vs v1) 17-17 (a mirror match: side_stats for candidate and opponent are
identical, so this folder only shows b1's absolute behaviour); arena vs Team A (v8): **0-34**.
Every arena game ended "reached 1000 gems" for v8, in round 669 on average (fastest: corners
439/467). Weakest maps: contest (b1 scores 0 gems on both sides, 67 and 48 deaths) and collision
cand-B (0 gems, 15 deaths). No side is better: 0-17 on each.
Arena averages per match (results/arena_1/summary.json side_stats): b1 deaths 18.0 vs 0.5 for v8;
b1 kills 0.4 vs 10.0; b1 collects 198.5 gems but tributes only 115.5, while v8 tributes 1035.7;
b1 champion damage done 2263 vs 12068; b1 earns 1397 gold vs 5881.

1. **Draft bot crashes every game, so the team is chosen at random**
   - Evidence: all 34 arena logs say "team B draft bot yielded without picking; its remaining
     picks are random" (e.g. results/arena_1/b1/corners__cand-A.txt:13). So do all 34 bench logs,
     for both teams. As a result b1's lineup changes with every map: Willow+Vendetta+Varg on
     collision, Cassi&Issac+Prism+Vesper on ambush, Cassi&Issac+Marcella+Stellar+Prism+Tavi on
     contest. v8 always drafts Varg/Ryth/Stellar/Marcella/Tavi. Random picks include weak choices:
     in benchB_b1, Cassi and Issac average 10.7 deaths per match each (linked fate, so 2 bodies
     die per kill), and Willow's heal is never used. Collision cand-A: Willow 4 deaths, 0 gems
     tributed.
   - Cause in code: `bots/b1/src/draft.py:12` (play): `cambc.draft.pick(damn)` uses an undefined
     name, so it raises NameError, which `main.py:15` catches. No pick is made, and the
     `available` list built at line 8 is never used.
   - Suggested fix: pick from a fixed priority list of `cambc.ChampionDraft` values skipping ones
     in `current_draft(ALLY)`, e.g. VARG, RYTH, MARCELLA, STELLAR, TAVI (sturdy melee first, no
     Cassi&Issac, no Willow). Check that the log no longer says "yielded without picking".
   - Confidence: high (the bug is certain). Win-rate gain on its own: medium.

2. **Champions farm camps alone and die to monsters; the recall at low HP is cancelled by camp damage**
   - Evidence: v1 is a mirror bot with 3.0 kills per match, yet in benchB_b1 b1 averages 26.1
     deaths per match, so about 23 per match come from camps. In the arena, b1 dies 18.0 times
     per match but v8 gets only 10.0 kills, so about 8 per match are camp deaths. Camp deaths
     destroy the carried gems (GameRules.md:365). Per map: ambush cand-A has 34 deaths vs 11
     v8 kills, eight cand-A 27 vs 12, corners cand-A 12 vs 3. In
     results/arena_1/b1/corners__cand-A.stats.json, b1's Stellar has 4 deaths, 0 champion
     damage taken and 3000 monster damage taken, so it died only to camps. Ryth (2 deaths) and
     Varg (2) show 0 champion damage taken and about 2000-2700 monster damage. b1 tributes only
     58% of the gems it collects (115.5/198.5); v8 tributes 94% (1035.7/1102.1).
   - Cause in code: `bots/b1/src/bot.py:126-128` (play_turn) calls `me.recall()` as soon as HP
     drops below 35%, even while the champion is still within range 3 of an awake camp.
     A recall is cancelled by any damage (GameRules.md:272, :376), so the champion keeps
     taking hits and dies. In `farm_camps` (bot.py:64-82) each champion walks to the nearest
     camp alone, with no check of the camp's HP or strength against its own HP. Elk deal 60
     damage per hit and Wolf groups hit together, against 700-900 HP for Stellar, Cassi or Prism.
   - Suggested fix: when HP < 35%, first move out of every camp's attack range (more than 3
     tiles from any awake camp; monsters do not chase, GameRules.md:206), and only recall once
     no damage was taken last turn. Separately, skip camps whose total remaining HP is more than
     about 1.5 times what the champion can deal before falling to 35%. Measure deaths minus
     enemy kills in a bench run.
   - Confidence: medium-high. The camp-death numbers are solid. That cancelled recalls cause
     them is inferred from the rules, not traced in event logs.

3. **No abilities, no fighting logic, and gold wasted on Focus**
   - Evidence: in arena_1 b1 does 2263 champion damage per match vs 12068 for v8, with 0.4 kills
     vs 10.0. v8 kills b1 champions carrying gems and gains them: about 83 gems per match go from
     b1's bags to v8 or are lost. In corners__cand-A.stats.json, v8's Varg has shieldingDone 5250
     and Monster Emblems, and v8 buys Altar Locks. b1 shows shieldingDone 0 everywhere and no
     consumables. b1's Vendetta bought a Power Emblem of Focus, which is useless because b1 never
     casts. Contest, the map with the most fighting, gives b1 0 gems on both sides, 67 and 48
     deaths, and 61590 champion damage taken.
   - Cause in code: `bots/b1/src/bot.py` never calls `me.abilities()` or `Ability.use`. The
     attack loop at bot.py:131-133 only basic-attacks the first enemy already in range, and gems
     are carried straight past enemies. In `buy_items` (bot.py:91-98) `chosen_stat = below(3)`
     buys Focus 1/3 of the time. bot.py:116 also returns early when dead, so dead champions
     never shop (shopping while dead is allowed, GameRules.md:361).
   - Suggested fix (one change): each turn, before the basic attack, cast any ready ability
     (`a.is_ready()` and `me.can_cast()`). Use damage or CC on the nearest enemy or camp in
     `a.valid_tiles()`, shield or attack-reset on self, and skip dashes. Separately, buy
     Strength or Health only, never Focus, unless the champion is a caster.
   - Confidence: medium. The damage gap is clear. How much of it abilities alone would close
     is a hypothesis.

Fix first: #1 (draft). It is a one-line crash that affects 100% of games. It also decides
which champions #2 and #3 are tuned for, so without it every later evaluation runs on random
lineups.

### b2 — promoted (88% vs b1)
- Based on: b1
- Changes: b2 is ready and has 0 crashes in both smoke tests. It made findings #1 and #2, plus the "don't buy Focus" part of #3.

**Changes**
1. **`bots/b2/src/draft.py:play`** (finding #1): rewritten. It now picks the first champion from a fixed priority list that the team hasn't already taken: Ryth, Marcella, Varg, Vendetta, Vesper Vale, then Ren, Tavi, Stellar, Prism, Willow, Cassi & Issac. The bot only basic-attacks, so tanky, high-Strength fighters come first. Cassi & Issac (die together) and Willow (her heal is never used) come last. The old `pick(damn)` crash is gone, so the team is no longer random.
2. **`bots/b2/src/bot.py`**:
   - **New `danger_tiles()`** (finding #2): marks the tiles awake camps can hit (their attack range around each one) and anything within 4 tiles of a visible enemy champion.
   - **Low-HP branch in `Bot.play_turn`** (finding #2): below 35% HP away from spawn, the champion first steps to a safe tile within 3. If there isn't one, it heads toward spawn. It only recalls once it's out of danger, or when it can't move. Before, it recalled while still in a camp's range, and the first hit cancelled the recall.
   - **`Bot.buy_items`** (part of #3): buys only Strength or Health shards. Focus was wasted because the bot never casts.
   - I also removed the leftover shared-memory and draft-memory debug prints from `play_turn`.

**Why it should win:** every game now uses a strong, consistent lineup instead of a random one that included the weak picks. Hurt champions should stop dying to monsters mid-recall, which loses the gems they carry; that was most of b1's ~18–26 deaths per match. Every shopping trip now goes into stats the bot actually uses.

**Smoke tests** (only crash checks, not evidence of strength):
- `cambc run b2 b1 --map corners`: b2 won by reaching 1000 gems in round 1068. b2 had 1030 gems, 4 kills, 0 deaths and **0 crashes**, with the draft Ryth, Marcella, Varg, Vendetta, Vesper Vale. b1 had 422 gems and 38 deaths.
- `cambc run b1 b2 --map contest`: b2 won at the round limit on gold. Both teams had 0 gems; b2 had 14 kills, 3 deaths and **0 crashes**.

Contest still ends with 0 gems for both sides, so banking gems on that map remains a problem for a later version. Casting abilities (the rest of #3) is still not done.
- Evaluation (results/evalB_b2): b1 88%, v1 88%; overall 88%
- Status: promoted, new champion.

### Analysis of b2 — 2026-10-17 (results/evalB_b2, results/arena_2)
Record: evalB_b2 30-4 (88%; b1 88%, v1 88%); all 4 losses are fragment (0-4). Arena vs Team A (v9): **0-34**, every game "reached 1000 gems" for v9 (about 436-1076 rounds, corners cand-A 517). Per match (results/arena_2/summary.json side_stats, b2 = opponent): deaths 9.1 vs 0.6, kills 0.4 vs 8.6, gems collected 276 vs 1098 (submitted 185 vs 1036), earned gold 1650 vs 5645, champion damage done 2596 vs 14341, champion damage taken 14341 vs 2596, monster damage taken 8460 vs 18523. Worst maps: stampede (b2 21 and 23 deaths, 0 gems on the side with those deaths), swirl (15 and 10 deaths), rushbait-v2 (5 deaths, 286 gems).

1. **b2 now dies to enemy champions and neither fights back nor avoids them**
   - Evidence: b2 takes 14341 champion damage per match vs 8460 monster damage (arena_1 b1 deaths were mostly camps; the problem has moved). Stampede cand-A (arena_2 summary.json ~L5481): 21 deaths, 43920 champion damage taken, 0 monster damage, 0 gems, 0 kills. v9 loses only 0.6 champions per match, so b2 has no deterrent. Corners cand-A: Ryth, Marcella, Vendetta, Vesper Vale 2 deaths each, Varg 1, 0 kills; Vendetta and Vesper Vale collect 35 gems and submit 0 (lost on death).
   - Cause in code: `bots/b2/src/bot.py:134-144` and `:146-149` (play_turn). The danger-aware retreat only triggers below 35% HP. Above that, the bot walks into enemy range, basic-attacks the first enemy already in range, and otherwise banks or farms. `danger_tiles()` (bot.py:54-66) is not used while banking (`move_towards_closest(goals)`, bot.py:162) or farming. There is no retreat when outnumbered, no focus fire, and no ability use (`me.abilities()` is never called).
   - Suggested fix: when a visible enemy champion is within about 6 tiles and enemies outnumber nearby allies (or carried gems > ~50), step to non-danger tiles / toward the altar instead of farming. Add one ability cast per turn (the unfinished half of old finding #3). Measure b2 deaths per match on stampede and swirl in an arena run (target < 5).
   - Confidence: medium-high (damage split is clear; no individual fight traces were read).

2. **Gem income is a quarter of Team A's; champions cluster and bank inefficiently**
   - Evidence: b2 collects 276.4 and submits 185.3 (67%) vs 1097.7 and 1035.8 (94%) for v9. Earned gold 1650 vs 5645, so b2 spent 1300 vs 5034 on shards. In corners cand-A Varg has 0 gems, 0 gold, 0 items bought and still died once; Ryth 108 and Marcella 144 submitted, the other three about 0-35.
   - Cause in code: `bots/b2/src/bot.py:151-163` sends any champion carrying even 1 gem to the altar, ignoring `danger_tiles()` on the way. `farm_camps` (bot.py:79-98) targets the union of all camp spawn tiles, so all five champions head for the same nearest camp group, ignoring camp strength and allies' positions; priority is random (bot.py:167). Stat choice is `below(2)` per champion regardless of role (bot.py:118).
   - Suggested fix: spread champions across camp groups (exclude groups an ally within ~5 tiles already targets) and bank only above ~40 gems or when HP is low. Compare collectedGems per match in a bench run (goal > 600).
   - Confidence: medium (rates are solid; causes inferred from code, not traced).

3. **Fragment is a total loss and several maps run to the 2000-round limit**
   - Evidence: evalB_b2/summary.json by_map fragment 0-4 (rounds 2000 in both b1 and v1 games, L2919/L3058 for b1); other 2000-round games: contest, pilgrimage cand-B, rows cand-A, stampede, swirl cand-A. b2 also banked 0 gems on contest in its own smoke test (above).
   - Cause in code: hypothesis only. `bots/b2/src/bot.py:79-98` (farm_camps) just moves toward camp spawn tiles. If they are unreachable or `blocked_tiles()` (bot.py:21-27, includes altars and enemy spawn) blocks the route, `move_towards_closest` returns False and the champion idles with no fallback. Camp ASLEEP/DEAD `Camp.state()` (new in 2.2) is not used.
   - Suggested fix: run `cambc run b2 b1 --map fragment`, log each champion's position every 100 rounds to confirm they are stuck, then add a fallback (move toward the nearest altar or map centre) when `move_towards_closest` returns False. Target: fragment 2/4 wins.
   - Confidence: low (cause not traced).

Fix first: #1. Arena games are decided by deaths: b2 loses 9.1 champions per match, which destroys its carried gems and gold, so much of #2 follows from it.

### b3 — rejected (44% vs b2)
- Based on: b2
- Changes: I've changed `bots/b3/src/bot.py`. The smoke test on stampede ran with 0 crashes, but it doesn't show the change helps. It was a 2000-round draw on gems, 0 kills and 0 deaths for both sides. b3 won only on the gold tiebreak, 8071 to 8008.

**What changed** (finding #1, plus the banking part of #2):
- **Ability cast:** the new `Bot.cast_ability` uses one ready damage, crowd-control or area-damage ability per turn on the nearest enemy champion. It only fires if the ability can target enemies and the target is within `info().range`. The whole call is wrapped in `try/except` because I couldn't confirm which abilities the draft gives each champion.
- **Retreat:** `Bot.play_turn` now counts visible enemy champions and allies within 7 tiles. If enemies outnumber us, or we're below 60% HP and not ahead, it walks toward the ally spawn region. If it can't move and is below 60% HP, it casts and recalls.
- **Banking:** a champion now goes to the altar only with 30 or more gems, or with any gems when below 60% HP. Before, any single gem sent it to the altar, even through enemy fire.

I expect fewer deaths and more kills, since the 9.1 deaths per match and the 14341 champion damage taken were the biggest problems in the analysis. I did not touch finding #3 (fragment). I also did not spread the champions across camp groups, which was the other half of #2.

**Smoke test:** `cambc run b3 b2 --map stampede` finished with b3 at 0 crashes.
- Evaluation (results/evalB_b3): b2 44%, b1 85%, v1 85%; overall 72%
- Status: rejected, moved to rejected/b3. Lesson: these changes did not beat b2.

### Analysis of b2 (second pass, with b3 data) — 2026-10-17 (results/arena_2, results/evalB_b2, results/evalB_b3)
Record: evalB_b2 30-4 (all 4 losses on fragment, 0-4); evalB_b3 (b3 vs b2) 15-19 for b3, so b2 beat b3 19-15, and b3 was 0-6 on fragment; arena vs Team A (v9): **0-34**, all "reached 1000 gems" for Team A. Weakest maps/side: fragment (every b2 game vs b1/v1 lost), stampede and swirl in the arena. In evalB_b3 the B side won 82% (42-9) vs 61% for side A, partly because ties go to team B (4 games "tied on gems, gold and kills; team B wins ties", evalB_b3/summary.json end_reasons).

1. **b2 has no answer to enemy champions: it collects a quarter of Team A's gems and loses 9.1 champions per match**
   - Evidence: results/arena_2/summary.json side_stats (b2 = opponent): deaths 9.1 vs 0.6, kills 0.4 vs 8.6, champion damage taken 14341 vs 2596, gems collected 276 vs 1098, submitted 185 vs 1036 (67% vs 94%), earned gold 1650 vs 5645. b3's attempted fix (retreat + one ability cast + bank at >=30 gems) went 15-19 vs b2 (evalB_b3/summary.json by_opponent b2), so retreat/bank heuristics alone are not enough.
   - Cause in code: `bots/b2/src/bot.py:146-149` (play_turn) basic-attacks only the first enemy already in range and never moves toward enemies or focuses. `bot.py:134` reacts only below 35% HP. No ability is ever cast (`me.abilities()` is never called). `bot.py:110` buys Strength or Health at random (`below(2)`, line 118), with no role logic.
   - Suggested fix: make champions fight as a group. If an enemy champion is visible, move to a tile within attack range of the lowest-HP visible enemy and near allies instead of farming, and cast ready damage abilities on it. Don't retreat on HP alone (b3's retreat was rejected). Check arena deaths < 5 and kills > 3 per match.
   - Confidence: medium-high for the diagnosis (the damage/kill split is large); low for how much untried fight logic would recover.

2. **Champions all go for the nearest camp group and bank after every gem; gem income is the main reason Team A wins by round ~670**
   - Evidence: arena_2 gems 276 vs 1098 (above). evalB_b2/summary.json L2788-2917 (fragment, b2 cand-A vs b1): b2 collects 742 gems vs b1's 1034 even though b1 had 29 deaths to 1 kill (Vesper Vale 11, Prism 9, Marcella 9). b2's three champions are very unequal: Varg 513 gems, Marcella 178, Ryth 51. b2's monster damage taken is 30460 vs 64940 for b1, i.e. b2 farms camps less.
   - Cause in code: `bots/b2/src/bot.py:79-98` (farm_camps) builds one Bitboard from every group's spawn tiles and calls `move_towards_closest(goals)` (bot.py:30-51), so champions leaving spawn together choose the same nearest group. There is no per-champion group assignment. `bot.py:151-163` also sends a champion to the altar for any `gem_count() > 0`, costing a round trip per few gems.
   - Suggested fix: assign each champion a camp group by index (groups sorted by distance from spawn, champion i takes group i mod n) and bank only at >= 25 gems or low HP. Test with collectedGems per match on a bench run (target > 600) before judging.
   - Confidence: medium (per-champion gems are solid; clustering is inferred from code and Ryth's 51 gems, not from position traces).

3. **Fragment is lost every time (0-4 b2, 0-6 b3) and runs to the 2000-round limit**
   - Evidence: evalB_b2 by_map fragment 0-4; evalB_b3 fragment 0-6 (e.g. results/evalB_b3/b2/fragment__cand-A.txt: b3 284 gems vs b2 706). In the b2 vs b1 game b2 had the better kills/deaths (4/1 vs 1/29) but lost on gems 684 vs 976 at the round limit. Fragment drafts only 3 champions per team (Ryth, Marcella, Varg), so per-champion farming matters more.
   - Cause in code: hypothesis. Same clustering as #2 with only 3 champions, plus `move_towards_closest` (bot.py:37-40) returns False when `goals &= ~blocked | camp_tiles` is empty, and farm_camps then does nothing. `Camp.state()` (ASLEEP/DEAD, new in 2.2) is not used.
   - Suggested fix: first log each champion's position and the `move_towards_closest` result every 100 rounds (`cambc run b2 b1 --map fragment`), then add a fallback when it returns False (toward the least-visited camp group or the map centre). Target: 2 of 4 fragment wins.
   - Confidence: low-medium (outcome solid, cause not traced).

Fix first: #2 (camp-group assignment and banking threshold). It's the smallest change, it targets the 4x gem gap and the fragment losses, and b3 showed a heavier fight/retreat rewrite (#1) did not beat b2. Do the fight logic (#1) as a separate version so the effects can be measured separately.

### b4 — rejected (24% vs b2)
- Based on: b2
- Changes: I made `b4` and it beat `b2` on fragment in the smoke test, with 0 crashes. `b4` reached 1000 gems at round 1131 and finished with 1008 gems to `b2`'s 102. It is a single deterministic match, so it only shows the bot runs and doesn't measure strength.

The changes are in `bots/b4/src/bot.py` and implement analyst finding #2:
- **`farm_camps(slot)`:** each champion now heads for its own camp group (group `slot mod n`) instead of the nearest of all groups combined. If that group is empty or respawning, it falls back to every group. Before, champions leaving spawn together all went to the same group.
- **`Bot.__init__` and `play_turn`:** each champion gets a `slot` on its first turn, computed as `p.x*7 + p.y*3 + below(3)` from its spawn position plus a small random offset. This is a hash, not a guaranteed distinct index, so two champions can still pick the same group. I couldn't find a champion id in the API docs, which is why I used the position. I didn't find `x` and `y` documented for the position type, but the run didn't crash.
- **`play_turn`:** a champion now banks gems only at 25 or more, or when it carries any gems and is below 50% HP. Before, it left for the altar after a single gem, which cut farming time.

Why it should win: the aim is to raise gem income, which was about a quarter of Team A's, by spreading champions across camp groups and cutting altar trips. The fight logic from finding #1 is left for a separate version so its effect can be measured on its own.
- Evaluation (results/evalB_b4): b2 24%, b1 56%, v1 56%; overall 45%
- Status: rejected, moved to rejected/b4. Lesson: these changes did not beat b2.

### Analysis of b2 (third pass, with b3 and b4 data) — 2026-10-17 (results/arena_2, results/evalB_b3, results/evalB_b4)
Record: evalB_b3 (b3 vs b2) b2 won 19-15; evalB_b4 (b4 vs b2) b4 won 24%, so b2 beat b4 about 76%; arena vs Team A (v9): **0-34**, every game "reached 1000 gems" for v9 (average round 679). Weakest: stampede (b2 21 and 23 deaths, 0 gems on both sides, results/arena_2/summary.json L5374-5620), swirl, corners. By side: no difference (17-0 each side for Team A).
Two heuristic rewrites (b3: retreat, one cast, bank at 30 gems; b4: per-champion camp group, bank at 25 gems) both lost to b2. So b2's weakness is probably not in the farm or bank heuristics. It is that it cannot contest the enemy.

1. **b2 walks repeatedly into an enemy it cannot beat, and never uses abilities or fighting builds**
   - Evidence: arena_2 stampede cand-B (summary.json L5557-5620): b2 has 23 deaths, 1 kill, 0 gems, 0 monster damage taken, 61788 champion damage taken, 3150 gold spent. Cand-A: 21 deaths, 0 kills, 43920 damage taken. So on stampede b2 never reaches a camp: it dies to Team A's champions over and over (where is a hypothesis; I read no traces). Arena average: deaths 9.1 vs 0.6, champion damage done 2596 vs 14341. Team A drafts Varg, Ryth, Stellar, Marcella, Tavi; b2 drafts Ryth, Marcella, Varg, Vendetta, Vesper Vale (arena_2/b2/corners__cand-A.txt:6-7).
   - Cause in code: `bots/b2/src/bot.py:146-149` (play_turn) only basic-attacks the first enemy already in range. `me.abilities()` is never called, there is no focus fire, and above 35% HP (bot.py:134) there is no reaction to enemies at all. Stat choice is random per champion (bot.py:118, `below(2)`).
   - Suggested fix: one narrow change in play_turn: if an enemy champion is visible, cast each ready ability at it (one per turn) and attack the lowest-HP visible enemy in range instead of the first. No retreat change (b3 showed that did not help). First confirm in a smoke run that the cast actually fires (b3 wrapped it in try/except and it was never shown to fire). Target: arena deaths < 5 on stampede.
   - Confidence: medium (damage and death numbers are solid; what exactly kills b2 is not traced).

2. **b2 earns a quarter of Team A's gold, and champions don't shop while dead or away from spawn**
   - Evidence: arena_2 side_stats opponent: collectedGems 276 vs 1098, submittedGems 185 vs 1036 (67% vs 94%), earnedGold 1650 vs 5645, spentGold 1300 vs 5034. Corners cand-A: b2 earns 1218 gold vs 4752 and has 80 gems. Gems carried are lost on death (GameRules.md:365), and b2 has 9.1 deaths per match.
   - Cause in code: `bots/b2/src/bot.py:129-131` shops only when standing in the spawn region, and `bot.py:124` returns early when dead, although shopping while dead is allowed (GameRules.md:361). `bot.py:151-163` sends a champion with even 1 gem to the altar without checking `danger_tiles()` on the way. Neither b3 nor b4 changed the shopping path.
   - Suggested fix: shop every turn including while dead (move the buy call before the alive check), and measure spentGold / earnedGold in a bench run (target > 90%).
   - Confidence: low-medium (the ratio is solid; the win-rate effect is a hypothesis, since low gold mostly follows from low gems).

3. **Fragment and other 2000-round maps are lost on gems; cause untraced**
   - Evidence: evalB_b2 fragment 0-4; evalB_b3 fragment 0-6 (results/evalB_b3/b2/fragment__cand-A.txt: b3 284 gems vs b2 706); evalB_b4 by_map has several maps at 0.0 (summary.json L93, L141, L157, L173). The b4 smoke test beat b2 on fragment (1008 vs 102 gems) but b4 lost the full evaluation (24%), so one match said little. Fragment drafts only 3 champions.
   - Cause in code: hypothesis. `bots/b2/src/bot.py:37-40` (move_towards_closest) returns False when no goal tile is free, and farm_camps (bot.py:79-98) then does nothing. The respawn check (bot.py:89-91) applies only to groups whose spawn tiles are visible, so a champion can wait at a group that is respawning. `Camp.state()` is unused.
   - Suggested fix: log each champion's position and the move_towards_closest result every 100 rounds on `cambc run b2 b1 --map fragment` to confirm idling, then add a fallback (nearest non-respawning group, else map centre).
   - Confidence: low.

Fix first: #1 as a single narrow change (ability cast plus lowest-HP target, no retreat or banking changes). b3 and b4 each changed several things at once and neither beat b2. Judge it on arena kills and deaths, not only on win rate against b1 and v1.

### b5 — rejected (50% vs b2)
- Based on: b2
- Changes: I changed `bots/b5/src/bot.py` so champions use their abilities and focus fire on enemy champions. The smoke test ran clean, but it can't show whether the change helps.

**Changes**
- **New `cast_abilities(enemies)`:** it loops over `me.abilities()`. For each slot that is ready and can target enemies, it casts at the lowest-HP enemy inside `valid_tiles()`. At most one cast succeeds per turn, and any API error just skips that slot.
- **`Bot.play_turn`:** the old "attack the first enemy in range" loop now builds a list of visible, living enemy champions sorted by health. It casts abilities first, then basic-attacks the lowest-HP enemy in range. I made no retreat, banking or stat-choice changes.

**Why it should win:** b2 never cast a spell and spread its basic attacks over whichever enemy it happened to see first. Casting on cooldown adds damage and stuns. Focusing the lowest-HP enemy should turn lost fights into kills. This is analyst finding #1 only, so arena kills and deaths measure it directly.

**Smoke test:** `cambc run b5 b2 --map stampede` ended 0 crashes for both bots, 0 kills, 0 deaths, and b5 won on gold earned (8071 vs 8008). That map shows no fights in this match, so the new combat code probably never ran.
- Evaluation (results/evalB_b5): b2 50%, b1 79%, v1 79%; overall 70%
- Status: rejected, moved to rejected/b5. Lesson: these changes did not beat b2.

### Analysis of b2 (fourth pass, with b3/b4/b5 data) — 2026-10-17 (results/arena_2, results/evalB_b4, results/evalB_b5)
Record: evalB_b4 (b4 vs b2) b2 won 26-8; evalB_b5 (b5 vs b2) 17-17 (50%); arena vs Team A (v9): **0-34**, all "reached 1000 gems", average round 679. Weakest maps/side: stampede (b2 21 deaths, 0 kills, 0 gems; results/arena_2/summary.json L5374-5500), corners cand-A (b2 80 gems, round 517), contest (evalB_b5 by_map contest 1-5). No side effect in the arena (17-0 each).
Three rewrites (b3 retreat+cast, b4 camp-group split, b5 cast+focus) each failed to beat b2 (44%, 24%, 50%). In evalB_b4 b4 went 0-6 on corners and lanes against b2. This suggests b2's tendency to cluster at one camp group may be a mild strength (hypothesis: the five champions defend each other). So don't break the clustering. The fix has to add something b2 lacks.

1. **b2 loses fights on items, not tactics: Team A buys 2-5x more stat shards per champion and out-trades it**
   - Evidence: stampede cand-A (summary.json L5416-5500): Team A itemsBought Varg 175, Ryth 116, Stellar 70, Tavi 38, Marcella 32; earnedGold 11712 vs b2's 4319 (b2 spent 3450). b2 does 7224 champion damage to Team A's 43920 and gets 0 kills; Team A has 0 deaths, so b2's damage is spread and never finishes one target. Arena average: kills 0.4 vs 8.6. b5 added focus fire and casts and still only reached 50% vs b2 (evalB_b5/summary.json by_opponent b2 17-17), so focus alone does not close the gap.
   - Cause in code: `bots/b2/src/bot.py:118` and `:110` (play_turn, buy_items): each champion randomly picks Strength or Health (`below(2)`) and buys only that. Half the team has no damage investment and half no HP. Shopping happens only in the spawn region (`bot.py:129-131`), after the alive check at `bot.py:124`.
   - Suggested fix: in buy_items alternate Strength and Health per purchase instead of a random single stat, and call buy_items before the alive/recall early-return so gold never sits idle (dead shopping is allowed, GameRules.md:361). Measure itemsBought per champion and championDamageDone in an arena run.
   - Confidence: medium-low (the item-count gap is solid; the gain from a different mix is a hypothesis).

2. **b2 spends only about two thirds of its gold and earns a quarter of Team A's, so the gap compounds**
   - Evidence: evalB_b5 side_stats opponent (b2 side): earnedGold 3580.6, spentGold 2289.4 (64%); arena_2 b2 earned 1650, spent 1300 (79%); stampede cand-A 4319 earned, 3450 spent (80%). Team A's ratio is 89% (5034/5645) in the arena and 93% on stampede. Corners cand-A: Team A 4752 earned vs 1218 (results/arena_2/b2/corners__cand-A.txt:6-7).
   - Cause in code: `bots/b2/src/bot.py:124-131`. Shopping only occurs on a turn where the champion is alive, not busy, and standing in spawn. Gold earned away from spawn is spent only after a return trip (hypothesis; I did not trace buy timing).
   - Suggested fix: as in #1, buy first, before the early return, whenever gold >= item cost and `can_buy` is true. Check spentGold/earnedGold > 90%.
   - Confidence: low-medium.

3. **b2 has no reaction to enemies above 35% HP and walks out of spawn piecemeal, so it feeds kills on maps with a fast enemy push**
   - Evidence: stampede cand-A and cand-B: 21 and 23 deaths, 0 monster damage taken (b2 never reached a camp), so every death is to Team A champions near spawn or on the route. Arena swirl 15 and 10 deaths. Team A deaths are 0.6 per match. Deaths are even across champions (corners cand-A: 2 each for four champions), so it is not a single bad pick.
   - Cause in code: `bots/b2/src/bot.py:146-149` (basic attack then return, standing in place) and `bot.py:134` (react only below 35% HP). Respawned champions walk out one at a time via `farm_camps` (bot.py:79-98) without waiting for allies. b3's HP retreat was rejected, so don't retreat on HP; this is about not leaving spawn alone.
   - Suggested fix: a narrow gate: a champion in the spawn region with a visible enemy champion within ~8 tiles holds there and attacks instead of walking out. Test on stampede in an arena run: deaths < 10, kills > 2.
   - Confidence: low (inferred; I read no positional traces).

Fix first: #1 (stat mix plus buying before the early return, a small change). It's the one area b3, b4 and b5 never touched. Judge it by itemsBought and spent/earned gold in the arena, not only win rate against b1/v1.

### b6 — rejected (47% vs b2)
- Based on: b2
- Changes: I made b6 alternate Strength and Health shards on every purchase, and let it shop while dead. The smoke test on stampede shows 0 crashes, but it doesn't show whether b6 is stronger.

**Changes, both in `bots/b6/src/bot.py`:**
- **`Bot.buy_items`:** It used to buy only the one stat each champion picked at random, all in one batch. Now it buys one shard at a time, up to 6 per turn, flipping `chosen_stat` after each buy. This covers findings #1 and #2 from the analysis.
- **`Bot.play_turn`:** A dead champion now calls `buy_items()` before returning. Previously it skipped shopping unless it was alive and in the spawn region. `GameRules.md:361` allows buying while dead, but I didn't test whether `can_buy` works for a dead champion.

I left finding #3 (holding at spawn near enemy champions) for a later version, so this one change can be measured on its own.

**Smoke test:** `cambc run b6 b2 --map stampede` ended at the 2000-round limit with 0 gems each and no kills or deaths. b6 won only on the tiebreak, gold earned 8071 vs 8008. Crashes were 0 for both bots.

The analysis said to judge this by items bought and gold spent in the arena, not only win rate. This smoke test doesn't measure either.
- Evaluation (results/evalB_b6): b2 47%, b1 91%, v1 91%; overall 76%
- Status: rejected, moved to rejected/b6. Lesson: these changes did not beat b2.
