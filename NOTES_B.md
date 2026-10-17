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
