"""Tests for main.py lifespan worker_role branching (Phase 0)."""
from unittest.mock import patch, MagicMock, AsyncMock

import pytest


@pytest.mark.asyncio
async def test_lifespan_web_role_no_scheduler_but_arq_pool():
    """web role: an arq pool is created for enqueuing, APScheduler is NOT started."""
    import main
    from config import settings

    app = MagicMock()
    app.state = MagicMock()
    fake_pool = MagicMock()
    fake_pool.close = AsyncMock()

    with patch.object(settings, "worker_role", "web"), \
         patch("main.init_db", new_callable=AsyncMock), \
         patch("task_queue.get_arq_pool", new_callable=AsyncMock, return_value=fake_pool), \
         patch("main.create_scheduler") as mock_create_sched:
        async with main.lifespan(app):
            assert app.state.arq is fake_pool
            assert app.state.scheduler is None
        mock_create_sched.assert_not_called()
    fake_pool.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_lifespan_scheduler_role_starts_apscheduler_enqueue_only():
    """scheduler role: APScheduler is started AND an arq pool exists for enqueuing."""
    import main
    from config import settings

    app = MagicMock()
    app.state = MagicMock()
    fake_pool = MagicMock()
    fake_pool.close = AsyncMock()
    fake_sched = MagicMock()

    with patch.object(settings, "worker_role", "scheduler"), \
         patch("main.init_db", new_callable=AsyncMock), \
         patch("task_queue.get_arq_pool", new_callable=AsyncMock, return_value=fake_pool), \
         patch("main.create_scheduler", return_value=fake_sched) as mock_create_sched:
        async with main.lifespan(app):
            assert app.state.arq is fake_pool
            assert app.state.scheduler is fake_sched
            fake_sched.start.assert_called_once()
        mock_create_sched.assert_called_once()
    fake_sched.shutdown.assert_called_once()
    fake_pool.close.assert_awaited_once()
