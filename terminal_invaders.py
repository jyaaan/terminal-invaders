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
from enum import StrEnum

import curses
import time
import logging
import sys
import subprocess
import traceback


class GAME_STATE(StrEnum):
    PLAY = "play"
    LOSE = "lose"
    WIN = "win"


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
PROJECTILE_CHR: str = "|"
INITIAL_ENEMY_SPEED: float = 0.5  # Seconds
MAX_ENEMY_SPEED: float = 0.05  # Seconds
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
    alive_enemies: List[Enemy],
    enemy_direction: int,
    width: int,
    move_down: bool,
) -> Tuple[int, int, bool]:
    left_most = width
    right_most = 0
    bottom_most = 0

    for enemy in alive_enemies:
        if move_down:
            enemy["y"] += 1
        else:
            enemy["x"] += enemy_direction
        bottom_most = max(bottom_most, enemy["y"])
        left_most = min(left_most, enemy["x"])
        right_most = max(right_most, enemy["x"])

    # Flip direction of travel if edge of screen reached by leftmost or rightmost enemy.
    if left_most == LEFT_EDGE or right_most == width - 1:
        if move_down:
            enemy_direction *= -1
            move_down = False
        else:
            move_down = True

    return bottom_most, enemy_direction, move_down


def update_enemy_speed(alive_enemies: List[Enemy], total_enemy_count: int) -> float:
    destroyed_enemy_count = total_enemy_count - len(alive_enemies)
    destruction_ratio = destroyed_enemy_count / total_enemy_count
    # Quadratic scaling
    speed_factor = destruction_ratio**2
    enemy_speed = (
        INITIAL_ENEMY_SPEED - (INITIAL_ENEMY_SPEED - MAX_ENEMY_SPEED) * speed_factor
    )

    return max(MAX_ENEMY_SPEED, enemy_speed)


def move_projectiles(
    projectiles, curr_time, total_enemy_count, enemies, enemy_speed
) -> tuple[GAME_STATE, float]:
    game_state = GAME_STATE.PLAY
    for projectile in projectiles[:]:
        if curr_time - projectile["last_move_time"] >= projectile["speed"]:
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
                        alive_enemies = [enemy for enemy in enemies if enemy["alive"]]
                        if len(alive_enemies) == 0:
                            game_state = GAME_STATE.WIN
                        enemy_speed = update_enemy_speed(
                            alive_enemies, total_enemy_count
                        )
                        break

            # Move projectile after collision check
            projectile["y"] -= 1
            projectile["last_move_time"] = curr_time

    return game_state, enemy_speed


def render(stdscr, enemies, player_pos, projectiles):
    for enemy in enemies:
        if enemy["alive"]:
            stdscr.addch(enemy["y"], enemy["x"], ENEMY_SHIP, curses.color_pair(1))
    stdscr.addch(player_pos[0], player_pos[1], PLAYER_SHIP)
    # put projectile rendering here
    for projectile in projectiles:
        stdscr.addch(
            projectile["y"], projectile["x"], PROJECTILE_CHR, curses.color_pair(2)
        )


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
    alive_enemies: List[Enemy] = [enemy for enemy in enemies if enemy["alive"]]
    total_enemy_count: int = len(enemies)
    last_move_time: float = time.time()
    move_down = False

    curses.start_color()
    curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)  # Enemy ship
    curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)  # BEAM
    curses.init_pair(3, curses.COLOR_BLUE, curses.COLOR_BLACK)  # Player ship

    game_state: GAME_STATE = GAME_STATE.PLAY

    while game_state == GAME_STATE.PLAY:
        stdscr.clear()
        curr_time: float = time.time()

        # Projectile movement
        game_state, enemy_speed = move_projectiles(
            projectiles, curr_time, total_enemy_count, enemies, enemy_speed
        )

        # Enemy ship movement
        time_since_last_move: float = curr_time - last_move_time
        if time_since_last_move > enemy_speed:
            if alive_enemies:
                bottom_edge, enemy_direction, move_down = move_enemies(
                    alive_enemies, enemy_direction, width, move_down
                )
                last_move_time = curr_time
                if bottom_edge >= height - 1:
                    game_state = GAME_STATE.LOSE

        # Handle user input
        player_key = stdscr.getch()
        if player_key == curses.KEY_LEFT and player_pos[1] > LEFT_EDGE:
            player_pos[1] -= 1
        elif (
            player_key == curses.KEY_RIGHT and player_pos[1] < width - RIGHT_EDGE_OFFSET
        ):
            player_pos[1] += 1
        elif player_key == ord("q"):
            game_state = GAME_STATE.LOSE
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

        # Render ships
        render(stdscr, enemies, player_pos, projectiles)

        # Status bar
        status: str = (
            f"{width=} - {height=}, "
            f"{enemy_speed=:.2f}, "
            f"{enemy_direction=}, "
            f"{time_since_last_move=:.2f}, "
        )
        stdscr.addstr(0, 0, status[:width])

        if game_state == GAME_STATE.LOSE:
            stdscr.addstr(
                height // 2, width // 2 - min(width // 2, 4), "game over"[:width]
            )
            stdscr.refresh()
            time.sleep(2)
        elif game_state == GAME_STATE.WIN:
            stdscr.addstr(
                height // 2,
                width // 2 - min(width // 2, 3),
                "you win"[:width],
            )
            stdscr.refresh()
            time.sleep(2)
        else:
            stdscr.refresh()

            # Game loop speed, keep it low for responsive player movement
            time.sleep(0.05)


curses.wrapper(main)
