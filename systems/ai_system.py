"""
Monster AI system.

Each monster runs a 4-state FSM:

    WANDER ──► ALERT ──► HUNT ──► FLEE ──► (despawn at map edge)
       ▲          │
       └──────────┘  (if player left aggro range before alert expires)

Transitions
-----------
WANDER → ALERT:  monster detects the player within aggro_radius
ALERT  → HUNT:   alert timer expires AND player still within aggro_radius * 1.5
ALERT  → WANDER: alert timer expires AND player left aggro_radius * 1.5  [Fix 1]
HUNT   → FLEE:   monster enters a light source's radius
FLEE   → (gone):  monster reaches the screen edge and is removed          [Fix 3]

Damage
------
- Lantern light deals HP damage to monsters inside its radius each frame. [Fix 4]
- SMASHER monsters hunt the campfire and deal structural damage to it.     [Fix 5]
"""

from __future__ import annotations

import logging
import random
from enum import Enum, auto
from typing import TYPE_CHECKING

import pygame

from core.event_bus import EventBus, Events
from entities.monster import Monster, MonsterType
from settings import DISPLAY, MONSTER

if TYPE_CHECKING:
    from entities.player import Player
    from systems.light_system import LightSystem
    from world.world import World

log = logging.getLogger(__name__)


class AIState(Enum):
    WANDER = auto()
    ALERT = auto()
    HUNT = auto()
    FLEE = auto()


# (world_pos, radius, is_lantern)
LightEntry = tuple[pygame.Vector2, float, bool]


class AISystem:
    def __init__(self, bus: EventBus) -> None:
        self._bus = bus
        self.monsters: list[Monster] = []
        self._spawn_timer: float = 0.0
        self._night_number: int = 0
        self._wave_count: int = 0

    def begin_night(self, world: World, night_number: int) -> None:
        self.monsters.clear()
        self._night_number = night_number
        self._spawn_timer = 0.0
        self._wave_count = 0

    # ------------------------------------------------------------------
    def update(
        self,
        dt: float,
        player: Player,
        world: World,
        light_system: LightSystem,
        lantern_sources: list[tuple[pygame.Vector2, float]],
    ) -> None:
        self._spawn_timer -= dt
        if self._spawn_timer <= 0:
            self._spawn_wave(world)

        lights: list[LightEntry] = [
            (pos, radius, True) for pos, radius in lantern_sources
        ]
        for ls in world.light_sources:
            if ls.active:
                lights.append((ls.pos, ls.radius, False))

        dead: list[Monster] = []
        for monster in self.monsters:
            self._update_fsm(monster, dt, player, lights, world)
            self._apply_lantern_damage(monster, dt, lantern_sources)
            if monster.hp <= 0:
                dead.append(monster)

        for m in dead:
            self.monsters.remove(m)
            self._bus.publish(Events.MONSTER_KILLED, monster_type=m.kind.name)

    # ------------------------------------------------------------------
    # FSM
    # ------------------------------------------------------------------
    def _update_fsm(
        self,
        m: Monster,
        dt: float,
        player: Player,
        lights: list[LightEntry],
        world: World,
    ) -> None:
        in_light = self._is_in_light(m, lights)
        dist_to_player = m.pos.distance_to(player.pos)

        match m.state:
            case AIState.WANDER:
                self._do_wander(m, dt)
                if dist_to_player < m.aggro_radius:
                    m.state = AIState.ALERT
                    m.alert_timer = MONSTER.alert_timeout

            case AIState.ALERT:
                m.alert_timer -= dt
                if in_light:
                    m.state = AIState.FLEE
                elif m.alert_timer <= 0:
                    # [Fix 1] Back to WANDER if player wandered off
                    if dist_to_player > m.aggro_radius * 1.5:
                        m.state = AIState.WANDER
                        m.wander_target = None
                    else:
                        m.state = AIState.HUNT

            case AIState.HUNT:
                if in_light:
                    m.state = AIState.FLEE
                elif m.targets_campfire:
                    self._do_hunt_campfire(m, dt, world)
                else:
                    self._do_hunt_player(m, dt, player)

            case AIState.FLEE:
                self._do_flee(m, dt)

    # ------------------------------------------------------------------
    # Behaviours
    # ------------------------------------------------------------------
    def _do_wander(self, m: Monster, dt: float) -> None:
        if m.wander_target is None or m.pos.distance_to(m.wander_target) < 8:
            margin = MONSTER.spawn_margin
            m.wander_target = pygame.Vector2(
                random.uniform(margin, DISPLAY.width - margin),
                random.uniform(margin, DISPLAY.height - margin),
            )
        direction = m.wander_target - m.pos
        if direction.length() > 0:
            m.pos += direction.normalize() * (m.speed * 0.4) * dt

    def _do_hunt_player(self, m: Monster, dt: float, player: Player) -> None:
        direction = player.pos - m.pos
        if direction.length() > 0:
            m.pos += direction.normalize() * m.speed * dt
        if m.pos.distance_to(player.pos) < 20:
            player.take_damage(1)
            if direction.length() > 0:
                m.pos -= direction.normalize() * 30

    def _do_hunt_campfire(self, m: Monster, dt: float, world: World) -> None:
        """[Fix 5] SMASHER hunts and damages the campfire."""
        campfire = world.campfire
        if campfire is None or not campfire.active:
            m.state = AIState.WANDER
            m.wander_target = None
            return
        direction = campfire.pos - m.pos
        dist = direction.length()
        if dist < 25:
            campfire.take_damage(MONSTER.campfire_damage_per_sec * dt)
        elif dist > 0:
            m.pos += direction.normalize() * m.speed * dt

    def _do_flee(self, m: Monster, dt: float) -> None:
        """[Fix 3] Run to nearest screen edge, despawn when off-screen."""
        w, h = DISPLAY.width, DISPLAY.height
        cx, cy = m.pos.x, m.pos.y

        edges = [
            (cy, pygame.Vector2(cx, -MONSTER.spawn_margin)),
            (h - cy, pygame.Vector2(cx, h + MONSTER.spawn_margin)),
            (cx, pygame.Vector2(-MONSTER.spawn_margin, cy)),
            (w - cx, pygame.Vector2(w + MONSTER.spawn_margin, cy)),
        ]
        _, target = min(edges, key=lambda e: e[0])

        direction = target - m.pos
        if direction.length() > 0:
            m.pos += direction.normalize() * m.speed * 1.6 * dt

        margin2 = MONSTER.spawn_margin * 2
        if (
            m.pos.x < -margin2
            or m.pos.x > w + margin2
            or m.pos.y < -margin2
            or m.pos.y > h + margin2
        ):
            m.hp = 0

    # ------------------------------------------------------------------
    # Lantern damage                                                    [Fix 4]
    # ------------------------------------------------------------------
    @staticmethod
    def _apply_lantern_damage(
        m: Monster,
        dt: float,
        lantern_sources: list[tuple[pygame.Vector2, float]],
    ) -> None:
        for lp, lr in lantern_sources:
            if m.pos.distance_to(lp) < lr:
                m.hp -= MONSTER.light_damage_per_sec * dt
                break

    # ------------------------------------------------------------------
    # Light exposure check                                              [Fix 6]
    # ------------------------------------------------------------------
    @staticmethod
    def _is_in_light(m: Monster, lights: list[LightEntry]) -> bool:
        """
        Fixed: previously lr * MONSTER.flee_light_radius / lr always equalled
        MONSTER.flee_light_radius, ignoring the actual source radius entirely.
        Now we use min(lr, flee_light_radius) as the effective threshold.
        """
        for lp, lr, _ in lights:
            effective = min(lr, MONSTER.flee_light_radius)
            if m.pos.distance_to(lp) < effective:
                return True
        return False

    # ------------------------------------------------------------------
    # Spawn
    # ------------------------------------------------------------------
    def _spawn_wave(self, world: World) -> None:
        self._spawn_timer = MONSTER.spawn_interval
        self._wave_count += 1
        difficulty = MONSTER.night_difficulty_scale ** (self._night_number - 1)
        count = int(MONSTER.base_spawn_count * difficulty) + (self._wave_count // 2)

        for _ in range(count):
            pos = self._random_offscreen_pos()
            kind = self._pick_type()
            m = Monster.create(kind, pos, self._night_number)
            self.monsters.append(m)

        self._bus.publish(Events.WAVE_SPAWNED, count=count)
        log.debug(
            "Wave %d: spawned %d monsters (night %d)",
            self._wave_count,
            count,
            self._night_number,
        )

    def _pick_type(self) -> MonsterType:
        pool: list[MonsterType] = [MonsterType.BASIC] * 3
        if self._night_number >= 3:
            pool.append(MonsterType.STALKER)
        if self._night_number >= 5:
            pool.append(MonsterType.SMASHER)
        return random.choice(pool)

    @staticmethod
    def _random_offscreen_pos() -> pygame.Vector2:
        margin = MONSTER.spawn_margin
        w, h = DISPLAY.width, DISPLAY.height
        side = random.randint(0, 3)
        match side:
            case 0:
                return pygame.Vector2(random.uniform(0, w), -margin)
            case 1:
                return pygame.Vector2(w + margin, random.uniform(0, h))
            case 2:
                return pygame.Vector2(random.uniform(0, w), h + margin)
            case _:
                return pygame.Vector2(-margin, random.uniform(0, h))
