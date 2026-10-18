"""Champion decisions for the farming bot. main.py dispatches here after the draft.

Strategy in one paragraph: every champion is an independent farmer. It scores every camp group by
(gems + weighted gold) per turn of work, claims the best free one in shared memory so teammates
pick different ones, walks there, kills it with focus fire and abilities, stands on the spawn tile
until the reward lands, and moves on. When hurt it backs out of camp range (sleeping camps do not
attack and never heal), recalls, shops and returns. Gems are carried in batches and tributed when
that is cheap or when the team can win.
"""
import cambc
from cambc import game_map
import tables as T
from ball import BallMixin, BALL_PARTY, ESP_AVOID, CAP_PATIENCE, BALL_WAIT_MAX, ESCORT_R

ALLY = cambc.Team.ALLY
ENEMY = cambc.Team.ENEMY
Vec2 = cambc.Vec2
Bitboard = cambc.Bitboard
DistanceField = cambc.DistanceField
Error = cambc.Error

DEBUG = False           # print one status line per turn (costs fuel; leave off for submissions)
UNREACHED = 65535
STELLAR_FOCUS = 1     # v17: 1 gives Stellar the Focus build (T.BUILD_STELLAR); 0 keeps BUILD_FIGHTER
CAP_TURNS = 5
HOME_OPEN_SLOTS = 4  # v16: with this many champions play v15's stay-home opening ...
OPEN_HOME_R = 300    # ... before this round: no push toward the enemy spawn and no hunting near sightings
WAIT_NEAR_MAX = 16      # longest respawn wait we are willing to spend standing next to a group
K_PARTY = 2             # most champions that may work on the same camp group at once
BIG_GEMS = 150          # packs worth this many gems are worth a bigger party ...
BIG_PARTY = 3           # ... of up to this many champions, who take turns at being the nearest (hit) one
BIG_EFF = 1.25          # joining a big pack may cost at most this much more champion-time than it saves
NEAR_K = 30             # groups (nearest our spawn first) examined when choosing work; keeps big maps cheap
CHOOSE_MIN_FUEL = 1500000   # choosing a new task can cost up to ~1M fuel; defer it when less is left
KAPPA0 = 0.3            # value of one gold in gems at round 0 ...
KAPPA_MIN = 0.05        # ... falling linearly to this floor ...
KAPPA_DECAY = 1200.0    # ... over this many rounds
ROUND_LIMIT = 2000      # carried gems do not count when the game ends here
ENDGAME_SLACK = 8       # extra turns allowed for the last walk to an altar

# ability kinds
K_NONE, K_RESET, K_DAMAGE, K_AOE, K_CC, K_HEAL, K_DASH, K_SHIELD = range(8)
_ABILITY_CLASSES = (
    (cambc.AbilityAttackReset, K_RESET), (cambc.AbilityDamage, K_DAMAGE),
    (cambc.AbilityAoeDamage, K_AOE), (cambc.AbilityCc, K_CC), (cambc.AbilityHeal, K_HEAL),
    (cambc.AbilityDash, K_DASH), (cambc.AbilityShield, K_SHIELD),
)

# modes
M_IDLE, M_HOME, M_BANK = 0, 1, 2
# claim states stored in shared memory
C_HEAD, C_STAGE, C_FIGHT, C_DONE = 0, 1, 2, 3


class Grp:
    """Static facts about one camp group plus what we remember about it."""
    __slots__ = ("i", "cg", "xy", "vec", "bb", "gems", "gold", "resp", "kind", "hp", "st", "n", "adj",
                 "cx", "cy", "rank", "d_spawn", "far", "ready_at", "block_until", "hpleft", "hp_ver",
                 "est_key", "est", "xyset", "v0", "stsum", "hp_total", "hpsum", "contest", "deny", "d_enemy",
                 "threat_until")


def is_big(g):
    """A rich pack of several monsters; a lone monolith is one long static fight that a party only exposes."""
    return g.gems >= BIG_GEMS and g.n >= 2


def cheb(ax, ay, bx, by):
    dx = ax - bx
    dy = ay - by
    if dx < 0:
        dx = -dx
    if dy < 0:
        dy = -dy
    return dx if dx > dy else dy


def simulate(hps, sts, adj, dps, splash, mult):
    """Time to clear a group and damage taken, killing the highest threat-per-hp camp first."""
    n = len(hps)
    hp = list(hps)
    alive = [True] * n
    t = 0.0
    taken = 0.0
    for _ in range(n + 1):
        prim = -1
        best = -1.0
        for i in range(n):
            if alive[i]:
                key = sts[i] / hp[i] * 1000.0 - hp[i] * 1e-6
                if key > best:
                    best = key
                    prim = i
        if prim < 0:
            break
        rates = [0.0] * n
        rates[prim] = dps
        if splash > 0.0:
            row = adj[prim]
            for j in range(n):
                if alive[j] and row[j]:
                    rates[j] = splash
        dt = 1e18
        inc = 0.0
        for j in range(n):
            if alive[j]:
                inc += sts[j]
                if rates[j] > 0.0:
                    d = hp[j] / rates[j]
                    if d < dt:
                        dt = d
        taken += inc * dt * mult
        t += dt
        for j in range(n):
            if alive[j] and rates[j] > 0.0:
                hp[j] -= rates[j] * dt
                if hp[j] <= 1e-6:
                    alive[j] = False
    return t, taken


class Bot(BallMixin):
    def __init__(self):
        self.inited = False
        self.task = None
        self.mode = M_IDLE
        self.note = ""               # DEBUG: tags of this turn's notable events (end of the status line)
        self.pend_note = ""
        self.recent = []             # DEBUG: event letters of the last few turns, reported at death

    # ------------------------------------------------------------------ setup
    def init_world(self):
        me = self.me = cambc.me()
        self.ctype = int(me.champion_name())
        self.arange = me.attack_range()
        self.melee = self.arange <= 1
        self.W = game_map.width()
        self.H = game_map.height()
        walls, holes, altars = game_map.walls(), game_map.holes(), game_map.altars()
        self.aspawn = game_map.spawn_region(ALLY)
        self.espawn = game_map.spawn_region(ENEMY)
        self.static_block = walls | holes | altars | self.espawn
        self.spawn_xy = set((v.x, v.y) for v in self.aspawn.positions())
        self.altar_vecs = altars.positions()
        self.altar_xy = [(v.x, v.y) for v in self.altar_vecs]
        goals = Bitboard()
        for v in self.altar_vecs:
            goals.draw_chebyshev(v, cambc.constants.SUBMIT_GEMS_RANGE)
        self.altar_goals = goals & ~self.static_block
        self.df_spawn = DistanceField()
        self.df_spawn.compute(self.static_block, self.aspawn, Bitboard())
        self.df_altar = DistanceField()
        self.df_altar.compute(self.static_block & ~self.altar_goals, self.altar_goals, Bitboard())
        self.df_enemy = DistanceField()
        self.df_enemy.compute(self.static_block & ~self.espawn, self.espawn, Bitboard())
        self.df_me = DistanceField()
        self.df_path = DistanceField()
        self.scratch = Bitboard()

        # camp groups
        self.groups = []
        self.tile_idx = {}
        for gi, cg in enumerate(game_map.camp_groups()):
            g = Grp()
            g.i = gi
            g.cg = cg
            g.gems = cg.gem_value()
            g.gold = cg.gold_value()
            g.resp = cg.max_respawn_timer()
            xy, vec, kind = [], [], []
            for c in cg.camps():
                sp = c.spawn_position()
                xy.append((sp.x, sp.y))
                vec.append(sp)
                kind.append(int(c.kind()))
            n = len(xy)
            g.n = n
            g.xy = xy
            g.xyset = set(xy)
            g.vec = vec
            g.v0 = vec[0]
            g.kind = kind
            g.hp = [T.CAMP_HP[k] for k in kind]
            g.st = [T.CAMP_ST[k] for k in kind]
            g.stsum = sum(g.st)
            g.hp_total = sum(g.hp)
            g.hpsum = g.hp_total
            g.adj = [[i != j and cheb(xy[i][0], xy[i][1], xy[j][0], xy[j][1]) <= 1 for j in range(n)]
                     for i in range(n)]
            g.bb = cg.spawn_tiles()
            g.cx = sum(p[0] for p in xy) / n
            g.cy = sum(p[1] for p in xy) / n
            g.d_spawn = self.df_spawn.get(vec[0])
            d_enemy = self.df_enemy.get(vec[0])
            g.far = d_enemy < g.d_spawn
            # groups the enemy reaches as fast as we do are fought over: discount them (1.0 safe .. 0.6 theirs)
            lean = (g.d_spawn - d_enemy + 6) / 12.0
            g.contest = 1.0 - 0.4 * (0.0 if lean < 0.0 else (1.0 if lean > 1.0 else lean))
            g.ready_at = 0
            g.block_until = 0
            g.threat_until = 0           # v20: enemies we would not fight were seen here until this round
            g.hpleft = None
            g.hp_ver = 0
            g.est_key = None
            g.est = {}
            for ci, t in enumerate(xy):
                self.tile_idx[t] = (gi, ci)
            self.groups.append(g)
        order = sorted(range(len(self.groups)), key=lambda i: self.groups[i].d_spawn)
        self.rank_to_g = order
        for r, gi in enumerate(order):
            self.groups[gi].rank = r
        # choose_task looks at the groups nearest our spawn first; the rest only if those are all taken
        self.near_groups = [self.groups[gi] for gi in order[:NEAR_K]]
        self.rest_groups = [self.groups[gi] for gi in order[NEAR_K:]]

        # team slot from the draft memory
        mem = bytes(cambc.DraftMemoryBuffer())
        self.slot = self.ctype % 6
        self.nslots = 6
        self.slot_types = []
        if len(mem) > 1 and mem[0] > 0:
            n = mem[0]
            types = list(mem[1:1 + n])
            if self.ctype in types and n <= 6:
                self.slot = types.index(self.ctype)
                self.nslots = n
                self.slot_types = types
            elif n < 6:
                self.slot = n + self.ctype % (6 - n)
        self.home_open = (self.nslots == HOME_OPEN_SLOTS)
        self.sbuf = bytearray(8)
        self.my_byte = 0
        self.rep_gems = 0
        self.tot = 0
        self.others = {}
        self.claims = {}
        self.last_done = {}
        self.done_rank = -1
        self.cstate = C_HEAD

        # abilities
        self.abil = []
        for ab in me.abilities():
            info = ab.info()
            kind = K_NONE
            for cls, k in _ABILITY_CLASSES:
                if type(info) is cls:
                    kind = k
                    break
            self.abil.append((ab, kind, info))
        self.has_dmg_spell = any(k in (K_DAMAGE, K_CC, K_AOE) and getattr(i, "modifier", 0) > 0
                                 for _, k, i in self.abil)

        # shopping
        if STELLAR_FOCUS and self.ctype == T.STELLAR:
            self.build = list(T.BUILD_STELLAR)
        elif self.home_open:
            self.build = list(T.BUILD_FIGHTER_MON)
        else:
            self.build = list(T.BUILD_FIGHTER)
        self.set_pos = 0
        self.set_cnt = 0
        self.flags = set()
        self.field_shop = self.ctype == T.TAVI
        self.items = {}
        # per-turn / progress state
        self.stats_version = 0
        self.stats_dirty = True
        self.sightings = []          # (round, x, y) of recent enemy champion sightings
        self.last_attack_round = -10
        self.awake = False
        self.awake_round = -10
        self.took_round = -10
        self.fight_gi = -1
        self.prev_eff = None
        self.camp_hp = {}            # (x, y) -> health when last seen
        self.camp_awake = {}         # (x, y) -> last round the camp lost health or hit us
        self.safe_round = -1         # round for which df_path holds the way out of camp reach
        self.safe_steps = None
        self.pair = self.ctype in (T.CASSI, T.ISSAC)
        self.margin = 1.8 if self.pair else 1.0    # Cassi and Issac die together: leave more room
        self.was_alive = True
        self.fuel_max = 0
        self.last_pos = None
        self.same_pos = 0
        self.t_start = 0
        self.recall_started = -10
        self.cap_since = 0
        self.cw_n = 0
        self.kparty = K_PARTY
        self.ball_init()
        self.inited = True

    def item(self, fam, stat):
        key = (fam, stat)
        it = self.items.get(key)
        if it is None:
            it = getattr(cambc.ItemType, f"{T.FAMILY[fam]}_SHARD_OF_{T.STAT[stat]}")
            self.items[key] = it
        return it

    def refresh_stats(self):
        me = self.me
        s = me.strength()
        f = me.focus()
        self.mstr, self.mfocus, self.maxhp = s, f, me.max_health()
        mon = 1.1 if "MON" in self.flags else 1.0
        dps = s * mon
        shield = 0.0
        for ab, kind, info in self.abil:
            cd = info.max_cooldown if info is not None else 8
            if kind in (K_DAMAGE, K_CC, K_AOE):
                dps += info.modifier * f * mon / (cd + 1)
            elif kind == K_RESET:
                dps += s * mon / (cd + 1)
            elif kind == K_SHIELD:
                shield = info.modifier * f
        self.dps = dps
        pvp = float(s)
        for ab, kind, info in self.abil:
            cd = info.max_cooldown if info is not None else 8
            if kind in (K_DAMAGE, K_CC, K_AOE):
                pvp += info.modifier * f / (cd + 1)
            elif kind == K_RESET:
                pvp += s / (cd + 1)
        self.pvp_dps = pvp
        self.splash = s * mon if self.ctype == T.VARG else 0.0
        self.shield_amt = shield
        self.mult = (0.7 if "JUN" in self.flags else 1.0) * (0.9 if "DUR" in self.flags else 1.0)
        self.stats_version += 1
        self.stats_dirty = False

    # ------------------------------------------------------------------ logging
    def log(self, msg):
        if DEBUG:
            print(f"R{self.rnd} S{self.slot} {msg}", flush=True)

    def tag(self, word):
        """DEBUG: mark this turn's status line with an event word (counted by the action tally)."""
        if DEBUG:
            self.note = (self.note + "+" + word) if self.note else (" " + word)

    # ------------------------------------------------------------------ shared memory
    def read_shared(self):
        buf = self.sbuf
        cambc.shared_memory.read(0, buf)
        self.my_byte = buf[self.slot]
        self.ball_phase()
        if self.bstage != 0:
            self.tot = buf[6] | (buf[7] << 8)
            self.ball_read(buf)
            return
        others = {}
        for s in range(self.nslots):
            if s != self.slot:
                b = buf[s]
                r = (b & 63) - 1
                if r >= 0:
                    st = b >> 6
                    others[s] = (r, st)
                    if st == C_DONE and self.last_done.get(s) != r:
                        self.last_done[s] = r
                        g = self.groups[self.rank_to_g[r]] if r < len(self.rank_to_g) else None
                        if g is not None:
                            g.ready_at = max(g.ready_at, self.rnd + g.resp)
                            g.hpleft = None
                            g.hpsum = g.hp_total
                            g.hp_ver += 1
                else:
                    self.last_done.pop(s, None)
        self.others = others
        claims = {}
        for sl, (r, st) in others.items():
            if st != C_DONE:
                if r in claims:
                    claims[r].append((sl, st))
                else:
                    claims[r] = [(sl, st)]
        self.claims = claims
        self.tot = buf[6] | (buf[7] << 8)

    def write_shared(self, alive=True):
        if self.bstage != 0:
            self.ball_write(alive)
            return
        b = 0
        if alive:
            if self.task is not None and self.task.rank < 63:
                b = ((C_STAGE if self.cap_since > 0 else self.cstate) << 6) | (self.task.rank + 1)
            elif self.done_rank >= 0 and self.done_rank < 63:
                b = (C_DONE << 6) | (self.done_rank + 1)
        if b != self.my_byte:
            cambc.shared_memory[self.slot] = b
            self.my_byte = b
        gems = self.gems if alive else 0
        if gems != self.rep_gems:
            tot = self.tot + gems - self.rep_gems
            if tot < 0:
                tot = 0
            if tot > 65535:
                tot = 65535
            cambc.shared_memory.write(6, bytes((tot & 255, tot >> 8)))
            self.tot = tot
            self.rep_gems = gems

    # ------------------------------------------------------------------ turn entry
    def play_turn(self):
        self.rnd = cambc.round_number()
        try:
            if not self.inited:
                self.init_world()
            self.turn()
        except Exception as error:
            import sys
            tb = sys.exc_info()[2]
            lines = []
            while tb is not None:
                lines.append(tb.tb_lineno)
                tb = tb.tb_next
            print(f"ERR R{self.rnd} S{getattr(self, 'slot', -1)} {error!r} lines={lines}", flush=True)
            if DEBUG:      # a status line too, so the action tally counts errors
                print(f"R{self.rnd} S{getattr(self, 'slot', 0)} (0,0) hp=0/0 gems=0 gold=0 mode=0 task=-1/0 "
                      f"fuel=0/0 bot-ERR", flush=True)

    def turn(self):
        me = self.me
        f0 = cambc.fuel_remaining()
        if DEBUG:
            self.note = ""
            if self.pend_note:
                self.tag(self.pend_note)
                self.pend_note = ""
        st = int(me.state())
        self.st = st
        if not (st & 1):
            self.dead_turn()
            return
        self.can_move = bool(st & 8)
        self.can_attack = bool(st & 16)
        self.can_cast = bool(st & 2048)
        self.moved = False
        self.was_alive = True
        if st & (2 | 4 | 4096):          # recalling, tributing or teleporting: let the channel run
            self.gems = me.gem_count()
            self.read_shared()
            self.write_shared()
            self.prev_eff = me.health() + self.shield_value()
            return
        pos = me.position()
        self.pos = pos
        self.px, self.py = pos.x, pos.y
        self.hp = me.health()
        self.gems = me.gem_count()
        self.gold = me.gold_count()
        if self.stats_dirty:
            self.refresh_stats()
        self.read_shared()
        self.scan()
        self.scan_allies()
        act = self.decide()
        self.write_shared()
        self.prev_eff = self.hp + self.shield_value()
        used = f0 - cambc.fuel_remaining()
        if used > self.fuel_max:
            self.fuel_max = used
        if DEBUG:
            extra = ""
            if self.camps and (self.inc > 0.0 or self.mode == M_HOME):
                extra = " camps=" + str([(c[0], c[1], int(c[2])) for c in self.camps]) + f" inc={self.inc:.0f} aw={int(self.awake)}"
            if act in ("step retreat", "hold retreat"):
                act = act.replace(" ", "-")       # stand-off turns get their own word in the tally
            self.log(f"({self.px},{self.py}) hp={int(self.hp)}/{int(self.maxhp)} gems={self.gems} gold={self.gold} "
                     f"mode={self.mode} task={self.task.i if self.task else -1}/{self.cstate} fuel={used}/{self.fuel_max} {act}{self.note}{extra}")
            nt, a, fl = self.note, act or "", ""
            for w, c in (("standoff-break", "S"), ("threat-drop", "D"), ("altar-run", "A"), ("press-fail", "P")):
                if w in nt:
                    fl += c
            if a.endswith("retreat"):
                fl += "R"
            elif a.endswith("fight"):
                fl += "F"
            if self.mode == M_HOME:
                fl += "H"
            self.recent.append(fl)
            if len(self.recent) > 6:
                del self.recent[0]

    def dead_turn(self):
        if self.was_alive:
            print(f"R{self.rnd} S{self.slot} DEAD", flush=True)
            self.was_alive = False
            if DEBUG and self.rnd - getattr(self, "press_rnd", -99) <= 10:
                self.pend_note = "press-died"
            if DEBUG:      # one tally line per event seen in the last 6 turns before this death
                feats = sorted(set("".join(self.recent))) or ["W"]
                for w in ["died"] + ["died-" + c for c in feats] + (["died-g"] if self.gems >= 20 else []):
                    print(f"R{self.rnd} S{self.slot} (0,0) hp=0/0 gems=0 gold=0 mode=0 task=-1/0 fuel=0/0 {w}",
                          flush=True)
                self.recent = []
        self.task = None
        self.mode = M_IDLE
        self.done_rank = -1
        self.gems = 0
        self.prev_eff = None
        self.bstate = 0
        self.is_leader = False
        self.has_lock = False
        self.arrived = False
        try:
            gold = self.me.gold_count()
            if gold >= 30:
                self.gold = gold
                self.buy_items()
        except Error:
            pass
        self.read_shared()
        self.write_shared(alive=False)

    # ------------------------------------------------------------------ perception
    def scan(self):
        """Collect live camps in view, damage we are taking and nearby enemies."""
        px, py = self.px, self.py
        camps = []
        nearest = 99
        inc = 0.0
        eff = self.hp + self.shield_value()
        prev = self.prev_eff
        took = prev is not None and eff < prev - 0.5
        self.took_amt = prev - eff if took else 0.0
        rnd = self.rnd
        if not cambc.vision.camp_tiles().is_empty():
            groups = self.groups
            chp = self.camp_hp
            awk = self.camp_awake
            for c in cambc.vision.camps():
                p = c.position()
                x, y = p.x, p.y
                idx = self.tile_idx.get((x, y))
                if idx is None:
                    continue
                hp = c.health()
                gi, ci = idx
                camps.append((x, y, hp, gi, ci, c, p))
                d = cheb(px, py, x, y)
                if d < nearest:
                    nearest = d
                if d <= 3:
                    inc += groups[gi].st[ci]
                    if took:
                        awk[(x, y)] = rnd           # something in reach just hit us
                before = chp.get((x, y))
                if before is not None and hp < before - 0.5:
                    awk[(x, y)] = rnd               # somebody (us or a teammate) is hitting it
                chp[(x, y)] = hp
        self.camps = camps
        self.nearest_camp = nearest
        # Camps wake when damaged, keep attacking while a champion is in range, and doze off after
        # two rounds without one. Sleeping camps never attack.
        # A camp group is awake when we hit it or it hit us in the last couple of rounds; sleeping camps
        # never attack, so merely standing in range does not keep them awake.
        if took:
            self.took_round = self.rnd
        if took or self.rnd - self.last_attack_round <= 1:
            self.awake_round = self.rnd
        self.awake = self.rnd - self.awake_round <= 2
        # Camps hit the champion nearest to them, so a teammate may be soaking it all: count incoming
        # damage only while it is really landing on us.
        self.inc = inc * self.mult if (self.awake and self.rnd - self.took_round <= 1) else 0.0
        enemies = []
        if not cambc.vision.champion_tiles(ENEMY).is_empty():
            for e in cambc.vision.champions(ENEMY):
                try:
                    ep = e.position()
                    ehp = e.health()
                    est, emax, ect = 0, ehp, 0
                    try:
                        est = int(e.state())
                        emax = e.max_health()
                        ect = int(e.champion_name())
                    except Error:
                        pass
                    egem = 0
                    try:
                        egem = int(e.gem_count())
                    except Exception:
                        pass
                    enemies.append((ep.x, ep.y, ehp, e.strength(), e, ep, e.attack_range(), e.focus(), ect, emax, est, egem))
                except Error:
                    pass
        self.enemies = enemies
        self.duel = None
        if enemies:
            sg = self.sightings
            e = enemies[0]
            if not sg or sg[-1][0] != self.rnd:
                sg.append((self.rnd, e[0], e[1]))
                if len(sg) > 8:
                    del sg[0]
        # remember damage on the group we are working on
        g = self.task
        if g is not None and camps:
            seen = [c for c in camps if c[3] == g.i]
            if seen:
                left = list(g.hpleft) if g.hpleft is not None else list(g.hp)
                vis = cambc.vision.visible_tiles()
                seen_ci = set()
                for c in seen:
                    left[c[4]] = c[2]
                    seen_ci.add(c[4])
                for ci in range(g.n):
                    if ci not in seen_ci and vis.is_set(g.vec[ci]):
                        left[ci] = 0.0
                if g.hpleft != left:
                    g.hpleft = left
                    g.hpsum = sum(left)
                    g.hp_ver += 1

    # ------------------------------------------------------------------ decisions
    def check_group_done(self):
        g = self.task
        if g is None or self.cstate != C_FIGHT or self.cap_since == 0:
            return
        if cheb(self.px, self.py, int(g.cx), int(g.cy)) > 8:
            return
        try:
            state = g.cg.state()
        except Error:
            return
        if isinstance(state, game_map.CampGroupRespawning):
            self.finish_group(g, state.timer)

    def decide(self):
        if self.bstage != 0:
            return self.ball_decide()
        me = self.me
        px, py = self.px, self.py
        on_spawn = (px, py) in self.spawn_xy
        self.check_group_done()
        self.try_heal()              # a healer tops up whoever is hurt (costs no movement)
        if self.enemies:
            self.duel = self.assess_enemies()
        # 1. enemy champions we would lose to: run for the spawn (one consistent direction)
        duel = self.duel
        if duel is not None and not duel[0]:
            act = self.flee(duel)
            if act:
                return act
        # 2. take cover if camps (or enemies) are hurting us too much
        if self.inc > 0.0 or self.enemies:
            act = self.maybe_retreat()
            if act:
                return act
        # 3. take the enemy fights we win
        act = self.fight_enemies()
        if act:
            return act
        # 3. spawn: shop and heal
        if on_spawn:
            self.buy_items()
            if self.hp < self.maxhp * 0.97 and not self.enemies:
                self.mode = M_IDLE
                return "heal-at-spawn"
            if self.mode == M_HOME:
                self.mode = M_IDLE
        elif self.field_shop and self.gold >= 30:
            self.buy_items()
        # 4. go home to heal / shop
        if self.mode == M_HOME or self.need_home():
            self.mode = M_HOME
            return self.go_home()
        # 5. bank gems
        if self.mode == M_BANK or self.want_bank():
            act = self.do_bank()
            if act:
                return act
        # 6. work on a camp group
        return self.work()

    def need_home(self):
        if self.task is not None and self.camps and self.awake and self.nearest_camp <= 3:
            return False
        if self.hp < self.maxhp * 0.5:
            return True
        if self.gold >= self.shop_gold() and not self.field_shop:
            d = self.df_spawn.get(self.pos)
            if d <= 10 and self.task is None:
                return True
            if self.gold >= 400 and self.task is None:
                return True
        return False

    def shop_gold(self):
        return 150

    # ------------------------------------------------------------------ retreat / enemies
    def maybe_retreat(self):
        hp = self.hp + self.shield_value()
        inc = self.inc
        # enemies able to hit us add their damage as well
        enemy_need = 0.0
        for e in self.enemies:
            if cheb(self.px, self.py, e[0], e[1]) <= e[6] + 1:
                enemy_need += (e[3] + 0.2 * e[7]) * 2.0
        base = self.maxhp * 0.06 + enemy_need
        if inc <= 0.0 and base <= self.maxhp * 0.1:
            return None
        # Once we have broken off hurt we stay out until healed, even if the next tile looks safe enough.
        hold = self.mode == M_HOME and self.hp < self.maxhp * 0.6 and inc > 0.0
        if not hold:
            if hp > inc * 9.0 * self.margin + base:
                return None                   # healthy enough that the exact way out cannot matter yet
            steps = self.steps_to_safety()
            if steps is None:
                steps = 4 - self.nearest_camp if self.nearest_camp < 4 else 1
            need = inc * (steps + 1.0) * self.margin + base
            if hp > need:
                return None
        # nearly dead camps: finish them instead of running
        if self.camps and not hold:
            left = sum(c[2] for c in self.camps if cheb(self.px, self.py, c[0], c[1]) <= 3)
            if left <= self.dps * 2.0 and hp > inc * 3.0:
                return None
        act = self.cast_shield()
        if self.hp < self.maxhp * 0.6:
            self.mode = M_HOME
        if self.can_move:
            moved = self.step_to_safety()
            if moved:
                return act + "retreat"
        return None

    def plan_safety(self):
        """Fill df_path with the way out of every tile a camp (or enemy) can reach; returns the steps needed."""
        if self.safe_round == self.rnd:
            return self.safe_steps
        self.safe_round = self.rnd
        self.safe_steps = None
        danger = Bitboard()
        groups = self.groups
        for c in self.camps:
            if groups[c[3]].st[c[4]] > 0.0:        # clusters never hit back
                danger.draw_chebyshev(c[6], 3)
        for e in self.enemies:
            danger.draw_chebyshev(e[5], 2)
        safe = ~danger & ~self.dyn_block()
        if safe.is_empty():
            return None
        walls = self.dyn_block() & ~safe
        walls.set(self.pos, False)
        dest = Bitboard()
        dest.set(self.pos)
        self.df_path.compute_to(walls, safe, dest, self.scratch)
        d = self.df_path.get(self.pos)
        if d < UNREACHED:
            self.safe_steps = d
        return self.safe_steps

    def steps_to_safety(self):
        return self.plan_safety()

    def step_to_safety(self):
        """Move toward the nearest tile that no live camp can reach."""
        if self.plan_safety() is None:
            return False
        return self.follow(self.df_path)

    def assess_enemies(self):
        """(win, remaining_hp_fraction, enemy_dps, attackers) for the enemies able to engage us soon."""
        px, py = self.px, self.py
        near = []
        for e in self.enemies:
            if cheb(px, py, e[0], e[1]) <= e[6] + 2:
                near.append(e)
        if not near:
            return None
        my = self.pvp_dps
        try:
            for a in cambc.vision.champions(ALLY):
                if a.is_alive():
                    ap = a.position()
                    if (ap.x != px or ap.y != py) and cheb(px, py, ap.x, ap.y) <= 4:
                        my += a.strength()
        except Error:
            pass
        if my < 1.0:
            my = 1.0
        inc = self.inc
        order = sorted(near, key=lambda e: e[2])
        for e in order:
            inc += e[3] + 0.2 * e[7]
        hp = self.hp + self.shield_value()
        for e in order:
            hp -= inc * (e[2] / my)
            if hp <= 0.0:
                break
            inc -= e[3] + 0.2 * e[7]
        keep = 0.2 + (0.2 if self.gems >= 30 else 0.0)
        win = hp > keep * self.maxhp
        return (win, hp / self.maxhp, near)

    def flee(self, duel):
        """Break contact with enemies we would lose to: head for the spawn, where we heal at turn end."""
        if (self.px, self.py) in self.spawn_xy:
            return None                       # fight from the spawn tile instead
        d = self.df_spawn.get(self.pos)
        if d >= UNREACHED:
            return None
        threat = 0.0
        for e in duel[2]:
            if self.melee_enemy(e):
                threat += (e[3] + 0.2 * e[7]) * d      # a melee chaser hits us on every step
        if threat >= self.hp * 0.9:
            return None                       # cannot make it home: fight on
        act = self.cast_shield()
        if self.hp < self.maxhp * 0.7:
            self.mode = M_HOME
        if not self.can_move:
            return None
        if self.walk_home():
            return act + "flee"
        return None

    def aspawn_free(self):
        return self.aspawn & ~self.dyn_block()

    def melee_enemy(self, e):
        return e[6] <= 1

    def fight_enemies(self):
        if not self.enemies or not self.can_attack:
            return None
        duel = self.duel
        px, py = self.px, self.py
        best = None
        for e in self.enemies:
            if cheb(px, py, e[0], e[1]) <= self.arange:
                if best is None or e[2] < best[2]:
                    best = e
        act = ""
        if best is None:
            # a melee champion can step in and strike in the same turn
            if self.melee and self.can_move and (duel is None or duel[0]):
                target = None
                for e in self.enemies:
                    if cheb(px, py, e[0], e[1]) == 2 and (target is None or e[2] < target[2]):
                        target = e
                if target is None:
                    return None
                goals = Bitboard()
                goals.draw_chebyshev(target[5], 1)
                goals &= ~self.dyn_block()
                if not self.step_to(goals):
                    return None
                act = "chase "
                if cheb(self.px, self.py, target[0], target[1]) > self.arange:
                    return act
                best = target
            else:
                return None
        act += self.cast_enemy_spells(best)
        if self.can_attack:
            try:
                self.me.attack(best[4])
                self.can_attack = False
                if not self.melee:
                    self.can_move = False
                act += "hit-enemy"
            except Error:
                pass
        return act if act.strip() else None

    def cast_enemy_spells(self, tgt):
        """Damage and stun spells on an enemy champion in spell range."""
        if not self.can_cast:
            return ""
        for ab, kind, info in self.abil:
            if kind not in (K_DAMAGE, K_CC, K_AOE) or info.modifier <= 0:
                continue
            if info.exclusive_with_movement and self.moved:
                continue
            if ab.cooldown() != 0 or cheb(self.px, self.py, tgt[0], tgt[1]) > info.range:
                continue
            try:
                ok = ab.use(tgt[5]) if kind == K_AOE else ab.use(tgt[4])
            except Error:
                continue
            if ok:
                self.can_cast = False
                if info.exclusive_with_movement:
                    self.can_move = False
                return "spell-enemy "
        return ""

    # ------------------------------------------------------------------ movement helpers
    def dyn_block(self):
        b = self.static_block | cambc.vision.camp_tiles() | cambc.vision.champion_tiles()
        return b

    def follow(self, df):
        """Take one step along a distance field, avoiding units we can see."""
        self.revealed = False
        if not self.can_move:
            return False
        try:
            moves = df.next_moves_from(self.pos)
        except Error:
            return False
        for d in moves:
            try:
                if self.me.move(d):
                    self.px += d.x
                    self.py += d.y
                    self.pos = Vec2(self.px, self.py)
                    if not self.melee:
                        self.can_attack = False
                    self.can_move = False
                    self.moved = True
                    return True
                self.revealed = True            # an unseen unit (in a bush) is there: now we know about it
            except Error:
                continue
        return False

    def step_to(self, goals, avoid=None):
        """Walk one step toward the nearest goal tile; goals must be free tiles."""
        if not self.can_move or goals.is_empty():
            return False
        for _ in range(3):
            block = self.dyn_block()
            if avoid is not None:
                block |= avoid
            block = block & ~goals
            block.set(self.pos, False)
            dest = Bitboard()
            dest.set(self.pos)
            self.df_path.compute_to(block, goals, dest, self.scratch)
            if self.df_path.get(self.pos) >= UNREACHED:
                return False
            if self.follow(self.df_path):
                return True
            if not self.revealed:
                return False
        return False

    # ------------------------------------------------------------------ home, shop, bank
    def hot_zone(self):
        """Tiles within reach of camps that are awake, i.e. hit lately by us or a teammate (None when there are none)."""
        if not self.camps:
            return None
        rnd = self.rnd
        awk = self.camp_awake
        groups = self.groups
        zone = None
        for c in self.camps:
            if rnd - awk.get((c[0], c[1]), -99) <= 2 and groups[c[3]].st[c[4]] > 0.0:
                if zone is None:
                    zone = Bitboard()
                zone.draw_chebyshev(c[6], 3)
        return zone

    def walk_home(self):
        """One step toward the spawn, going around camps that are awake."""
        if not self.can_move:
            return False
        zone = self.hot_zone()
        if zone is not None:
            if self.step_to(self.aspawn_free(), zone):
                return True
            if not zone.is_set(self.pos):
                return False                  # the only way home crosses an awake camp: wait for it to doze off
        return self.follow(self.df_spawn)

    def go_home(self):
        d = self.df_spawn.get(self.pos)
        if d >= UNREACHED:
            return "home-unreachable"
        if (self.px, self.py) in self.spawn_xy:
            return "home-wait"
        recall_t = 3 if "HOME" in self.flags else 5
        hunted = False
        for e in self.enemies:
            if cheb(self.px, self.py, e[0], e[1]) <= e[6] + 5:
                hunted = True
                break
        if d <= recall_t + 1 or hunted:
            if self.walk_home():
                return "walk-home"
        # bank on the way when an altar is close to our path home
        if self.gems >= 20 and self.df_altar.get(self.pos) <= 8 and not hunted and self.hp >= self.maxhp * 0.5:
            act = self.do_bank()
            if act:
                return act
        if self.inc > 0.0:
            if self.step_to_safety():
                return "home-evade"
            if self.task is not None and any(c[3] == self.task.i for c in self.camps):
                return "home-cornered " + self.work()
            return "home-wait-danger"
        try:
            self.me.recall()
            self.recall_started = self.rnd
            return "recall"
        except Error as error:
            return f"recall-failed {error}"

    def buy_items(self):
        me = self.me
        if self.bstage != 0 and (self.px, self.py) in self.spawn_xy:
            self.buy_lock()
        gold = self.gold
        bought = False
        while gold >= 30 and self.set_pos < len(self.build):
            fam, stat = self.build[self.set_pos]
            it = self.item(fam, stat)
            cost = 30
            n = min(gold // cost, 5 - self.set_cnt)
            if n <= 0:
                break
            try:
                me.buy(it, n)
            except Error as error:
                self.log(f"buy-failed {error}")
                break
            gold -= cost * n
            self.set_cnt += n
            bought = True
            if self.set_cnt >= 5:
                self.set_cnt = 0
                self.set_pos += 1
                self.flags.add(("MON", "POW", "DUR", "TRE", "JUN", "HOME", "BRU")[fam])
        if bought:
            self.gold = gold
            self.stats_dirty = True
            self.log(f"bought sets={self.set_pos}+{self.set_cnt} gold_left={gold}")
        return bought

    def bank_threshold(self, d):
        t = 6 * d + 10
        if t < 30:
            t = 30
        if t > 110:
            t = 110
        return t

    def want_bank(self):
        gems = self.gems
        if gems <= 0:
            return False
        if self.task is not None and self.camps and (self.inc > 0.0):
            return False
        d = self.df_altar.get(self.pos)
        if d >= UNREACHED:
            return False
        if self.endgame_bank(d):
            return True
        submitted = cambc.global_submitted_gems(ALLY)
        if submitted + max(self.tot, gems) >= 1000 - 2:
            return True
        if self.committed():
            return False
        return gems >= self.bank_threshold(d)

    def endgame_bank(self, d):
        """Close to the round limit carried gems are worth nothing: take them to an altar while there is time."""
        return ROUND_LIMIT - self.rnd <= d + (self.gems + 9) // 10 + ENDGAME_SLACK

    def do_bank(self):
        px, py = self.px, self.py
        for k, (ax, ay) in enumerate(self.altar_xy):
            if cheb(px, py, ax, ay) <= cambc.constants.SUBMIT_GEMS_RANGE:
                try:
                    self.me.submit_gems(self.altar_vecs[k])
                    print(f"R{self.rnd} S{self.slot} BANK {self.gems}", flush=True)
                    self.mode = M_IDLE
                    self.task = None
                    self.bank_latch = -1
                    return "submit"
                except Error as error:
                    return f"submit-failed {error}"
        self.mode = M_BANK
        if self.follow(self.df_altar):
            return "walk-bank"
        if self.step_to(self.altar_goals):
            return "walk-bank2"
        self.mode = M_IDLE
        return None

    # ------------------------------------------------------------------ choosing work
    def group_estimate(self, g, n=1):
        """(turns to clear, damage the tank takes) for n champions of our strength working together."""
        key = self.stats_version * 1000003 + g.hp_ver
        if g.est_key != key:
            g.est_key = key
            g.est = {}
        est = g.est.get(n)
        if est is not None:
            return est
        hps = g.hp if g.hpleft is None else [h for h in g.hpleft]
        idx = [i for i in range(g.n) if hps[i] > 0.0]
        dps = self.dps * n
        if not idx:
            est = (0.0, 0.0)
        elif len(idx) > 5:
            tot = sum(hps[i] for i in idx)
            t = tot / max(dps, 1.0)
            est = (t, sum(g.st[i] for i in idx) * t * 0.5 * self.mult)
        else:
            sub_adj = [[g.adj[i][j] for j in idx] for i in idx]
            est = simulate([hps[i] for i in idx], [g.st[i] for i in idx], sub_adj, dps, self.splash, self.mult)
        g.est[n] = est
        return est

    def choose_task(self):
        roots = Bitboard()
        roots.set(self.pos)
        self.df_me.compute(self.static_block, roots, self.scratch)
        best = self.best_group(self.near_groups)
        if best is None and self.rest_groups:
            best = self.best_group(self.rest_groups)
        return best

    def cycles_for(self, taken, b0, bfull):
        """Recall trips needed to absorb `taken` damage with a health budget of b0 (then bfull per trip)."""
        if taken <= b0:
            return 0
        return 1 + int((taken - b0) / bfull) if bfull > 0 else 9

    def best_group(self, groups, ball=False):
        """Pick the group with the best (gems + gold) per turn. Cheap bound first, exact fight estimate
        only for the few groups that could still win. Groups a teammate is already on are considered as
        joins when working together saves more time than it costs."""
        rnd = self.rnd
        claims = self.claims
        kappa = max(KAPPA_MIN, KAPPA0 - rnd / KAPPA_DECAY)
        hp_full = self.maxhp
        shield = self.shield_amt
        b0 = 0.7 * (self.hp + shield)
        bfull = 0.7 * (hp_full + shield)
        recall_t = 3 if "HOME" in self.flags else 5
        mult = self.mult
        cap_inc = 0.15 * hp_full / mult if mult > 0 else 1e9      # skip groups hitting harder than 15% hp/turn
        dps = self.dps if self.dps > 1.0 else 1.0
        spl = self.splash
        df_get = self.df_me.get
        cands = []
        joins = []
        party = BALL_PARTY if ball else K_PARTY
        esc = 1.0
        if ball:
            n_esc = 0
            for a in self.allies:
                if cheb(self.px, self.py, a[0], a[1]) <= ESCORT_R:
                    n_esc += 1
            esc = 1.0 if n_esc >= 2 else (0.5 if n_esc == 1 else 0.0)
        push = self.push_f * esc if ball else 0.0
        opening = self.home_open and rnd < OPEN_HOME_R
        if opening:
            push = 0.0                              # v16: 4-champion maps play at home in the opening
        big_ok = self.nslots >= BIG_PARTY
        for g in groups:
            if g.block_until > rnd:
                continue
            if g.threat_until > rnd:
                continue                            # v20: a stronger enemy is about there
            hs = g.hpsum
            if ball and g.d_enemy <= ESP_AVOID:
                continue                            # never camp on the enemy's doorstep
            big = big_ok and is_big(g)
            cl = claims.get(g.rank)
            if cl is not None:
                if len(cl) < (BIG_PARTY if big and party < BIG_PARTY else party):
                    joins.append((g, cl))
                continue
            if g.stsum > cap_inc:
                continue
            d = df_get(g.v0)
            if d >= UNREACHED:
                continue
            travel = d - 1 if d > 1 else 0
            wait = g.ready_at - rnd - travel
            if wait < 0:
                wait = 0
            elif wait > WAIT_NEAR_MAX:
                continue
            val = g.gems + kappa * g.gold
            wt = (1.0 + (g.deny - 1.0) * push) if ball else g.contest
            ub = wt * val / (travel + wait + CAP_TURNS + hs / (dps + spl * (g.n - 1)))
            cands.append((ub, g.i, travel, val))
        cands.sort(reverse=True)
        groups_by_i = self.groups
        estimate = self.group_estimate
        best = None
        best_score = 0.0
        for ub, gi, travel, val in cands:
            if ub <= best_score:
                break
            g = groups_by_i[gi]
            # a group we can see right now may be respawning (taken by someone else): trust the engine
            timer = self.peek_respawn(g)
            if timer is not None:
                g.ready_at = rnd + timer
            wait = g.ready_at - rnd - travel
            if wait < 0:
                wait = 0
            elif wait > WAIT_NEAR_MAX:
                if timer is not None:
                    g.block_until = rnd + timer - WAIT_NEAR_MAX // 2
                continue
            tf, taken = estimate(g)
            if tf <= 0.0 and g.hpsum > 0.0:
                continue
            wt = (1.0 + (g.deny - 1.0) * push) if ball else g.contest
            score = wt * val / (travel + wait + CAP_TURNS + tf
                                + self.cycles_for(taken, b0, bfull) * (recall_t + g.d_spawn + 3))
            for t, ex, ey in self.sightings:
                if ball:
                    if rnd - t < 40 and cheb(ex, ey, int(g.cx), int(g.cy)) <= 9:
                        score *= 1.25 if (esc >= 1.0 and not opening) else 0.7    # hunt in company, keep away alone
                        break
                elif rnd - t < 50 and cheb(ex, ey, int(g.cx), int(g.cy)) <= 7:
                    score *= 0.7            # enemies were seen around there lately
                    break
            if score > best_score:
                best_score = score
                best = g
        # joins: a teammate is already on the group; is our help worth more than our time?
        if joins:
            r_ref = best_score if best_score > 0.0 else 0.3
            join_score = 0.0
            for g, cl in joins:
                if cl[0][1] == C_STAGE:
                    continue                            # they are already collecting the reward
                n0 = len(cl)
                d = df_get(g.v0)
                if d >= UNREACHED:
                    continue
                travel = d - 1 if d > 1 else 0
                tf0, tk0 = estimate(g, n0)
                tf1, tk1 = estimate(g, n0 + 1)
                if tf0 <= 0.0 or tf1 <= 0.0:
                    continue
                t_cycle = recall_t + g.d_spawn + 3
                big = big_ok and is_big(g)
                if big:
                    # the party shares the hits (nearest champion), so its health is pooled between trips
                    big0 = tf0 + self.cycles_for(tk0, n0 * b0, n0 * bfull) * t_cycle
                    big1 = tf1 + self.cycles_for(tk1, (n0 + 1) * b0, (n0 + 1) * bfull) * t_cycle
                else:
                    big0 = tf0 + self.cycles_for(tk0, b0, bfull) * t_cycle
                    big1 = tf1 + self.cycles_for(tk1, b0, bfull) * t_cycle
                saving = n0 * (big0 - big1)
                cost = travel + big1 + CAP_TURNS
                if big and (n0 + 1) * big1 + travel <= BIG_EFF * n0 * big0:
                    # our own share of the reward, as long as the party does not waste much champion-time
                    wt = (1.0 + (g.deny - 1.0) * push) if ball else g.contest
                    share = wt * (g.gems + kappa * g.gold) / (n0 + 1) / cost
                    if share > join_score:
                        join_score = share
                        best_join = g
                if saving <= 1.15 * cost:
                    continue
                score = r_ref * saving / cost
                if score > join_score:
                    join_score = score
                    best_join = g
            if join_score > best_score:
                best = best_join
        return best

    def peek_respawn(self, g):
        """Respawn timer of a group we can see right now, None if it is not visibly respawning."""
        if cheb(self.px, self.py, int(g.cx), int(g.cy)) > 8:
            return None
        try:
            state = g.cg.state()
        except Error:
            return None
        if isinstance(state, game_map.CampGroupRespawning):
            return state.timer
        return None

    def work(self):
        act = self.work_once()
        if self.task is None and act != "no-task" and act != "defer-choose":
            # the task just ended without using the turn: pick the next one right away
            act += " | " + self.work_once()
        return act

    def work_once(self):
        # choose a group when we have none
        if self.task is None:
            f_before = cambc.fuel_remaining()
            if f_before < CHOOSE_MIN_FUEL:
                return "defer-choose"
            g = self.pick_task()
            if DEBUG:
                self.log(f"choose_task fuel={f_before - cambc.fuel_remaining()}")
            if g is None:
                return "no-task"
            self.task = g
            self.cstate = C_HEAD
            self.done_rank = -1
            self.t_start = self.rnd
            self.cap_since = 0
            self.log(f"TASK {g.i} rank={g.rank} gems={g.gems} gold={g.gold} kind={g.kind}")
        g = self.task
        # more teammates on it than K_PARTY: the highest slots step aside
        cl = self.claims.get(g.rank)
        limit = self.kparty if self.bstage == 0 else BALL_PARTY
        if is_big(g) and self.nslots >= BIG_PARTY and limit < BIG_PARTY:
            limit = BIG_PARTY
        if cl is not None and len(cl) >= limit:
            lower = 0
            for sl, st in cl:
                if sl < self.slot:
                    lower += 1
            if lower >= limit:
                self.task = None
                return "task-lost"
        px, py = self.px, self.py
        mine = [c for c in self.camps if c[3] == g.i]
        if mine:
            self.cstate = C_FIGHT
            return self.fight(g, mine)
        d_anchor = cheb(px, py, int(g.cx), int(g.cy))
        if d_anchor <= 8:
            state = None
            try:
                state = g.cg.state()
            except Error:
                state = None
            if isinstance(state, game_map.CampGroupRewardAvailable):
                return self.capture(g)
            if isinstance(state, game_map.CampGroupRespawning):
                return self.on_respawning(g, state.timer)
        # walk toward the camps
        return self.approach(g)

    def on_respawning(self, g, timer):
        """The group we came for is down: our own capture ended, or it is a short wait away."""
        if self.cstate == C_FIGHT and self.cap_since > 0:
            return self.finish_group(g, timer)
        g.ready_at = self.rnd + timer
        g.hpleft = None
        g.hpsum = g.hp_total
        g.hp_ver += 1
        self.cstate = C_HEAD
        limit = BALL_WAIT_MAX if self.bstage != 0 else WAIT_NEAR_MAX
        if timer > limit:
            # too long to idle here: come back when it is nearly up
            g.block_until = self.rnd + timer - limit // 2
            self.task = None
            self.cap_since = 0
            return "group-later"
        return self.approach(g, waiting=True)

    def finish_group(self, g, timer):
        if self.cstate == C_FIGHT and self.cap_since > 0:
            g.ready_at = self.rnd + g.resp
            self.done_rank = g.rank
            self.done_b_rank = g.rank             # v20: broadcast the capture for two rounds (ball_byte)
            self.done_b_until = self.rnd + 1
            self.tag("captured")
            self.log(f"CAPTURED {g.i} gems={self.gems} gold={self.gold}")
        else:
            g.ready_at = self.rnd + timer
            g.block_until = 0
        g.hpleft = None
        g.hpsum = g.hp_total
        g.hp_ver += 1
        self.task = None
        self.cap_since = 0
        self.cstate = C_HEAD
        return "group-done"

    def capture(self, g):
        self.cstate = C_FIGHT
        if self.cap_since == 0:
            self.cap_since = self.rnd
        if (self.px, self.py) in g.xyset:
            self.cw_n = 0
            if self.rnd - self.cap_since > 25:
                g.block_until = self.rnd + 50
                self.task = None
                self.cap_since = 0
                return "capture-timeout"
            return "capturing" + self.capture_fire(g)
        if self.bstage != 0 and not self.enemies:
            # an ally already stands on the spawn tiles and nobody contests it: the reward is theirs, move on
            mates = g.bb & cambc.vision.champion_tiles(ALLY)
            mates.set(self.pos, False)
            if not mates.is_empty():
                g.ready_at = self.rnd + CAP_TURNS + g.resp
                self.task = None
                self.cap_since = 0
                self.cstate = C_HEAD
                return "capture-left"
        goals = g.bb & ~self.dyn_block()
        if self.bstage != 0 and not goals.is_empty() and not self.my_turn_to_capture(g, goals):
            self.cw_n += 1
            if self.cw_n <= CAP_PATIENCE:
                return "capture-wait"
        else:
            self.cw_n = 0
        if goals.is_empty():
            # someone already stands on every spawn tile: they collect, we move on
            g.ready_at = self.rnd + CAP_TURNS + g.resp
            self.task = None
            self.cap_since = 0
            return "capture-yield"
        if self.step_to(goals):
            return "to-capture"
        return "capture-stuck"

    def capture_fire(self, g):
        """Standing on the capture tile anyway: hit a camp in range instead of idling."""
        if not self.can_attack or not self.camps:
            return ""
        best = None
        for c in self.camps:
            if c[3] == g.i or cheb(self.px, self.py, c[0], c[1]) > self.arange:
                continue
            st = self.groups[c[3]].stsum
            if st > 0 and (self.hp < 0.7 * self.maxhp or st > 60):
                continue                          # only wake fighting camps when healthy and they are weak
            key = (st, c[2])
            if best is None or key < best[0]:
                best = (key, c)
        if best is None:
            return ""
        try:
            self.me.attack(best[1][5])
        except Error:
            return ""
        self.can_attack = False
        self.last_attack_round = self.rnd
        if not self.melee:
            self.can_move = False
        return "+hit"

    def approach(self, g, waiting=False):
        # target tiles: next to (melee) or in range of (ranged) the group's camps
        goals = Bitboard()
        for v in g.vec:
            goals.draw_chebyshev(v, self.arange)
        if waiting:
            goals &= ~g.bb              # keep the spawn tiles free for the respawn
        goals &= ~self.dyn_block()
        if goals.is_empty():
            g.block_until = self.rnd + 40
            self.task = None
            return "approach-blocked"
        if waiting and goals.is_set(self.pos):
            self.same_pos = 0
            return "wait-respawn"
        if self.last_pos == (self.px, self.py):
            self.same_pos += 1
        else:
            self.same_pos = 0
        self.last_pos = (self.px, self.py)
        ph = self.pos_hist
        ph.append(self.last_pos)
        if len(ph) > 10:
            del ph[0]
            if len(set(ph)) <= 2:
                self.same_pos = 99               # shuffling between two tiles gets us nowhere
                del ph[:]
        if self.same_pos > 8:
            g.block_until = self.rnd + 60
            self.task = None
            self.same_pos = 0
            return "approach-stuck"
        if self.step_to(goals):
            return "approach"
        return "approach-fail"

    # ------------------------------------------------------------------ fighting camps
    def fight(self, g, mine):
        me = self.me
        arange = self.arange
        act = ""

        def key(c):
            # kill the camp with the most damage per remaining hp first, then the weakest
            return (g.st[c[4]] / max(c[2], 1.0), -c[2])

        def reachable(c):
            return cheb(self.px, self.py, c[0], c[1]) <= arange

        in_range = [c for c in mine if reachable(c)]
        if not in_range and self.can_move:
            goals = Bitboard()
            for c in mine:
                goals.draw_chebyshev(c[6], arange)
            block = self.dyn_block()
            if not self.melee:
                inner = Bitboard()
                for c in mine:
                    inner.draw_chebyshev(c[6], arange - 1)
                ring = goals & ~inner & ~block
                if not ring.is_empty():
                    goals = ring
            goals &= ~block
            if self.step_to(goals):
                act += "step "
                in_range = [c for c in mine if reachable(c)]
        if in_range:
            tgt = max(in_range, key=key)
            act += self.cast_spells(mine, tgt)
            if self.can_attack:
                try:
                    me.attack(tgt[5])
                    self.last_attack_round = self.rnd
                    self.fight_gi = g.i
                    self.can_attack = False
                    if not self.melee:
                        self.can_move = False
                    act += "hit "
                    act += self.cast_reset(tgt)
                    if sum(g.st) > 0:
                        act += self.cast_shield()
                except Error as error:
                    act += f"hit-failed({error}) "
        else:
            act += self.cast_spells(mine, None)
            act += "closing"
        return act

    # ------------------------------------------------------------------ abilities
    def shield_value(self):
        if self.rnd > getattr(self, "shield_until", -1):
            return 0.0
        try:
            buffs = self.me.buffs()
            if buffs.has_shield():
                return float(buffs.get(cambc.BuffShield).value)
        except Exception:
            pass
        return 0.0

    def cast_shield(self):
        if not self.can_cast:
            return ""
        for ab, kind, info in self.abil:
            if kind == K_SHIELD and ab.cooldown() == 0:
                try:
                    if ab.use():
                        self.can_cast = False
                        self.shield_until = self.rnd + info.duration
                        return "shield "
                except Error:
                    pass
        return ""

    def cast_reset(self, tgt):
        """Attack-reset abilities grant a second swing this turn."""
        if not self.can_cast:
            return ""
        for ab, kind, info in self.abil:
            if kind == K_RESET and ab.cooldown() == 0:
                try:
                    if ab.use():
                        self.can_cast = False
                        self.me.attack(tgt[5])
                        return "reset+hit "
                except Error:
                    pass
        return ""

    def cast_spells(self, mine, tgt):
        """Damage / stun spells on the toughest camp in spell range."""
        if not self.can_cast:
            return ""
        px, py = self.px, self.py
        for ab, kind, info in self.abil:
            if kind not in (K_DAMAGE, K_CC, K_AOE) or info.modifier <= 0:
                continue
            if info.exclusive_with_movement and self.moved:
                continue
            if ab.cooldown() != 0:
                continue
            best = None
            for c in mine:
                if cheb(px, py, c[0], c[1]) <= info.range:
                    if best is None or c[2] > best[2]:
                        best = c
            if best is None:
                continue
            try:
                ok = ab.use(best[6]) if kind == K_AOE else ab.use(best[5])
            except Error:
                continue
            if ok:
                self.can_cast = False
                if info.exclusive_with_movement:
                    self.can_move = False
                self.last_attack_round = self.rnd
                self.fight_gi = best[3]
                self.tag(f"campcast{self.ctype}")
                return "spell "
        return ""
