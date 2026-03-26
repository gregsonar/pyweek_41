"""
Player entity.

Handles input, movement, lantern fuel, inventory, and HP.
Does NOT contain rendering logic for the light cone — that's LightSystem.
"""

from __future__ import annotations

import pygame

from core.event_bus import EventBus, Events
from settings import DISPLAY, LIGHT, PLAYER


class Player:
    def __init__(self, pos: pygame.Vector2, bus: EventBus) -> None:
        self._bus = bus

        self.pos: pygame.Vector2 = pygame.Vector2(pos)
        self.rect = pygame.Rect(0, 0, *PLAYER.size)
        self.rect.center = (int(self.pos.x), int(self.pos.y))

        self.hp: int = PLAYER.hp
        self.speed: float = PLAYER.speed

        # Lantern
        self.lantern_on: bool = True
        self.lantern_fuel: float = LIGHT.lantern_max_fuel
        self.lantern_radius: float = LIGHT.lantern_base_radius

        # Inventory: resource_name → count
        self.inventory: dict[str, int] = {}

        # Input state
        self._move_vec: pygame.Vector2 = pygame.Vector2(0, 0)
        self._sprinting: bool = False

        # When True, all player input is ignored (e.g. during phase transitions)
        self.input_locked: bool = False

        # Interaction cooldown
        self._interact_cooldown: float = 0.0

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------
    def handle_keydown(self, key: int) -> None:
        if self.input_locked:
            return
        match key:
            case pygame.K_f:
                self.toggle_lantern()
            case pygame.K_e:
                self._interact_cooldown = 0.3
            case pygame.K_LSHIFT | pygame.K_RSHIFT:
                self._sprinting = True

        self._update_move_vec()

    def handle_keyup(self, key: int) -> None:
        if self.input_locked:
            return
        match key:
            case pygame.K_LSHIFT | pygame.K_RSHIFT:
                self._sprinting = False
        self._update_move_vec()

    def handle_mouse(self, button: int, pos: tuple[int, int]) -> None:
        pass

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------
    def update(self, dt: float, world, collision, *, is_night: bool) -> None:
        if not self.input_locked:
            self._update_move_vec()

            move = self._move_vec.copy()
            if move.length() > 0:
                move = move.normalize()
            speed = self.speed * (PLAYER.sprint_multiplier if self._sprinting else 1.0)

            velocity = move * speed * dt
            if velocity.length() > 0:
                new_rect, _ = collision.move(self.rect, velocity)
                self.rect = new_rect

        # --- Fix 7: clamp to screen bounds ---
        screen_rect = pygame.Rect(0, 0, DISPLAY.width, DISPLAY.height)
        self.rect.clamp_ip(screen_rect)
        self.pos.update(self.rect.center)

        # Lantern drain (only at night, only when on)
        if is_night and self.lantern_on and self.lantern_fuel > 0:
            self.lantern_fuel -= LIGHT.lantern_fuel_drain_per_sec * dt
            self.lantern_fuel = max(0.0, self.lantern_fuel)

            if self.lantern_fuel <= 10.0:
                self._bus.publish(Events.LANTERN_FUEL_LOW, fuel=self.lantern_fuel)
            if self.lantern_fuel == 0.0:
                self._bus.publish(Events.LANTERN_EMPTY)

        # --- Fix 2: lantern recharge when off ---
        if not self.lantern_on and LIGHT.lantern_recharge_enabled:
            if self.lantern_fuel < LIGHT.lantern_max_fuel:
                self.lantern_fuel = min(
                    LIGHT.lantern_max_fuel,
                    self.lantern_fuel + LIGHT.lantern_recharge_rate * dt,
                )

        # Interaction
        if self._interact_cooldown > 0:
            self._interact_cooldown -= dt
            if self._interact_cooldown <= 0:
                self._try_interact(world)

    # ------------------------------------------------------------------
    def draw(self, screen: pygame.Surface) -> None:
        color = (200, 180, 80) if self.lantern_on else (150, 140, 100)
        pygame.draw.rect(screen, color, self.rect)
        for i in range(self.hp):
            pygame.draw.circle(
                screen, (220, 60, 60), (self.rect.x + 6 + i * 10, self.rect.top - 8), 4
            )

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def toggle_lantern(self) -> None:
        self.lantern_on = not self.lantern_on

    def take_damage(self, amount: int) -> None:
        self.hp -= amount
        if self.hp <= 0:
            self._bus.publish(Events.PLAYER_DIED)

    def add_item(self, item: str, qty: int = 1) -> None:
        self.inventory[item] = self.inventory.get(item, 0) + qty
        self._bus.publish(Events.ITEM_PICKED_UP, item=item, qty=qty)

    def refuel_lantern(self, amount: float) -> None:
        self.lantern_fuel = min(LIGHT.lantern_max_fuel, self.lantern_fuel + amount)

    # ------------------------------------------------------------------
    def _try_interact(self, world) -> None:
        for obj in world.interactables:
            if self.pos.distance_to(obj.pos) <= PLAYER.interact_radius:
                obj.interact(self)
                break

    def _update_move_vec(self) -> None:
        keys = pygame.key.get_pressed()
        self._move_vec.update(
            (keys[pygame.K_d] or keys[pygame.K_RIGHT])
            - (keys[pygame.K_a] or keys[pygame.K_LEFT]),
            (keys[pygame.K_s] or keys[pygame.K_DOWN])
            - (keys[pygame.K_w] or keys[pygame.K_UP]),
        )
