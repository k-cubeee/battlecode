"""Draft: pick the roster in priority order and record it for the champions.

The rosters were chosen by playing candidate rosters against each other (same code on both teams, both
sides, the maps of that team size). Varg's splash is what makes the farming fast, Ryth and Marcella are the
tanks, Stellar is the ranged burst and Willow keeps the front line alive. Cassi and Issac die together, so
they cost more deaths than the extra body is worth and are left out.
"""
import cambc
import tables as T

# Preferred picks per team size (ChampionDraft values), best first. Only the first `size` entries are
# normally used; the rest is a safety net.
PREFS = {
    3: [T.D_VARG, T.D_RYTH, T.D_MARCELLA, T.D_STELLAR, T.D_WILLOW, T.D_TAVI],
    4: [T.D_VARG, T.D_RYTH, T.D_STELLAR, T.D_MARCELLA, T.D_TAVI, T.D_WILLOW],
    5: [T.D_VARG, T.D_RYTH, T.D_STELLAR, T.D_MARCELLA, T.D_TAVI, T.D_WILLOW],
}


def play():
    size = cambc.draft.team_size()
    chosen = list(cambc.draft.current_draft(cambc.Team.ALLY))
    prefs = PREFS.get(size, PREFS[5])
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
