"""Browser automation, screenshotting, and tracking-pixel capture.

Wraps Playwright so that ``main.py`` can simply call
``scraper.visit_website(url)`` and get back a populated
:class:`VisitResults`.
"""

from __future__ import annotations

import base64
import gzip
import json
import logging
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import brotli
from playwright.sync_api import Page, Request, Response, sync_playwright

from src import config
from src.retry import retry_with_backoff

log = logging.getLogger(__name__)


# PII cookies — when --mask-pii is set, these get their values replaced
# with "<masked>" before the captured data is written to disk. The set
# below covers Facebook's identity-bearing cookies; extend as needed for
# other platforms.
#
# Why these three (not all five FB auth cookies):
#   c_user — the literal Facebook account ID. Definitely PII.
#   xs     — session token. Possession lets someone hijack the session.
#   fr     — auth-related token. Identity-bearing.
#   datr   — browser-level identifier; less identity-rich. NOT masked here.
#   sb     — login signal; less identity-rich. NOT masked here.
_PII_COOKIE_NAMES = {"c_user", "xs", "fr"}


def _mask_cookie_header(header: str) -> str:
    """Replace PII cookie values inside a ``Cookie:`` header string with
    ``<masked>``. Non-PII cookies are passed through unchanged."""
    if not header:
        return header
    masked_parts: list[str] = []
    for kv in header.split(";"):
        kv = kv.strip()
        if "=" in kv:
            name, _, _value = kv.partition("=")
            if name.strip() in _PII_COOKIE_NAMES:
                masked_parts.append(f"{name.strip()}=<masked>")
            else:
                masked_parts.append(kv)
        else:
            masked_parts.append(kv)
    return "; ".join(masked_parts)


def _mask_cookies_list(cookies: list[dict]) -> list[dict]:
    """Return a copy of the cookie-jar entry list with PII values masked."""
    result: list[dict] = []
    for c in cookies:
        c2 = dict(c)
        if c2.get("name") in _PII_COOKIE_NAMES:
            c2["value"] = "<masked>"
        result.append(c2)
    return result


@dataclass
class VisitResults:
    """Everything we learn about visiting a single website."""

    website: str

    success: bool = True
    error_message: str | None = None

    screenshots_b64: list[str] = field(default_factory=list)
    request_info: list[dict] = field(default_factory=list)

    cookie_banner_info: str = ""

    diagnostic_log: dict | str = ""
    date_str: str = ""

    # Filled in by main.py around the scrape call so the per-site
    # info.json is self-contained.
    idx: int = 0
    duration_seconds: float = 0.0

    def save(self, dir: str | Path, folder_name: str) -> None:
        """Write this result into ``<dir>/<folder_name>/``."""
        directory = Path(dir)
        if not directory.exists() or not directory.is_dir():
            raise ValueError(f"Directory {directory} is faulty")

        sbdir = directory / folder_name
        sbdir.mkdir(exist_ok=False)

        info = {
            "idx": self.idx,
            "website": self.website,
            "success": self.success,
            "error_message": self.error_message,
            "cookie_banner": self.cookie_banner_info,
            "pixels_captured": len(self.request_info),
            "screenshots_taken": len(self.screenshots_b64),
            "duration_seconds": round(self.duration_seconds, 2),
            "date_of_visit": self.date_str,
            "diagnostic_log": self.diagnostic_log,
        }
        with open(sbdir / "info.json", "w", encoding="utf-8") as f:
            json.dump(info, f, indent=2)

        with open(sbdir / "request_info.json", "w", encoding="utf-8") as f:
            json.dump(self.request_info, f, indent=2)

        pic_dir = sbdir / "screenshots"
        pic_dir.mkdir()
        for i, screenshot_b64 in enumerate(self.screenshots_b64):
            with open(pic_dir / f"screenshot_{i}.png", "wb") as f:
                f.write(base64.b64decode(screenshot_b64))


class Scraper:
    def __init__(
        self,
        pixels: list[str],
        delete_user_data: bool = True,
        run_local: bool = True,
        use_proxy: bool = True,
        auth_profile_path: Path | None = None,
        mask_pii: bool = False,
    ) -> None:
        log.info(
            "Initialising Scraper (run_local=%s, use_proxy=%s, pixels=%d, "
            "auth_profile=%s, mask_pii=%s)",
            run_local, use_proxy, len(pixels),
            auth_profile_path or "<none>", mask_pii,
        )

        self.playwright = sync_playwright().start()
        self.mask_pii = mask_pii

        # If an auth profile is given, use it as the persistent Chromium
        # profile and DO NOT wipe it (it holds the logged-in cookies).
        # Otherwise use the default ./user-data dir and wipe per the
        # delete_user_data flag (anonymous mode).
        if auth_profile_path is not None:
            self.user_data_dir = Path(auth_profile_path)
            self.delete_user_data = False
            if not self.user_data_dir.exists():
                raise FileNotFoundError(
                    f"Auth profile directory does not exist: {self.user_data_dir}. "
                    f"Bootstrap it first: python -m src.auth_login --profile <name>"
                )
            log.info(
                "AUTH MODE: using persistent profile at %s (NOT wiping)",
                self.user_data_dir,
            )
        else:
            self.user_data_dir = Path("./user-data")
            self.delete_user_data = delete_user_data
            self._delete_user_data()

        self.context = self.playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.user_data_dir),
            headless=False,
            executable_path="/snap/bin/chromium" if not run_local else None,
            viewport={"width": 1280, "height": 800},
            locale="en-US",
            slow_mo=100,
            timezone_id="America/New_York",
            channel="chromium" if run_local else None,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-features=IsolateOrigins,site-per-process",
            ],
            ignore_default_args=["--enable-automation"],
            proxy={"server": "socks5://127.0.0.1:1080"} if use_proxy else None,
        )

        self.pixels = pixels
        log.info("Chromium launched successfully")

    # ------------------------------------------------------------------
    # User data cleanup
    # ------------------------------------------------------------------
    def _delete_user_data(self) -> None:
        if self.delete_user_data:
            shutil.rmtree(self.user_data_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    # Stealth / human-like behaviour
    # ------------------------------------------------------------------
    def _simulate_human_behavior(self, page: Page) -> None:
        page.wait_for_timeout(250)
        page.mouse.move(200, 300)
        page.wait_for_timeout(250)
        page.mouse.move(600, 400)
        page.wait_for_timeout(300)

    # ------------------------------------------------------------------
    # Diagnostic snapshot of a visit
    # ------------------------------------------------------------------
    def get_visit_log(self, page: Page, response: Response | None) -> dict:
        return {
            "status": response.status if response else None,
            "final_url": page.url,
            "title": page.title(),
            "user_agent": page.evaluate("navigator.userAgent"),
            "webdriver": page.evaluate("navigator.webdriver"),
        }

    # ------------------------------------------------------------------
    # The main visit method
    # ------------------------------------------------------------------
    def visit_website(
        self,
        website: str,
        delays: tuple[int, ...] = (3, 3, 4),
        capture: bool = True,
    ) -> VisitResults:
        results = VisitResults(
            website=website,
            date_str=datetime.now().strftime("%Y-%m-%d_%H-%M-%S"),
        )
        page = self.context.new_page()
        captured_data: list[dict] = []

        # Single listener using ``requestfinished`` — fires once per
        # completed pixel exchange with BOTH the request and response
        # available. This is more robust than separate request/response
        # listeners because Playwright's sync API does NOT guarantee
        # that ``response.request is request`` from the request event
        # (they wrap the same underlying Playwright object in distinct
        # Python proxies), which makes id()-based matching unreliable.
        def handle_request_finished(request: Request) -> None:
            if not any(pixel in request.url for pixel in self.pixels):
                return
            try:
                # --- Response side -----------------------------------
                response = request.response()
                response_status: int | None = (
                    response.status if response is not None else None
                )
                response_set_cookies: list[str] = []
                if response is not None:
                    # ``headers_array()`` preserves duplicate header
                    # names — important because ``Set-Cookie`` is
                    # commonly sent more than once on a single response.
                    response_set_cookies = [
                        h["value"]
                        for h in response.headers_array()
                        if h["name"].lower() == "set-cookie"
                    ]

                # --- Request side ------------------------------------
                parsed_url = urlparse(request.url)
                qs = parse_qs(parsed_url.query, keep_blank_values=True)
                url_params = {
                    k: (v[0] if len(v) == 1 else v) for k, v in qs.items()
                }

                payload = self._extract_payload(request)

                # ``request.headers`` (property) returns only the
                # script-level headers and omits headers added by
                # Chromium's network stack (notably Cookie). The
                # ``all_headers()`` method returns the full set as it
                # went on the wire.
                req_headers = request.all_headers()
                cookie_header = req_headers.get("cookie", "")
                other_req_headers = {
                    k: v for k, v in req_headers.items() if k != "cookie"
                }

                # The cookie jar Playwright holds for this URL. May
                # differ from cookie_header above when ``SameSite`` /
                # third-party-cookie rules cause the browser to withhold
                # some jar cookies from a specific request.
                cookies_in_jar = self.context.cookies(request.url)

                # Apply PII masking if requested. Masks c_user / xs / fr
                # values in both cookie_header (string) and cookies (list of
                # dicts) so the JSON we write is safe to share externally.
                if self.mask_pii:
                    cookie_header = _mask_cookie_header(cookie_header)
                    cookies_in_jar = _mask_cookies_list(cookies_in_jar)

                captured_data.append({
                    "request_url": request.url,
                    "request_method": request.method,
                    "url_host": parsed_url.netloc,
                    "url_path": parsed_url.path,
                    "url_params": url_params,
                    "post_data": payload,
                    "cookie_header": cookie_header,
                    "request_headers": other_req_headers,
                    "cookies": cookies_in_jar,
                    "response_status": response_status,
                    "response_set_cookies": response_set_cookies,
                })
                log.debug(
                    "captured pixel: %s %s -> %s  params=%d  "
                    "cookie_hdr=%dB  jar=%d  set_cookies=%d",
                    request.method, request.url[:100], response_status,
                    len(url_params), len(cookie_header),
                    len(cookies_in_jar), len(response_set_cookies),
                )
            except Exception as exc:
                # Don't fail the whole visit just because we couldn't
                # process one pixel — capture the error so the operator
                # can see it in the per-site output.
                log.warning(
                    "pixel capture failed for %s: %s: %s",
                    request.url[:120], type(exc).__name__, exc,
                )
                captured_data.append({
                    "request_url": request.url,
                    "request_method": request.method,
                    "url_host": "",
                    "url_path": "",
                    "url_params": {},
                    "post_data": None,
                    "cookie_header": "",
                    "request_headers": {},
                    "cookies": [],
                    "response_status": None,
                    "response_set_cookies": [],
                    "extract_error": f"{type(exc).__name__}: {exc}",
                })

        # Note: ``requestfinished`` fires after the response has been
        # fully received. Aborted / network-failed requests will NOT
        # appear here — they fire ``requestfailed`` instead. For our
        # tracker-pixel use case that's the right trade-off: a request
        # with no response has no Set-Cookie data worth capturing.
        page.on("requestfinished", handle_request_finished)

        try:
            log.debug("page.goto(%s)", website)

            # Retry on transient network/timeout issues.
            def _goto() -> Response | None:
                return page.goto(
                    website,
                    wait_until="domcontentloaded",
                    timeout=config.PAGE_GOTO_TIMEOUT_MS,
                )

            page_response = retry_with_backoff(
                _goto,
                max_attempts=config.PAGE_GOTO_MAX_ATTEMPTS,
                initial_delay=2.0,
                label=f"page.goto({website})",
            )

            results.diagnostic_log = self.get_visit_log(page, page_response)
            log.debug("diagnostic_log=%s", results.diagnostic_log)

            log.debug("simulating human behaviour")
            self._simulate_human_behavior(page)

            if capture:
                log.debug("capturing %d screenshots at delays=%s",
                          len(delays), delays)
                for delay in delays:
                    page.wait_for_timeout(delay * 1000)
                    results.screenshots_b64.append(self._get_screenshot(page))

            results.request_info = captured_data

        except Exception as exc:
            results.success = False
            results.error_message = f"{type(exc).__name__}: {exc}"
            log.warning("visit_website(%s) failed: %s", website, results.error_message)
        finally:
            page.close()

        return results

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _get_screenshot(self, page: Page) -> str:
        image_bytes = page.screenshot()
        return base64.b64encode(image_bytes).decode("utf-8")

    def _extract_payload(self, request: Request) -> dict | None:
        raw = request.post_data_buffer
        if not raw:
            return {"status": "empty"}

        def try_json(data: bytes) -> dict | list | None:
            try:
                return json.loads(data.decode("utf-8"))
            except Exception:
                return None

        # 1. Plain JSON
        parsed = try_json(raw)
        if parsed is not None:
            return parsed

        # 2. Compressed (gzip / brotli)
        for fn in (gzip.decompress, brotli.decompress):
            try:
                decompressed = fn(raw)
                parsed = try_json(decompressed)
                if parsed is not None:
                    return parsed
            except Exception:
                continue

        # 3. Base64-wrapped
        try:
            decoded = base64.b64decode(raw)
            parsed = try_json(decoded)
            if parsed is not None:
                return parsed
            return {
                "status": "base64_text",
                "data": decoded.decode("utf-8", errors="ignore"),
            }
        except Exception:
            pass

        # 4. Fallback: binary preview + base64 of raw bytes
        return {
            "status": "unparsable_binary",
            "preview": raw.decode("utf-8", errors="ignore")[:200],
            "raw_b64": base64.b64encode(raw).decode("ascii"),
        }

    # ------------------------------------------------------------------
    # Teardown
    # ------------------------------------------------------------------
    def end(self) -> None:
        log.info("Closing Chromium context")
        try:
            self.context.close()
        finally:
            self.playwright.stop()
            self._delete_user_data()
