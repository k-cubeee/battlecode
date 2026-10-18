"""Draft: pick the roster in priority order and record it for the champions.

v20 drafts the ladder meta roster by user directive: Ren, Stellar, Cassi & Issac, Varg and Ryth, in that
order, for every team size (3 picks: Ren, Stellar, Cassi & Issac = 4 bodies; 4 picks: + Varg; 5 picks:
+ Ryth = 6 bodies). The tail of the list is only a safety net (picks are simultaneous, mirroring is allowed).

Earlier versions drafted Varg, Ryth, Marcella / Stellar / Tavi from roster-vs-roster tests. The far-spawn
3-pick list PREFS_FAR_3 stays disabled (FAR_SPAWN_DIST).
"""
import cambc
from cambc import game_map
import tables as T

# Preferred picks per team size (ChampionDraft values), best first. Only the first `size` entries are
# normally used; the rest is a safety net.
_META = [T.D_REN, T.D_STELLAR, T.D_CASSI_ISSAC, T.D_VARG, T.D_RYTH, T.D_MARCELLA, T.D_TAVI, T.D_WILLOW]
PREFS = {
    3: list(_META),
    4: list(_META),
    5: list(_META),
}
# 3-pick maps with distant spawns: the farming roster of v2 (four bodies).
PREFS_FAR_3 = [T.D_VARG, T.D_CASSI_ISSAC, T.D_RYTH, T.D_MARCELLA, T.D_STELLAR, T.D_WILLOW, T.D_TAVI]

# Spawn-to-spawn walking distance (measured with spawn_distance): packs 26, collision 34, expanse 85.
# Threshold sits between the contact maps and expanse.
FAR_SPAWN_DIST = 10**6   # v16: far-spawn roster disabled (expanse plays better with the normal roster)
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
