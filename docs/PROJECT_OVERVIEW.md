<div style="text-align: justify;">

# Cookie Detection — Project Overview

> A complete, end-to-end walkthrough of this codebase, written for someone who has never seen the project before. Read this first; we will move on to EC2 deployment only after you are comfortable with everything below.

---

## Table of Contents

1. [High-Level Summary](#1-high-level-summary)
2. [What Problem Does This Project Solve?](#2-what-problem-does-this-project-solve)
3. [Key Concepts You Need to Know First](#3-key-concepts-you-need-to-know-first)
   - [3.1 What is a "cookie banner"?](#31-what-is-a-cookie-banner)
   - [3.2 What is a "tracking pixel"?](#32-what-is-a-tracking-pixel)
   - [3.3 What is Playwright?](#33-what-is-playwright)
   - [3.4 What is a headed vs headless browser, and why Xvfb?](#34-what-is-a-headed-vs-headless-browser-and-why-xvfb)
   - [3.5 What is a Google Service Account?](#35-what-is-a-google-service-account)
4. [Repository Layout](#4-repository-layout)
5. [End-to-End Data Flow](#5-end-to-end-data-flow)
6. [File-by-File Code Walkthrough](#6-file-by-file-code-walkthrough)
   - [6.1 `src/main.py` — the entry point](#61-srcmainpy--the-entry-point)
   - [6.2 `src/input_manager.py` — reading the Google Sheet](#62-srcinput_managerpy--reading-the-google-sheet)
   - [6.3 `src/scraper.py` — the browser automation engine](#63-srcscraperpy--the-browser-automation-engine)
   - [6.4 `src/gpt.py` — asking GPT to read the screenshots](#64-srcgptpy--asking-gpt-to-read-the-screenshots)
   - [6.5 `src/helper_funcs.py` — small utilities](#65-srchelper_funcspy--small-utilities)
7. [Dependencies (`requirements.txt`)](#7-dependencies-requirementstxt)
8. [The Dockerfile, Explained Line by Line](#8-the-dockerfile-explained-line-by-line)
9. [Configuration, Secrets, and Credentials](#9-configuration-secrets-and-credentials)
10. [Command-Line Flags and Run Modes](#10-command-line-flags-and-run-modes)
11. [Output Files Produced by a Run](#11-output-files-produced-by-a-run)
12. [Important Caveats and Gotchas](#12-important-caveats-and-gotchas)
13. [Glossary of Terms](#13-glossary-of-terms)
14. [What You Need to Have Ready Before Deployment](#14-what-you-need-to-have-ready-before-deployment)

---

## 1. High-Level Summary

This project is a **Python web scraper** that automates a real Chrome browser to visit a list of websites and check two things for each one:

1. **Does the website show a cookie consent banner?**
   It does this by taking screenshots and asking **OpenAI GPT-4.1** to look at them and answer "YES" (with the visible banner text) or "NONE".

2. **Which tracking pixels (e.g., Google Analytics, Facebook Pixel, etc.) does the website fire, and what data do they send?**
   It does this by intercepting the website's outgoing network requests in real time, filtering them by a list of "pixel URL fragments" you provide, and saving the request URL, HTTP method, post body (decoded from JSON / gzip / brotli / base64 where possible), and the browser's cookies.

For every website it visits, it writes a folder under `outputs/` (or `/app/outputs/` inside Docker) containing:
- a JSON file with the cookie-banner verdict and diagnostic info,
- a JSON file with all captured tracking-pixel requests,
- the screenshots (PNG files) it took.

The list of websites to visit and the list of tracking-pixel URL fragments are **read from a Google Sheet** (not committed to the repo) using a Google service account.

The project is **packaged as a Docker image** so it can run consistently on an Ubuntu EC2 virtual machine. Because the browser runs in **headed mode** (not headless — many anti-bot systems block headless Chrome), the Docker container starts a **virtual display server (Xvfb)** so the browser has somewhere to "draw" even though no monitor is attached.

---

## 2. What Problem Does This Project Solve?

The team needs to audit how a list of websites handles user privacy:

- **Compliance angle:** Do they show a cookie banner asking for consent (as required under laws like GDPR / CCPA)?
- **Data-leakage angle:** What third-party tracking pixels fire when a user just lands on the page, and what data do those pixels send (URLs, cookies, payloads)?

Doing this manually for many sites is slow, error-prone, and inconsistent. This project automates it: feed it a spreadsheet of sites and pixel signatures, and it produces a structured per-site report you can inspect later.

---

## 3. Key Concepts You Need to Know First

### 3.1 What is a "cookie banner"?

A small overlay that appears on a website asking the visitor to **accept**, **reject**, or **customize** cookies / tracking. Examples: "We use cookies to improve your experience. [Accept All] [Reject All] [Manage Preferences]". The project tries to detect whether such a banner shows up, and if so, captures its visible text verbatim.

### 3.2 What is a "tracking pixel"?

A tiny network request a website fires off (often to a third party like Google, Meta/Facebook, TikTok, etc.) that reports things like "this user visited this page". The project recognizes a pixel by matching **substrings** in the outgoing request URL — e.g., if `google-analytics.com` is in your pixel list, then any request URL containing that string is captured.

Each captured pixel record includes:
- The full request URL.
- HTTP method (GET, POST, etc.).
- The POST body (decoded if it was JSON, gzipped, brotli-compressed, or base64-encoded).
- The cookies the browser had for that URL at the time.

### 3.3 What is Playwright?

[Playwright](https://playwright.dev/python/) is a Python library that programmatically drives a real browser (Chromium / Chrome / Firefox / WebKit). The project uses Playwright to:
- Launch Chromium with realistic settings (custom viewport, US timezone, mouse movements, etc.) to look less like a bot.
- Navigate to each site.
- Listen for every network request the page makes.
- Take screenshots.

### 3.4 What is a headed vs headless browser, and why Xvfb?

- **Headless** browser = runs without drawing anything on a screen. Faster, lighter, but **many websites detect and block it**.
- **Headed** browser = draws a real window, exactly like when you open Chrome on your laptop. Harder for anti-bot systems to detect.

This project explicitly runs Chromium **headed** (`headless=False` in `scraper.py`). But a server like EC2 has no monitor, so there is nothing to "draw" on — the browser would refuse to start.

**Xvfb** ("X Virtual Frame Buffer") is a fake display server. The Dockerfile installs it and the command `xvfb-run -a python -u -m src.main` starts a virtual screen, then runs the scraper inside that virtual screen. Chromium happily believes there is a monitor.

### 3.5 What is a Google Service Account?

To read the Google Sheet of websites and pixels, the project authenticates as a non-human "service account" — a special Google identity with its own JSON credentials file. You share the Google Sheet with the service account's email address (just like sharing a Google Doc), and then the script can read it.

The JSON key file lives at `credentials/google-drive-key.json` (not committed to the repo — see [§9](#9-configuration-secrets-and-credentials)).

---

## 4. Repository Layout

```
cookie-detection/
├── .dockerignore         # Files Docker should NOT copy into the image
├── .gitignore            # Files git should NOT track (secrets, outputs, etc.)
├── Dockerfile            # Recipe for building the Docker image
├── README.md             # Short EC2 + Docker runbook
├── requirements.txt      # Pinned Python dependencies
└── src/
    ├── main.py           # Entry point — orchestrates the whole run
    ├── input_manager.py  # Reads websites + pixels from a Google Sheet
    ├── scraper.py        # Browser automation, screenshotting, network capture
    ├── gpt.py            # Sends screenshots to OpenAI to detect cookie banners
    └── helper_funcs.py   # Small URL / image utilities
```

There are only **5 Python files** total. The codebase is small and focused.

Things that are intentionally **not** in the repo (but the running code needs):
- `credentials/openai-key.txt` — your OpenAI API key.
- `credentials/google-drive-key.json` — the Google service account JSON.
- `outputs/` — created at runtime; holds results.
- `user-data/` — created at runtime by Playwright as Chromium's profile directory.
- `.env` — referenced in the README's `docker run` command via `--env-file .env`, but the code itself does not actually read any env vars. See [§9](#9-configuration-secrets-and-credentials) and [§12](#12-important-caveats-and-gotchas).

---

## 5. End-to-End Data Flow

Here is exactly what happens, in order, when you run the program:

```
                ┌────────────────────────────────────────────────────┐
                │   1. main.py starts                                │
                │   - parses CLI flags (--run_local, --use_proxy)    │
                │   - reads OpenAI key from credentials/             │
                └─────────────────────┬──────────────────────────────┘
                                      │
                                      ▼
                ┌────────────────────────────────────────────────────┐
                │   2. InputManager loads Google Sheet "cookie-banner"│
                │   - authenticates with google-drive-key.json       │
                │   - reads "websites" column   → list of URLs       │
                │   - reads "pixels"   column   → list of substrings │
                └─────────────────────┬──────────────────────────────┘
                                      │
                                      ▼
                ┌────────────────────────────────────────────────────┐
                │   3. Wipe & recreate output dir                    │
                │   - local mode: ./outputs                          │
                │   - docker:     /app/outputs (mounted from host)   │
                └─────────────────────┬──────────────────────────────┘
                                      │
                                      ▼
                ┌────────────────────────────────────────────────────┐
                │   4. Scraper boots a single Chromium browser       │
                │   - persistent context (./user-data/, then wiped)  │
                │   - headed, 1280x800, en-US, America/New_York      │
                │   - anti-automation flags / stealth                │
                │   - optional SOCKS5 proxy at 127.0.0.1:1080        │
                └─────────────────────┬──────────────────────────────┘
                                      │
                ┌─────────────────────┴──────────────────────────────┐
                │   FOR EACH WEBSITE in the list:                    │
                │                                                    │
                │   5a. Open a new page                              │
                │   5b. Attach a request listener that:              │
                │       - watches every outgoing request             │
                │       - keeps only ones whose URL contains a pixel │
                │       - extracts the POST body & current cookies   │
                │   5c. page.goto(website), wait for DOM ready       │
                │   5d. Move the mouse around (look human)           │
                │   5e. Wait 3s → screenshot                         │
                │       Wait 3s → screenshot                         │
                │       Wait 4s → screenshot                         │
                │   5f. Close the page                               │
                │                                                    │
                │   6. If the visit succeeded:                       │
                │       - Send all 3 screenshots to GPT-4.1          │
                │       - GPT returns either                         │
                │         "YES - <banner text>" or "NONE"            │
                │                                                    │
                │   7. Write outputs/website_NNN/                    │
                │       - info.json         (metadata + verdict)     │
                │       - request_info.json (captured pixel calls)   │
                │       - screenshots/screenshot_0.png … _2.png      │
                └─────────────────────┬──────────────────────────────┘
                                      │
                                      ▼
                ┌────────────────────────────────────────────────────┐
                │   8. Close browser, stop Playwright, delete        │
                │      user-data/                                    │
                └────────────────────────────────────────────────────┘
```

---

## 6. File-by-File Code Walkthrough

### 6.1 `src/main.py` — the entry point

This is the script that actually runs when you do `python -m src.main`. It is small and procedural — read top to bottom and it tells the whole story.

**What it does, step by step:**

1. **Parses two CLI flags** (via `argparse`):
   - `--run_local`: switches paths and Chromium settings appropriate for running on a laptop instead of inside the Docker container on EC2.
   - `--use_proxy`: makes the browser route through a local SOCKS5 proxy at `127.0.0.1:1080`. Per the README's "Notes" section, the Docker setup **does not use the proxy flow** — so on EC2 this flag is left off.

2. **Reads the OpenAI API key** from `credentials/openai-key.txt`. Just a plain-text file with the key on the first line.

3. **Constructs an `InputManager`**, passing it the path to the Google service account JSON. The `InputManager` immediately authenticates and pulls the spreadsheet (see [§6.2](#62-srcinput_managerpy--reading-the-google-sheet)).

4. **Picks the output directory:**
   - With `--run_local`: `./outputs`
   - Without (the EC2/Docker default): `/app/outputs` (this is the path that the Dockerfile uses and that the `docker run -v ...` mount targets).
   - It then **deletes and recreates** the directory — meaning **every run wipes previous results** in that directory.

5. **Gets `websites` and `pixels`** from the `InputManager`.

6. **Creates a single `Scraper`** that boots one Chromium browser, then loops over the websites:
   - For each website, calls `scraper.visit_website(website)`.
   - If the visit succeeded, instantiates a `GPTClient` and sends the screenshots to GPT for banner detection.
   - Calls `visit_results.save(out_dir, idx=idx)` to write the per-website folder.

7. **Cleans up** by calling `scraper.end()`, which closes the browser, stops Playwright, and deletes Chromium's user-data folder.

> Note: a fresh `GPTClient` is created **inside the per-website loop**, not once outside. Functionally fine — the `OpenAI()` client is cheap — but worth knowing.

### 6.2 `src/input_manager.py` — reading the Google Sheet

The `InputManager` class is the bridge to the Google Sheet that holds the inputs.

**Key details:**

- It uses `gspread` (a Python wrapper around the Google Sheets API) plus `google.oauth2.service_account.Credentials`.
- The required OAuth scopes are `spreadsheets` and `drive`.
- It loads the credentials from the JSON file path you pass to the constructor (in practice: `credentials/google-drive-key.json`).
- It **opens a spreadsheet by name: `"cookie-banner"`** — so the Google Sheet shared with the service account must literally be named `cookie-banner`. (If the sheet is renamed, the code breaks.)
- It uses `spreadsheet.sheet1` — i.e. the **first tab** only.

**Expected sheet layout:**

The first row is treated as headers. The code requires two specific header values: `pixels` and `websites`.

| websites              | pixels                        |
|-----------------------|-------------------------------|
| example.com           | google-analytics.com          |
| https://foo.com/      | googletagmanager.com          |
| bar.org               | facebook.com/tr               |
| ...                   | doubleclick.net               |

- `websites`: each row is a URL to visit. Missing `https://` is fine — `normalize_url()` (see [§6.5](#65-srchelper_funcspy--small-utilities)) prepends `https://`.
- `pixels`: each row is a **substring** to look for inside outgoing request URLs. Anything matching is captured.

`get_column_by_name(name)` finds the column index of a header in row 1 and returns every value below it (header row excluded). If the header is missing it raises `ValueError` with a helpful message listing what headers were actually found.

### 6.3 `src/scraper.py` — the browser automation engine

This is the most complex file. It defines two things:

#### a) `VisitResults` (a `@dataclass`)

A container for everything we learn about one website visit:
- `website`: the URL.
- `success`: `True` unless something went wrong.
- `error_message`: filled in on failure.
- `screenshots_b64`: a list of PNG screenshots, base64-encoded as strings.
- `request_info`: a list of dicts, one per captured tracking-pixel request.
- `cookie_banner_info`: filled in later by GPT (`"YES - ..."` or `"NONE"`).
- `diagnostic_log`: a dict with HTTP status, final URL after redirects, page title, navigator.userAgent string, and `navigator.webdriver` (a flag many sites use to detect automation — should be `False`/`undefined` ideally).
- `date_str`: timestamp of the visit, formatted like `2026-05-20_14-30-15`.

`VisitResults.save(dir, idx)` writes the data to disk under `<out_dir>/website_<idx:03d>/`:
- `info.json` — metadata + the banner verdict + the diagnostic log.
- `request_info.json` — the captured pixel calls.
- `screenshots/screenshot_N.png` — the screenshots, decoded from base64 to PNG bytes.

#### b) `Scraper` (the class that actually drives the browser)

**Constructor (`__init__`):**

- Starts Playwright.
- Wipes the local `./user-data/` directory (fresh browser profile every run — no leftover cookies / cache).
- Launches a **persistent Chromium context** with carefully chosen settings:
  - `user_data_dir`: `./user-data` — Playwright stores profile data here.
  - `headless=False` — **visible browser** (see [§3.4](#34-what-is-a-headed-vs-headless-browser-and-why-xvfb)).
  - `executable_path="/snap/bin/chromium"` when not running locally — i.e., inside Docker, it uses the system Chromium installed via `apt-get` (the Dockerfile symlinks `/usr/bin/chromium` to `/snap/bin/chromium`, see [§8](#8-the-dockerfile-explained-line-by-line)).
  - `viewport=1280x800`, `locale="en-US"`, `timezone_id="America/New_York"` — looks like a US desktop user.
  - `slow_mo=100` — adds a 100 ms pause between Playwright actions, helping avoid bot detection.
  - `args=[...]` — a list of Chromium flags that hide common automation fingerprints:
    - `--disable-blink-features=AutomationControlled` (key one — removes the `navigator.webdriver = true` signal),
    - `--disable-infobars`,
    - `--no-sandbox`, `--disable-dev-shm-usage` (needed when running as root in Docker / on low-memory containers),
    - `--disable-features=IsolateOrigins,site-per-process` (helps when sites use strict cross-origin iframes / WAF rules).
  - `ignore_default_args=["--enable-automation"]` — strips the default "I am being automated" flag Playwright would otherwise pass.
  - `proxy={"server": "socks5://127.0.0.1:1080"}` if `--use_proxy` was given. (Not used in the Docker / EC2 flow.)

- Stores the list of pixel substrings on `self.pixels`.

**`visit_website(website, delays=[3,3,4], capture=True)`** — the workhorse:

1. Creates a fresh `VisitResults` for this visit.
2. Opens a new tab (`page`).
3. Defines an inner `handle_request(request)` callback. **For every outgoing request the page makes**, it checks if the URL contains any of the pixel substrings. If yes, it extracts:
   - `request_url`
   - `request_method`
   - `post_data` (decoded — see `_extract_payload` below)
   - `cookies` (from the context, scoped to that URL)
   and appends to a local `captured_data` list.
4. Attaches the listener: `page.on("request", handle_request)` — **before** navigation, so initial pixels are not missed.
5. `page.goto(website, wait_until="domcontentloaded", timeout=45000)` — load the page, wait until basic DOM is ready, give up after 45 s.
6. Records diagnostic info (status, final URL, title, user agent, webdriver flag).
7. Calls `_simulate_human_behavior(page)` — moves the mouse around: `(200, 300)` → `(600, 400)` with short waits in between. Some pixels only fire after user interaction; this nudges them.
8. If `capture=True` (the default), iterates over `delays = [3, 3, 4]`:
   - Wait 3 s, take a screenshot.
   - Wait another 3 s, take another screenshot.
   - Wait another 4 s, take a third screenshot.
   - So screenshots are taken at roughly **3 s, 6 s, and 10 s** after the page finished loading. This spread lets the model see the page both before and after lazy banners / interstitials appear.
9. Saves `captured_data` into `results.request_info`.
10. Any exception during all of this sets `success=False` and stores the error.
11. Closes the page (the browser context stays alive for the next site).
12. Returns the populated `VisitResults`.

**`_extract_payload(request)`** — decodes the POST body of a captured pixel request. It tries, in order:

1. Plain JSON (`json.loads(raw)`).
2. **Gzip-decompressed** JSON.
3. **Brotli-decompressed** JSON.
4. **Base64-decoded** JSON; if base64 decodes to plain text but not JSON, it returns `{"status": "base64_text", "data": ...}`.
5. Fallback: a binary preview (`{"status": "unparsable_binary", "preview": ...}`) — usually means the payload is in a binary format like protobuf, which we don't try to parse.

This matters because tracking pixels routinely send compressed or binary payloads; the project tries hard to surface readable JSON when it can.

**`get_visit_log(page, response)`** — returns the dict that becomes `diagnostic_log`. The `navigator.webdriver` value here is especially useful for confirming the stealth flags worked.

**`end()`** — closes the persistent context, stops Playwright, and deletes `./user-data/`.

### 6.4 `src/gpt.py` — asking GPT to read the screenshots

Two things live here.

#### a) `prompt_message` (the system instruction)

A carefully written natural-language instruction to GPT:

> "You are reviewing multiple screenshots from the same website... Determine whether a cookie banner... appears in any screenshot... If yes, respond exactly `YES - <exact visible banner text>`. If no, respond exactly `NONE`."

Key details of the prompt:
- It tells the model to quote banner text **verbatim**, not summarize.
- It defines the strict response format the downstream code expects (`"YES - ..."` or `"NONE"`).

#### b) `GPTClient`

A thin wrapper over the official `openai` Python SDK.

- `__init__(api_key)`: instantiates `OpenAI(api_key=api_key)`.
- `_decode_image(image_path)`: reads a PNG/JPG from disk and base64-encodes it.
- `ask_message(message, img_path_or_b64)`:
  - Builds a list of content blocks: first the text prompt, then one image block per screenshot.
  - Each image is sent as a data URL: `data:image/png;base64,<encoded>`.
  - Calls `self.client.responses.create(model="gpt-4.1", input=[...])` — this uses OpenAI's **Responses API** (not the older Chat Completions API).
  - Returns `response.output_text` — the model's plain-text reply.

So when `main.py` calls `client.ask_message(message=prompt_message, img_path_or_b64=visit_results.screenshots_b64)`, GPT-4.1 is shown the prompt plus all 3 base64 screenshots in a single request, and replies with a single string.

### 6.5 `src/helper_funcs.py` — small utilities

Two helpers, both straightforward:

- `normalize_url(url)` — strips whitespace and prepends `https://` if neither `http://` nor `https://` is present. Used to clean the values coming out of the spreadsheet.
- `b64_to_pil(b64_string)` — turns a base64 string into a `PIL.Image.Image`. Handles the optional `data:image/png;base64,...` prefix. **It is defined but not currently imported anywhere else** — likely leftover utility code.

---

## 7. Dependencies (`requirements.txt`)

The requirements are heavily pinned (exact versions for almost everything). The most important entries:

| Package                              | Why it's here                                                  |
|--------------------------------------|----------------------------------------------------------------|
| `playwright==1.57.0`                 | Browser automation library.                                    |
| `playwright-stealth==1.0.6`          | Bot-evasion helpers (imported transitively / future use).      |
| `openai==2.26.0`                     | OpenAI SDK; uses the Responses API in `gpt.py`.                |
| `pillow==12.2.0`                     | Image handling (used in `helper_funcs.b64_to_pil`).            |
| `brotli==1.2.0`                      | Decompressing brotli-encoded pixel payloads.                   |
| `pandas==2.3.3`, `openpyxl==3.1.5`   | Tabular / Excel handling. Not used by current code paths but pinned.|
| `gspread`                            | Reading the Google Sheet.                                      |
| `google-auth`                        | OAuth credentials for the service account.                     |
| `httpx`, `requests`, `urllib3`, ...  | Networking dependencies of the above.                          |
| `ipython`, `ipykernel`, `jupyter_*`  | Dev / notebook tooling — not used at runtime in production.    |
| `python-dotenv`                      | Loading `.env` files. Imported transitively; the project code itself does not call `load_dotenv()`. |

The Jupyter/IPython packages add a lot of weight but no runtime function for the scraper. They can be trimmed later if you want a smaller image.

Two non-pinned entries (`gspread`, `google-auth`) will install the **latest** version at build time — a small reproducibility risk.

---

## 8. The Dockerfile, Explained Line by Line

```dockerfile
FROM python:3.14-slim
```
Start from the official Python 3.14 image, "slim" variant (smaller, fewer pre-installed packages).

```dockerfile
WORKDIR /app
```
All subsequent commands run from `/app`. Code will live in `/app`, outputs at `/app/outputs`.

```dockerfile
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
```
- `PYTHONUNBUFFERED=1`: print logs immediately, don't buffer (important so `docker logs` shows progress live).
- `PYTHONDONTWRITEBYTECODE=1`: don't create `.pyc` files (keeps the container clean).

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    xvfb \
    xauth \
  && rm -rf /var/lib/apt/lists/*
```
Install three system packages and clean up the apt cache afterward:
- `chromium`: the actual Chrome-based browser the scraper drives.
- `xvfb`: the **X Virtual Frame Buffer** — fake display server, see [§3.4](#34-what-is-a-headed-vs-headless-browser-and-why-xvfb).
- `xauth`: lets Xvfb properly hand out display authentication tokens to Chromium.

```dockerfile
RUN mkdir -p /snap/bin && ln -s /usr/bin/chromium /snap/bin/chromium
```
The Python code in `scraper.py` looks for Chromium at `/snap/bin/chromium` (the Ubuntu snap path). On a Debian-slim base image, Chromium lives at `/usr/bin/chromium`. This line creates a **symlink** so the Python code can keep its hardcoded path and still find the binary.

```dockerfile
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
```
Install the Python dependencies. Done **before** copying the rest of the code so Docker can cache this layer — if you change source files but not `requirements.txt`, this step will not re-run.

```dockerfile
COPY . .
```
Copy the project source (respecting `.dockerignore`) into `/app`. Files **excluded by `.dockerignore`** include: `.venv/`, `.git/`, `__pycache__/`, `*.pyc`, `.DS_Store`, the SSH key `.pem`, `outputs/`, and `.env`. Notably, the `credentials/` folder is **not** in `.dockerignore`, so if it exists locally during the build it would be copied in — but on EC2 it is provided after-the-fact via `scp`, not at build time.

```dockerfile
CMD ["sh", "-c", "echo CONTAINER STARTED; xvfb-run -a python -u -m src.main"]
```
The default command when the container starts:
1. Prints `CONTAINER STARTED` so you can see in logs that it began.
2. Runs `xvfb-run -a python -u -m src.main`:
   - `xvfb-run -a` — start a virtual X display and run the next command inside it; `-a` auto-picks a free display number.
   - `python -u -m src.main` — run our `src/main.py` as a module (so `from src.gpt import ...` works correctly), with unbuffered output (`-u`).

> Because the `CMD` uses `xvfb-run`, the container **cannot easily be passed CLI flags** like `--run_local` or `--use_proxy` without overriding the CMD on `docker run`. On EC2 we run **without** those flags — the defaults are correct for Docker.

---

## 9. Configuration, Secrets, and Credentials

Three things must be in place **before the container can do useful work**:

1. **`credentials/openai-key.txt`** — a plain-text file containing your OpenAI API key on the first line. The code reads it with `open('credentials/openai-key.txt', 'r')` from the current working directory (`/app` inside Docker). The key must have access to the `gpt-4.1` model.

2. **`credentials/google-drive-key.json`** — the JSON file downloaded when you create a Google Cloud service account. The service account's email must be **added as a viewer (or editor)** on the Google Sheet named `cookie-banner`. The sheet's first tab must contain a `websites` column and a `pixels` column.

3. **The Google Sheet "cookie-banner"** — must exist, be named exactly that, and contain the two columns above.

`.env` and `--env-file .env`:

- The README's `docker run` command includes `--env-file .env`. Looking at the code, **no environment variables are actually consumed by the Python files** — secrets are read from the `credentials/` folder, not from env vars. So you can pass an empty `.env` (or remove the flag) without affecting behavior. The flag is there as a placeholder in case you later add env-driven settings (e.g., a proxy URL, a webhook for posting results, etc.). On EC2 you can create an empty file with `touch .env` so the `docker run` command does not fail.

`.gitignore` / `.dockerignore` keep secrets out of git history and out of the Docker image at build time. **Do not commit anything in `credentials/` to the repository.**

---

## 10. Command-Line Flags and Run Modes

The two flags `main.py` accepts:

| Flag           | Default | Effect when set                                                                                  |
|----------------|---------|---------------------------------------------------------------------------------------------------|
| `--run_local`  | off     | Output dir = `./outputs` instead of `/app/outputs`. Chromium uses the local-mode launch (`channel='chromium'`, no hardcoded `executable_path`). |
| `--use_proxy`  | off     | Routes the browser through `socks5://127.0.0.1:1080`. Assumes you have set up a SOCKS proxy yourself (e.g., via SSH tunnel).                    |

Three sensible run modes:

1. **Local dev, no proxy** — `python -m src.main --run_local`. Output goes to `./outputs`. The browser pops up on your screen.
2. **EC2 inside Docker, no proxy (the README's intended setup)** — the container's `CMD` runs `python -u -m src.main` (no flags). Output goes to `/app/outputs`, which the `docker run -v ~/cookie_detect_outputs:/app/outputs` mount maps onto the EC2 host's home dir.
3. **Local with proxy** — `python -m src.main --run_local --use_proxy`. You must have a SOCKS5 proxy running on `localhost:1080` first.

---

## 11. Output Files Produced by a Run

For a run with N websites, you get:

```
outputs/
├── website_000/
│   ├── info.json
│   ├── request_info.json
│   └── screenshots/
│       ├── screenshot_0.png
│       ├── screenshot_1.png
│       └── screenshot_2.png
├── website_001/
│   ├── info.json
│   ├── request_info.json
│   └── screenshots/
│       ├── screenshot_0.png
│       ├── screenshot_1.png
│       └── screenshot_2.png
└── ...
```

**`info.json`** — example shape:

```json
{
  "website": "https://example.com",
  "success": true,
  "error_message": null,
  "cookie_banner": "YES - We use cookies to enhance your experience. Accept All | Reject All | Manage Preferences",
  "diagnostic_log": {
    "Status": 200,
    "Final URL": "https://example.com/",
    "Title": "Example Domain",
    "User agent": "Mozilla/5.0 ... Chrome/...",
    "webdriver": false
  },
  "date_of_visit": "2026-05-20_14-30-15"
}
```

**`request_info.json`** — an array of captured pixel calls:

```json
[
  {
    "request_url": "https://www.google-analytics.com/g/collect?...",
    "request_method": "POST",
    "post_data": { "...parsed JSON or status string..." },
    "cookies": [ {"name": "_ga", "value": "...", "domain": ".example.com", ...}, ... ]
  },
  ...
]
```

**`screenshots/screenshot_*.png`** — the actual PNG screenshots, full-viewport (1280x800), taken at roughly 3 s, 6 s, and 10 s after page load.

> Reminder: each run **deletes the output directory** and recreates it. Copy results off the EC2 host before re-running, or change `out_dir` if you want to preserve history.

---

## 12. Important Caveats and Gotchas

These are things that will bite you later if you don't know them:

1. **Output directory is wiped on every run.** `shutil.rmtree(out_dir, ignore_errors=True)` runs near the top of `main.py`. On EC2, with the README's mount, this wipes `~/cookie_detect_outputs` on the host. Copy outputs off before re-running.

2. **The browser runs headed.** Inside Docker on EC2 this is only possible because of Xvfb. If you ever change `CMD` and drop the `xvfb-run` wrapper, Chromium will crash with errors like "missing X server". Do not switch the code to `headless=True` lightly — many target sites detect it and behave differently.

3. **The `credentials/` folder is not built into the image.** It is `scp`'d onto the EC2 host into `~/cookie_detect/credentials` *after* the image is built. Because `docker run` is launched from `~/cookie_detect`, and `COPY . .` already happened during build, the **credentials must be present at build time** for the running container to see them — **or** the run command must mount the credentials folder. Re-check this carefully when deploying: the current `README.md` step ordering (scp credentials, then build, then run) means the credentials folder will be `COPY`'d in at build time, which works but means the image contains your secrets. We will tighten this up during deployment.

4. **`--env-file .env` is required by the run command but the code does not read env vars.** On a fresh EC2 host you must `touch .env` (or remove the flag) or `docker run` will error out: `open .env: no such file or directory`.

5. **The spreadsheet must be named exactly `cookie-banner`** and must have a tab whose **first row contains the headers `websites` and `pixels`**. Anything else and `InputManager` will fail loudly.

6. **Pixel matching is `substring` matching, not regex or exact host matching.** So `tr` in your pixel list would match a lot of unrelated URLs. Pixel entries should be specific enough to avoid false positives (e.g. `connect.facebook.net/`, not just `facebook`).

7. **Anti-bot is best-effort, not bulletproof.** Some sites with strong WAFs (Akamai, Cloudflare Bot Management, DataDome) will still block the scraper. The `diagnostic_log.Status` field is the first place to look when a visit "succeeds" but no pixels fire — a 403 there explains it.

8. **`gpt-4.1` model name and the Responses API.** The code uses `model="gpt-4.1"` via `client.responses.create(...)`. If the OpenAI key does not have access to that model, the cookie-banner detection step will throw and `cookie_banner_info` will remain `""`. The visit-level data still gets saved.

9. **No retry / no parallelism.** Websites are visited one by one in a single browser, sequentially. A long list will take a long time. There is no failover / retry on transient errors — a flaky network will just mark that site as `success: false`.

10. **`b64_to_pil` in `helper_funcs.py` is dead code today.** Not an issue, just noting.

11. **README assumes a fixed EC2 host** (`ec2-3-131-85-149.us-east-2.compute.amazonaws.com`). If you spin up a new EC2 instance during deployment, that hostname will change and the SSH / `scp` commands must be updated accordingly.

---

## 13. Glossary of Terms

| Term | Meaning |
|------|---------|
| **EC2** | Amazon Elastic Compute Cloud — a virtual server you rent from AWS. Our deployment target. |
| **Docker** | Tool that packages an application + its dependencies + its OS environment into a portable "image" you can run as a "container". |
| **Docker image** | The packaged blueprint (built once via `docker build`). |
| **Docker container** | A running instance of an image (started via `docker run`). |
| **Dockerfile** | A text file with build instructions for an image. |
| **Headless browser** | A browser with no visible UI window. Faster but easier to detect. |
| **Xvfb** | "X Virtual Frame Buffer" — fakes a display so headed browsers can run on a server. |
| **Playwright** | Python library for driving real browsers programmatically. |
| **Tracking pixel** | A small HTTP request a site makes to a third party to report analytics / advertising data. |
| **Cookie banner** | The overlay asking the user to accept/reject cookies. |
| **SOCKS5 proxy** | A network proxy protocol; here used optionally to route browser traffic through a different IP. |
| **Service account** | A non-human Google identity used by code to access Google APIs (Drive, Sheets, etc.). |
| **gspread** | Python wrapper for the Google Sheets API. |
| **Responses API** | OpenAI's newer chat/agent API used by `gpt.py`. |
| **Stealth flags** | Chromium launch flags that hide automation fingerprints. |
| **base64** | A way of encoding binary data (like a PNG screenshot) as plain text. |
| **brotli / gzip** | Compression algorithms — many tracking pixels send compressed payloads. |
| **SSH** | Secure Shell — remote-login protocol; how you'll get into EC2. |
| **scp** | Secure Copy — copies files over SSH between local machine and EC2. |
| **`.pem` file** | Private key for SSH'ing into EC2. Treat as a secret; never commit. |

---

## 14. What You Need to Have Ready Before Deployment

Once you are comfortable with everything above, we will move to EC2 deployment. To make that smooth, please confirm or gather the following beforehand — we will go through them one by one when we start:

1. **AWS account access**, with permission to launch / connect to an EC2 instance.
2. **An EC2 instance** (Ubuntu, ideally 22.04 or 24.04, with at least 2 GB RAM — Chromium is heavy).
3. **The `.pem` SSH key** for that instance, downloaded to your local machine and `chmod 400`'d.
4. **The EC2 instance's public DNS / IP**, plus the username (usually `ubuntu` for Ubuntu AMIs).
5. **The OpenAI API key** (as a plain string), with access to `gpt-4.1`.
6. **The Google service account JSON** (the contents of `credentials/google-drive-key.json`).
7. **Confirmation that the Google Sheet named `cookie-banner` is shared with that service account's email** and has the `websites` and `pixels` columns.
8. **The GitHub repository URL** (and either deploy-key access or HTTPS-with-token access) — the README assumes `git@github.com:MarcusBluestone/cookie_detection.git`.
9. **Where you want outputs to live** on EC2 (the README uses `~/cookie_detect_outputs`) and where you want them copied to on your local machine afterward.

When you're ready, tell me — we'll go through SSH'ing in, installing Docker, getting the code onto the instance, dropping the credentials in safely, building the image, running it, and pulling the results back. Step by step, no jumping ahead.

</div>