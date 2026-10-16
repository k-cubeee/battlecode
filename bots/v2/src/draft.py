"""Draft: pick the farming roster in priority order and record it for the champions."""
import cambc
import tables as T

# Preferred picks per team size (ChampionDraft values), best first.
PREFS = {
    3: [T.D_VARG, T.D_CASSI_ISSAC, T.D_RYTH, T.D_STELLAR, T.D_TAVI, T.D_MARCELLA, T.D_VENDETTA, T.D_REN],
    4: [T.D_VARG, T.D_CASSI_ISSAC, T.D_RYTH, T.D_STELLAR, T.D_TAVI, T.D_MARCELLA, T.D_VENDETTA, T.D_REN],
    5: [T.D_VARG, T.D_CASSI_ISSAC, T.D_RYTH, T.D_STELLAR, T.D_TAVI, T.D_MARCELLA, T.D_VENDETTA, T.D_REN],
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
