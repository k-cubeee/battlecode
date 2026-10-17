"""Champion decisions. main.py dispatches here after the draft."""
import struct
from randomness import below

import cambc
from cambc import game_map

Team, Item = cambc.Team, cambc.ItemType


def distance(a, b):
    return a.chebyshev_distance(b)


def tiles_around(position, radius):
    tiles = cambc.Bitboard()
    tiles.draw_chebyshev(position, radius)
    return tiles


def blocked_tiles():
    # Combine terrain and visible occupants using native bitboard operations.
    blocked = (game_map.walls() | game_map.holes() | game_map.altars()
               | game_map.spawn_region(Team.ENEMY) | cambc.vision.champion_tiles()
               | cambc.vision.camp_tiles() | cambc.vision.teleport_tiles())
    blocked.set(cambc.me().position(), False)
    return blocked


def move_towards_closest(goals):
    me = cambc.me()
    origin = me.position()
    if not me.can_move() or goals.is_set(origin):
        return False

    # Only free goals or occupied camp tiles can seed the field.
    blocked = blocked_tiles()
    goals &= ~blocked | cambc.vision.camp_tiles()
    if goals.is_empty():
        return False
    if goals.count() == 1 and not blocked.is_set(goals.positions()[0]):
        return me.move_towards(goals.positions()[0])

    # Expand from the goals until our current tile is reached.
    field = cambc.DistanceField()
    field.compute_to(blocked & ~goals, goals, tiles_around(origin, 0), cambc.Bitboard())

    # Choose a reachable step with a smaller distance to the goal.
    reachable = blocked.reachable_tiles(origin, me.base_stats().base_move_speed)
    step = min([origin, *reachable.positions()], key=field.get)
    return step != origin and me.move_absolute(step)


def danger_tiles():
    # Tiles an awake camp or a visible enemy champion can hit next turn.
    danger = cambc.Bitboard()
    for camp in cambc.vision.camps():
        try:
            if camp.is_awake():
                danger |= tiles_around(camp.position(), camp.attack_range())
        except Exception:
            pass
    for enemy in cambc.vision.champions(Team.ENEMY):
        if enemy.is_visible() and enemy.health() > 0:
            danger |= tiles_around(enemy.position(), 4)
    return danger


def attack_if_in_range(target):
    # Make one basic attack if the target is already in attack range.
    me = cambc.me()
    if (not me.can_attack() or not target.is_visible() or target.health() <= 0
            or not me.attack_tiles().is_set(target.position())):
        return False
    me.attack(target)
    return True


def farm_camps():
    # Attack a camp already in range, otherwise move toward the nearest camp tiles.
    for camp in cambc.vision.camps():
        if attack_if_in_range(camp):
            return

    # Union every group's spawn tiles except visibly respawning groups.
    goals = cambc.Bitboard()
    visible = cambc.vision.visible_tiles()
    for group in game_map.camp_groups():
        if (not (group.spawn_tiles() & visible).is_empty()
                and isinstance(group.state(), game_map.CampGroupRespawning)):
            continue
        goals |= group.spawn_tiles()

    # Fresh vision after movement may reveal a camp already in range.
    if move_towards_closest(goals):
        for camp in cambc.vision.camps():
            if attack_if_in_range(camp):
                return


class Bot:
    def __init__(self):
        # Per-champion state survives between turns. Pick one stat and keep buying it.
        self.chosen_stat = None

    def buy_items(self):
        # Spend only on power shards of the randomly chosen stat.
        me = cambc.me()
        # Focus is useless: this bot never casts abilities.
        for _ in range(6):
            item = (Item.POWER_SHARD_OF_STRENGTH, Item.POWER_SHARD_OF_HEALTH)[self.chosen_stat]
            if me.gold_count() < item.cost() or not me.can_buy(item, 1):
                break
            me.buy(item, 1)
            self.chosen_stat ^= 1

    def play_turn(self):
        # Initialise this champion's build and read the draft message once.
        if self.chosen_stat is None:
            self.chosen_stat = below(2)

        # Priorities: shop and recall, attack enemies in range, bank gems, then farm.
        me = cambc.me()

        # Shop even while dead (allowed by rules).
        if not me.is_alive():
            self.buy_items()
            return

        # Leave channels running and skip turns where we cannot act.
        if (not me.is_alive() or me.is_recalling() or me.is_submitting_gems() or me.is_teleporting()
                or (not me.can_move() and not me.can_attack())):
            return

        # Shop before leaving spawn.
        at_spawn = game_map.spawn_region(Team.ALLY).is_set(me.position())
        if at_spawn:
            self.buy_items()

        # When badly hurt away from spawn: leave danger first (damage cancels recall), then recall.
        if not at_spawn and me.health() < me.max_health() * 0.35:
            danger = danger_tiles()
            origin = me.position()
            if danger.is_set(origin) and me.can_move():
                safe = tiles_around(origin, 3) & ~danger
                if safe.is_empty() or not move_towards_closest(safe):
                    move_towards_closest(game_map.spawn_region(Team.ALLY))
                if danger_tiles().is_set(me.position()):
                    return
            me.recall()
            return

        # Attack the first enemy champion already in range.
        for enemy in cambc.vision.champions(Team.ENEMY):
            if attack_if_in_range(enemy):
                return

        # Bank any carried gems before farming.
        if me.gem_count() > 0:
            # Union all altar approach tiles: the field chooses the nearest reachable altar.
            goals = cambc.Bitboard()
            for altar in game_map.altars().positions():
                if cambc.vision.has_altar_lock(altar):
                    continue
                if distance(me.position(), altar) <= cambc.constants.SUBMIT_GEMS_RANGE:
                    me.submit_gems(altar)
                    return
                goals |= tiles_around(altar, cambc.constants.SUBMIT_GEMS_RANGE)
            move_towards_closest(goals)
            return

        farm_camps()

        me.set_priority(1 + below(100))

