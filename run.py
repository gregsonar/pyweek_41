"""
Entry point.

    python run.py
    python run.py --debug
"""
from __future__ import annotations

import argparse
import logging
import sys


def _configure_logging(debug: bool) -> None:
    level = logging.DEBUG if debug else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(levelname)-8s %(name)s — %(message)s",
        stream=sys.stdout,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Into the Dark")
    parser.add_argument("--debug", action="store_true", help="Verbose logging")
    args = parser.parse_args()

    _configure_logging(args.debug)

    # Deferred imports so logging is configured before pygame boots
    from core.game             import Game
    from scenes.menu_scene     import MenuScene
    from scenes.game_scene     import GameScene
    from scenes.gameover_scene import GameOverScene

    game = Game()
    game.scenes.register("menu",     MenuScene(game))
    game.scenes.register("game",     GameScene(game))
    game.scenes.register("gameover", GameOverScene(game))
    game.scenes.switch("menu")
    game.run()


if __name__ == "__main__":
    main()
