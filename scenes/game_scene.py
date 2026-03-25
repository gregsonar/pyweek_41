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

from core.event_bus   import Events
from scenes.base_scene import BaseScene
from settings          import DISPLAY, LIGHT, PHASE
from systems.light_system import LightSystem
from systems.ai_system    import AISystem
from systems.collision    import CollisionSystem
from systems.craft_system import CraftSystem
from world.world          import World
from world.generator      import generate_day_map, generate_night_map
from entities.player      import Player
from ui.hud               import HUD

log = logging.getLogger(__name__)


class Phase(Enum):
    DAY                = auto()
    TRANSITION_TO_NIGHT = auto()
    NIGHT              = auto()
    TRANSITION_TO_DAY  = auto()


class GameScene(BaseScene):
    def on_enter(self) -> None:
        self._init_game()

    def on_exit(self) -> None:
        self._cleanup()

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------
    def _init_game(self) -> None:
        self.night_number: int = 0
        self.phase: Phase = Phase.DAY
        self.phase_timer: float = 0.0
        self.transition_alpha: int = 0        # 0..255 fade overlay

        # Shared subsystems
        self._light     = LightSystem(DISPLAY.size)
        self._ai        = AISystem(self.game.bus)
        self._collision = CollisionSystem()
        self._craft     = CraftSystem(self.game.bus)

        # HUD
        self._hud = HUD(self.game.assets)

        # Subscribe to game events
        bus = self.game.bus
        bus.subscribe(Events.PLAYER_DIED,   self._on_player_died)
        bus.subscribe(Events.ITEM_CRAFTED,  self._on_item_crafted)

        self._start_day()

    def _start_day(self) -> None:
        self.night_number += 1
        self.phase = Phase.DAY
        self.phase_timer = PHASE.day_duration

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

        # Rebuild map around the campfire
        self.world = generate_night_map(self.night_number, self.player.inventory)
        self._collision.load_world(self.world)
        self._ai.begin_night(self.world, self.night_number)
        self.game.bus.publish(Events.PHASE_NIGHT_START)
        log.debug("Night %d started", self.night_number)

    # ------------------------------------------------------------------
    # Frame loop
    # ------------------------------------------------------------------
    def handle_event(self, event: pygame.Event) -> None:
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
        if self.phase in (Phase.NIGHT, Phase.TRANSITION_TO_NIGHT, Phase.TRANSITION_TO_DAY):
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
            self.game.bus.publish(Events.PHASE_TRANSITION, to_phase="night")

    def _update_night(self, dt: float) -> None:
        self.player.update(dt, self.world, self._collision, is_night=True)
        self._ai.update(dt, self.player, self.world, self._light)

        if self.phase_timer <= 0:
            self.phase = Phase.TRANSITION_TO_DAY
            self.phase_timer = PHASE.transition_duration
            self.game.bus.publish(Events.PHASE_TRANSITION, to_phase="day")

    def _update_transition(self, dt: float, *, going_to_night: bool) -> None:
        progress = 1.0 - (self.phase_timer / PHASE.transition_duration)
        if going_to_night:
            self.transition_alpha = int(255 * progress)
        else:
            self.transition_alpha = int(255 * (1.0 - progress))

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
        """
        Returns list of (world_pos, radius, intensity 0..1).
        Intensity feeds both the visual brightness and the threat multiplier.
        """
        sources: list[tuple[pygame.Vector2, float, float]] = []

        # Player lantern
        if self.player.lantern_on and self.player.lantern_fuel > 0:
            sources.append((self.player.pos, self.player.lantern_radius, 1.0))

        # Static light sources from world (campfire, torches, …)
        for light in self.world.light_sources:
            if light.active:
                sources.append((light.pos, light.radius, light.intensity))

        return sources

    def _on_player_died(self) -> None:
        scene = self.manager._scenes.get("gameover")
        if scene is not None:
            scene.nights_survived = self.night_number - 1  # type: ignore[attr-defined]
        self.manager.switch("gameover")

    def _on_item_crafted(self, result: str) -> None:
        log.info("Crafted: %s", result)

    def _cleanup(self) -> None:
        bus = self.game.bus
        bus.unsubscribe(Events.PLAYER_DIED,  self._on_player_died)
        bus.unsubscribe(Events.ITEM_CRAFTED, self._on_item_crafted)
        bus.clear(Events.WAVE_SPAWNED)
