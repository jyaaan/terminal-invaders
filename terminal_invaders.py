"""
Coordinates are y, x!
Raises an exception if attempting to display out of bounds.

Minimum terminal size: 3 (width) x 4 (height).
This size allows for a "center" and a gap between player and enemies,
along with a status bar at the top.

Enemies are dynamically spaced across the center third of the screen.
"""

import curses
import time
import logging
import sys
import subprocess
import traceback

PLAYER_SHIP = "☺"
ENEMY_SHIP = "V"
INITIAL_ENEMY_SPEED = 1.0
LEFT_EDGE = 0
RIGHT_EDGE_OFFSET = 2


# Decorator to display exceptions while using curses
# Otherwise exceptions get
#                          all
#                              weird
def curses_safe_run(func):
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


def move_enemies(enemies, enemy_direction, width):
    for enemy in enemies:
        enemy[1] += enemy_direction
    enemy_edges = [
        min(enemies, key=lambda enemy: enemy[1])[1],
        max(enemies, key=lambda enemy: enemy[1])[1],
    ]
    # Flip direction of travel if edge of screen reached by leftmost or rightmost enemy.
    if enemy_edges[0] == LEFT_EDGE or enemy_edges[1] == width - 1:
        enemy_direction *= -1
    return enemy_edges, enemy_direction


@curses_safe_run
def main(stdscr):
    width = curses.COLS
    height = curses.LINES
    if width < 3 or height < 4:
        raise TerminalSizeError(
            "Your terminal must be at least 3 (width) x 4 (height) to play this game."
        )
    third_of_screen = width // 3

    # Initial settings
    curses.curs_set(0)  # Hides cursor
    stdscr.nodelay(True)  # Don't wait for input

    player_pos = [height - 1, width // 2]  # bottom center

    enemy_direction = 1  # Start right
    enemy_speed = INITIAL_ENEMY_SPEED  # Seconds per movement.
    # Dynamically size enemies to occupy third of screen
    enemies = [
        [1, num] for num in range(third_of_screen + 1, third_of_screen * 2 + 1, 2)
    ]
    # Not entirely necessary to eval this here, but it's nice for debug.
    enemy_edges = [
        min(enemies, key=lambda enemy: enemy[1])[1],
        max(enemies, key=lambda enemy: enemy[1])[1],
    ]
    last_move_time = time.time()

    # Colors! Uncomment to officially launch feature.
    # curses.start_color()
    # curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)

    while True:
        stdscr.clear()

        # Status bar
        curr_time = time.time()
        time_since_last_move = curr_time - last_move_time
        status = (
            f"{width=} - {height=}, "
            f"{enemy_speed=}, "
            f"{enemy_direction=}, "
            f"{time_since_last_move=:.2f}, "
            f"{enemy_edges=}"
        )
        stdscr.addstr(0, 0, status[:width])

        # Render ships
        for enemy in enemies:
            stdscr.addch(enemy[0], enemy[1], ENEMY_SHIP, curses.color_pair(1))
        stdscr.addch(player_pos[0], player_pos[1], PLAYER_SHIP)

        # Enemy ship movement
        if time_since_last_move > enemy_speed:
            enemy_edges, enemy_direction = move_enemies(enemies, enemy_direction, width)
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
            break

        stdscr.refresh()

        # Game loop speed, keep it low for responsive player movement
        time.sleep(0.05)

    print("\n game over!")
    time.sleep(1)


curses.wrapper(main)
