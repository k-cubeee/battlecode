import cambc

D = cambc.ChampionDraft

# Fixed priority: the bot fights with basic attacks only, so favour high
# health/strength bodies first. Cassi & Issac (linked death) and Willow
# (heal unused) go last.
PRIORITY = (
    D.RYTH, D.MARCELLA, D.VARG, D.VENDETTA, D.VESPER_VALE,
    D.REN, D.TAVI, D.STELLAR, D.PRISM, D.WILLOW, D.CASSI_AND_ISSAC,
)


def play():
    chosen = [int(c) for c in cambc.draft.current_draft(cambc.Team.ALLY)]
    for champ in PRIORITY:
        if int(champ) not in chosen:
            cambc.draft.pick(champ)
            return
