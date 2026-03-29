"""
Main gameplay scene.

State machine:
    DAY  ──► TRANSITION_TO_NIGHT ──► NIGHT ──► TRANSITION_TO_DAY ──► DAY …

During DAY:   player explores, loots containers, builds structures.
During NIGHT: campfire burns, monsters spawn, survival loop runs.
"""

from __future__ import annotations

import logging
from enum import Enum, auto

import pygame

from core.event_bus import Events
from entities.player import Player
from scenes.base_scene import BaseScene
from settings import DISPLAY, LIGHT, PHASE
from systems.ai_system import AISystem
from systems.collision import CollisionSystem
from systems.craft_system import CraftSystem
from systems.light_system import LightSystem
from ui.hud import HUD
from world.generator import generate_day_map, generate_night_map
from world.world import World

log = logging.getLogger(__name__)


class Phase(Enum):
    DAY = auto()
    TRANSITION_TO_NIGHT = auto()
    NIGHT = auto()
    TRANSITION_TO_DAY = auto()


class GameScene(BaseScene):
    def on_enter(self) -> None:
        self._init_game()

    def on_exit(self) -> None:
        self._cleanup()

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------
    def _init_game(self) -> None:
        from core.sprite_renderer import SpriteRegistry

        SpriteRegistry.init()

        self.night_number: int = 0
        self.phase: Phase = Phase.DAY
        self.phase_timer: float = 0.0
        self.transition_alpha: int = 0
        self._input_locked: bool = False

        # Lantern flicker state — active when fuel < FLICKER_THRESHOLD
        self._flicker_mult: float = 1.0  # current radius multiplier (0..1)
        self._flicker_timer: float = 0.0  # countdown to next flicker event

        self._light = LightSystem(DISPLAY.size)
        self._ai = AISystem(self.game.bus)
        self._collision = CollisionSystem()
        self._craft = CraftSystem(self.game.bus)
        self._hud = HUD(self.game.assets)

        bus = self.game.bus
        bus.subscribe(Events.PLAYER_DIED, self._on_player_died)
        bus.subscribe(Events.ITEM_CRAFTED, self._on_item_crafted)

        self._start_day()

    def _start_day(self) -> None:
        self.night_number += 1
        self.phase = Phase.DAY
        self.phase_timer = PHASE.day_duration
        self._input_locked = False

        self._ai.begin_day()  # clear all monsters before generating new map

        self.world = generate_day_map(self.night_number)
        self.player = Player(
            pos=pygame.Vector2(DISPLAY.width // 2, DISPLAY.height // 2),
            bus=self.game.bus,
        )
        self._collision.load_world(self.world)
        log.debug("Day %d started", self.night_number)

    def _start_night(self) -> None:
        self.phase = Phase.NIGHT
        self.phase_timer = PHASE.night_duration

        self.world = generate_night_map(self.night_number, self.player.inventory)
        self._collision.load_world(self.world)
        self._ai.begin_night(self.world, self.night_number)

        # [Fix 8] Move player to a safe position beside the campfire
        safe_pos = pygame.Vector2(DISPLAY.width // 2, DISPLAY.height // 2 + 90)
        self.player.pos.update(safe_pos)
        self.player.rect.center = (int(safe_pos.x), int(safe_pos.y))
        self.player.input_locked = False
        self._input_locked = False

        self.game.bus.publish(Events.PHASE_NIGHT_START)
        log.debug("Night %d started", self.night_number)

    # ------------------------------------------------------------------
    # Frame loop
    # ------------------------------------------------------------------
    def handle_event(self, event: pygame.Event) -> None:
        if self._input_locked:
            return
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.manager.switch("menu")
            else:
                self.player.handle_keydown(event.key)
        elif event.type == pygame.KEYUP:
            self.player.handle_keyup(event.key)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            self.player.handle_mouse(event.button, pygame.mouse.get_pos())

    def update(self, dt: float) -> None:
        self.phase_timer -= dt

        match self.phase:
            case Phase.DAY:
                self._update_day(dt)
            case Phase.TRANSITION_TO_NIGHT:
                self._update_transition(dt, going_to_night=True)
            case Phase.NIGHT:
                self._update_night(dt)
            case Phase.TRANSITION_TO_DAY:
                self._update_transition(dt, going_to_night=False)

    def draw(self, screen: pygame.Surface) -> None:
        # 1. World (terrain, obstacles, containers)
        self.world.draw(screen)

        # 2. Entities
        self.player.draw(screen)
        for monster in self._ai.monsters:
            monster.draw(screen)

        # 3. Light/shadow overlay (drawn on top of everything)
        if self.phase in (
            Phase.NIGHT,
            Phase.TRANSITION_TO_NIGHT,
            Phase.TRANSITION_TO_DAY,
        ):
            light_sources = self._collect_light_sources()
            self._light.draw(screen, self.world.obstacle_segments(), light_sources)

        # 4. Transition fade
        if self.transition_alpha > 0:
            fade = pygame.Surface(DISPLAY.size, pygame.SRCALPHA)
            fade.fill((5, 8, 20, self.transition_alpha))
            screen.blit(fade, (0, 0))

        # 5. HUD (always on top)
        self._hud.draw(
            screen,
            phase=self.phase.name,
            time_left=max(0.0, self.phase_timer),
            night=self.night_number,
            player=self.player,
        )

    # ------------------------------------------------------------------
    # Phase update helpers
    # ------------------------------------------------------------------
    def _update_day(self, dt: float) -> None:
        self.player.update(dt, self.world, self._collision, is_night=False)

        if self.phase_timer <= 0:
            self.phase = Phase.TRANSITION_TO_NIGHT
            self.phase_timer = PHASE.transition_duration
            self._input_locked = True
            self.player.input_locked = True
            self.game.bus.publish(Events.PHASE_TRANSITION, to_phase="night")

    def _update_night(self, dt: float) -> None:
        self.world.update(dt)  # [Fix 6] drain campfire fuel, etc.
        self.player.update(dt, self.world, self._collision, is_night=True)
        self._update_lantern_flicker(dt)

        lantern_sources = self._collect_lantern_sources()
        self._ai.update(dt, self.player, self.world, self._light, lantern_sources)

        if self.phase_timer <= 0:
            self.phase = Phase.TRANSITION_TO_DAY
            self.phase_timer = PHASE.transition_duration
            self._input_locked = True
            self.player.input_locked = True
            self.game.bus.publish(Events.PHASE_TRANSITION, to_phase="day")

    _FLICKER_THRESHOLD = 0.30  # fuel fraction below which flicker activates
    _FLICKER_INTERVAL = 0.08  # seconds between flicker state changes
    _FLICKER_DIM = 0.25  # minimum radius fraction during a dim flash

    def _update_lantern_flicker(self, dt: float) -> None:
        """
        When lantern fuel is below the threshold, randomly toggle between
        full brightness and a dimmed state at irregular intervals.

        Two parameters scale with desperation as fuel drops:
          - interval shortens (flicker becomes more frequent)
          - probability of dimming increases
        """
        import random

        fuel_frac = self.player.lantern_fuel / LIGHT.lantern_max_fuel

        if fuel_frac >= self._FLICKER_THRESHOLD or not self.player.lantern_on:
            self._flicker_mult = 1.0
            self._flicker_timer = 0.0
            return

        self._flicker_timer -= dt
        if self._flicker_timer <= 0:
            urgency = 1.0 - (fuel_frac / self._FLICKER_THRESHOLD)  # 0 → 1 as fuel drops
            base = self._FLICKER_INTERVAL * (1.0 - urgency * 0.6)
            self._flicker_timer = base + random.uniform(0.0, base)

            if random.random() < 0.45 + urgency * 0.35:
                self._flicker_mult = random.uniform(self._FLICKER_DIM, 0.70)
            else:
                self._flicker_mult = 1.0

    def _update_transition(self, dt: float, *, going_to_night: bool) -> None:
        progress = 1.0 - (self.phase_timer / PHASE.transition_duration)
        self.transition_alpha = (
            int(255 * progress) if going_to_night else int(255 * (1.0 - progress))
        )
        if self.phase_timer <= 0:
            self.transition_alpha = 0
            if going_to_night:
                self._start_night()
            else:
                self._start_day()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _collect_light_sources(self) -> list[tuple[pygame.Vector2, float, float]]:
        """All light sources for the shadow renderer: (pos, radius, intensity)."""
        sources: list[tuple[pygame.Vector2, float, float]] = []
        if self.player.lantern_on and self.player.lantern_fuel > 0:
            sources.append(
                (self.player.pos, self.player.lantern_radius, self._flicker_mult)
            )
        for light in self.world.light_sources:
            if light.active:
                sources.append((light.pos, light.radius, light.intensity))
        return sources

    def _collect_lantern_sources(self) -> list[tuple[pygame.Vector2, float]]:
        """Only the player's lantern — used for monster HP damage (not campfire)."""
        if self.player.lantern_on and self.player.lantern_fuel > 0:
            return [(self.player.pos, self.player.lantern_radius)]
        return []

    def _on_player_died(self) -> None:
        scene = self.manager._scenes.get("gameover")
        if scene is not None:
            scene.nights_survived = self.night_number - 1  # type: ignore[attr-defined]
        self.manager.switch("gameover")

    def _on_item_crafted(self, result: str) -> None:
        log.info("Crafted: %s", result)

    def _cleanup(self) -> None:
        bus = self.game.bus
        bus.unsubscribe(Events.PLAYER_DIED, self._on_player_died)
        bus.unsubscribe(Events.ITEM_CRAFTED, self._on_item_crafted)
        bus.clear(Events.WAVE_SPAWNED)
