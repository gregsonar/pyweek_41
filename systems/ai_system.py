"""
Monster AI system.

Each monster runs a simple 4-state FSM:

    WANDER ──► ALERT ──► HUNT ──► FLEE
       ▲                           │
       └───────────────────────────┘

Transitions
-----------
WANDER → ALERT:  monster detects the player (line-of-sight within aggro_radius)
ALERT  → HUNT:   monster is outside any light source's radius  (dark = confident)
HUNT   → FLEE:   monster enters a light source's radius
FLEE   → WANDER: monster escapes far enough from all lights
"""
from __future__ import annotations

import logging
import math
import random
from enum import Enum, auto
from typing import TYPE_CHECKING

import pygame

from core.event_bus import EventBus, Events
from entities.monster import Monster, MonsterType
from settings import MONSTER, DISPLAY

if TYPE_CHECKING:
    from entities.player import Player
    from systems.light_system import LightSystem
    from world.world import World

log = logging.getLogger(__name__)


class AIState(Enum):
    WANDER = auto()
    ALERT  = auto()
    HUNT   = auto()
    FLEE   = auto()


class AISystem:
    """Owns all active monsters and updates their FSM each frame."""

    def __init__(self, bus: EventBus) -> None:
        self._bus = bus
        self.monsters: list[Monster] = []
        self._spawn_timer: float = 0.0
        self._night_number: int = 0
        self._wave_count: int = 0

    # ------------------------------------------------------------------
    def begin_night(self, world: World, night_number: int) -> None:
        self.monsters.clear()
        self._night_number = night_number
        self._spawn_timer = 0.0
        self._wave_count = 0
        log.debug("AISystem: night %d begins", night_number)

    # ------------------------------------------------------------------
    def update(
        self,
        dt: float,
        player: Player,
        world: World,
        light_system: LightSystem,
    ) -> None:
        self._spawn_timer -= dt
        if self._spawn_timer <= 0:
            self._spawn_wave(world)

        # Collect active light positions + radii for threat checks
        lights = self._extract_lights(player)

        dead: list[Monster] = []
        for monster in self.monsters:
            self._update_fsm(monster, dt, player, lights, world)
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
        lights: list[tuple[pygame.Vector2, float]],
        world: World,
    ) -> None:
        in_light, nearest_light_dist = self._check_light_exposure(m, lights)

        match m.state:
            case AIState.WANDER:
                self._do_wander(m, dt, world)
                dist_to_player = m.pos.distance_to(player.pos)
                if dist_to_player < m.aggro_radius:
                    m.state = AIState.ALERT
                    log.debug("Monster %s: WANDER → ALERT", id(m))

            case AIState.ALERT:
                # Pause briefly, assess situation
                m.alert_timer -= dt
                if in_light:
                    m.state = AIState.FLEE
                elif m.alert_timer <= 0:
                    m.state = AIState.HUNT

            case AIState.HUNT:
                if in_light:
                    m.state = AIState.FLEE
                    log.debug("Monster %s: HUNT → FLEE", id(m))
                else:
                    self._do_hunt(m, dt, player, world)

            case AIState.FLEE:
                self._do_flee(m, dt, lights, world)
                if not in_light and nearest_light_dist > MONSTER.flee_light_radius * 1.5:
                    m.state = AIState.WANDER
                    m.wander_target = None

    # ------------------------------------------------------------------
    # Behaviours
    # ------------------------------------------------------------------
    def _do_wander(self, m: Monster, dt: float, world: World) -> None:
        if m.wander_target is None or m.pos.distance_to(m.wander_target) < 8:
            # Pick new random target near current position
            cx, cy = DISPLAY.width // 2, DISPLAY.height // 2
            margin = MONSTER.spawn_margin
            m.wander_target = pygame.Vector2(
                random.uniform(margin, DISPLAY.width  - margin),
                random.uniform(margin, DISPLAY.height - margin),
            )

        direction = (m.wander_target - m.pos)
        if direction.length() > 0:
            m.pos += direction.normalize() * (m.speed * 0.4) * dt

    def _do_hunt(self, m: Monster, dt: float, player: Player, world: World) -> None:
        direction = player.pos - m.pos
        if direction.length() > 0:
            m.pos += direction.normalize() * m.speed * dt

        if m.pos.distance_to(player.pos) < 20:
            self._bus.publish(Events.PLAYER_DAMAGED, hp_remaining=player.hp - 1)
            player.take_damage(1)
            # Knock back slightly
            m.pos -= direction.normalize() * 30

    def _do_flee(
        self,
        m: Monster,
        dt: float,
        lights: list[tuple[pygame.Vector2, float]],
        world: World,
    ) -> None:
        if not lights:
            return
        # Flee from nearest light
        nearest_light_pos = min(lights, key=lambda l: m.pos.distance_to(l[0]))[0]
        direction = m.pos - nearest_light_pos
        if direction.length() > 0:
            m.pos += direction.normalize() * m.speed * 1.4 * dt

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
            m = Monster.create(MonsterType.BASIC, pos, self._night_number)
            self.monsters.append(m)

        self._bus.publish(Events.WAVE_SPAWNED, count=count)
        log.debug("Wave %d: spawned %d monsters", self._wave_count, count)

    @staticmethod
    def _random_offscreen_pos() -> pygame.Vector2:
        margin = MONSTER.spawn_margin
        side = random.randint(0, 3)
        w, h = DISPLAY.width, DISPLAY.height
        match side:
            case 0: return pygame.Vector2(random.uniform(0, w),   -margin)
            case 1: return pygame.Vector2(w + margin,              random.uniform(0, h))
            case 2: return pygame.Vector2(random.uniform(0, w),   h + margin)
            case _: return pygame.Vector2(-margin,                 random.uniform(0, h))

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_lights(player: Player) -> list[tuple[pygame.Vector2, float]]:
        sources: list[tuple[pygame.Vector2, float]] = []
        if player.lantern_on and player.lantern_fuel > 0:
            sources.append((player.pos, player.lantern_radius))
        return sources

    @staticmethod
    def _check_light_exposure(
        m: Monster,
        lights: list[tuple[pygame.Vector2, float]],
    ) -> tuple[bool, float]:
        """Returns (is_in_any_light, distance_to_nearest_light)."""
        if not lights:
            return False, math.inf

        min_dist = min(m.pos.distance_to(lp) for lp, _ in lights)
        for lp, lr in lights:
            if m.pos.distance_to(lp) < lr * MONSTER.flee_light_radius / lr:
                return True, min_dist
        return False, min_dist
