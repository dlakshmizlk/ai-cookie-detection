<div style="text-align: justify;">

# Cookie Detection — Improvement Opportunities

> A grounded, code-aware analysis of what could be tightened, hardened, or re-shaped to take this project from "works on a single EC2 box" to "production-ready, maintainable, and pleasant to work on". Every suggestion is tied to specific files, lines, or behaviors in the existing codebase.

---

## Table of Contents

1. [How to Read This Document](#1-how-to-read-this-document)
2. [Priority Snapshot (TL;DR)](#2-priority-snapshot-tldr)
3. [Code Quality and Latent Bugs](#3-code-quality-and-latent-bugs)
   - [3.1 Mutable default argument in `visit_website`](#31-mutable-default-argument-in-visit_website)
   - [3.2 `GPTClient` re-created on every loop iteration](#32-gptclient-re-created-on-every-loop-iteration)
   - [3.3 Cross-cutting `success`/`error_message` writes from the request listener](#33-cross-cutting-successerror_message-writes-from-the-request-listener)
   - [3.4 Hard-coded magic strings and paths](#34-hard-coded-magic-strings-and-paths)
   - [3.5 Silent fallthrough in `_extract_payload`](#35-silent-fallthrough-in-_extract_payload)
   - [3.6 Dead code in `helper_funcs.py`](#36-dead-code-in-helper_funcspy)
   - [3.7 `prompt_message` lives at module scope](#37-prompt_message-lives-at-module-scope)
   - [3.8 `OpenAI key` reading is fragile](#38-openai-key-reading-is-fragile)
   - [3.9 Inconsistent pin discipline in `requirements.txt`](#39-inconsistent-pin-discipline-in-requirementstxt)
   - [3.10 `cookies` snapshot timing](#310-cookies-snapshot-timing)
4. [Architecture and Design](#4-architecture-and-design)
   - [4.1 Separate scrape from analyze](#41-separate-scrape-from-analyze)
   - [4.2 Introduce a job/task abstraction](#42-introduce-a-jobtask-abstraction)
   - [4.3 Persist results to a database, not only to disk](#43-persist-results-to-a-database-not-only-to-disk)
   - [4.4 Move configuration into one place](#44-move-configuration-into-one-place)
   - [4.5 Replace substring pixel matching with explicit rules](#45-replace-substring-pixel-matching-with-explicit-rules)
   - [4.6 One context per site, not one for the whole run](#46-one-context-per-site-not-one-for-the-whole-run)
5. [Security](#5-security)
   - [5.1 Do not bake `credentials/` into the Docker image](#51-do-not-bake-credentials-into-the-docker-image)
   - [5.2 Move secrets into a real secrets manager](#52-move-secrets-into-a-real-secrets-manager)
   - [5.3 Stop running the container as root](#53-stop-running-the-container-as-root)
   - [5.4 Tighten the EC2 security group](#54-tighten-the-ec2-security-group)
   - [5.5 Add image scanning to the build](#55-add-image-scanning-to-the-build)
   - [5.6 Avoid logging full URLs and payloads unredacted](#56-avoid-logging-full-urls-and-payloads-unredacted)
6. [Reliability and Error Handling](#6-reliability-and-error-handling)
   - [6.1 No retries on transient failures](#61-no-retries-on-transient-failures)
   - [6.2 The output directory is wiped on every run](#62-the-output-directory-is-wiped-on-every-run)
   - [6.3 No global timeout / no graceful shutdown](#63-no-global-timeout--no-graceful-shutdown)
   - [6.4 A single browser crash kills the whole run](#64-a-single-browser-crash-kills-the-whole-run)
   - [6.5 GPT API errors silently zero out the verdict](#65-gpt-api-errors-silently-zero-out-the-verdict)
7. [Observability and Logging](#7-observability-and-logging)
   - [7.1 Replace `print` with the `logging` module](#71-replace-print-with-the-logging-module)
   - [7.2 Emit a structured per-website log line](#72-emit-a-structured-per-website-log-line)
   - [7.3 Add basic metrics](#73-add-basic-metrics)
   - [7.4 Surface progress in a sidecar file](#74-surface-progress-in-a-sidecar-file)
8. [Performance and Scalability](#8-performance-and-scalability)
   - [8.1 Parallel browser workers](#81-parallel-browser-workers)
   - [8.2 Stream screenshots to disk instead of holding base64 in memory](#82-stream-screenshots-to-disk-instead-of-holding-base64-in-memory)
   - [8.3 Batch the GPT calls or downgrade the model](#83-batch-the-gpt-calls-or-downgrade-the-model)
   - [8.4 Stop loading at `domcontentloaded`-only](#84-stop-loading-at-domcontentloaded-only)
9. [Deployment and Infrastructure](#9-deployment-and-infrastructure)
   - [9.1 Move builds to CI; pull image at deploy time](#91-move-builds-to-ci-pull-image-at-deploy-time)
   - [9.2 Codify infrastructure with Terraform or CloudFormation](#92-codify-infrastructure-with-terraform-or-cloudformation)
   - [9.3 Replace ad-hoc EC2 with a scheduled task](#93-replace-ad-hoc-ec2-with-a-scheduled-task)
   - [9.4 Push outputs to S3 automatically](#94-push-outputs-to-s3-automatically)
   - [9.5 Pin Chromium](#95-pin-chromium)
   - [9.6 Multi-stage Docker build](#96-multi-stage-docker-build)
   - [9.7 Use `.env` only if you actually need it](#97-use-env-only-if-you-actually-need-it)
10. [Testing and Continuous Integration](#10-testing-and-continuous-integration)
    - [10.1 No tests today](#101-no-tests-today)
    - [10.2 What to test, and how](#102-what-to-test-and-how)
    - [10.3 Add CI on every push](#103-add-ci-on-every-push)
    - [10.4 Add a dry-run / offline mode](#104-add-a-dry-run--offline-mode)
11. [Developer Experience](#11-developer-experience)
    - [11.1 Adopt `pyproject.toml`](#111-adopt-pyprojecttoml)
    - [11.2 Add `ruff`, `black`, and `mypy`](#112-add-ruff-black-and-mypy)
    - [11.3 Add a `Makefile` or `justfile`](#113-add-a-makefile-or-justfile)
    - [11.4 Pre-commit hooks](#114-pre-commit-hooks)
    - [11.5 Devcontainer or Compose for local parity](#115-devcontainer-or-compose-for-local-parity)
12. [Documentation](#12-documentation)
    - [12.1 Promote `PROJECT_OVERVIEW.md` to a real architecture doc](#121-promote-project_overviewmd-to-a-real-architecture-doc)
    - [12.2 Add an ADR folder](#122-add-an-adr-folder)
    - [12.3 Document the input contract](#123-document-the-input-contract)
    - [12.4 Add a CHANGELOG](#124-add-a-changelog)
13. [Cost Optimization](#13-cost-optimization)
14. [Data Handling, Privacy, and Retention](#14-data-handling-privacy-and-retention)
15. [Suggested Phased Roadmap](#15-suggested-phased-roadmap)

---

## 1. How to Read This Document

Each suggestion has:

- **Where it shows up** — the actual file or behavior in the current codebase.
- **Why it matters** — the concrete risk, pain, or limitation.
- **What to do** — a focused change you (or a future contributor) can implement.

Suggestions are not features-for-the-sake-of-features. They are things that would meaningfully reduce risk, ease maintenance, or unlock real scale.

Tags used below:

- `[Quick]` — under an hour, near-zero risk.
- `[Medium]` — a few hours; touches multiple files.
- `[Large]` — a meaningful project; days, possibly behind a flag.

---

## 2. Priority Snapshot (TL;DR)

If you only address five things, address these — in this order:

| # | Improvement | Tag |
|---|---|---|
| 1 | Stop baking `credentials/` into the Docker image — bind-mount at runtime instead. See [§5.1](#51-do-not-bake-credentials-into-the-docker-image). | `[Quick]` |
| 2 | Don't wipe outputs on every run — write to a per-run subfolder. See [§6.2](#62-the-output-directory-is-wiped-on-every-run). | `[Quick]` |
| 3 | Add retries + a global timeout per website. See [§6.1](#61-no-retries-on-transient-failures) and [§6.3](#63-no-global-timeout--no-graceful-shutdown). | `[Medium]` |
| 4 | Replace `print()` with `logging`, add a structured one-line-per-site summary. See [§7](#7-observability-and-logging). | `[Quick]` |
| 5 | Add a minimal CI pipeline that lints, type-checks, and builds the image on every push. See [§10.3](#103-add-ci-on-every-push). | `[Medium]` |

Everything else compounds on top of these.

---

## 3. Code Quality and Latent Bugs

### 3.1 Mutable default argument in `visit_website`

**Where:** [src/scraper.py:117](src/scraper.py:117)

```python
def visit_website(self, website: str, delays: list[int] = [3, 3, 4], capture: bool = True):
```

**Why it matters:** Mutable default arguments are a classic Python footgun. The list is created **once** at function-definition time and **shared across calls**. If anything ever mutates `delays`, every subsequent call inherits the mutation. It is not buggy *today* because nothing mutates it, but linters will flag this and it is one of the easiest "don't think about it" bugs to inherit later. `[Quick]`

**What to do:**
```python
def visit_website(self, website: str, delays: tuple[int, ...] = (3, 3, 4), capture: bool = True):
```
Or accept `None` and assign inside the body.

### 3.2 `GPTClient` re-created on every loop iteration

**Where:** [src/main.py:50-60](src/main.py:50)

```python
for idx, website in enumerate(websites):
    ...
    if visit_results.success:
        client = GPTClient(api_key)  # new client every site
        response = client.ask_message(...)
```

**Why it matters:** Functionally fine, but wasteful — the `openai.OpenAI()` constructor does non-trivial setup (TLS, connection pool). Hoist it out of the loop so a single HTTP connection pool is reused across calls. `[Quick]`

**What to do:** Construct `client = GPTClient(api_key)` once **before** the loop and reuse.

### 3.3 Cross-cutting `success`/`error_message` writes from the request listener

**Where:** [src/scraper.py:125-141](src/scraper.py:125)

```python
def handle_request(request):
    if any(pixel in request.url for pixel in self.pixels):
        try:
            payload = self._extract_payload(request)
            ...
        except Exception as e:
            results.success = False
            results.error_message = f"Error: {e}"
```

**Why it matters:** The request-listener callback writes into the parent function's `results` object, which is also written by the main `try/except` of `visit_website`. So a transient payload-decode error in **one** captured pixel can flip the whole site's `success` to `False`, even though the page itself loaded fine. The two error channels should not be conflated.

**What to do:** Track pixel-capture errors per-pixel (e.g., `captured_data.append({..., "extract_error": str(e)})`), and reserve `results.success / results.error_message` for true page-visit failures.

### 3.4 Hard-coded magic strings and paths

**Where (a):** [src/input_manager.py:20-22](src/input_manager.py:20) — spreadsheet name `"cookie-banner"` is hard-coded.
**Where (b):** [src/scraper.py:74](src/scraper.py:74) — Chromium path `/snap/bin/chromium` is hard-coded; the Dockerfile creates a symlink just to satisfy it ([Dockerfile:14-15](Dockerfile:14)).
**Where (c):** [src/main.py:31, 35, 41](src/main.py:31) — credentials paths and `/app/outputs` are hard-coded.

**Why it matters:** Any of these constants might need to change per environment (dev vs. prod, different sheet, different OS). Right now changing one means editing source and rebuilding.

**What to do:** Move them to a single `src/config.py` (or read from environment variables) — e.g., `SPREADSHEET_NAME`, `CHROMIUM_PATH`, `OUTPUT_DIR`, `OPENAI_KEY_PATH`, `GOOGLE_CREDENTIALS_PATH`. The Dockerfile's symlink hack disappears once `CHROMIUM_PATH=/usr/bin/chromium` is the default in container. `[Quick]`

### 3.5 Silent fallthrough in `_extract_payload`

**Where:** [src/scraper.py:182-232](src/scraper.py:182)

The function tries JSON → gzip → brotli → base64 → "unparsable binary". The binary fallback returns the first 200 chars of the raw bytes decoded as UTF-8 with `errors="ignore"`. That preview is often useless for protobuf-style payloads.

**Why it matters:** You silently lose information about what the pixel actually sent. For analytics use cases this is exactly the data you wanted.

**What to do:** When the payload is unparsable, also store the **raw bytes** as a base64 string. That way the operator can later try their own decoders without re-scraping. `[Quick]`

### 3.6 Dead code in `helper_funcs.py`

**Where:** [src/helper_funcs.py:11-19](src/helper_funcs.py:11) — `b64_to_pil` is imported by nothing.

**Why it matters:** Dead code rots and confuses future readers ("am I supposed to use this?"). `[Quick]`

**What to do:** Delete it, or move it next to its first real caller.

### 3.7 `prompt_message` lives at module scope

**Where:** [src/gpt.py:7-28](src/gpt.py:7)

The very long prompt is a module-level constant. It is mixed with the `GPTClient` class definition, making the file harder to scan, and tweaking the prompt requires editing source.

**Why it matters:** Prompts are configuration — they change more often than client code. Treat them like data. `[Quick]`

**What to do:** Move prompts to `src/prompts/cookie_banner.txt` (or a `prompts.py`). Load on startup. Version the prompt in code reviews like any other content change.

### 3.8 OpenAI key reading is fragile

**Where:** [src/main.py:31-32](src/main.py:31)

```python
with open('credentials/openai-key.txt', 'r') as f:
    api_key = f.readline()
```

`f.readline()` includes the trailing `\n` if present. OpenAI's SDK will pass that into the `Authorization` header verbatim and you'll get a `401` with a non-obvious cause.

**Why it matters:** Cost-you-an-afternoon kind of bug if the operator pastes the key with a newline. `[Quick]`

**What to do:** `api_key = f.read().strip()` — and ideally read from an env var or secrets manager instead (see [§5.2](#52-move-secrets-into-a-real-secrets-manager)).

### 3.9 Inconsistent pin discipline in `requirements.txt`

**Where:** [requirements.txt:65-66](requirements.txt:65)

Most dependencies are exact-pinned. But `gspread` and `google-auth` are **unpinned**, so two builds a week apart can install different versions.

**Why it matters:** Reproducibility. If `gspread` ships a breaking change tomorrow, today's image still works but tomorrow's build fails for unrelated reasons. `[Quick]`

**What to do:** Pin everything. Regenerate the file with `pip freeze` from a known-good environment, or migrate to `uv` / `pip-tools` for proper lockfile management.

The file also includes Jupyter/IPython packages (`ipython`, `ipykernel`, `jupyter_client`, `jupyter_core`, `debugpy`) that the runtime does not import. They bloat the image. Move them to a separate `requirements-dev.txt`. `[Quick]`

### 3.10 `cookies` snapshot timing

**Where:** [src/scraper.py:136](src/scraper.py:136)

```python
"cookies": self.context.cookies(request.url),
```

This is fetched inside the `handle_request` callback **at the moment the request is observed**. That is usually the right moment, but cookies set by the *response* to that very request won't appear. Conversely, cookies set by a later response will leak into earlier captured records if you re-query.

**Why it matters:** Subtle correctness issue depending on what question the data is asked of.

**What to do:** Document explicitly that `cookies` represents browser state at request-fire time, not response-receive time. If response-time cookies are needed, hook `page.on("response", ...)` too.

---

## 4. Architecture and Design

### 4.1 Separate scrape from analyze

**Where:** [src/main.py:50-62](src/main.py:50)

Today, `main.py` interleaves "visit site" → "send screenshots to GPT" → "save". They run synchronously for every site. If GPT is slow or down, every site is slow or fails.

**Why it matters:** Coupling. The two concerns have very different reliability and cost profiles. Splitting them lets you:
- Re-run only the analysis if you tweak the prompt, without re-scraping.
- Tolerate OpenAI outages without losing the scrape.
- Parallelize the analysis independently. `[Medium]`

**What to do:** Two scripts (or two phases of one): `scrape.py` writes screenshots + `request_info.json` + a stub `info.json`. `analyze.py` walks the output tree and fills `cookie_banner` for any site missing it. Idempotent; re-runnable.

### 4.2 Introduce a job/task abstraction

**Where:** [src/main.py:50](src/main.py:50)

Sites are processed in a hard-coded `for` loop. There is no notion of "a job that ran on YYYY-MM-DD with these inputs and these results".

**Why it matters:** Once two people care about the output, you need to refer to runs by name, find the run that produced a given file, re-run a single failed site, etc. `[Medium]`

**What to do:** A `Run` has:
- a unique `run_id` (e.g. ISO timestamp),
- a `manifest.json` at the run root listing inputs + start/end times + per-site status,
- per-site subdirectories named by URL hash (not numeric index, which changes if the sheet is re-ordered).

This is what makes future improvements like "re-run only failed sites" trivial.

### 4.3 Persist results to a database, not only to disk

**Where:** [src/scraper.py:29-59](src/scraper.py:29)

`VisitResults.save()` only writes JSON to disk. To analyze trends ("did this site stop showing a banner last week?") you have to grep through folders.

**Why it matters:** As soon as you have ≥10 runs, "where did I see banner X" becomes friction.

**What to do:** Add an optional sink that also writes a row to SQLite (cheap, file-based, zero infra) or DynamoDB. Schema: `(run_id, website, success, cookie_banner, screenshot_paths, ...)`. The JSON-on-disk stays for raw artifacts. `[Medium]`

### 4.4 Move configuration into one place

There is no `config.py` today. Knobs are scattered: sheet name in `input_manager.py`, paths in `main.py`, Chromium args in `scraper.py`, prompt in `gpt.py`.

**Why it matters:** Knowing "what could I change?" requires reading every file. `[Quick]`

**What to do:** A single `src/config.py` that reads from environment variables (with sensible defaults). Document the env vars in the README.

### 4.5 Replace substring pixel matching with explicit rules

**Where:** [src/scraper.py:127](src/scraper.py:127)

```python
if any(pixel in request.url for pixel in self.pixels):
```

Substring matching is brittle: `"tr"` matches more than `connect.facebook.net/tr/`.

**Why it matters:** False positives or, worse, false negatives. The data downstream is only as good as the rules. `[Medium]`

**What to do:** Make each pixel rule structured:
```json
{ "name": "Meta Pixel", "host": "connect.facebook.net", "path_prefix": "/tr" }
```
or accept a regex. Keep backward-compat with a `kind: substring` rule.

### 4.6 One context per site, not one for the whole run

**Where:** [src/scraper.py:71](src/scraper.py:71)

The `launch_persistent_context` is created once; pages are opened against it for every site. Cookies, localStorage, and service workers from site A persist into site B.

**Why it matters:** Cross-site contamination skews analytics. A bidder pixel from site A might mark the visitor and influence what site B fires.

**What to do:** Either:
- Create a fresh context per site (slower, ~1-2 s startup per site), or
- Continue using one context but `context.clear_cookies()` and `context.clear_permissions()` between sites — fast and removes the most-common contamination vector. `[Quick]`

---

## 5. Security

### 5.1 Do not bake `credentials/` into the Docker image

**Where:** [.dockerignore](.dockerignore) does not list `credentials/`, and the Dockerfile does `COPY . .` ([Dockerfile:20](Dockerfile:20)).

**Why it matters:** Anyone who can `docker save` the image — or grab it off the EC2 disk — gets your OpenAI key and Google service-account JSON. The image becomes a secret.

**What to do:** `[Quick]`
1. Add `credentials/` to `.dockerignore`.
2. At runtime, bind-mount the credentials folder:
   ```bash
   docker run --rm \
     -v ~/cookie_detect/credentials:/app/credentials:ro \
     -v ~/cookie_detect_outputs:/app/outputs \
     cookie-detect
   ```
   (`:ro` makes the mount read-only — good defense.)
3. Update the deployment runbook (the EC2 README) accordingly.

### 5.2 Move secrets into a real secrets manager

For long-term operation, even mounted files are clunky. Better:

- Store the OpenAI key in **AWS Secrets Manager** or **SSM Parameter Store** (`SecureString`).
- Give the EC2 instance an **IAM role** that lets it read just that secret.
- At container start, fetch the secret and inject as an env var, e.g. via an entrypoint shim or `aws ssm get-parameter`.

**Why it matters:** Rotation, audit, no plaintext files on disk. `[Medium]`

### 5.3 Stop running the container as root

**Where:** [Dockerfile](Dockerfile) — no `USER` directive, so it runs as root. Combined with `--no-sandbox` in Chromium args ([src/scraper.py:84](src/scraper.py:84)), this is a small but real risk: a Chromium sandbox escape would land on root inside the container.

**Why it matters:** Defense in depth. Even if you trust the sites you visit today, the project's whole point is to visit arbitrary external sites whose JS you do not control.

**What to do:** `[Medium]`
1. Create a non-root user in the Dockerfile:
   ```dockerfile
   RUN useradd -m -u 1001 scraper
   USER scraper
   ```
2. Remove `--no-sandbox` and adjust kernel capabilities at run-time (`--cap-add=SYS_ADMIN` is one route; better is to grant a user-namespace and let Chromium's setuid sandbox work).

This is non-trivial; do it only after the easier fixes.

### 5.4 Tighten the EC2 security group

The recommended deployment opens port 22 only from your IP. Two extra hardenings:

- **Use SSM Session Manager** instead of opening port 22 at all. AWS lets you SSH into instances via the AWS console with no inbound rule.
- **Add VPC Flow Logs** so connection attempts are auditable.

**Why it matters:** Anything on the open internet attracts scans. Closing port 22 entirely removes a class of risk. `[Medium]`

### 5.5 Add image scanning to the build

**What to do:** Run `trivy image cookie-detect:latest` in CI. It catches CVEs in the base image and pip deps in seconds. Free, no vendor lock-in. `[Quick]`

### 5.6 Avoid logging full URLs and payloads unredacted

The captured pixel payloads can contain user identifiers, hashed emails, IP addresses, device IDs. The screenshots can contain user-visible PII. Treat the `outputs/` tree as **sensitive data** with all the responsibility that implies (storage encryption, access controls, retention policy — see [§14](#14-data-handling-privacy-and-retention)).

---

## 6. Reliability and Error Handling

### 6.1 No retries on transient failures

**Where:** [src/scraper.py:146-167](src/scraper.py:146) — `page.goto(...)` runs once; if the network blips, the site is marked failed forever.

**Why it matters:** A 5-second DNS hiccup ruins a 30-minute run.

**What to do:** Wrap the visit in a `tenacity` retry (3 attempts, exponential backoff, only on `TimeoutError` / network errors — not on `ValueError`). Same for the OpenAI call. `[Quick]`

### 6.2 The output directory is wiped on every run

**Where:** [src/main.py:42-43](src/main.py:42)

```python
shutil.rmtree(out_dir, ignore_errors=True)
out_dir.mkdir(parents=True, exist_ok=True)
```

**Why it matters:** Every run obliterates the previous. Forget to `scp` results off the host before a re-run? They're gone. `[Quick]`

**What to do:** Write to `out_dir / run_id` where `run_id` is a timestamp. Keep a `latest` symlink for convenience. Old runs accumulate; cleanup is a separate concern (cron + retention).

### 6.3 No global timeout / no graceful shutdown

**Where:** [src/scraper.py:149](src/scraper.py:149) — only the `page.goto` has a 45-s timeout. The 3+3+4 s screenshot delays plus banner detection have no upper bound. If GPT-4.1 takes 90 s, you wait 90 s.

**Why it matters:** One stuck site can stall the whole run. There is no SIGINT/SIGTERM handling either, so a `docker stop` will leak a Chromium child process.

**What to do:** `[Medium]`
- Per-site wall-clock budget (e.g., 60 s), enforced with `asyncio.wait_for` or a signal-based watchdog.
- A `try/finally` in `Scraper.end()` that always closes the context, with `atexit` and SIGTERM handlers.

### 6.4 A single browser crash kills the whole run

**Where:** [src/scraper.py:65](src/scraper.py:65) — one Playwright instance shared across all sites.

**Why it matters:** If Chromium segfaults on site 47 of 200, all later sites fail too.

**What to do:** `[Medium]` Detect "context closed" exceptions and re-launch the context for subsequent sites. Or simpler: per-batch-of-N restart of the browser.

### 6.5 GPT API errors silently zero out the verdict

**Where:** [src/main.py:54-60](src/main.py:54)

There is no `try/except` around `client.ask_message(...)`. If the API call raises, the entire program crashes mid-run.

**Why it matters:** Saw a `RateLimitError`? You lose every site after that one.

**What to do:** `[Quick]` Wrap the call. On failure, set `visit_results.cookie_banner_info = ""` and add an `analysis_error` field. Continue to the next site.

---

## 7. Observability and Logging

### 7.1 Replace `print` with the `logging` module

**Where:** [src/main.py:26, 51, 63](src/main.py:26), [src/scraper.py:147, 153, 156](src/scraper.py:147)

`print()` mixes with `flush=True` to keep Docker logs live, but it has no severity, no timestamps, no structure.

**Why it matters:** When something goes wrong in production you want `WARNING` and `ERROR` to stand out. `[Quick]`

**What to do:**
```python
import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger(__name__)
log.info("Processing %s", website)
```

### 7.2 Emit a structured per-website log line

A single JSON line per visit summarizing duration, success, status code, banner verdict, # of pixels captured. Easy to grep, easy to feed into anything later (CloudWatch Logs Insights, Datadog, jq).

```json
{"ts": "...", "site": "https://x", "ok": true, "ms": 9123, "pixels": 7, "banner": "YES"}
```
`[Quick]`

### 7.3 Add basic metrics

Even without a metrics backend, write per-run counters to `outputs/<run_id>/metrics.json`:

```json
{ "sites_total": 200, "sites_ok": 192, "sites_failed": 8, "banner_yes": 144, "banner_no": 48, "duration_seconds": 3120 }
```

If/when you adopt CloudWatch / Prometheus / etc., point the same emit function at it. `[Quick]`

### 7.4 Surface progress in a sidecar file

Long runs benefit from a `outputs/<run_id>/progress.txt` that gets a line per site as it completes. SSH-in, `tail -f`, watch progress without keeping the docker logs stream open. `[Quick]`

---

## 8. Performance and Scalability

### 8.1 Parallel browser workers

**Where:** [src/main.py:50](src/main.py:50) — `for idx, website in enumerate(websites)`. Sites are visited one at a time.

**Why it matters:** Wall-clock time scales linearly. 1000 sites at ~12 s each ≈ 3 h 20 m. A 4-way parallel scrape brings that under an hour at the cost of more RAM and outbound bandwidth.

**What to do:** `[Large]`
- Move to `playwright.async_api` and use an `asyncio.Semaphore(4)` to bound concurrency.
- Or, simpler: keep sync Playwright but spawn `N` worker processes each handling 1/N of the sites.
- Each worker writes to its own per-site folder; no shared mutable state.

Watch out: per-site contexts ([§4.6](#46-one-context-per-site-not-one-for-the-whole-run)) become necessary, not optional, under parallelism.

### 8.2 Stream screenshots to disk instead of holding base64 in memory

**Where:** [src/scraper.py:159-160](src/scraper.py:159)

```python
results.screenshots_b64.append(self._get_screenshot(page))
```

`screenshots_b64` is a list of base64 strings held in memory until `save()`. For 200 sites × 3 screenshots × ~200 KB each ≈ 120 MB resident. On a `t3.small` (2 GB) that competes with Chromium.

**Why it matters:** Memory pressure at scale.

**What to do:** Write each screenshot to disk **immediately** (`page.screenshot(path=...)`) and store only paths in `VisitResults`. Re-read the file when feeding GPT. `[Quick]`

### 8.3 Batch the GPT calls or downgrade the model

The whole prompt is essentially "look at 3 images, tell me if a banner exists". GPT-4.1 is overkill. `gpt-4o-mini` (or similar smaller vision-capable model) cuts cost ~30× with comparable accuracy on this kind of crisp visual classification.

**What to do:** `[Quick]` Make the model name a config value (env var). Try `gpt-4o-mini` on a sample of 50 sites; compare verdicts to the `gpt-4.1` ones; if they match ≥98% of the time, switch.

### 8.4 Stop loading at `domcontentloaded`-only

**Where:** [src/scraper.py:149](src/scraper.py:149)

```python
page.goto(website, wait_until="domcontentloaded", timeout=45000)
```

`domcontentloaded` fires once the HTML is parsed — before most third-party scripts run. Cookie banners are usually injected by those scripts. The fixed 3+3+4 s sleeps partially compensate, but they're a guess.

**What to do:** `[Medium]` Use `wait_until="networkidle"` (waits until network goes quiet) **with** a hard timeout, then take the first screenshot. You get more deterministic capture timing and can probably drop one of the 3 screenshots.

---

## 9. Deployment and Infrastructure

### 9.1 Move builds to CI; pull image at deploy time

**Today:** The README has you `git pull && docker build` on the EC2 host. Two problems:
- Build state lives on the host. If the disk is wiped, you re-build from scratch.
- Build needs the source tree, which means the EC2 host needs GitHub access (deploy keys).

**Why it matters:** Slower iteration, more secrets on the host. `[Medium]`

**What to do:**
- Have GitHub Actions build the image on every push to `main`.
- Push it to **Amazon ECR** (a private Docker image registry inside AWS).
- On the EC2 host, just `docker pull <ecr-uri>:latest && docker run ...`.

### 9.2 Codify infrastructure with Terraform or CloudFormation

**Today:** EC2 is launched by clicking buttons in the Console. Repeatability lives in a deployment doc, not code.

**Why it matters:** Tomorrow's instance won't match today's. You can't diff infra changes. `[Medium]`

**What to do:** A small Terraform module: `aws_instance`, `aws_security_group`, `aws_key_pair`, `aws_iam_role`. `terraform apply` becomes the standard way to provision.

### 9.3 Replace ad-hoc EC2 with a scheduled task

If this scraper runs on a schedule (daily/weekly), an always-on EC2 box is overkill — it sits idle 23 h/day.

**Better fits:**
- **AWS Batch / ECS Scheduled Tasks** — launches a Fargate container on cron, runs scraper, exits.
- **GitHub Actions** with a self-hosted runner — if you're already in GH.
- **A `cron` job on the EC2 box** with `tmux` — cheap but still pays for idle time. `[Medium-Large]`

### 9.4 Push outputs to S3 automatically

**Today:** Results stay on the EC2 disk until you `scp` them off.

**Why it matters:** If the instance is terminated, results are lost. If multiple people want to consume results, they have to take turns. `[Quick]`

**What to do:**
- Create an S3 bucket with versioning + server-side encryption.
- After each run, `aws s3 sync ~/cookie_detect_outputs/<run_id> s3://bucket/<run_id>/`.
- Attach an IAM role to the EC2 instance with `s3:PutObject` permission on that bucket.

### 9.5 Pin Chromium

**Where:** [Dockerfile:8-12](Dockerfile:8)

```dockerfile
RUN apt-get install -y --no-install-recommends chromium xvfb xauth
```

`apt-get` installs whichever version is current at build time. If Chromium ships a behavior change that breaks the scraper, you can't reproduce yesterday's working image.

**What to do:** `[Medium]`
- Pin to a specific Chromium version, or
- Use Playwright's bundled browser binary (`playwright install chromium`) instead of system Chromium, which is the canonical way to control which Chromium runs.

### 9.6 Multi-stage Docker build

**Today:** Build deps (Jupyter, pip itself, apt indexes) end up in the final image. The image is ~1.2 GB.

**What to do:** `[Medium]` Split into a builder stage that does `pip install --target /deps -r requirements.txt`, and a runtime stage that `COPY --from=builder /deps /app/deps`. Cuts image size and surface area.

### 9.7 Use `.env` only if you actually need it

The current `docker run` includes `--env-file .env`, but the code reads nothing from the environment. Either:

- Drop `--env-file` (cleanest), or
- Start reading config from env vars (best — see [§4.4](#44-move-configuration-into-one-place)).

The current state — pass an empty `.env` to satisfy a flag — is the worst of both. `[Quick]`

---

## 10. Testing and Continuous Integration

### 10.1 No tests today

**Where:** There is no `tests/` folder. Zero unit, integration, or end-to-end tests.

**Why it matters:** Any change carries the risk of silently breaking a downstream consumer. Refactors are "do it carefully and pray".

### 10.2 What to test, and how

`[Medium]`

| What to test | How |
|---|---|
| `_extract_payload` decoders | Unit test with fixture bytes (JSON / gzip / brotli / base64 / random binary). No browser needed. |
| `normalize_url` | Trivial unit tests. |
| `InputManager.get_column_by_name` | Fake `gspread.Worksheet` (a small mock object with `.row_values` / `.col_values`). |
| `VisitResults.save` | Pass a `tmp_path` fixture, assert the produced files. |
| `Scraper.visit_website` happy-path | Spin up a local static site with `python -m http.server`, point the scraper at it, assert it captures the requests we know it makes. |

Use **`pytest`**. Keep the browser-touching tests in a separate marker (`@pytest.mark.browser`) so CI can run them only on capable runners.

### 10.3 Add CI on every push

A minimal `.github/workflows/ci.yml`:

```yaml
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.14" }
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - run: ruff check src
      - run: mypy src
      - run: pytest -m "not browser"
      - run: docker build -t cookie-detect:ci .
```

`[Medium]`

### 10.4 Add a dry-run / offline mode

A `--no-gpt` flag that runs the scraper without making any OpenAI calls. Cheap end-to-end smoke-test that exercises Playwright and the file-saving logic without burning API credits. `[Quick]`

---

## 11. Developer Experience

### 11.1 Adopt `pyproject.toml`

**Today:** `requirements.txt` only. No `[project]` metadata, no script entry points.

**What to do:** Move dependencies into `pyproject.toml` (PEP 621). Define `[project.scripts]` so you can install the project and run `cookie-detect` instead of `python -m src.main`. Pairs naturally with `uv` for fast deterministic installs. `[Medium]`

### 11.2 Add `ruff`, `black`, and `mypy`

- **`ruff`** — fast Python linter, catches dozens of footguns (including [§3.1](#31-mutable-default-argument-in-visit_website)).
- **`black`** — opinionated formatter; ends "where do braces go" debates forever.
- **`mypy` (or `pyright`)** — static type-checking. The codebase already uses type hints in some places; lock that in.

Configure all three in `pyproject.toml`. Run them in CI ([§10.3](#103-add-ci-on-every-push)). `[Quick]`

### 11.3 Add a `Makefile` or `justfile`

So humans don't have to remember the long `docker run` line.

```makefile
build:
    docker build -t cookie-detect .

run:
    docker run --rm \
        -v $(PWD)/credentials:/app/credentials:ro \
        -v $(PWD)/outputs:/app/outputs \
        cookie-detect

test:
    pytest -m "not browser"

lint:
    ruff check src && mypy src
```
`[Quick]`

### 11.4 Pre-commit hooks

`pre-commit` config that runs `ruff --fix`, `black`, and `trailing-whitespace` before each commit. Saves CI from rejecting trivial style issues. `[Quick]`

### 11.5 Devcontainer or Compose for local parity

Today, running the scraper locally on a Mac means Chromium behaves differently than inside the Docker image (which is why the `--run_local` flag has a different `executable_path`). A `docker-compose.yml` that lets you run the EXACT production image against a local mount removes that drift. `[Medium]`

---

## 12. Documentation

### 12.1 Promote `PROJECT_OVERVIEW.md` to a real architecture doc

The overview is solid (you're reading the result of the same audit). Keep it as the single source of truth, **link to it from the README**, and add:

- A simple architecture diagram (one PNG — Mermaid in Markdown also works).
- An "Inputs and outputs" reference table for each module.
- A "How to run on your laptop in 5 minutes" section. The README only describes the EC2 path. `[Quick]`

### 12.2 Add an ADR folder

**ADR = Architecture Decision Record.** A `docs/adr/0001-use-headed-chromium-with-xvfb.md`-style file per non-obvious decision (why headed not headless, why GPT and not regex, why Google Sheets and not a config file). Future-you will thank present-you. `[Quick]`

### 12.3 Document the input contract

The spreadsheet's expected columns (`websites`, `pixels`) and the rules (case-sensitive sheet name, first tab only, header in row 1) live only in code. Drop a `docs/input-format.md`. `[Quick]`

### 12.4 Add a CHANGELOG

`CHANGELOG.md` in Keep-A-Changelog format. Every PR adds a bullet. When EC2 misbehaves, the changelog tells you what changed last week without spelunking through git. `[Quick]`

---

## 13. Cost Optimization

| Lever | Effect | Tag |
|---|---|---|
| Stop the EC2 instance when not running a scrape (~$30/mo saved on a `t3.medium`). | High. | `[Quick]` |
| Use an EC2 **Spot** instance (60–80% cheaper) — fine because runs are batch and resumable. | High, if jobs are re-runnable. | `[Medium]` |
| Switch from `gpt-4.1` to `gpt-4o-mini` for banner detection ([§8.3](#83-batch-the-gpt-calls-or-downgrade-the-model)). | OpenAI costs cut by ~30×. | `[Quick]` |
| Move to Fargate scheduled tasks (pay only during the run). | Cleanest for batch workloads. | `[Medium-Large]` |
| Use S3 Intelligent-Tiering for old runs. | Pennies, but the right hygiene. | `[Quick]` |
| Set CloudWatch billing alarms. | Catch surprises early. | `[Quick]` |

---

## 14. Data Handling, Privacy, and Retention

The `request_info.json` files and the screenshots are not innocuous: they can contain hashed emails, device IDs, IPs, and a literal picture of a third-party website's UI at a moment in time.

**Concrete recommendations:**

1. **Encryption at rest.** Whichever S3 bucket or EBS volume holds outputs should have SSE enabled (S3 default is now AES-256; verify).
2. **Retention policy.** Decide and document: e.g., "raw outputs deleted after 90 days; only aggregated stats kept." Implement with an S3 lifecycle rule.
3. **Access control.** Only the operators who need raw screenshots should have access. Use IAM policies, not "everyone with the bucket name".
4. **Robots.txt / TOS.** This project drives a real browser against arbitrary third-party sites. Make sure the engagement and legal posture allows that.
5. **Watermark/identify your traffic.** Optionally, set a custom `User-Agent` so site owners can identify and contact you if they care. (You currently strip Playwright's automation marks but don't add a contactable identifier.)

---

## 15. Suggested Phased Roadmap

If you can only do this in phases, here is a defensible order:

**Phase 1 — Make it safer and more durable (1-2 days).** `[Quick]` items only.
- §5.1 credentials out of image
- §6.2 per-run output folder
- §6.5 swallow GPT errors
- §3.8 strip newline on key
- §3.9 pin everything; split dev deps
- §7.1 + §7.2 logging
- §11.2 + §11.3 ruff/black/mypy + Makefile

Outcome: same behavior, much less likely to surprise you.

**Phase 2 — Make it observable and testable (3-5 days).** Mostly `[Medium]`.
- §10.2 + §10.3 tests + CI
- §6.1 retries
- §6.3 timeouts and signal handling
- §7.3 metrics
- §9.1 + §9.5 image to ECR + pinned Chromium
- §12.x documentation refresh

Outcome: changes are reviewable and rollbacks are trivial.

**Phase 3 — Make it operational (1-2 weeks).** A mix.
- §5.2 secrets manager
- §9.2 Terraform
- §9.3 scheduled task (Fargate)
- §9.4 S3 outputs
- §4.1 + §4.2 scrape/analyze split + run-id model

Outcome: no manual deployment, no manual data transfer, no manual triggers.

**Phase 4 — Scale (when you actually need it).**
- §8.1 parallel workers
- §4.3 database sink
- §4.5 structured pixel rules
- §4.6 per-site contexts

Outcome: 10× sites without 10× wall-clock time.

---

When deployment time comes, we will revisit a couple of these (specifically §5.1, §6.2, and §9.7) before the first run, because they are essentially free wins. The rest can be sequenced as time and need allow.

</div>
