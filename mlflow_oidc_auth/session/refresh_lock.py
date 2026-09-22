"""In-process single-flight for session refreshes, awaited on the event loop (issue #367).

Concurrent requests that find the same session expired must not each exchange its refresh token.
Within one event loop they queue here, on an ``asyncio.Lock`` per session: waiting costs no
thread. Only the request that holds the lock goes on to the repository's refresh guard — which
takes the cross-process row lock in a worker thread — and to the IdP. Blocking waiters in
executor threads instead would let a burst of them fill the default executor that the refresher
itself needs (anyio resolves DNS there), stalling the one request that could release them.

Locks are per event loop, since an ``asyncio.Lock`` belongs to one loop. Several loops in one
process (threaded servers, test clients) are still serialised by the repository guard's
process-wide lock behind this one.
"""

from __future__ import annotations

import asyncio
import threading
import weakref
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, List

# loop -> {session_id: [lock, users]}. Weak on the loop so a closed loop's table goes with it.
_LOCKS: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, Dict[str, List]]" = weakref.WeakKeyDictionary()
_LOCKS_GUARD = threading.Lock()


def _table(loop: asyncio.AbstractEventLoop) -> Dict[str, List]:
    with _LOCKS_GUARD:
        table = _LOCKS.get(loop)
        if table is None:
            table = {}
            _LOCKS[loop] = table
        return table


@asynccontextmanager
async def local_refresh_turn(session_id: str, timeout: float) -> AsyncIterator[None]:
    """Hold this event loop's refresh turn for ``session_id``.

    Parameters:
        session_id: The session being refreshed.
        timeout: Seconds to wait for the turn.

    Yields:
        Nothing; the turn is held for the body.

    Raises:
        TimeoutError: If another request on this loop held the turn for ``timeout``.
    """
    table = _table(asyncio.get_running_loop())
    # Only this loop's thread touches ``table`` from here on, so no further locking is needed.
    entry = table.setdefault(session_id, [asyncio.Lock(), 0])
    entry[1] += 1
    acquired = False
    try:
        try:
            await asyncio.wait_for(entry[0].acquire(), timeout)
        except asyncio.TimeoutError as exc:
            raise TimeoutError("timed out waiting for a concurrent refresh of this session") from exc
        acquired = True
        yield
    finally:
        if acquired:
            entry[0].release()
        entry[1] -= 1
        if entry[1] == 0 and table.get(session_id) is entry:
            del table[session_id]


def pending_turns() -> int:
    """How many sessions currently have a turn held or awaited, across loops. For tests."""
    with _LOCKS_GUARD:
        return sum(len(table) for table in _LOCKS.values())
