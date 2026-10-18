"""Static game data used by the bot: camp stats, champion stats and shop build orders."""

# Camp kinds (cambc.CampType values).
WOLF, ELK, GEM, GOLD, MONO = 0, 1, 2, 3, 4
CAMP_HP = (1350.0, 2400.0, 500.0, 500.0, 20000.0)
CAMP_ST = (20.0, 60.0, 0.0, 0.0, 200.0)

# Champion types (cambc.ChampionType values).
RYTH, VESPER, VENDETTA, CASSI, ISSAC, STELLAR, PRISM, MARCELLA, WILLOW, REN, VARG, TAVI = range(12)

# Draft picks (cambc.ChampionDraft values).
D_RYTH, D_VESPER, D_VENDETTA, D_CASSI_ISSAC, D_STELLAR, D_PRISM, D_MARCELLA, D_WILLOW, D_REN, D_VARG, D_TAVI = range(11)

# health, strength, focus, health growth, strength growth, focus growth
CHAMP = {
    RYTH: (1200, 50, 100, 100, 5, 10),
    VESPER: (900, 45, 100, 100, 5, 10),
    VENDETTA: (800, 70, 100, 100, 5, 10),
    CASSI: (700, 30, 70, 71.25, 3.5, 15),
    ISSAC: (900, 40, 100, 95, 4.75, 10),
    STELLAR: (750, 35, 100, 75, 3.5, 10),
    PRISM: (700, 35, 80, 75, 3.5, 10),
    MARCELLA: (1200, 45, 50, 100, 5, 10),
    WILLOW: (700, 45, 105, 50, 3, 5),
    REN: (900, 40, 100, 100, 5, 10),
    VARG: (1000, 50, 100, 100, 5, 10),
    TAVI: (750, 35, 100, 75, 5, 10),
}


def bodies_of_pick(pick):
    """Champion types created by one draft pick."""
    if pick == D_CASSI_ISSAC:
        return (CASSI, ISSAC)
    return (pick if pick < D_CASSI_ISSAC else pick + 1,)


# Item families (prefixes of the ItemType names) and stats.
FAMILY = ("MONSTER", "POWER", "DURABILITY", "TREASURE", "JUNGLE", "HOME", "BRUISER")
MON, POW, DUR, TRE, JUN, HOME, BRU = range(7)
STAT = ("STRENGTH", "FOCUS", "HEALTH")
STR, FOC, HP = range(3)

# Shop build orders: each entry is a set of five shards (family, stat) that combines into an emblem.
BUILD_FIGHTER = (
    [(JUN, HP), (MON, STR), (TRE, STR), (DUR, HP), (POW, STR), (HOME, HP)]
    + [(POW, STR), (POW, HP)] * 12
)
# v17: 4-champion maps (home_open) keep v16's Monster-first order; Jungle first lost interlock A and rows B there
BUILD_FIGHTER_MON = (
    [(MON, STR), (JUN, HP), (TRE, STR), (DUR, HP), (POW, STR), (HOME, HP)]
    + [(POW, STR), (POW, HP)] * 12
)
BUILD_STELLAR = (     # v17: Focus pays more than Strength only for Stellar's spells
    [(JUN, FOC), (MON, FOC), (TRE, FOC), (DUR, HP), (POW, FOC), (HOME, HP)]
    + [(POW, FOC), (POW, HP)] * 12
)
# v20: Focus builds for the spell champions (Stellar, Ren, Cassi) by user directive; the ladder's top teams buy
# Focus on every champion except Varg
BUILD_FOCUS = BUILD_STELLAR
BUILD_RANGED = (
    [(MON, STR), (JUN, HP), (TRE, STR), (DUR, HP), (POW, STR), (HOME, HP)]
    + [(POW, STR), (POW, HP)] * 12
)
BUILD_SUPPORT = (
    [(MON, STR), (JUN, HP), (TRE, STR), (DUR, HP), (POW, STR), (HOME, HP)]
    + [(POW, STR), (POW, HP)] * 12
)


# ---- PvP data -------------------------------------------------------------------------------
# (spell damage in multiples of Focus per 8-turn cooldown cycle, has an attack reset)
PVP_KIT = {
    RYTH: (1.0, True), VESPER: (0.0, True), VENDETTA: (0.0, True), CASSI: (2.0, False), ISSAC: (0.0, True),
    STELLAR: (3.4, False), PRISM: (2.5, False), MARCELLA: (2.0, True), WILLOW: (0.0, True), REN: (1.25, False),
    VARG: (0.0, True), TAVI: (2.2, True),
}
# how much we want a champion dead first (weight on damage dealt to it)
TARGET_W = {
    RYTH: 1.0, VESPER: 1.1, VENDETTA: 1.1, CASSI: 1.3, ISSAC: 1.1, STELLAR: 1.3, PRISM: 1.25, MARCELLA: 0.9,
    WILLOW: 1.6, REN: 1.0, VARG: 0.95, TAVI: 1.3,
}

# Shop order once the push starts: the first emblem is Durability, then Power (one extra shard each).
BUILD_BALL = [(DUR, HP)] + [(POW, STR), (POW, HP)] * 14
