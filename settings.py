"""
Global configuration. All magic numbers live here.
Import the singleton instances at the bottom, not the classes.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DisplayConfig:
    width: int = 1280
    height: int = 720
    fps: int = 60
    title: str = "Working Title: Into the Dark"
    vsync: bool = True

    @property
    def size(self) -> tuple[int, int]:
        return self.width, self.height

    @property
    def center(self) -> tuple[int, int]:
        return self.width // 2, self.height // 2


@dataclass(frozen=True)
class PhaseConfig:
    """Day/night cycle timings in seconds."""

    day_duration: float = 20.0
    night_duration: float = 60.0
    transition_duration: float = 3.0  # fade between phases


@dataclass(frozen=True)
class LightConfig:
    # Darkness overlay
    darkness_color: tuple[int, int, int] = (5, 8, 20)
    darkness_alpha_day: int = 0
    darkness_alpha_night: int = 215

    # Player lantern defaults
    lantern_base_radius: float = 130.0
    lantern_fuel_drain_per_sec: float = 8.0  # fuel units / sec
    lantern_max_fuel: float = 100.0
    lantern_recharge_enabled: bool = True
    lantern_recharge_rate: float = 5.0

    # Campfire
    campfire_radius: float = 220.0
    campfire_max_hp: float = 100.0

    # How many extra rays per light (more = smoother shadows, slower)
    ray_epsilon: float = 0.0001

    # Threat multiplier per light source active at night
    # threat_per_light * active_lights = extra spawn weight
    threat_per_light: float = 0.4


@dataclass(frozen=True)
class PlayerConfig:
    speed: float = 180.0  # px / sec
    sprint_multiplier: float = 1.6
    hp: int = 3
    interact_radius: float = 60.0
    size: tuple[int, int] = (28, 28)


@dataclass(frozen=True)
class MonsterConfig:
    # Light sensitivity: distance at which a monster starts fleeing
    flee_light_radius: float = 140.0
    # How fast they close distance when hunting
    hunt_speed_base: float = 90.0
    # Multiplier applied each night
    night_difficulty_scale: float = 1.15
    # Base monsters spawned per night
    base_spawn_count: int = 3
    spawn_interval: float = 12.0  # seconds between spawn waves
    spawn_margin: float = 60.0  # px outside screen edge
    alert_timeout: float = 4.0
    light_damage_per_sec: float = 12.0
    campfire_damage_per_sec: float = 6.0


@dataclass(frozen=True)
class WorldConfig:
    tile_size: int = 64
    # Day map: play area in tiles
    day_map_width: int = 24
    day_map_height: int = 16
    # Night map: tighter, camp-centered
    night_map_width: int = 18
    night_map_height: int = 12
    # Loot container spawn odds per tile
    container_density: float = 0.06
    obstacle_density: float = 0.10
    grid_unit: int = 32


@dataclass(frozen=True)
class ResourceConfig:
    """Resource type names used as keys everywhere."""

    FUEL: str = "fuel"
    BATTERY: str = "battery"
    WOOD: str = "wood"
    METAL: str = "metal"
    CLOTH: str = "cloth"


@dataclass(frozen=True)
class CraftRecipes:
    """
    recipes[result] = {ingredient: count, ...}
    Keep it data-driven so the designer can tweak without touching logic.
    """

    recipes: dict[str, dict[str, int]] = field(
        default_factory=lambda: {
            "torch": {"wood": 2, "cloth": 1},
            "campfire": {"wood": 5},
            "barricade": {"wood": 3, "metal": 1},
            "lantern_upgrade": {"metal": 3, "battery": 2},
        }
    )


# ---------------------------------------------------------------------------
# Singletons — import these in the rest of the codebase
# ---------------------------------------------------------------------------
DISPLAY = DisplayConfig()
PHASE = PhaseConfig()
LIGHT = LightConfig()
PLAYER = PlayerConfig()
MONSTER = MonsterConfig()
WORLD = WorldConfig()
RESOURCES = ResourceConfig()
RECIPES = CraftRecipes()


@dataclass(frozen=True)
class AudioConfig:
    music_volume: float = 0.1  # 0.0 – 1.0
    sfx_volume: float = 0.2

    # Music tracks (relative to assets/music/)
    music_menu: str = "700639__xkeril__organic-background.wav"
    music_day: str = "727920__ehved__forest-theme-orchestral-loop.mp3"
    music_night: str = "667375__bloodpixelhero__retro-tense-loop2.wav"
    music_gameover: str = "700639__xkeril__organic-background.wav"

    # SFX (relative to assets/sounds/)
    sfx_crate_open: str = "321082__benjaminnelan__wooden-hover.wav"
    sfx_lantern_toggle: str = "840321__robo9418__wooden-short-click.wav"
    sfx_monster_die: tuple[str, ...] = (
        "398088__gamezger__quack.wav",
        "353250__zuzek06__slimejump.wav",
    )
    sfx_player_hurt: str = "658431__deathbyfairydust__pop.wav"

    # Night transition — one of three is picked at random each night
    sfx_night_transition: tuple[str, ...] = (
        "445719__lilmati__evil-presence-01.wav",
        "445718__lilmati__evil-presence-02.wav",
        "445717__lilmati__evil-presence-03.wav",
    )

    # Fade duration in milliseconds for music transitions
    music_fade_ms: int = 1500


AUDIO = AudioConfig()
