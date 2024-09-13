"""
Coordinates are y, x!
Raises an exception if attempting to display out of bounds.

Minimum terminal size: 3 (width) x 4 (height).
This size allows for a "center" and a gap between player and enemies,
along with a status bar at the top.

Enemies are dynamically spaced across the center third of the screen.

Data structures:
enemies = [{'y': int, 'x': int, 'alive': bool}]
projectiles = [{'y': int, 'x': int, 'last_move_time': time.time()}]
"""

from typing import Callable, List, Tuple, TypedDict

import curses
import time
import logging
import sys
import subprocess
import traceback


class Enemy(TypedDict):
    y: int
    x: int
    alive: bool


class Projectile(TypedDict):
    y: int
    x: int
    speed: float
    last_move_time: float


PLAYER_SHIP: str = "☺"
ENEMY_SHIP: str = "V"
INITIAL_ENEMY_SPEED: float = 1.0  # Seconds
INITIAL_PROJECTILE_SPEED: float = 0.1  # Seconds
LEFT_EDGE: int = 0
RIGHT_EDGE_OFFSET: int = 2


# Decorator to display exceptions while using curses
# Otherwise exceptions get
#                          all
#                              weird
def curses_safe_run(func: Callable[..., None]):
    def wrapper(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except curses.error as e:
            curses.endwin()
            subprocess.run(["reset"])
            logging.error(f"Curses Error: {e}")
            traceback.print_exc()
            input("Press Enter to continue...")
            sys.exit(1)  # Remove to allow recovery
        except Exception as e:
            curses.endwin()
            subprocess.run(["reset"])
            logging.error(f"Unhandled Exception: {type(e).__name__}: {e}")
            traceback.print_exc()
            input("Press Enter to continue...")
            sys.exit(1)  # Gracefully exit to prevent unstable state

    return wrapper


class TerminalSizeError(Exception):
    """Raised when the terminal size is too small to play the game."""

    pass


def move_enemies(
    alive_enemies: List[Enemy], enemy_direction: int, width: int
) -> Tuple[List[int], int]:
    for enemy in alive_enemies:
        enemy["x"] += enemy_direction

    enemy_edges: List[int] = [
        min(alive_enemies, key=lambda enemy: enemy["x"])["x"],
        max(alive_enemies, key=lambda enemy: enemy["x"])["x"],
    ]

    # Flip direction of travel if edge of screen reached by leftmost or rightmost enemy.
    if enemy_edges[0] == LEFT_EDGE or enemy_edges[1] == width - 1:
        enemy_direction *= -1
    return enemy_edges, enemy_direction


@curses_safe_run
def main(stdscr: curses.window):
    width: int = curses.COLS
    height: int = curses.LINES
    if width < 3 or height < 4:
        raise TerminalSizeError(
            "Your terminal must be at least 3 (width) x 4 (height) to play this game."
        )
    third_of_screen: int = width // 3

    # Initial settings
    curses.curs_set(0)  # Hides cursor
    stdscr.nodelay(True)  # Don't wait for input

    player_pos: List[int] = [height - 1, width // 2]  # bottom center

    projectiles: List[Projectile] = []
    fire_cooldown: float = 0.5  # Seconds
    last_fire_time: float = time.time()

    enemy_direction: int = 1  # Start right
    enemy_speed: float = INITIAL_ENEMY_SPEED  # Seconds per movement.
    # Dynamically size enemies to occupy third of screen
    enemies: List[Enemy] = [
        {"y": 1, "x": num, "alive": True}
        for num in range(third_of_screen + 1, third_of_screen * 2 + 1, 2)
    ]
    # Not entirely necessary to eval this here, but it's nice for debug.
    alive_enemies: List[Enemy] = [enemy for enemy in enemies if enemy["alive"]]
    enemy_edges: List[int] = [
        min(alive_enemies, key=lambda enemy: enemy["x"])["x"],
        max(alive_enemies, key=lambda enemy: enemy["x"])["x"],
    ]
    last_move_time: float = time.time()

    # Colors! Uncomment to officially launch feature.
    curses.start_color()
    curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)

    while True:
        stdscr.clear()

        # Status bar
        curr_time: float = time.time()
        time_since_last_move: float = curr_time - last_move_time
        status: str = (
            f"{width=} - {height=}, "
            f"{enemy_speed=}, "
            f"{enemy_direction=}, "
            f"{time_since_last_move=:.2f}, "
            f"{enemy_edges=}"
        )
        stdscr.addstr(0, 0, status[:width])

        # Render ships
        for enemy in enemies:
            if enemy["alive"]:
                stdscr.addch(enemy["y"], enemy["x"], ENEMY_SHIP, curses.color_pair(1))
        stdscr.addch(player_pos[0], player_pos[1], PLAYER_SHIP)
        # put projectile rendering here
        for projectile in projectiles:
            stdscr.addch(projectile["y"], projectile["x"], "|")

        # Projectile movement
        for projectile in projectiles[:]:
            if curr_time - projectile["last_move_time"] >= projectile["speed"]:
                projectile["y"] -= 1
                projectile["last_move_time"] = curr_time

                if projectile["y"] < 1:
                    projectiles.remove(projectile)
                else:
                    for enemy in enemies:
                        if (
                            enemy["alive"]
                            and enemy["y"] == projectile["y"]
                            and enemy["x"] == projectile["x"]
                        ):
                            projectiles.remove(projectile)
                            enemy["alive"] = False
                            alive_enemies = [
                                enemy for enemy in enemies if enemy["alive"]
                            ]
                            break

        # Enemy ship movement
        if time_since_last_move > enemy_speed:
            enemy_edges, enemy_direction = move_enemies(
                alive_enemies, enemy_direction, width
            )
            last_move_time = curr_time

        # Handle user input
        player_key = stdscr.getch()
        if player_key == curses.KEY_LEFT and player_pos[1] > LEFT_EDGE:
            player_pos[1] -= 1
        elif (
            player_key == curses.KEY_RIGHT and player_pos[1] < width - RIGHT_EDGE_OFFSET
        ):
            player_pos[1] += 1
        elif player_key == ord("q"):
            stdscr.addstr(
                height // 2, width // 2 - min(width // 2, 4), "game over"[:width]
            )
            stdscr.refresh()
            time.sleep(2)
            break
        # handle user input here
        elif player_key == ord(" "):
            if curr_time - last_fire_time >= fire_cooldown:
                projectiles.append(
                    {
                        "y": player_pos[0] - 1,
                        "x": player_pos[1],
                        "speed": INITIAL_PROJECTILE_SPEED,
                        "last_move_time": time.time(),
                    }
                )
                last_fire_time = curr_time

        stdscr.refresh()

        # Game loop speed, keep it low for responsive player movement
        time.sleep(0.05)


curses.wrapper(main)
