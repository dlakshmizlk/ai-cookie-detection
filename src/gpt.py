"""OpenAI client wrapper used for cookie-banner detection.

The prompt below is the single source of truth for what we're asking
the model. Tweak it here.
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path

from openai import OpenAI

from src import config
from src.retry import retry_with_backoff

log = logging.getLogger(__name__)


prompt_message = """
You are reviewing multiple screenshots from the same website, captured at different moments in time.

Your task is to determine whether a cookie banner, cookie notice, consent banner, privacy preferences popup, or tracking-consent prompt appears in any screenshot.

Carefully inspect every screenshot.

A cookie banner may mention cookies, tracking, consent, privacy choices, personalized ads, accepting/rejecting cookies, managing preferences, or similar language.

If at least one screenshot contains a cookie banner, respond in exactly this format:

YES - <exact visible banner text>

Rules:
- Quote only the visible banner text.
- Do not summarize or paraphrase the banner text.
- Do not include unrelated page text.
- If the banner text is partially obscured, include only the text that is clearly visible.

If no screenshot contains a cookie banner, respond exactly:
NONE
"""


class GPTClient:
    def __init__(self, api_key: str) -> None:
        self.client = OpenAI(
            api_key=api_key,
            timeout=config.GPT_TIMEOUT_SECONDS,
        )
        log.debug(
            "GPTClient initialised (model=%s, timeout=%.1fs, retries=%d)",
            config.GPT_MODEL, config.GPT_TIMEOUT_SECONDS, config.GPT_MAX_RETRIES,
        )

    def _decode_image(self, image_path: str | Path) -> str:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def ask_message(self, message: str, img_path_or_b64) -> str:
        """Send a prompt + one or more screenshots, return the model's text."""
        content: list[dict] = [
            {"type": "input_text", "text": message},
        ]

        if not isinstance(img_path_or_b64, list):
            img_path_or_b64 = [img_path_or_b64]

        for img in img_path_or_b64:
            if isinstance(img, (str, Path)) and str(img).lower().endswith(
                (".png", ".jpg", ".jpeg")
            ):
                img_b64 = self._decode_image(img)
            else:
                img_b64 = img
            content.append({
                "type": "input_image",
                "image_url": f"data:image/png;base64,{img_b64}",
            })

        log.debug(
            "Calling OpenAI model=%s with %d image(s)",
            config.GPT_MODEL, len(content) - 1,
        )

        def _call():
            return self.client.responses.create(
                model=config.GPT_MODEL,
                input=[{"role": "user", "content": content}],
            )

        response = retry_with_backoff(
            _call,
            max_attempts=config.GPT_MAX_RETRIES,
            initial_delay=2.0,
            label="openai.responses.create",
        )
        return response.output_text
