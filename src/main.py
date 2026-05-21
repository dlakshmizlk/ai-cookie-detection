"""Entry point for the cookie-detection scraper.

End-to-end flow:

  1. Parse CLI flags.
  2. Resolve the two secrets paths (.env file + Google credentials JSON)
     from CLI flags / environment variables. NO repo-relative defaults
     are used — paths must be provided explicitly.
  3. Load the .env file via python-dotenv so that OPENAI_API_KEY and any
     other environment overrides are available before anything else
     reads ``os.environ``.
  4. Create a unique, timestamped run folder under the output base.
  5. Configure logging to write to BOTH the terminal and run.log inside
     that folder.
  6. Connect to the Google Sheet, fetch websites + pixels.
  7. Construct GPTClient (once) and Scraper (once).
  8. For each website: scrape -> GPT -> save. Per-site exceptions are
     caught so a single failure does not abort the whole run.
  9. Write manifest.json summarising the run.
 10. Always tear down the browser, even on errors.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# Imported at the top because it has no side effects and we use it
# during path resolution.
from src.helper_funcs import hostname_slug


# ---------------------------------------------------------------------------
# Per-machine path defaults from src/local_config.py (gitignored)
# ---------------------------------------------------------------------------
# Kept here, not in src/config.py, so importing config is NOT a side
# effect of resolving the secrets paths. That way config's module-level
# constants are computed AFTER load_dotenv has populated os.environ.
def _load_local_path_defaults() -> tuple[str | None, str | None]:
    try:
        from src import local_config  # type: ignore[attr-defined]
    except ImportError:
        return None, None
    secrets_env = getattr(local_config, "SECRETS_ENV_PATH", None)
    google_creds = getattr(local_config, "GOOGLE_CREDENTIALS_PATH", None)
    return secrets_env, google_creds


# ---------------------------------------------------------------------------
# Secret-path resolution
# ---------------------------------------------------------------------------
def _resolve_secret_path(
    cli_value: str | None,
    env_var_name: str,
    local_default: str | None,
    flag_name: str,
    purpose: str,
) -> Path:
    """Resolve a secret-file path with no repo-relative fallback.

    Priority (highest wins):
        1. ``cli_value`` (from a CLI flag) if non-empty.
        2. The environment variable ``env_var_name`` if set.
        3. ``local_default`` (from ``src/local_config.py``) if set.
        4. Otherwise, exit with a helpful error.

    The returned path is expanded (``~``), absolute, and verified to
    exist as a regular file.
    """
    raw = cli_value or os.environ.get(env_var_name) or local_default
    if not raw:
        sys.stderr.write(
            f"ERROR: path to {purpose} is required.\n"
            f"       Provide it via one of:\n"
            f"         - CLI flag:       {flag_name} <path>\n"
            f"         - env variable:   {env_var_name}=<path>\n"
            f"         - local_config:   set in src/local_config.py\n"
        )
        sys.exit(2)

    path = Path(raw).expanduser().resolve()
    if not path.is_file():
        sys.stderr.write(
            f"ERROR: {purpose} not found at: {path}\n"
            f"       (resolved from {raw})\n"
        )
        sys.exit(2)
    return path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scrape websites for cookie banners and tracking pixels.",
    )
    parser.add_argument(
        "--secrets-env-path",
        dest="secrets_env_path",
        default=None,
        help=(
            "Path to the .env file containing OPENAI_API_KEY (and any other "
            "env overrides). Required, unless the env var SECRETS_ENV_PATH "
            "is set."
        ),
    )
    parser.add_argument(
        "--google-credentials-path",
        dest="google_credentials_path",
        default=None,
        help=(
            "Path to the Google service-account credentials JSON file. "
            "Required, unless the env var GOOGLE_CREDENTIALS_PATH is set."
        ),
    )
    parser.add_argument(
        "--run_local",
        action="store_true",
        help="Run on the developer's laptop instead of inside Docker/EC2.",
    )
    parser.add_argument(
        "--use_proxy",
        action="store_true",
        help="Route browser traffic through socks5://127.0.0.1:1080.",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show DEBUG-level log lines on the console (file always has DEBUG).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    # --- 1. Resolve and load secrets ------------------------------------
    local_default_env, local_default_google = _load_local_path_defaults()

    secrets_env_path = _resolve_secret_path(
        args.secrets_env_path,
        env_var_name="SECRETS_ENV_PATH",
        local_default=local_default_env,
        flag_name="--secrets-env-path",
        purpose="secrets .env file",
    )
    google_creds_path = _resolve_secret_path(
        args.google_credentials_path,
        env_var_name="GOOGLE_CREDENTIALS_PATH",
        local_default=local_default_google,
        flag_name="--google-credentials-path",
        purpose="Google service-account JSON",
    )

    # Load the .env file into os.environ. override=False means
    # values already set in the shell win over the file — handy for
    # one-off overrides without editing the file.
    load_dotenv(secrets_env_path, override=False)

    api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if not api_key:
        sys.stderr.write(
            f"ERROR: OPENAI_API_KEY not set after loading {secrets_env_path}.\n"
            "       Add a line like:  OPENAI_API_KEY=sk-...\n"
        )
        return 2

    # --- 2. Lazy imports of project modules ----------------------------
    # These are imported AFTER load_dotenv so any config knobs put in
    # the .env file (GPT_MODEL, APP_ENV, etc.) are picked up by
    # ``src.config`` at its first import time.
    from src import config
    from src.gpt import GPTClient, prompt_message
    from src.input_manager import InputManager
    from src.logging_config import configure_logging
    from src.scraper import Scraper

    # --- 3. Environment label + run folder -----------------------------
    env_label = config.get_env_label(run_local=args.run_local)
    run_id = config.make_run_id(env_label)
    base_dir = config.get_base_output_dir(run_local=args.run_local)
    base_dir.mkdir(parents=True, exist_ok=True)
    run_dir = base_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    # --- 4. Logging ----------------------------------------------------
    console_level = logging.DEBUG if args.verbose else logging.INFO
    log_paths = configure_logging(
        run_dir=run_dir,
        env_label=env_label,
        console_level=console_level,
    )
    log = logging.getLogger("main")

    log.info("=" * 72)
    log.info("Cookie-detection scraper starting")
    log.info("  run_id             = %s", run_id)
    log.info("  env_label          = %s", env_label)
    log.info("  run_dir            = %s", run_dir.resolve())
    log.info("  log (info)         = %s", log_paths.info_log.resolve())
    log.info("  log (debug)        = %s", log_paths.debug_log.resolve())
    log.info("  secrets_env_path   = %s", secrets_env_path)
    log.info("  google_creds_path  = %s", google_creds_path)
    log.info("  run_local          = %s", args.run_local)
    log.info("  use_proxy          = %s", args.use_proxy)
    log.info("  gpt_model          = %s", config.GPT_MODEL)
    log.info("  spreadsheet        = %s", config.SPREADSHEET_NAME)
    log.info("=" * 72)
    log.info("OpenAI API key loaded (%d chars)", len(api_key))

    # --- 5. Load inputs from Google Sheet ------------------------------
    log.info("Connecting to Google Sheet '%s'…", config.SPREADSHEET_NAME)
    try:
        input_mngr = InputManager(google_creds_path)
    except Exception:
        log.exception("Failed to read inputs from Google Sheet")
        return 3

    websites = input_mngr.websites
    pixels = input_mngr.pixels
    log.info(
        "Loaded %d websites and %d pixel patterns from sheet '%s'",
        len(websites), len(pixels), config.SPREADSHEET_NAME,
    )
    if not websites:
        log.warning("No websites in input sheet — nothing to do.")
        return 0

    # --- 6. Init GPT + Scraper (once each) -----------------------------
    gpt_client = GPTClient(api_key)
    scraper = Scraper(
        pixels=pixels,
        run_local=args.run_local,
        use_proxy=args.use_proxy,
    )

    # --- 7. Per-site loop ----------------------------------------------
    started_at = datetime.now()
    per_site_summary: list[dict] = []
    successes = 0
    failures = 0

    try:
        for idx, website in enumerate(websites):
            site_started = datetime.now()
            log.info("[%d/%d] -> Visiting %s",
                     idx + 1, len(websites), website)

            # ---- scrape ----
            try:
                visit_results = scraper.visit_website(website)
            except Exception as exc:
                log.exception("Scraper crashed on %s", website)
                failures += 1
                per_site_summary.append({
                    "idx": idx,
                    "website": website,
                    "success": False,
                    "stage": "scrape",
                    "error": f"{type(exc).__name__}: {exc}",
                })
                continue

            # ---- analyze (only if scrape succeeded) ----
            if visit_results.success:
                log.info("[%d/%d]    visit OK   pixels=%d screenshots=%d",
                         idx + 1, len(websites),
                         len(visit_results.request_info),
                         len(visit_results.screenshots_b64))
                try:
                    response = gpt_client.ask_message(
                        message=prompt_message,
                        img_path_or_b64=visit_results.screenshots_b64,
                    )
                    visit_results.cookie_banner_info = response
                    preview = response[:120].replace("\n", " ")
                    if len(response) > 120:
                        preview += "…"
                    log.info("[%d/%d]    GPT verdict: %s",
                             idx + 1, len(websites), preview)
                except Exception as exc:
                    log.exception("GPT analysis failed for %s", website)
                    visit_results.cookie_banner_info = ""
                    visit_results.error_message = (
                        (visit_results.error_message or "")
                        + f" | gpt_error: {type(exc).__name__}: {exc}"
                    ).strip(" |")
            else:
                log.warning("[%d/%d]    visit FAILED: %s",
                            idx + 1, len(websites),
                            visit_results.error_message)

            # ---- save ----
            duration = (datetime.now() - site_started).total_seconds()
            visit_results.idx = idx
            visit_results.duration_seconds = duration

            folder_name = f"website_{idx:03d}__{hostname_slug(website)}"
            try:
                visit_results.save(run_dir, folder_name=folder_name)
            except Exception:
                log.exception("Failed to save results for %s", website)
                failures += 1
                continue

            if visit_results.success:
                successes += 1
            else:
                failures += 1

            per_site_summary.append({
                "idx": idx,
                "website": website,
                "folder": folder_name,
                "success": visit_results.success,
                "duration_seconds": round(duration, 2),
                "pixels_captured": len(visit_results.request_info),
                "screenshots": len(visit_results.screenshots_b64),
                "cookie_banner_preview": (
                    visit_results.cookie_banner_info[:200]
                    if visit_results.cookie_banner_info else ""
                ),
                "error": visit_results.error_message,
            })

            log.info("[%d/%d]    done in %.2fs",
                     idx + 1, len(websites), duration)
    finally:
        log.info("Tearing down browser…")
        try:
            scraper.end()
        except Exception:
            log.exception("Error while shutting down the scraper (continuing).")

    # --- 8. Write manifest + summary -----------------------------------
    ended_at = datetime.now()
    duration_s = round((ended_at - started_at).total_seconds(), 2)
    manifest = {
        "run_id": run_id,
        "env_label": env_label,
        "started_at": started_at.isoformat(timespec="seconds"),
        "ended_at": ended_at.isoformat(timespec="seconds"),
        "duration_seconds": duration_s,
        "websites_total": len(websites),
        "websites_succeeded": successes,
        "websites_failed": failures,
        "pixels_count": len(pixels),
        "run_local": args.run_local,
        "use_proxy": args.use_proxy,
        "gpt_model": config.GPT_MODEL,
        "sites": per_site_summary,
    }
    manifest_path = run_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    summary_path = run_dir / "SUMMARY.txt"
    summary_path.write_text(_render_summary(manifest), encoding="utf-8")

    _update_latest_symlink(base_dir, run_id, log)

    log.info("=" * 72)
    log.info("Run finished")
    log.info("  ok=%d  failed=%d  total=%d",
             successes, failures, len(websites))
    log.info("  duration=%.1fs", duration_s)
    log.info("  manifest=%s", manifest_path.resolve())
    log.info("  summary =%s", summary_path.resolve())
    log.info("  outputs =%s", run_dir.resolve())
    log.info("=" * 72)

    return 0 if failures == 0 else 1


# ---------------------------------------------------------------------------
# Summary rendering + latest symlink
# ---------------------------------------------------------------------------
def _render_summary(manifest: dict) -> str:
    """Build a human-readable, tabular summary of a finished run.

    Designed to be ``less``-friendly: one line per website, fixed-width
    columns, scannable at a glance.
    """
    sites = manifest.get("sites", [])
    total = manifest.get("websites_total", 0) or 1
    avg = manifest.get("duration_seconds", 0.0) / total

    lines: list[str] = []
    lines.append("Cookie Detection — Run Summary")
    lines.append("=" * 78)
    lines.append(f"Run ID:     {manifest.get('run_id')}")
    lines.append(f"Env:        {manifest.get('env_label')}")
    lines.append(f"Started:    {manifest.get('started_at')}")
    lines.append(f"Ended:      {manifest.get('ended_at')}")
    lines.append(
        f"Duration:   {manifest.get('duration_seconds', 0):.1f}s "
        f"(avg {avg:.1f}s / site)"
    )
    lines.append(f"Model:      {manifest.get('gpt_model')}")
    lines.append("")
    lines.append(
        f"Total: {manifest.get('websites_total')}   "
        f"OK: {manifest.get('websites_succeeded')}   "
        f"Failed: {manifest.get('websites_failed')}"
    )
    lines.append("")

    header = f"  {'IDX':>3}  {'STATUS':<6}  {'DURATION':>9}  {'PIXELS':>6}  {'WEBSITE':<34}  BANNER"
    lines.append(header)
    lines.append("  " + "-" * (len(header) - 2))

    for site in sites:
        idx = site.get("idx", 0)
        status = "OK" if site.get("success") else "FAIL"
        dur = site.get("duration_seconds", 0.0)
        pixels = site.get("pixels_captured", 0)
        website = (site.get("website") or "")[:34]
        banner_text = (site.get("cookie_banner_preview") or "").strip()

        # The model is instructed to reply "YES - ..." or "NONE". Pull
        # out just the verdict word for the table; full text stays in
        # info.json / manifest.json.
        if banner_text.upper().startswith("YES"):
            verdict = "YES"
        elif banner_text.upper().startswith("NONE"):
            verdict = "NONE"
        elif site.get("error"):
            verdict = "ERR"
        else:
            verdict = "—"

        lines.append(
            f"  {idx:03d}  {status:<6}  {dur:>7.2f}s  {pixels:>6}  {website:<34}  {verdict}"
        )

    return "\n".join(lines) + "\n"


def _update_latest_symlink(base_dir: Path, run_id: str, log: logging.Logger) -> None:
    """Point ``<base_dir>/latest`` at the most recent run.

    Safe to call repeatedly — replaces any existing symlink. If the
    operating system or filesystem refuses symlinks (rare on Mac/Linux),
    this logs a warning and continues.
    """
    latest = base_dir / "latest"
    try:
        if latest.is_symlink() or latest.exists():
            latest.unlink()
        latest.symlink_to(run_id)  # relative target — survives moves of base_dir
        log.info("Updated 'latest' symlink -> %s", run_id)
    except OSError as exc:
        log.warning("Could not update 'latest' symlink: %s", exc)


if __name__ == "__main__":
    sys.exit(main())
