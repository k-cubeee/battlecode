"""The deathball: farm first, then gather at home, march out together, take camps as one body and win
skirmishes with a small turn planner (focus fire, spells, heals, altar locks).

BallMixin is mixed into bot.Bot; it relies on the farming machinery there (task, work_once, go_home, ...).
"""
import cambc
import tables as T

ALLY = cambc.Team.ALLY
ENEMY = cambc.Team.ENEMY
Vec2 = cambc.Vec2
Bitboard = cambc.Bitboard
DistanceField = cambc.DistanceField
Error = cambc.Error

# ------------------------------------------------------------------ tuning
DEBUG_HOLD = 1            # log why a champion is idling in a fight (only with DEBUG)
BALL_ON = 1               # 0 turns the whole push off (pure farming)
R_GATHER = 130            # default round at which everybody heads home to shop and group up
R_GATHER_MIN = 110        # ... on maps where the spawns are close together
R_GATHER_MAX = 200        # ... and where they are far apart
R_GATHER_SLOPE = 1.5      # extra rounds of build-up per tile between the spawns
D_REF = 24                # spawn distance at which the push starts at R_GATHER_MIN
GATHER_MIN = 6            # never march before this many rounds into the gather
GATHER_MAX = 30           # march with whoever is ready after this many rounds
LEAD_WAIT = 6             # a new leader waits this long at home for stragglers that are on their way
GATHER_BANK_GEMS = 25     # bank before going home when carrying at least this many gems and an altar is close
GATHER_BANK_DIST = 8
HOME_HP = 0.45            # go home to heal below this health fraction
GOLD_HOME = 300           # go home to shop when carrying this much gold and home is near
GOLD_HOME_FAR = 450       # ... or this much from anywhere when between jobs
FOLLOW_R = 2              # followers stay within this many tiles of the leader when there is no objective
CONVOY_R = 6              # allies within this distance count as "with the ball"
CONVOY_NEED = 2           # allies that must be close before the ball steps on while travelling
HOLD_MAX = 3              # most consecutive turns spent waiting for the ball
HOLD_BUDGET = 14          # most waiting per objective
BALL_KAPPA = 0.15         # value of one gold in gems during the push
DENY_W = 3.0              # extra weight on groups on the enemy's half of the map
DENY_MODE = 1             # 0: by how much closer to the enemy than to us; 1: by closeness to the enemy spawn
SIEGE_D = 30.0            # DENY_MODE 1: groups within this distance of the enemy spawn get the bonus
FRONT_OFF = 6             # a group this much further from us than from the enemy spawn is neutral (lean 0.5) ...
FRONT_SPAN = 12           # ... and the weight saturates this many tiles further in
ESP_AVOID = 7             # skip groups this close to the enemy spawn
BALL_WAIT_MAX = 12        # longest respawn wait the leader accepts
SEE_R = 10                # enemies this close take part in the fight assessment
R_GO = 1.05               # strength ratio needed to start a fight
R_STAY = 0.7              # ... and to keep fighting
LAMBDA = 0.45             # weight on expected incoming damage in the turn planner
CO_W = 5.0                # pull toward the ball's centre
ADV_W = 14.0              # pull toward the target while advancing
RET_W = 10.0              # pull toward the spawn while retreating
HEAL_W = 1.0
KILL_TURNS = 5.0
GEM_K = 8.0               # kill value per gem the enemy is carrying (the killer takes them)
GEM_F = 0.25              # focus-target score per carried gem (capped at 150)
ATTACH_R = 9              # a champion that sees an ally this close counts as being with the ball
ALONE_N = 4               # turns without seeing an ally before we count as detached
PATH_R = 7                # an enemy this many steps away (or fewer) counts as able to reach us
HOME_FIGHT_R = 10         # v16: on 4-champion maps, within this walk of our spawn the needed ratio ...
HOME_FIGHT_F = 0.85       # ... is scaled by this
HOME_R = 3               # enemies this close to their own spawn are not chased
HOLD_FIGHT_MAX = 4        # consecutive idle fight turns before we get on with other business
GATHER_FINISH = 25        # most rounds spent finishing a camp fight that was under way when the gather began

R_AREA = 14               # followers pick camp groups this close to the leader's objective
SITE_R = 10               # the ball is "at work" when its leader is this close to its objective
R_LEASH = 26              # a follower this far from the leader gives up an uncommitted job and rejoins
BALL_PARTY = 2            # most champions on one camp group during the push
BANK_LATCH = 30           # once we set out to bank we keep at it this long
CAP_PATIENCE = 4          # most turns spent waiting for a poorer ally to take the spawn tiles of a cleared group
PUSH_SPAN = 200.0         # gem lead (either way) at which the push weight reaches its limits
BANK_MULT = 1.0           # bank threshold relative to the farming bot's

ESCORT_R = 6              # allies this close count as company when choosing where to go
XCH_A = 0.4               # smoothing of the observed damage exchange in a fight
XCH_MIN_TURNS = 2         # turns of exchange seen before trusting it
XCH_MARGIN = 1.1          # back off when we would die before killing their weakest by this factor
BAIL_HP = 0.3             # back off below this health fraction unless a kill is at hand
DEEP_DE = 10              # alone, tiles this close to the enemy spawn are penalised ...
DEEP_W = 8.0              # ... by this much per tile
GEM_CAUTION = 200.0       # carried gems raise the strength ratio we want before fighting (x2 at this many)
MARCH_BANK_BASE = 30      # during the push bank at 30 + 3 * (steps to an altar) gems at most
MARCH_BANK_PER = 3
RET_W_FLEE = 60.0         # pull toward the spawn when running there would save us
FLEE_SAFETY = 0.8         # ... i.e. when the walk takes under this fraction of the turns we can survive
REGROUP_W = 3.0           # alone and outnumbered: drift toward the spawn instead of holding in place
REGROUP_W_BALL = 2.0      # v20: ... and with allies about (each planner retreats, CO_W keeps the body together)
BANK_NEAR = 3             # an altar this close is used even with enemies about (damage does not stop a tribute)
BANK_NEAR_GEMS = 20
BANK_RUN_ANY = 25         # v20: a retreat with this many gems heads for the altar when it is nearer than home and the enemy
PRESS_BANK_MARGIN = 2.0   # v20: pressed beside an altar, tribute when our health covers this much of the channel's damage
MELEE_TYPES = (T.RYTH, T.VENDETTA, T.ISSAC, T.MARCELLA, T.REN, T.VARG)

THREAT_R = 6              # v20: a lost fight marks camp groups whose centre is this close to the enemy ...
THREAT_T = 25             # ... for this many rounds (no new task there, and the current one is dropped)
STANDOFF_SKIP = 3         # v20: lost fight but nobody can hit us next turn: ignore it this long and get on with work
# v20: how far each champion can strike before our next turn: walk (or dash 2) and a basic attack, or a spell's
# range plus its radius. A refused fight presses us only within this + 1, and a retreat keeps out of it.
HIT_REACH = {T.RYTH: 5, T.VESPER: 5, T.VENDETTA: 4, T.CASSI: 4, T.ISSAC: 4, T.STELLAR: 5, T.PRISM: 5,
             T.MARCELLA: 4, T.WILLOW: 3, T.REN: 4, T.VARG: 2, T.TAVI: 4}

SPAWN_HOLD_D = 9          # v17: on our spawn, enemies this close and a fight we would lose: wait for company
SPAWN_HOLD_MAX = 30       # ... for at most this many consecutive turns
SPAWN_HOLD_W = 1000.0     # turn-planner penalty for stepping off the spawn while holding
SPAWN_RISK_F = 0.35       # incoming damage on our spawn tiles counts this much (they heal us every turn end)

SOLO = 1                 # no ball: every champion farms on its own once the push stage starts

COMMIT_GO_SLACK = 1       # in a camp fight, ignore enemies we would beat until they are this close to reaching us
COMMIT_RUN_SLACK = 3      # ... and enemies we would lose to until this close

B_FARM, B_GATHER, B_MARCH = 0, 1, 2
# S_GATHER: heading home / at home; S_READY: in the field; S_LEAD: leader; S_DONE: in the field and just finished
# the group named in the code (the others learn that it is respawning)
S_GATHER, S_READY, S_LEAD, S_DONE = 0, 1, 2, 3
NOOBJ = 63

# enemy record fields (built in plan_fight)
E_X, E_Y, E_HP, E_MAXHP, E_DPS, E_RNG, E_CT, E_ST, E_OBJ, E_POS, E_STR, E_ONSP = range(12)


def cheb(ax, ay, bx, by):
    dx = ax - bx
    dy = ay - by
    if dx < 0:
        dx = -dx
    if dy < 0:
        dy = -dy
    return dx if dx > dy else dy


def unit_dps(ctype, s, f):
    """Average damage per turn of a champion over a full cooldown cycle."""
    mods, reset = T.PVP_KIT.get(ctype, (0.0, False))
    d = s + mods * f / 9.0
    if reset:
        d += s / 9.0
    return d


class BallMixin:
    # ------------------------------------------------------------------ setup
    def ball_init(self):
        self.bstage = B_FARM
        self.bstate = S_GATHER
        self.is_leader = False
        self.leader_slot = -1
        self.bmem = {}
        self.ball_n = 1
        self.marching = False
        self.gather_t0 = -1
        self.engaged = False
        self.hold_sp = 0
        self.spawn_hold = False
        self.hold_n = 0
        self.hold_total = 0
        self.hold_obj = -1
        self.lead_wait_n = 0
        self.last_leader_pos = None
        self.allies = []
        self.espawn_xy = set((v.x, v.y) for v in self.espawn.positions())
        self.has_lock = False
        self.lock_cons = None
        self.lock_type = None
        try:
            self.lock_type = cambc.ConsumableType.ALTAR_LOCK
        except Exception:
            self.lock_type = None
        self.slot_types = getattr(self, "slot_types", [])
        # how much each altar leans toward the enemy (positive: closer to them than to us)
        self.alt_lean = []
        for (ax, ay) in self.altar_xy:
            best_s, best_e = 65535, 65535
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    v = Vec2(ax + dx, ay + dy)
                    try:
                        ds = self.df_spawn.get(v)
                        de = self.df_enemy.get(v)
                    except Error:
                        continue
                    if ds < best_s:
                        best_s = ds
                    if de < best_e:
                        best_e = de
            self.alt_lean.append((best_s - best_e) if best_s < 65535 and best_e < 65535 else 0)
        # per-group weight for pushing into the enemy's half, and a keep-out near their spawn
        for g in self.groups:
            d_enemy = self.df_enemy.get(g.v0)
            if DENY_MODE == 1:
                lean = 1.0 - d_enemy / SIEGE_D
            else:
                lean = (g.d_spawn - d_enemy + FRONT_OFF) / FRONT_SPAN
            g.deny = 1.0 + DENY_W * (0.0 if lean < 0.0 else (1.0 if lean > 1.0 else lean))
            g.d_enemy = d_enemy
        self.ball_ready_flag = False
        self.alone_n = 0
        # how far apart the spawns are decides when the push starts: far apart, it pays to build up longer first
        dsp = 65535
        for v in self.aspawn.positions():
            try:
                dd = self.df_enemy.get(v)
            except Error:
                continue
            if dd < dsp:
                dsp = dd
        self.d_spawns = dsp
        if dsp >= 65535:
            self.r_gather = R_GATHER
        else:
            rg = R_GATHER_MIN + R_GATHER_SLOPE * (dsp - D_REF)
            self.r_gather = int(R_GATHER_MIN if rg < R_GATHER_MIN else (R_GATHER_MAX if rg > R_GATHER_MAX else rg))
        self.r_gather = 0                         # solo from the first round: the fight planner and push banking throughout
        self.log(f"MAPINFO D={dsp} r_gather={self.r_gather} W={self.W} H={self.H} groups={len(self.groups)} altars={len(self.altar_xy)}")
        self.leader_xy = None
        self.lead_written = None
        self.pos_hist = []
        self.df_near = DistanceField()
        self.hold_fights = 0
        self.skip_fight_until = -1
        self.done_b_rank = -1                     # v20: group we just captured, broadcast as S_DONE ...
        self.done_b_until = -1                    # ... until this round
        self.press_rnd = -99
        self.last_ratio = 1.0
        self.hard_retreat = False
        self.xch_round = -10
        self.xch_hp = {}
        self.xch_t = 0.0
        self.xch_d = 0.0
        self.xch_n = 0
        self.took_amt = 0.0
        self.replanned = False
        self.revealed = False
        self.bank_latch = -1
        self.push_f = 0.5
        self.anchor = None
        self.anchor_gi = -1
        self.arrived = False
        self.anchor_d = None

    # ------------------------------------------------------------------ phase and election
    def ball_phase(self):
        if self.bstage == B_FARM and self.rnd >= self.r_gather and BALL_ON:
            self.bstage = B_MARCH                 # the push starts where everybody is: no trip home
            self.bstate = S_READY if self.mode != 1 else S_GATHER
            self.marching = True
            self.gather_t0 = self.rnd
            # shopping for the push: finish the partial set, then durability and power
            pass                                  # keep the farming build order
            self.log("BALL gather")

    def ball_read(self, buf):
        mem = {}
        rnd = self.rnd
        if rnd >= self.r_gather + 2:
            for s in range(self.nslots):
                if s != self.slot:
                    b = buf[s]
                    if b:
                        mem[s] = (b >> 6, b & 63)
        self.bmem = mem
        n = 1
        claims = {}
        ld = self.last_done
        for sl, (st, code) in mem.items():
            if st == S_READY or st == S_LEAD or st == S_DONE:
                n += 1
            if st == S_DONE:
                r = code - 1
                if 0 <= r < len(self.rank_to_g) and ld.get(sl) != r:
                    ld[sl] = r
                    g = self.groups[self.rank_to_g[r]]
                    g.ready_at = max(g.ready_at, rnd + g.resp)
                    g.hpleft = None
                    g.hpsum = g.hp_total
                    g.hp_ver += 1
                continue
            ld.pop(sl, None)
            if (st == S_READY or st == S_LEAD) and code < 62:
                r = code - 1
                if r in claims:
                    claims[r].append((sl, 2))
                else:
                    claims[r] = [(sl, 2)]
        self.claims = claims
        self.ball_n = n
        lx, ly = buf[6], buf[7]
        self.leader_xy = (lx, ly) if (lx < self.W and ly < self.H) else None
        self.elect()

    def gather_done(self):
        dt = self.rnd - self.gather_t0
        if dt >= GATHER_MAX:
            return True
        if dt < GATHER_MIN:
            return False
        for st, code in self.bmem.values():
            if st == S_GATHER:
                return False
        return True

    def elect(self):
        """The leader is the lowest slot that is out in the field once the push has started."""
        if SOLO:
            # every champion out in the field leads itself: independent farmers with the fight planner
            if self.bstate == S_READY or self.bstate == S_DONE:
                self.bstate = S_LEAD
                self.lead_written = None
            self.is_leader = self.bstate == S_LEAD
            self.leader_slot = self.slot if self.is_leader else -1
            self.marching = True
            if self.bstage == B_GATHER:
                self.bstage = B_MARCH
            return
        mem = self.bmem
        lead = -1
        for sl in sorted(mem):
            if mem[sl][0] == S_LEAD:
                lead = sl
                break
        if self.bstate == S_LEAD:
            if 0 <= lead < self.slot:
                self.bstate = S_READY             # a lower slot already leads
            else:
                lead = self.slot
        elif lead < 0 and self.bstate == S_READY and self.rnd >= self.r_gather + 2:
            cand = self.slot
            for sl, (st, code) in mem.items():
                if (st == S_READY or st == S_DONE) and sl < cand:
                    cand = sl
            if cand == self.slot and (self.marching or self.gather_done()):
                self.bstate = S_LEAD
                self.lead_written = None
                lead = self.slot
        self.leader_slot = lead
        self.is_leader = lead == self.slot
        if lead >= 0 and not self.marching:
            self.marching = True
            self.log(f"MARCH leader={lead}")
        if self.marching and self.bstage == B_GATHER:
            self.bstage = B_MARCH

    def update_state(self):
        """GATHER while we are on our way home, READY once we are out in the field again."""
        if self.bstate == S_GATHER:
            return
        if self.mode == 1:
            self.bstate = S_GATHER
            self.is_leader = False
            self.leader_slot = -1
            self.task = None
            self.cstate = 0
            self.cap_since = 0

    def ball_write(self, alive):
        b = self.ball_byte(alive)
        if b != self.my_byte:
            cambc.shared_memory[self.slot] = b
            self.my_byte = b
        if alive and self.is_leader:
            xy = (self.px, self.py)
            if xy != self.lead_written and 0 <= xy[0] < 256 and 0 <= xy[1] < 256:
                cambc.shared_memory.write(6, bytes(xy))
                self.lead_written = xy

    def ball_byte(self, alive):
        if not alive:
            return 0
        if self.bstate != S_GATHER and self.rnd <= self.done_b_until and 0 <= self.done_b_rank < 61:
            self.tag("sdone-bcast")
            return (S_DONE << 6) | (self.done_b_rank + 1)   # v20: tell everybody what we just captured
        st = self.bstate
        code = NOOBJ
        if st != S_GATHER:
            t = self.task
            if self.mode != 0 and not self.engaged:
                t = None                          # on a bank or home trip: not working on anything
            if t is not None and t.rank < 61:
                code = t.rank + 1
            elif st == S_READY and 0 <= self.done_rank < 61:
                st = S_DONE
                code = self.done_rank + 1
        return (st << 6) | code

    # ------------------------------------------------------------------ perception
    def scan_allies(self):
        out = []
        px, py = self.px, self.py
        try:
            for a in cambc.vision.champions(ALLY):
                ap = a.position()
                if ap.x == px and ap.y == py:
                    continue
                if not a.is_alive():
                    continue
                st = 0
                try:
                    st = int(a.state())
                except Error:
                    pass
                out.append((ap.x, ap.y, a.health(), a.max_health(), a.strength(), a.focus(),
                            int(a.champion_name()), a, ap, st))
        except Error:
            pass
        self.allies = out

    def leader_pos(self):
        if self.leader_slot < 0 or self.is_leader:
            return None
        lt = self.slot_types[self.leader_slot] if self.leader_slot < len(self.slot_types) else -1
        for a in self.allies:
            if a[6] == lt:
                self.last_leader_pos = (a[0], a[1], self.rnd)
                return (a[0], a[1])
        return None

    # ------------------------------------------------------------------ decisions
    def update_push(self):
        """How hard to push toward the enemy: all out when they are ahead in the gem race, economy first when we are."""
        try:
            ours = cambc.global_submitted_gems(ALLY)
            theirs = cambc.global_submitted_gems(ENEMY)
        except Exception:
            return
        f = 0.5 + (theirs - ours) / PUSH_SPAN
        self.push_f = 0.0 if f < 0.0 else (1.0 if f > 1.0 else f)

    def ball_decide(self):
        px, py = self.px, self.py
        on_spawn = (px, py) in self.spawn_xy
        self.update_push()
        self.check_group_done()
        self.update_state()
        self.maybe_lock()
        self.spawn_hold = self.want_spawn_hold()
        if self.enemies:
            act = self.skirmish()
            if act and not (act.startswith("hold") and self.committed()):
                return act
        else:
            self.engaged = False
        if self.inc > 0.0:
            act = self.maybe_retreat()
            if act:
                return act
        heal = self.try_heal()
        if on_spawn:
            self.buy_items()
            if self.hp < self.maxhp * 0.97 and not self.enemies:
                self.mode = 0
                return heal + "heal-at-spawn"
            if self.mode == 1:
                self.mode = 0
        elif self.field_shop and self.gold >= 30:
            self.buy_items()
        if self.spawn_hold:
            return heal + "spawn-hold"
        if self.bstate == S_GATHER and on_spawn and self.hp >= self.maxhp * 0.97:
            self.bstate = S_READY
            if SOLO:
                self.elect()                      # v20: lead ourselves this turn instead of a "wait-leader" turn
        if SOLO and self.bstate == S_GATHER and not on_spawn and self.mode != 1:
            self.mode = 1                         # v20: on the way home (a bank detour reset the mode): carry on home
        if self.bstage == B_GATHER:
            return heal + self.gather_turn()
        # wounded or rich: back home
        if self.mode == 1 or self.need_home_ball():
            self.mode = 1
            return heal + self.go_home()
        wb = self.ball_want_bank()
        if wb:
            if self.rnd >= self.bank_latch:
                self.bank_latch = self.rnd + BANK_LATCH
            act = self.do_bank()
            if act:
                return heal + act
        elif self.mode == 2:
            self.mode = 0
        if self.is_leader:
            return heal + self.leader_turn()
        return heal + self.follower_turn()

    def want_spawn_hold(self):
        """v17: on our spawn with enemies lurking and no fight we would win: wait there for company."""
        if (self.px, self.py) not in self.spawn_xy:
            self.hold_sp = 0
            return False
        near = [e for e in self.enemies if cheb(self.px, self.py, e[0], e[1]) <= SPAWN_HOLD_D]
        if not near:
            self.hold_sp = 0
            return False
        if self.hold_sp >= SPAWN_HOLD_MAX:
            return False
        d = self.df_altar.get(self.pos)
        if d < 65535 and self.endgame_bank(d):
            return False
        if self.fight_ratio(near) >= R_GO:
            return False
        self.hold_sp += 1
        return True

    def threat_near(self):
        """An enemy close enough to matter (enemies loitering on their own spawn do not count)."""
        px, py = self.px, self.py
        for e in self.enemies:
            d = cheb(px, py, e[0], e[1])
            if d <= 3 or (d <= 6 and not self.at_home(e)):
                return True
        return False

    def ball_want_bank(self):
        gems = self.gems
        if gems <= 0:
            return False
        d = self.df_altar.get(self.pos)
        if d >= 65535:
            return False
        if self.endgame_bank(d):
            return True
        if self.task is not None and self.camps and self.inc > 0.0:
            return False
        if self.threat_near() and not (d <= BANK_NEAR and gems >= BANK_NEAR_GEMS):
            return False
        submitted = cambc.global_submitted_gems(ALLY)
        if submitted + gems * max(1, self.ball_n) >= 1000 - 2:
            return True
        if self.committed():
            return False
        if d <= 2 and gems >= 10:
            return True
        if self.rnd < self.bank_latch:
            return True                       # we set out to bank: do not turn back at the threshold
        thr = self.bank_threshold(d) * BANK_MULT
        if self.bstage == B_MARCH:
            cap = MARCH_BANK_BASE + MARCH_BANK_PER * d
            if cap < thr:
                thr = cap
        return gems >= thr

    def need_home_ball(self):
        if self.hp < self.maxhp * HOME_HP:
            return True
        if self.gold >= GOLD_HOME and not self.field_shop and not self.enemies:
            if self.df_spawn.get(self.pos) <= 18:
                return True
            if self.gold >= GOLD_HOME_FAR and not self.committed():
                return True                       # far from home but rich and between jobs: go and spend it
        return False

    def gather_turn(self):
        px, py = self.px, self.py
        on_spawn = (px, py) in self.spawn_xy
        if self.task is not None:
            if self.cstate == 2 and self.rnd - self.gather_t0 < GATHER_FINISH:
                return self.work()
            self.task = None
            self.cstate = 0
            self.cap_since = 0
            self.done_rank = -1
        if on_spawn:
            self.mode = 0
            return "gather-wait"
        if self.gems >= GATHER_BANK_GEMS and self.hp >= self.maxhp * 0.5 and not self.enemies:
            if self.df_altar.get(self.pos) <= GATHER_BANK_DIST:
                act = self.do_bank()
                if act:
                    return act
        self.mode = 1
        return self.go_home()

    # ------------------------------------------------------------------ marching and working as a ball
    def leader_obj(self):
        """The camp group the leader is working on (None when it has none)."""
        if self.leader_slot < 0:
            return None
        if self.is_leader:
            return self.task
        ent = self.bmem.get(self.leader_slot)
        if ent is None:
            return None
        code = ent[1]
        if code >= 62 or ent[0] == S_DONE:
            return None
        r = code - 1
        if 0 <= r < len(self.rank_to_g):
            return self.groups[self.rank_to_g[r]]
        return None

    def leader_turn(self):
        on_spawn = (self.px, self.py) in self.spawn_xy
        if on_spawn and not SOLO:
            laggards = 0
            for st, code in self.bmem.values():
                if st == S_GATHER:
                    laggards += 1
            if laggards and self.lead_wait_n < LEAD_WAIT:
                self.lead_wait_n += 1
                self.task = None
                return "leader-wait"
        else:
            self.lead_wait_n = 0
        if self.should_hold():
            self.hold_n += 1
            self.hold_total += 1
            return "convoy-hold"
        self.hold_n = 0
        act = self.work()
        if self.task is None and act.startswith("no-task"):
            return self.leader_idle()
        return act

    def leader_idle(self):
        """Nothing to take right now: wait beside the group that comes back first."""
        rnd = self.rnd
        roots = Bitboard()
        roots.set(self.pos)
        self.df_me.compute(self.static_block, roots, self.scratch)
        best = None
        best_t = 1e9
        for g in self.groups:
            if g.d_enemy <= ESP_AVOID or g.block_until > rnd + 30 or g.threat_until > rnd:
                continue
            d = self.df_me.get(g.v0)
            if d >= 65535:
                continue
            t = max(g.ready_at - rnd, d) + 0.3 * d
            if t < best_t:
                best_t = t
                best = g
        if best is None:
            return "idle"
        if cheb(self.px, self.py, int(best.cx), int(best.cy)) <= 4:
            return "idle-near-group"
        goals = Bitboard()
        for v in best.vec:
            goals.draw_chebyshev(v, 3)
        goals &= ~self.dyn_block()
        if self.step_to(goals):
            return "idle-walk"
        return "idle"

    def committed(self):
        """Busy with a camp fight or a capture: do not walk away from it."""
        if self.task is not None and (self.cstate == 2 or self.cap_since > 0):
            return True
        if self.task is not None and self.camps and self.awake:
            for c in self.camps:
                if c[3] == self.task.i:
                    return True
        return False

    def follower_turn(self):
        px, py = self.px, self.py
        lg = self.leader_obj()
        lp = self.leader_pos()
        ll = lp
        if ll is None and self.leader_xy is not None and self.leader_slot >= 0 and self.leader_slot != self.slot:
            ll = self.leader_xy
        if lg is not None:
            if lg.i != self.anchor_gi:
                self.anchor_gi = lg.i
                self.arrived = False
            self.anchor = (int(lg.cx), int(lg.cy))
            self.anchor_d = lg.d_enemy
        anchor = self.anchor
        # the leader is on its way to an objective that is still far off: the ball travels together
        marching = lg is not None and ll is not None and cheb(ll[0], ll[1], int(lg.cx), int(lg.cy)) > SITE_R
        if lg is not None and not marching:
            self.arrived = True
        t = self.task
        if t is not None:
            if self.committed():
                return self.work()
            behind = self.anchor_d is not None and t.d_enemy >= self.anchor_d - 1
            if anchor is not None and not behind and cheb(int(t.cx), int(t.cy), anchor[0], anchor[1]) > R_LEASH \
                    and cheb(px, py, anchor[0], anchor[1]) > R_LEASH:
                self.task = None                  # the push has moved on: catch up
                self.cstate = 0
                self.cap_since = 0
            elif marching and not behind and self.cstate == 0 and cheb(px, py, ll[0], ll[1]) > R_AREA:
                self.task = None                  # not started yet and far behind the marching ball: join it
            else:
                return self.work()
        if anchor is not None and (ll is not None or lg is not None) and (not marching or self.arrived):
            act = self.work()                     # the ball is at work: take a group of our own nearby
            if self.task is not None or not act.startswith("no-task"):
                return act
        if ll is None:
            return "wait-leader"
        if cheb(px, py, ll[0], ll[1]) <= FOLLOW_R:
            return "with-leader"
        goals = Bitboard()
        try:
            goals.draw_chebyshev(Vec2(ll[0], ll[1]), FOLLOW_R)
        except Error:
            return "follow-bad"
        goals &= ~self.dyn_block()
        if self.step_to(goals):
            return "follow-leader"
        return "follow-fail"

    def should_hold(self):
        g = self.task
        if g is None or self.hold_n >= HOLD_MAX:
            return False
        if self.hold_obj != g.i:
            self.hold_obj = g.i
            self.hold_total = 0
        if self.hold_total >= HOLD_BUDGET:
            return False
        if cheb(self.px, self.py, int(g.cx), int(g.cy)) <= 10:
            return False
        if self.enemies:
            return False
        idle = 0
        for st, code in self.bmem.values():
            if st == S_READY and code >= 62:
                idle += 1                         # following us, no job of its own
        if idle <= 0:
            return False
        need = min(idle, CONVOY_NEED)
        cnt = 0
        for a in self.allies:
            if cheb(self.px, self.py, a[0], a[1]) <= CONVOY_R:
                cnt += 1
        return cnt < need

    def pick_task(self):
        if self.bstage == B_FARM:
            return self.choose_task()
        roots = Bitboard()
        roots.set(self.pos)
        self.df_me.compute(self.static_block, roots, self.scratch)
        if self.is_leader:
            return self.best_group(self.groups, True)
        lg = self.leader_obj()
        if lg is not None:
            ax, ay = int(lg.cx), int(lg.cy)
        elif self.anchor is not None:
            ax, ay = self.anchor
        else:
            return None
        area = [g for g in self.groups if cheb(int(g.cx), int(g.cy), ax, ay) <= R_AREA]
        if area:
            got = self.best_group(area, True)
            if got is not None:
                return got
        # nothing to do beside the ball: farm behind it, on the safe side of its position
        ad = self.anchor_d
        if ad is not None:
            rear = [g for g in self.groups if g.d_enemy >= ad - 1 and cheb(int(g.cx), int(g.cy), ax, ay) > R_AREA]
            if rear:
                return self.best_group(rear, True)
        return None

    def my_turn_to_capture(self, g, goals):
        """With fewer free spawn tiles than people, the poorest champions stand on them so the loot is shared out."""
        free = 0
        for _ in goals.positions():
            free += 1
        if free <= 0:
            return False
        my_key = (self.gems, self.slot)
        better = 0
        for a in self.allies:
            if cheb(self.px, self.py, a[0], a[1]) <= 7 and (a[0], a[1]) not in g.xyset:
                try:
                    gem = a[7].gem_count()
                except Error:
                    continue
                idx = self.slot_types.index(a[6]) if a[6] in self.slot_types else 9
                if (gem, idx) < my_key:
                    better += 1
        return better < free

    # ------------------------------------------------------------------ healing
    def try_heal(self):
        if not self.can_cast or not self.allies:
            return ""
        for ab, kind, info in self.abil:
            if kind != 5 or ab.cooldown() != 0:        # K_HEAL
                continue
            full = info.modifier * self.mfocus
            best = None
            best_v = 0.0
            for a in self.allies:
                if cheb(self.px, self.py, a[0], a[1]) > info.range:
                    continue
                missing = a[3] - a[2]
                amt = full if missing > full else missing
                frac = a[2] / a[3] if a[3] > 0 else 1.0
                if amt >= 0.5 * full or (frac < 0.5 and amt > 0.2 * full):
                    v = amt + (200.0 if frac < 0.4 else 0.0)
                    if v > best_v:
                        best_v = v
                        best = a
            if best is not None:
                try:
                    if ab.use(best[7]):
                        self.can_cast = False
                        return "heal "
                except Error:
                    pass
        return ""

    # ------------------------------------------------------------------ altar locks
    def maybe_lock(self):
        if not self.has_lock or self.lock_type is None:
            return
        px, py = self.px, self.py
        for k, (ax, ay) in enumerate(self.altar_xy):
            if cheb(px, py, ax, ay) > 2:
                continue
            v = self.altar_vecs[k]
            try:
                if cambc.vision.has_altar_lock(v):
                    continue
            except Error:
                continue
            want = False
            for e in self.enemies:
                if (e[10] & 4) and cheb(e[0], e[1], ax, ay) <= 1:
                    want = True                 # cancel a tribute in progress
                    break
            if not want and self.bstage != B_FARM and self.alt_lean[k] >= -2:
                want = True                     # deny the enemy's side of the map
            if want:
                try:
                    cons = self.me.consumables()[int(self.lock_type)]
                    if cons.use(v):
                        self.has_lock = False
                        self.log(f"LOCK altar {k}")
                        return
                except Error:
                    pass

    def buy_lock(self):
        """Buy one altar lock when at home (called from buy_items)."""
        if self.has_lock or self.lock_type is None or self.gold < 40:
            return
        try:
            self.me.buy(self.lock_type)
            self.has_lock = True
            self.gold -= 10
        except Error:
            pass

    # ------------------------------------------------------------------ skirmish
    def fight_ratio(self, near):
        px, py = self.px, self.py
        a_hp = self.hp + self.shield_value()
        a_dps = unit_dps(self.ctype, self.mstr, self.mfocus)
        if self.ctype == T.WILLOW:
            a_hp += 2.0 * self.mfocus
        for a in self.allies:
            if cheb(px, py, a[0], a[1]) <= SEE_R and self.ally_in_fight(a, near):
                a_hp += a[2]
                a_dps += unit_dps(a[6], a[4], a[5])
                if a[6] == T.WILLOW:
                    a_hp += 2.0 * a[5]
        e_hp = 0.0
        e_dps = 0.0
        for e in near:
            w = 3.0 if (e[0], e[1]) in self.espawn_xy else 1.0
            e_hp += e[2] * w
            e_dps += unit_dps(e[8], e[3], e[7])
        if e_hp < 1.0 or e_dps < 1.0:
            return 9.0
        return (a_hp * a_dps) / (e_hp * e_dps)

    def ally_in_fight(self, a, near):
        """An ally that can take part: beside us, or within striking distance of one of these enemies."""
        if a[9] & (2 | 4 | 4096):
            return False                          # recalling, tributing or teleporting
        if cheb(self.px, self.py, a[0], a[1]) <= 2:
            return True
        reach = (1 if a[6] in MELEE_TYPES else 4) + 2
        for e in near:
            if cheb(a[0], a[1], e[0], e[1]) <= reach:
                return True
        return False

    def observe_exchange(self, rel):
        """(turns until we die, turns until their weakest dies) from the damage actually seen lately."""
        rnd = self.rnd
        cont = self.xch_round == rnd - 1
        hp_now = {}
        dealt = 0.0
        for e in rel:
            key = e[4].__index__()
            hp_now[key] = e[2]
            before = self.xch_hp.get(key)
            if cont and before is not None and before > e[2]:
                dealt += before - e[2]
        taken = self.took_amt
        if cont:
            self.xch_t = XCH_A * taken + (1.0 - XCH_A) * self.xch_t
            self.xch_d = XCH_A * dealt + (1.0 - XCH_A) * self.xch_d
            self.xch_n += 1
        else:
            self.xch_t = taken
            self.xch_d = 0.0
            self.xch_n = 0
        self.xch_hp = hp_now
        self.xch_round = rnd
        if self.xch_n < XCH_MIN_TURNS or self.xch_t < 1.0:
            return None
        eff = self.hp + self.shield_value()
        weakest = min(e[2] for e in rel)
        return eff / self.xch_t, weakest / max(self.xch_d, 1.0)

    def can_finish(self, rel):
        dmg = self.mstr * 1.1
        if self.can_cast:
            for ab, kind, info in self.abil:
                if kind in (2, 3, 4) and info.modifier > 0 and ab.cooldown() == 0:
                    dmg += info.modifier * self.mfocus
                    break
        reach = self.arange if self.arange > 4 else 4
        for e in rel:
            if cheb(self.px, self.py, e[0], e[1]) <= reach and e[2] <= dmg:
                return True
        return False

    def skirmish(self):
        px, py = self.px, self.py
        self.replanned = False
        near = [e for e in self.enemies if cheb(px, py, e[0], e[1]) <= SEE_R]
        if not near:
            self.engaged = False
            self.hold_fights = 0
            return None
        # only enemies that can really get at us: within shooting distance, or a short walk away. Enemies hugging
        # their own spawn heal every turn there, so they are only a threat when they are in reach.
        roots = Bitboard()
        roots.set(self.pos)
        self.df_near.compute(self.static_block, roots, self.scratch, PATH_R)
        rel = []
        for e in near:
            d = cheb(px, py, e[0], e[1])
            if d <= 4:
                rel.append(e)
            elif self.df_near.get(e[5]) <= PATH_R and not self.at_home(e):
                rel.append(e)
        if not rel:
            self.engaged = False
            return None
        if self.skip_fight_until > self.rnd:
            if not any(cheb(px, py, e[0], e[1]) <= HIT_REACH.get(e[8], 5) + 1 for e in rel):
                return None                       # resting from a stand-off, unless someone can hit us
        if DEBUG_HOLD:
            eg = [(e[8], e[11]) for e in rel if len(e) > 11 and e[11] > 0]
            if eg:
                self.log(f"EGEM {eg}")
        ratio = self.fight_ratio(rel)
        need = R_STAY if self.engaged else R_GO
        if self.gems > 0:
            need *= 1.0 + self.gems / GEM_CAUTION
        if self.home_open:
            # v16 (4-champion maps): fight readily near home (healing, respawns)
            try:
                if self.df_spawn.get(self.pos) <= HOME_FIGHT_R:
                    need *= HOME_FIGHT_F
            except Error:
                pass
        go = ratio >= need
        xch = self.observe_exchange(rel)
        eff = self.hp + self.shield_value()
        bad = False
        if go and xch is not None and xch[0] < xch[1] * XCH_MARGIN:
            go = False                            # the real exchange says we lose this one
            bad = True
        if go and eff < BAIL_HP * self.maxhp and not self.can_finish(rel):
            go = False
            bad = True
        self.engaged = go
        self.last_ratio = ratio
        self.hard_retreat = bad or ratio < 0.5 or eff < self.maxhp * 0.4
        if self.committed():
            slack = 99
            near_me = 99
            for e in rel:
                d = cheb(px, py, e[0], e[1])
                s_ = d - (2 if e[6] <= 1 else e[6])
                if s_ < slack:
                    slack = s_
                if d < near_me:
                    near_me = d
            if (go and slack >= COMMIT_GO_SLACK and near_me > 4) or (not go and slack >= COMMIT_RUN_SLACK):
                return None                       # nobody can get at us yet: keep working the camp
        if not go:
            # v20: a fight we refuse. Mark the area, and unless someone can hit us next turn leave with a new job
            # instead of hovering at the edge of their reach.
            self.mark_threat(rel)
            hitters = [e for e in rel if cheb(px, py, e[0], e[1]) <= HIT_REACH.get(e[8], 5) + 1]
            if not hitters:
                self.skip_fight_until = self.rnd + STANDOFF_SKIP
                self.hold_fights = 0
                self.tag("standoff-break")
                return None
            # pressed beside an altar with a bag: tribute when our health covers the channel (damage does not stop it)
            if self.gems >= BANK_NEAR_GEMS:
                at_altar = False
                for (ax, ay) in self.altar_xy:
                    if cheb(px, py, ax, ay) <= cambc.constants.SUBMIT_GEMS_RANGE:
                        at_altar = True
                        break
                if at_altar:
                    t_ch = max(1, (self.gems + 9) // 10)
                    inc = self.inc
                    for e in hitters:
                        inc += unit_dps(e[8], e[3], e[7])
                    if eff > PRESS_BANK_MARGIN * t_ch * inc:
                        act = self.do_bank()
                        if act == "submit":
                            self.press_rnd = self.rnd
                            return "submit-press"
                    else:
                        self.tag("press-fail")
        if cambc.fuel_remaining() < 500000:
            return self.fallback_attack(rel)
        act = self.plan_fight(rel, not go)
        if act is None:
            return None
        if act.startswith("hold"):
            if DEBUG_HOLD:
                self.log(f"HOLD ratio={ratio:.2f} go={go} enemies={[(e[0], e[1], int(e[2]), e[8], e[6]) for e in rel]} allies={[(a[0], a[1], int(a[2]), a[6]) for a in self.allies]}")
            self.hold_fights += 1
            if self.hold_fights >= HOLD_FIGHT_MAX:
                self.skip_fight_until = self.rnd + 3        # nobody wants to move: carry on with the day's work
                self.hold_fights = 0
        else:
            self.hold_fights = 0
        return act

    def mark_threat(self, rel):
        """v20: enemies we will not fight mark the camp groups around them for THREAT_T rounds; our own task there is
        dropped unless we are already capturing it."""
        pts = [(e[0], e[1]) for e in rel if not self.at_home(e)]
        if not pts:
            return
        rnd = self.rnd
        until = rnd + THREAT_T
        for g in self.groups:
            gx, gy = int(g.cx), int(g.cy)
            for (ex, ey) in pts:
                if cheb(gx, gy, ex, ey) <= THREAT_R:
                    if g.threat_until < until:
                        g.threat_until = until
                    break
        t = self.task
        if t is not None and t.threat_until > rnd and self.cap_since == 0:
            self.task = None
            self.cstate = 0
            self.done_rank = -1
            self.tag("threat-drop")

    def at_home(self, e):
        if (e[0], e[1]) in self.espawn_xy:
            return True
        try:
            return self.df_enemy.get(e[5]) <= HOME_R
        except Error:
            return False

    def fallback_attack(self, near):
        if not self.can_attack:
            return None
        best = None
        for e in near:
            if cheb(self.px, self.py, e[0], e[1]) <= self.arange and (best is None or e[2] < best[2]):
                best = e
        if best is None:
            return None
        try:
            self.me.attack(best[4])
            self.can_attack = False
            if not self.melee:
                self.can_move = False
            return "hit-fallback"
        except Error:
            return None

    def plan_fight(self, near, retreat):
        """Pick this turn's move, spell and attack by scoring every combination worth considering."""
        me = self.me
        px, py = self.px, self.py
        arange = self.arange
        melee = self.melee
        f_me = self.mfocus
        s_me = self.mstr
        rnd = self.rnd
        allies = self.allies
        near = sorted(near, key=lambda e: cheb(px, py, e[0], e[1]))[:5]
        n_en = len(near)
        EX = [e[0] for e in near]
        EY = [e[1] for e in near]
        EHP = [e[2] for e in near]
        EDPS = []
        EREACH = []
        ERISK = []
        EWT = []
        EKV = []
        ESV = []
        ESHARE = []
        for e in near:
            dps = unit_dps(e[8], e[3], e[7])
            EDPS.append(dps)
            reach = 2 if e[6] <= 1 else e[6]
            EREACH.append(reach)
            ERISK.append(HIT_REACH.get(e[8], reach) if retreat else reach)    # v20: retreats keep out of spell reach
            frac = e[2] / e[9] if e[9] > 0 else 1.0
            w = T.TARGET_W.get(e[8], 1.0) * (1.0 + 1.0 * (1.0 - frac))
            if (e[0], e[1]) in self.espawn_xy:
                w *= 0.15
            EWT.append(w)
            eg = e[11] if len(e) > 11 else 0
            EKV.append(dps * KILL_TURNS + 60.0 + eg * GEM_K)
            st = e[10]
            ESV.append(dps * 1.2 + (70.0 if st & 4 else 0.0) + (30.0 if st & 2 else 0.0))
            n = 1
            for a in allies:
                if cheb(a[0], a[1], e[0], e[1]) <= reach + 1:
                    n += 1
            ESHARE.append(n)
        # ball centre
        cx = cy = None
        if allies:
            sx, sy, k = px, py, 1
            for a in allies:
                if cheb(px, py, a[0], a[1]) <= 10:
                    sx += a[0]
                    sy += a[1]
                    k += 1
            if k > 1:
                cx, cy = int(sx / k), int(sy / k)
        # the enemy we want to get to: weakest-looking, most valuable
        focus = -1
        fscore = -1e9
        for i in range(n_en):
            e = near[i]
            if cheb(px, py, e[0], e[1]) > arange + 1 and self.at_home(e):
                continue
            frac = e[2] / e[9] if e[9] > 0 else 1.0
            sc = EWT[i] * 30.0 + (1.0 - frac) * 40.0 - cheb(px, py, EX[i], EY[i]) * 0.5
            if len(e) > 11:
                sc += (e[11] if e[11] < 150 else 150) * GEM_F
            if e[2] <= s_me + 100.0:
                sc += 40.0
            if sc > fscore:
                fscore = sc
                focus = i
        camp_thr = []
        awk = self.camp_awake
        for c in self.camps:
            st = self.groups[c[3]].st[c[4]]
            if st > 0.0 and rnd - awk.get((c[0], c[1]), -99) <= 2:
                camp_thr.append((c[0], c[1], st * 0.7))
        hpf = (self.hp + self.shield_value()) / max(1.0, self.maxhp)
        lam = LAMBDA
        if retreat:
            lam = 1.6
        elif hpf < 0.6:
            lam = LAMBDA * (1.0 + (0.6 - hpf) * 6.0)
        if self.maxhp >= 1000.0 and not retreat:
            lam *= 0.8
        if self.pair:
            lam *= 1.5
        if not retreat and self.last_ratio > 1.5:
            lam *= 1.5 / self.last_ratio             # clearly stronger than them: the exchange rate favours us
        # ---- candidate end positions (position, kind: 0 stay / 1 walk / 2 dash)
        block = self.dyn_block()
        W, H = self.W, self.H
        cands = [(px, py, 0, None)]
        if self.can_move:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx or dy:
                        nx, ny = px + dx, py + dy
                        if 0 <= nx < W and 0 <= ny < H and not block.is_set(Vec2(nx, ny)):
                            cands.append((nx, ny, 1, None))
        dash = None
        if self.can_cast and (melee or retreat):
            for ab, kind, info in self.abil:
                if kind == 6 and ab.cooldown() == 0:
                    dash = ab
        shield_ab = None
        if not self.shield_value() > 0.0:
            for ab, kind, info in self.abil:
                if kind == 7 and ab.cooldown() == 0:
                    shield_ab = (ab, info)
        close_enemy = any(cheb(px, py, EX[i], EY[i]) <= 5 for i in range(n_en))
        alone = not any(self.ally_in_fight(a, near) for a in allies)
        df_enemy = self.df_enemy
        no_chase = alone and focus >= 0 and df_enemy.get(near[focus][5]) < DEEP_DE + 4
        hard = retreat and self.hard_retreat
        adv_w = ADV_W * (1.0 + 0.5 * self.hold_fights)
        df_spawn = self.df_spawn
        splash = self.splash
        best = [-1e18, None]
        flee_w = RET_W
        if retreat and self.gems >= BANK_RUN_ANY:
            d_alt = self.df_altar.get(self.pos)
            if d_alt < df_spawn.get(self.pos) and d_alt < min(self.df_altar.get(e[5]) for e in near):
                # v20: carrying a bag, the altar is nearer than home and them; go there only if we can also
                # survive the walk and the tribute under the current pressure
                inc_hit = self.inc
                for i in range(n_en):
                    if cheb(px, py, EX[i], EY[i]) <= ERISK[i] + 1:
                        inc_hit += EDPS[i]
                t_ch = max(1, (self.gems + 9) // 10)
                if self.hp + self.shield_value() > PRESS_BANK_MARGIN * (t_ch + d_alt) * inc_hit:
                    df_spawn = self.df_altar
                    self.tag("altar-run")
        if retreat and hard:
            inc_est = self.xch_t if self.xch_n >= 1 else 0.0
            if inc_est < 1.0:
                inc_est = sum(EDPS[i] for i in range(n_en) if cheb(px, py, EX[i], EY[i]) <= EREACH[i] + 1)
            surv = (self.hp + self.shield_value()) / (inc_est if inc_est > 1.0 else 1.0)
            if df_spawn.get(self.pos) <= surv * FLEE_SAFETY:
                flee_w = RET_W_FLEE            # we can make it home, where the spawn heals us: go
        regroup = retreat and not hard       # v20: everybody pressed (see skirmish) backs off with a destination
        regroup_w = REGROUP_W if alone else REGROUP_W_BALL

        def tile_free(nx, ny):
            return 0 <= nx < W and 0 <= ny < H and not block.is_set(Vec2(nx, ny))

        spawn_set = self.spawn_xy
        hold = self.spawn_hold

        def evaluate(x, y, moved, dab):
            dist = [cheb(x, y, EX[i], EY[i]) for i in range(n_en)]
            risk = 0.0
            for i in range(n_en):
                if dist[i] <= ERISK[i]:
                    risk += EDPS[i] / ESHARE[i]
            for (kx, ky, kd) in camp_thr:
                if cheb(x, y, kx, ky) <= 3:
                    risk += kd
            on_sp = (x, y) in spawn_set
            if on_sp:
                risk *= SPAWN_RISK_F          # v17: spawn tiles heal us to full every turn end, enemies can't step on
            pos_v = -lam * risk
            if hold and not on_sp:
                pos_v -= SPAWN_HOLD_W
            if cx is not None:
                dc = cheb(x, y, cx, cy) - 3
                if dc > 0:
                    pos_v -= CO_W * dc
            if retreat:
                if hard:
                    pos_v -= flee_w * df_spawn.get(Vec2(x, y))
                elif regroup:
                    pos_v -= regroup_w * df_spawn.get(Vec2(x, y))
            elif focus >= 0 and not no_chase:
                d = dist[focus] - arange
                if d > 0:
                    pos_v -= adv_w * d
            if alone:
                de = df_enemy.get(Vec2(x, y))
                if de < DEEP_DE:
                    pos_v -= DEEP_W * (DEEP_DE - de)
            atk_ok = self.can_attack and (melee or moved == 0)
            in_rng = [i for i in range(n_en) if dist[i] <= arange] if atk_ok else []
            opts = [(0.0, 0, None, None, None, None)]
            if dab is None and self.can_cast:
                for ab, kind, info in self.abil:
                    if ab.cooldown() != 0:
                        continue
                    if kind == 1:
                        if in_rng:
                            opts.append((0.0, 1, ab, info, None, None))
                    elif kind == 7:
                        if shield_ab is not None and close_enemy:
                            opts.append((self.shield_amt * 0.5, 7, ab, info, None, None))
                    elif kind == 5:
                        full = info.modifier * f_me
                        for a in allies:
                            if cheb(x, y, a[0], a[1]) <= info.range:
                                missing = a[3] - a[2]
                                amt = full if missing > full else missing
                                if amt > 0:
                                    frac = a[2] / a[3] if a[3] > 0 else 1.0
                                    opts.append((HEAL_W * amt + (120.0 if frac < 0.35 else 0.0), 5, ab, info, a, None))
                    elif kind == 2 or kind == 4:
                        if info.exclusive_with_movement and moved:
                            continue
                        dmg = info.modifier * f_me
                        rng = info.range
                        for i in range(n_en):
                            if dist[i] <= rng:
                                real = dmg if dmg < EHP[i] else EHP[i]
                                v = real * EWT[i]
                                if dmg > 0 and dmg >= EHP[i]:
                                    v += EKV[i]
                                if kind == 4:
                                    v += ESV[i]
                                opts.append((v, kind, ab, info, i, {i: dmg}))
                    elif kind == 3:
                        if info.exclusive_with_movement and moved:
                            continue
                        dmg = info.modifier * f_me
                        rng = info.range
                        rad = getattr(info, "radius", 1)
                        stun = getattr(info, "duration", 0) > 0
                        centres = set()
                        for i in range(n_en):
                            if dist[i] <= rng:
                                centres.add((EX[i], EY[i]))
                            for j in range(i + 1, n_en):
                                if cheb(EX[i], EY[i], EX[j], EY[j]) == 2:
                                    mx, my = (EX[i] + EX[j]) // 2, (EY[i] + EY[j]) // 2
                                    if cheb(x, y, mx, my) <= rng:
                                        centres.add((mx, my))
                        for (ccx, ccy) in centres:
                            hits = {}
                            val = 0.0
                            for i in range(n_en):
                                if cheb(ccx, ccy, EX[i], EY[i]) <= rad:
                                    real = dmg if dmg < EHP[i] else EHP[i]
                                    v = real * EWT[i]
                                    if dmg >= EHP[i]:
                                        v += EKV[i]
                                    if stun:
                                        v += ESV[i]
                                    hits[i] = dmg
                                    val += v
                            if hits:
                                opts.append((val, 3, ab, info, Vec2(ccx, ccy), hits))
            gain = 0.0
            for (cval, ckind, cab, cinfo, ctgt, cmap) in opts:
                hpl = list(EHP)
                if cmap:
                    for i, d in cmap.items():
                        hpl[i] -= d
                av = 0.0
                atk_i = -1
                for i in in_rng:
                    h = hpl[i]
                    if h <= 0.0:
                        continue
                    real = s_me if s_me < h else h
                    v = real * EWT[i]
                    if s_me >= h:
                        v += EKV[i]
                    if splash > 0.0:
                        for j in range(n_en):
                            if j != i and hpl[j] > 0.0 and cheb(EX[i], EY[i], EX[j], EY[j]) <= 1:
                                v += (splash if splash < hpl[j] else hpl[j]) * EWT[j]
                    if v > av:
                        av = v
                        atk_i = i
                total = cval + av + pos_v
                atk2 = -1
                if ckind == 1:
                    if atk_i < 0:
                        continue
                    best2 = 0.0
                    for i in in_rng:
                        hh = hpl[i] - (s_me if i == atk_i else 0.0)
                        if hh <= 0.0:
                            continue
                        real = s_me if s_me < hh else hh
                        v = real * EWT[i]
                        if s_me >= hh:
                            v += EKV[i]
                        if v > best2:
                            best2 = v
                            atk2 = i
                    total += best2
                if total - pos_v > gain:
                    gain = total - pos_v
                if total > best[0]:
                    best[0] = total
                    best[1] = (x, y, moved, dab, ckind, cab, cinfo, ctgt, atk_i, atk2)
            return gain

        got_attack = False
        for (x, y, moved, dab) in cands:
            if evaluate(x, y, moved, dab) > 0.0:
                got_attack = True
        # dashing in (or out): only tiles two steps away that let a melee champion strike, or that lead home
        if dash is not None and close_enemy and not (got_attack and not retreat):
            seen = set()
            if retreat:
                ring = []
                for dx in range(-2, 3):
                    for dy in range(-2, 3):
                        if max(abs(dx), abs(dy)) == 2:
                            ring.append((px + dx, py + dy))
                ring.sort(key=lambda t: df_spawn.get(Vec2(t[0], t[1])) if 0 <= t[0] < W and 0 <= t[1] < H else 65535)
                tiles = ring[:3]
            else:
                tiles = []
                for i in range(n_en):
                    for dx in (-1, 0, 1):
                        for dy in (-1, 0, 1):
                            tiles.append((EX[i] + dx, EY[i] + dy))
            for (nx, ny) in tiles:
                if (nx, ny) in seen:
                    continue
                seen.add((nx, ny))
                if cheb(px, py, nx, ny) != 2 or not tile_free(nx, ny):
                    continue
                mx, my = px + ((nx > px) - (nx < px)), py + ((ny > py) - (ny < py))
                if not tile_free(mx, my):
                    continue
                evaluate(nx, ny, 2, dash)
        if best[1] is None:
            return None
        return self.exec_plan(best[1], near, retreat)

    def exec_plan(self, plan, near, retreat):
        me = self.me
        x, y, moved, dab, ckind, cab, cinfo, ctgt, atk_i, atk2 = plan
        act = ""
        px, py = self.px, self.py
        failed_move = False
        if moved == 2 and dab is not None:
            try:
                if dab.use(Vec2(x, y)):
                    self.px, self.py = x, y
                    self.pos = Vec2(x, y)
                    self.can_cast = False
                    self.moved = True
                    if not self.melee:
                        self.can_attack = False
                    act += "dash "
                else:
                    failed_move = True
            except Error:
                failed_move = True
        elif moved == 1:
            try:
                if me.move(Vec2(x - px, y - py)):
                    self.px, self.py = x, y
                    self.pos = Vec2(x, y)
                    self.moved = True
                    self.can_move = False
                    if not self.melee:
                        self.can_attack = False
                    act += "step "
                else:
                    failed_move = True
            except Error:
                failed_move = True
        if failed_move:
            # an unseen unit sits on that tile: it is revealed now, so plan again around it
            if not self.replanned and cambc.fuel_remaining() > 1400000:
                self.replanned = True
                again = self.plan_fight(near, retreat)
                if again:
                    return again
            return act + (self.fallback_attack(near) or "move-failed")
        if ckind in (2, 3, 4):
            try:
                ok = cab.use(ctgt) if ckind == 3 else cab.use(near[ctgt][4])
                if ok:
                    self.can_cast = False
                    if cinfo.exclusive_with_movement:
                        self.can_move = False
                    act += "spell "
            except Error:
                pass
        elif ckind == 5:
            try:
                if cab.use(ctgt[7]):
                    self.can_cast = False
                    act += "heal "
            except Error:
                pass
        elif ckind == 7:
            try:
                if cab.use():
                    self.can_cast = False
                    self.shield_until = self.rnd + cinfo.duration
                    act += "shield "
            except Error:
                pass
        if atk_i >= 0 and self.can_attack:
            try:
                me.attack(near[atk_i][4])
                self.can_attack = False
                if not self.melee:
                    self.can_move = False
                act += "hit "
                self.last_attack_round = self.rnd
            except Error:
                pass
        if ckind == 1 and atk2 >= 0 and self.can_cast:
            try:
                if cab.use():
                    self.can_cast = False
                    me.attack(near[atk2][4])
                    act += "reset+hit "
            except Error:
                pass
        if not act:
            act = "hold "
        return act + ("retreat" if retreat else "fight")
