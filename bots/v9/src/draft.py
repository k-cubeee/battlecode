"""Draft: pick the roster in priority order and record it for the champions.

The rosters were chosen by playing candidate rosters against each other (same code on both teams, both
sides, the maps of that team size). Varg's splash is what makes the farming fast, Ryth and Marcella are the
tanks, Stellar is the ranged burst and Willow keeps the front line alive. Cassi and Issac die together, so
they cost more deaths than the extra body is worth and are left out on maps where the spawns meet.

On 3-pick maps whose spawns are far apart (expanse) there is little contact and the game is a pure farming
race, so the extra body of Cassi & Issac wins it: those maps use PREFS_FAR_3 instead.
"""
import cambc
from cambc import game_map
import tables as T

# Preferred picks per team size (ChampionDraft values), best first. Only the first `size` entries are
# normally used; the rest is a safety net.
PREFS = {
    3: [T.D_VARG, T.D_RYTH, T.D_MARCELLA, T.D_STELLAR, T.D_WILLOW, T.D_TAVI],
    4: [T.D_VARG, T.D_RYTH, T.D_STELLAR, T.D_MARCELLA, T.D_TAVI, T.D_WILLOW],
    5: [T.D_VARG, T.D_RYTH, T.D_STELLAR, T.D_MARCELLA, T.D_TAVI, T.D_WILLOW],
}
# 3-pick maps with distant spawns: the farming roster of v2 (four bodies).
PREFS_FAR_3 = [T.D_VARG, T.D_CASSI_ISSAC, T.D_RYTH, T.D_MARCELLA, T.D_STELLAR, T.D_WILLOW, T.D_TAVI]

# Spawn-to-spawn walking distance (measured with spawn_distance): packs 26, collision 34, expanse 85.
# Threshold sits between the contact maps and expanse.
FAR_SPAWN_DIST = 60
UNREACHED = 65535
_spawn_dist = None  # cached across draft turns (computed on the first, 10x-fuel turn)


def spawn_distance():
    """Walking distance from our spawn region to the nearest enemy spawn tile (UNREACHED if none; 0 on error)."""
    global _spawn_dist
    if _spawn_dist is None:
        try:
            block = game_map.walls() | game_map.holes() | game_map.altars()
            field = cambc.DistanceField()
            field.compute(block, game_map.spawn_region(cambc.Team.ALLY), cambc.Bitboard())
            best = UNREACHED
            for v in game_map.spawn_region(cambc.Team.ENEMY).positions():
                d = field.get(v)
                if d < best:
                    best = d
            _spawn_dist = best
        except Exception as error:
            print(f"draft spawn distance error: {error}", flush=True)
            _spawn_dist = 0          # unknown: keep the default (v3) draft
    return _spawn_dist


def play():
    size = cambc.draft.team_size()
    chosen = list(cambc.draft.current_draft(cambc.Team.ALLY))
    prefs = PREFS.get(size, PREFS[5])
    if size == 3 and spawn_distance() >= FAR_SPAWN_DIST:
        prefs = PREFS_FAR_3
    pick = None
    for candidate in prefs:
        if candidate not in chosen:
            pick = candidate
            break
    if pick is None:
        pick = next(p for p in range(11) if p not in chosen)

    # Draft memory layout: [number of bodies, champion type of each body in order].
    bodies = []
    for p in chosen + [pick]:
        bodies.extend(T.bodies_of_pick(p))
    cambc.draft_memory.submit(bytes([len(bodies)] + bodies))
    cambc.draft.pick(pick)
