"""Centralized configuration for the cookie-detection scraper.

All knobs live here so the rest of the code never has to think about
environment variables or hardcoded paths. Values can be overridden via
environment variables for flexibility (e.g., to run against a different
spreadsheet, change the GPT model, or label the environment differently
when we eventually run from multiple AWS regions).

Importing this module has no side effects beyond computing constants.

Secret-file paths are NOT defined as committed defaults here.
They are resolved in ``main.py`` from, in order:

    1. CLI flag (--secrets-env-path / --google-credentials-path)
    2. Environment variable (SECRETS_ENV_PATH / GOOGLE_CREDENTIALS_PATH)
    3. ``src/local_config.py``  (a gitignored, per-machine file you
       create from ``src/local_config.py.example``)
    4. Otherwise, exit with a helpful error.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# Environment labelling
# ---------------------------------------------------------------------------
#
# Every run is tagged with an "environment label" so that, when looking at a
# log line or an output folder, you can immediately tell whether it came from
# your laptop or from EC2 (and later, from which EC2 region).
#
# Resolution order:
#   1. APP_ENV environment variable (used verbatim if set)
#   2. "local" if the --run_local CLI flag was passed
#   3. "ec2"   otherwise (the Docker / EC2 default)
#
# Example future values: "ec2-us-east-2", "ec2-us-west-1", "local-marcus", ...

def get_env_label(run_local: bool) -> str:
    explicit = os.environ.get("APP_ENV")
    if explicit:
        return explicit
    return "local" if run_local else "ec2"


def make_run_id(env_label: str, now: datetime | None = None) -> str:
    """Build a unique, sortable run identifier.

    Format:  <env_label>__<YYYY-MM-DD_HH-MM-SS>
    Example: local__2026-05-21_14-30-15
             ec2-us-east-2__2026-05-21_03-00-00
    """
    now = now or datetime.now()
    return f"{env_label}__{now.strftime('%Y-%m-%d_%H-%M-%S')}"


# ---------------------------------------------------------------------------
# Output directory
# ---------------------------------------------------------------------------
def get_base_output_dir(run_local: bool) -> Path:
    """Where run folders go.

    --run_local  -> ./outputs (relative to the working directory)
    EC2/Docker   -> /app/outputs (the bind-mount target inside the container)

    Each run creates a unique subdirectory under this base.
    """
    if run_local:
        return Path("./outputs")
    return Path("/app/outputs")


# ---------------------------------------------------------------------------
# OpenAI / GPT
# ---------------------------------------------------------------------------
GPT_MODEL: str = os.environ.get("GPT_MODEL", "gpt-4.1")
GPT_TIMEOUT_SECONDS: float = float(os.environ.get("GPT_TIMEOUT_SECONDS", "60"))
GPT_MAX_RETRIES: int = int(os.environ.get("GPT_MAX_RETRIES", "3"))


# ---------------------------------------------------------------------------
# Playwright / page navigation
# ---------------------------------------------------------------------------
PAGE_GOTO_TIMEOUT_MS: int = int(os.environ.get("PAGE_GOTO_TIMEOUT_MS", "45000"))
PAGE_GOTO_MAX_ATTEMPTS: int = int(os.environ.get("PAGE_GOTO_MAX_ATTEMPTS", "3"))


# ---------------------------------------------------------------------------
# Google Sheet
# ---------------------------------------------------------------------------
SPREADSHEET_NAME: str = os.environ.get("SPREADSHEET_NAME", "cookie-banner")


# Per-machine default secrets paths are intentionally NOT defined in
# this module — see main.py's _load_local_path_defaults() for that.
# Keeping it out of here means importing config does not also pull in
# the per-machine local_config.py, and lets main.py call load_dotenv
# BEFORE this module is imported (so .env-provided values for
# GPT_MODEL/APP_ENV/etc. are reflected in the constants above).
