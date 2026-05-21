"""Tiny retry helper used by network-touching code.

We intentionally avoid adding the ``tenacity`` dependency for now —
this implements just enough exponential backoff to be useful for the
two real failure modes we see in practice: transient page-load errors
and OpenAI rate-limit / timeout errors.

Usage::

    from src.retry import retry_with_backoff

    response = retry_with_backoff(
        lambda: page.goto(url, timeout=45000),
        max_attempts=3,
        initial_delay=2.0,
        label=f"page.goto({url})",
    )
"""

from __future__ import annotations

import logging
import time
from typing import Callable, TypeVar

T = TypeVar("T")
log = logging.getLogger(__name__)


def retry_with_backoff(
    fn: Callable[[], T],
    *,
    max_attempts: int,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
    label: str = "operation",
) -> T:
    """Call ``fn()`` up to ``max_attempts`` times, doubling the delay
    between attempts.

    Re-raises the *last* exception if every attempt fails. Each
    intermediate failure is logged at WARNING; each retry is announced
    at INFO so retries are easy to spot in the run.log.

    Parameters
    ----------
    fn:
        Zero-argument callable to invoke. Wrap your real call in a
        lambda or ``functools.partial`` if you need to pass arguments.
    max_attempts:
        Total number of attempts (NOT the number of retries — so 3 means
        the original call plus up to 2 retries).
    initial_delay:
        Seconds to wait before the second attempt.
    backoff_factor:
        Multiplier applied to ``initial_delay`` after every attempt.
    retry_on:
        Exception types that should trigger a retry. Anything else
        propagates immediately. Defaults to all ``Exception`` subclasses.
    label:
        Human-readable name for the operation, shown in log lines.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")

    delay = initial_delay
    last_exc: BaseException | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            if attempt > 1:
                log.info(
                    "Retrying %s (attempt %d/%d)",
                    label, attempt, max_attempts,
                )
            return fn()
        except retry_on as exc:
            last_exc = exc
            log.warning(
                "%s failed on attempt %d/%d: %s: %s",
                label, attempt, max_attempts,
                type(exc).__name__, exc,
            )
            if attempt == max_attempts:
                break
            time.sleep(delay)
            delay *= backoff_factor

    assert last_exc is not None  # by construction
    raise last_exc
