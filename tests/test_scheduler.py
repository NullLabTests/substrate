"""Tests for TickScheduler."""

from __future__ import annotations

import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio

from core.scheduler.tick_scheduler import TickScheduler


class TestTickScheduler:
    async def test_initialize_and_shutdown(self, scheduler: TickScheduler) -> None:
        assert scheduler.tick_count == 0

    async def test_tick_iteration(self, scheduler: TickScheduler) -> None:
        ticks = []
        async with scheduler.ticks(interval=0.01) as ticker:
            async for tick in ticker:
                ticks.append(tick)
                if len(ticks) >= 5:
                    break
        assert len(ticks) == 5
        assert ticks == [1, 2, 3, 4, 5]
        assert scheduler.tick_count == 5

    async def test_pause_and_resume(self, scheduler: TickScheduler) -> None:
        ticks = []
        scheduler.pause()
        assert scheduler.is_paused is True

        async with scheduler.ticks(interval=0.005) as ticker:
            await asyncio.sleep(0.03)
            scheduler.resume()
            assert scheduler.is_paused is False
            async for tick in ticker:
                ticks.append(tick)
                if len(ticks) >= 3:
                    break
        assert len(ticks) == 3

    async def test_pre_and_post_hooks(self, scheduler: TickScheduler) -> None:
        pre_calls: list[int] = []
        post_calls: list[int] = []

        async def pre(tick: int) -> None:
            pre_calls.append(tick)

        async def post(tick: int) -> None:
            post_calls.append(tick)

        scheduler.add_pre_hook(pre)
        scheduler.add_post_hook(post)

        async with scheduler.ticks(interval=0.01) as ticker:
            async for tick in ticker:
                if tick >= 3:
                    break
        assert len(pre_calls) == 3
        assert len(post_calls) == 2

    async def test_save_and_load_state(self, scheduler: TickScheduler) -> None:
        async with scheduler.ticks(interval=0.01) as ticker:
            async for tick in ticker:
                if tick >= 3:
                    break
        state = await scheduler.save_state()
        assert state["tick_count"] == 3

        new_sched = TickScheduler()
        await new_sched.load_state(state)
        assert new_sched.tick_count == 3
