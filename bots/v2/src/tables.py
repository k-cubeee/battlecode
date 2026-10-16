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
    [(MON, STR), (JUN, HP), (TRE, STR), (DUR, HP), (POW, STR), (HOME, HP)]
    + [(POW, STR), (POW, HP)] * 12
)
BUILD_RANGED = (
    [(MON, STR), (JUN, HP), (TRE, STR), (DUR, HP), (POW, STR), (HOME, HP)]
    + [(POW, STR), (POW, HP)] * 12
)
BUILD_SUPPORT = (
    [(MON, STR), (JUN, HP), (TRE, STR), (DUR, HP), (POW, STR), (HOME, HP)]
    + [(POW, STR), (POW, HP)] * 12
)
