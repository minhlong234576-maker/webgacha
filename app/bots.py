from __future__ import annotations

import asyncio
import logging
import random

from . import game, store
from .gacha import load_cases

log = logging.getLogger("jellyvale.bots")
_task: asyncio.Task | None = None


def _cases():
    cases = load_cases()
    return cases or []


def _tick() -> None:
    cases = _cases()
    if not cases:
        return
    for name in store.BOT_NAMES:
        game.seed_wallet(name, is_bot=True)

    roll = random.random()
    waiting = store.waiting_battles()

    # Bot-hosted rooms that are full: host bot presses Start after a short wait.
    for battle in waiting:
        seated = int(battle.get("seated") or 0)
        if seated < battle["slots"]:
            continue
        if battle["host"] not in store.BOT_NAMES:
            continue
        if store.now() - battle["created_at"] < 4:
            continue
        try:
            game.start_battle(battle["id"], battle["host"])
        except game.GameError:
            pass
        return

    if waiting and roll < 0.5:
        battle = random.choice(waiting)
        seated = store.battle_player_names(battle["id"])
        if len(seated) >= battle["slots"]:
            return
        free = [name for name in store.BOT_NAMES if name not in seated]
        if free:
            bot = random.choice(free)
            try:
                game.join_existing_battle(bot, battle["id"], is_bot=True)
            except game.GameError:
                pass
        return

    if (not waiting or len(waiting) < 3) and roll < 0.55:
        host = random.choice(store.BOT_NAMES)
        case = random.choice(cases)
        slots = random.choice((2, 2, 3, 4))
        rounds = random.choice((1, 1, 1, 2, 3))
        mode = "CRAZY" if random.random() < 0.15 else "STANDARD"
        try:
            created = game.create_battle(host, case.id, slots, rounds, mode, is_bot=True)
            if random.random() < 0.7:
                game.fill_bots(created["id"])
        except game.GameError:
            pass
        return

    bot = random.choice(store.BOT_NAMES)
    case = random.choice(cases)
    try:
        result = game.open_case(bot, case.id, is_bot=True)
        if result.winner["coin"] < 8000 and random.random() < 0.7:
            game.sell_items(bot, [result.inventory_id])
    except game.GameError:
        store.credit(bot, case.pull_cost * 8, "seed", "bot nạp")

    if random.random() < 0.2:
        held = store.list_inventory(bot, "held")
        cheap = [row["id"] for row in held if row["value"] < 8000][:6]
        if cheap:
            try:
                game.sell_items(bot, cheap)
            except game.GameError:
                pass


async def loop() -> None:
    await asyncio.sleep(1.5)
    while True:
        try:
            await asyncio.to_thread(_tick)
        except Exception:
            log.exception("bot tick")
        await asyncio.sleep(random.uniform(2.2, 4.8))


def start(app) -> None:
    global _task
    store.init()
    if _task is None or _task.done():
        _task = asyncio.create_task(loop())
        app.state.bot_task = _task
