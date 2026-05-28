"""Interactive login bootstrap for the persistent-profile auth mode.

Usage:
    python -m src.auth_login --profile facebook

Opens a Chromium window pointed at ``~/.cookie-detect/profiles/<name>/``.
The operator manually logs in to the target platform (facebook.com,
tiktok.com, etc.) and then presses Enter in this terminal when done.
The profile directory persists the resulting cookies for subsequent
runs of ``python -m src.main --auth-profile <name>``.

Why this exists:
    Our scraper's default mode wipes the Chromium ``user-data/`` directory
    before each run for reproducibility (every visit is an anonymous, fresh-
    browser visit). To audit what trackers receive from a *logged-in* user
    (e.g. Facebook's ``c_user`` cookie travelling cross-site to a tracker's
    ``/tr/`` endpoint), we need a Chromium profile that has been pre-logged
    into the target platform. This script creates and updates that profile.

The profile dir is *persistent* — it lives outside the repo and is reused
across runs. Don't delete it unless you want to start fresh (in which
case you'd need to bootstrap again).

See ``docs/TRACKING_FUNDAMENTALS.md`` §39 for the full design and context.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright


DEFAULT_START_URL = "https://www.facebook.com/"


def _profile_dir(name: str) -> Path:
    path = Path.home() / ".cookie-detect" / "profiles" / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Bootstrap a logged-in Chromium profile via manual login. "
            "Opens an interactive Chromium window; you log in by hand; "
            "the profile is saved for later non-interactive scraping runs."
        ),
    )
    parser.add_argument(
        "--profile",
        required=True,
        help=(
            "Profile name (e.g. 'facebook'). Stored under "
            "~/.cookie-detect/profiles/<name>/."
        ),
    )
    parser.add_argument(
        "--start-url",
        default=DEFAULT_START_URL,
        help=(
            "URL to open initially. Default is facebook.com; "
            "override for other platforms (tiktok.com, pinterest.com, etc.)."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    profile_dir = _profile_dir(args.profile)

    print("=" * 72)
    print("Auth-profile bootstrap")
    print("=" * 72)
    print(f"  Profile name:     {args.profile}")
    print(f"  Profile dir:      {profile_dir}")
    print(f"  Start URL:        {args.start_url}")
    print()
    print("A Chromium window will open. Follow these steps:")
    print()
    print("  1. Wait for the page to load.")
    print("  2. Log in to the target platform manually (email + password,")
    print("     handle any CAPTCHA / 2FA if prompted).")
    print("  3. Verify you're logged in (you should see your account, feed,")
    print("     profile icon, etc.).")
    print("  4. Come back to this terminal and press Enter to save & close.")
    print()
    print("Tip: do NOT close the Chromium window directly — press Enter here")
    print("first, so the profile is properly flushed to disk.")
    print()

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,
            viewport={"width": 1280, "height": 800},
            locale="en-US",
            timezone_id="America/New_York",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
            ignore_default_args=["--enable-automation"],
        )
        page = context.new_page()
        page.goto(args.start_url, wait_until="domcontentloaded", timeout=60000)

        try:
            input("\n>>> Press Enter when you are logged in and ready to save... ")
        except KeyboardInterrupt:
            print("\nInterrupted. Closing without verification.")
        finally:
            try:
                context.close()
            except Exception as exc:
                print(f"(non-fatal) error closing context: {exc}")

    # Verification: did the profile actually pick up cookies?
    cookies_db = profile_dir / "Default" / "Cookies"
    print()
    print("=" * 72)
    print("Verification")
    print("=" * 72)
    if cookies_db.exists():
        size_kb = cookies_db.stat().st_size / 1024
        print(f"  ✓ Cookies database found: {cookies_db}")
        print(f"    Size: {size_kb:.1f} KB")
        if size_kb < 5:
            print("  ⚠  Cookies file is unusually small — login may not have succeeded.")
            print("     Re-run this script and confirm you saw your logged-in account.")
    else:
        print(f"  ✗ Cookies database NOT found at {cookies_db}")
        print("    Login probably didn't complete. Re-run and try again.")
        return 1

    print()
    print("Next step — use this profile in a scrape run:")
    print(f"  python -m src.main --run_local --auth-profile {args.profile}")
    print()
    print("Or smoke-test on a single site first:")
    print(f"  python -m src.main --run_local --auth-profile {args.profile} \\")
    print(f"      --site https://hellmanns.com")
    return 0


if __name__ == "__main__":
    sys.exit(main())
