"""arq worker entrypoint.

Run with::

    uv run arq worker.WorkerSettings

Re-exports ``WorkerSettings`` from :mod:`task_queue` so the worker container has
a stable, unambiguous entrypoint. (The queue module is named ``task_queue`` — not
``queue`` — to avoid shadowing the stdlib ``queue`` module that ``redis`` imports,
given this project's flat ``backend/`` import layout.)
"""
from task_queue import WorkerSettings  # noqa: F401

__all__ = ["WorkerSettings"]
