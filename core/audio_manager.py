"""
AudioManager — centralised music and SFX controller.

Design
------
- Music runs through ``pygame.mixer.music`` (single streaming channel).
  Transitions use fade-out / fade-in so cuts are never jarring.
- SFX are ``pygame.mixer.Sound`` objects cached on first use.
- The manager subscribes to the EventBus and handles sounds itself —
  scenes never call play_sfx() directly for game events.
- Mute state affects both music and SFX simultaneously. State persists
  across scene switches because the manager lives on ``game.audio``.

File locations
--------------
  assets/music/   — background tracks
  assets/sounds/  — one-shot effects
"""

from __future__ import annotations

import logging
import random
from pathlib import Path

import pygame

from core.event_bus import EventBus, Events
from settings import AUDIO

log = logging.getLogger(__name__)

_MUSIC_DIR = Path(__file__).resolve().parent.parent / "assets" / "music"
_SOUNDS_DIR = Path(__file__).resolve().parent.parent / "assets" / "sounds"


class AudioManager:
    def __init__(self, bus: EventBus) -> None:
        self._bus = bus
        self._muted: bool = False
        self._current: str = ""  # track name currently loaded
        self._sfx: dict[str, pygame.mixer.Sound | None] = {}

        pygame.mixer.music.set_volume(AUDIO.music_volume)

        self._subscribe()

    # ------------------------------------------------------------------
    # Music
    # ------------------------------------------------------------------
    def play_music(self, track_filename: str) -> None:
        """
        Load and loop a music track.  If the track is already playing,
        do nothing.  Uses fade-out/fade-in for smooth transitions.

        Parameters
        ----------
        track_filename:
            Filename relative to ``assets/music/``, e.g. ``"night.wav"``.
        """
        if track_filename == self._current:
            return

        path = _MUSIC_DIR / track_filename
        if not path.exists():
            log.warning("AudioManager: music file not found — %s", path)
            return

        if pygame.mixer.music.get_busy():
            pygame.mixer.music.fadeout(AUDIO.music_fade_ms)

        try:
            pygame.mixer.music.load(str(path))
            if not self._muted:
                pygame.mixer.music.set_volume(AUDIO.music_volume)
                pygame.mixer.music.play(-1, fade_ms=AUDIO.music_fade_ms)
            self._current = track_filename
        except pygame.error as exc:
            log.warning("AudioManager: could not play music %s — %s", path, exc)

    def stop_music(self) -> None:
        pygame.mixer.music.fadeout(AUDIO.music_fade_ms)
        self._current = ""

    # ------------------------------------------------------------------
    # SFX
    # ------------------------------------------------------------------
    def play_sfx(self, sfx_filename: str) -> None:
        """Play a one-shot sound effect."""
        if self._muted:
            return
        snd = self._load_sfx(sfx_filename)
        if snd is not None:
            snd.play()

    def play_random_sfx(self, filenames: tuple[str, ...]) -> None:
        """Pick one filename at random and play it."""
        if filenames:
            self.play_sfx(random.choice(filenames))

    def _load_sfx(self, filename: str) -> pygame.mixer.Sound | None:
        if filename not in self._sfx:
            path = _SOUNDS_DIR / filename
            try:
                snd = pygame.mixer.Sound(str(path))
                snd.set_volume(AUDIO.sfx_volume)
                self._sfx[filename] = snd
            except (FileNotFoundError, pygame.error):
                log.warning("AudioManager: SFX not found — %s", path)
                self._sfx[filename] = None
        return self._sfx[filename]

    # ------------------------------------------------------------------
    # Mute
    # ------------------------------------------------------------------
    def toggle_mute(self) -> None:
        self._muted = not self._muted
        if self._muted:
            pygame.mixer.music.set_volume(0.0)
        else:
            pygame.mixer.music.set_volume(AUDIO.music_volume)
            # Resume music if a track was loaded but silenced
            if self._current and not pygame.mixer.music.get_busy():
                pygame.mixer.music.play(-1, fade_ms=AUDIO.music_fade_ms)

    @property
    def muted(self) -> bool:
        return self._muted

    # ------------------------------------------------------------------
    # Event subscriptions
    # ------------------------------------------------------------------
    def _subscribe(self) -> None:
        bus = self._bus
        bus.subscribe(Events.ITEM_PICKED_UP, self._on_crate_open)
        bus.subscribe(Events.LANTERN_EMPTY, self._on_lantern_toggle)
        bus.subscribe(Events.PHASE_TRANSITION, self._on_phase_transition)
        bus.subscribe(Events.MONSTER_KILLED, self._on_monster_killed)
        bus.subscribe(Events.PLAYER_DAMAGED, self._on_player_damaged)
        bus.subscribe(Events.GAME_OVER, self._on_game_over)

    # -- handlers -------------------------------------------------------
    def _on_crate_open(self, **_) -> None:
        self.play_sfx(AUDIO.sfx_crate_open)

    def _on_lantern_toggle(self, **_) -> None:
        self.play_sfx(AUDIO.sfx_lantern_toggle)

    def _on_monster_killed(self, **_) -> None:
        # self.play_sfx(AUDIO.sfx_monster_die)
        self.play_random_sfx(AUDIO.sfx_monster_die)

    def _on_player_damaged(self, **_) -> None:
        self.play_sfx(AUDIO.sfx_player_hurt)

    def _on_game_over(self, **_) -> None:
        self.play_music(AUDIO.music_gameover)

    def _on_phase_transition(self, to_phase: str) -> None:
        if to_phase == "night":
            self.play_music(AUDIO.music_night)
        elif to_phase == "day":
            self.play_music(AUDIO.music_day)
