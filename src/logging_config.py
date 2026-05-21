"""Logging setup for the cookie-detection scraper.

Call :func:`configure_logging` exactly once at program startup (from
``src/main.py``). After that, every module can simply do::

    import logging
    log = logging.getLogger(__name__)
    log.info("something happened")

Two files are written inside the run folder:

  * ``run.log``        — INFO level and above. The clean narrative of
                         the run. Open this first when triaging.
  * ``run.debug.log``  — DEBUG level and above. Full trace. Open this
                         only when investigating a specific failure.

Both files travel with the result files; ``scp``-ing a run folder
also copies the logs.

Every log line is prefixed with the environment label (e.g. ``local``
or ``ec2-us-east-2``), so it is always obvious where a line came from
when looking at logs from multiple machines side by side.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import NamedTuple


_LOG_FORMAT = (
    "%(asctime)s [%(levelname)-7s] [%(env_label)s] %(name)s :: %(message)s"
)
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class LogPaths(NamedTuple):
    """The two log files written for a run."""
    info_log: Path
    debug_log: Path


class _EnvLabelFilter(logging.Filter):
    """Injects an ``env_label`` field into every LogRecord."""

    def __init__(self, env_label: str) -> None:
        super().__init__()
        self.env_label = env_label

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401
        record.env_label = self.env_label
        return True


def configure_logging(
    run_dir: Path,
    env_label: str,
    console_level: int = logging.INFO,
) -> LogPaths:
    """Configure the root logger.

    Console gets INFO+ (or DEBUG+ if ``--verbose``). Two files are
    written: an INFO-only narrative and a DEBUG-everything trace.

    Returns the paths to both log files.
    """
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)

    root.setLevel(logging.DEBUG)  # let handlers decide their own thresholds

    env_filter = _EnvLabelFilter(env_label)
    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    # --- Console (stdout) ---------------------------------------------
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(console_level)
    console.setFormatter(formatter)
    console.addFilter(env_filter)
    root.addHandler(console)

    # --- INFO file: the narrative -------------------------------------
    info_log_path = run_dir / "run.log"
    info_handler = logging.FileHandler(info_log_path, encoding="utf-8")
    info_handler.setLevel(logging.INFO)
    info_handler.setFormatter(formatter)
    info_handler.addFilter(env_filter)
    root.addHandler(info_handler)

    # --- DEBUG file: the full trace -----------------------------------
    debug_log_path = run_dir / "run.debug.log"
    debug_handler = logging.FileHandler(debug_log_path, encoding="utf-8")
    debug_handler.setLevel(logging.DEBUG)
    debug_handler.setFormatter(formatter)
    debug_handler.addFilter(env_filter)
    root.addHandler(debug_handler)

    # --- Silence noisy third-party loggers ----------------------------
    #
    # The OpenAI SDK's internal logger dumps the FULL request body at
    # DEBUG, which for our use case includes the base64-encoded
    # screenshots. A single such log line can be several megabytes;
    # multiplied by N websites it makes the debug log unreadable.
    #
    # urllib3/httpx/httpcore are also chatty at DEBUG. WARNING is
    # plenty for all of these — we still see retries and errors.
    for noisy in (
        "openai",
        "openai._base_client",
        "openai._client",
        "urllib3",
        "httpcore",
        "httpx",
        "asyncio",
    ):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    return LogPaths(info_log=info_log_path, debug_log=debug_log_path)
