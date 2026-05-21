<div style="text-align: justify;">

# EC2 Deployment Guide — Cookie Detection Project

> A complete, beginner-first walkthrough. We assume **zero** prior knowledge of AWS, EC2, Linux, SSH, Docker, networking, or deployment. Every step is explained both as **what to do** and **why we are doing it**. Read sections in order — later steps depend on earlier ones.

---

## Table of Contents

1. [How to Use This Guide](#1-how-to-use-this-guide)
2. [Foundational Concepts (read this first)](#2-foundational-concepts-read-this-first)
   - [2.1 What is "deployment"?](#21-what-is-deployment)
   - [2.2 What is a server?](#22-what-is-a-server)
   - [2.3 What is "the cloud"?](#23-what-is-the-cloud)
   - [2.4 What is AWS?](#24-what-is-aws)
   - [2.5 What is EC2?](#25-what-is-ec2)
   - [2.6 What is an "instance"?](#26-what-is-an-instance)
   - [2.7 What is an AMI?](#27-what-is-an-ami)
   - [2.8 What is an instance type?](#28-what-is-an-instance-type)
   - [2.9 What is an AWS region?](#29-what-is-an-aws-region)
   - [2.10 What is a key pair (and a `.pem` file)?](#210-what-is-a-key-pair-and-a-pem-file)
   - [2.11 What is a security group?](#211-what-is-a-security-group)
   - [2.12 What is SSH?](#212-what-is-ssh)
   - [2.13 What is Linux / Ubuntu?](#213-what-is-linux--ubuntu)
   - [2.14 The handful of Linux commands you actually need](#214-the-handful-of-linux-commands-you-actually-need)
   - [2.15 What is Docker?](#215-what-is-docker)
   - [2.16 What are environment variables and `.env` files?](#216-what-are-environment-variables-and-env-files)
   - [2.17 What is Git and what is a "deploy key"?](#217-what-is-git-and-what-is-a-deploy-key)
3. [Prerequisites Checklist](#3-prerequisites-checklist)
4. [Part A — Sign In to AWS and Pick a Region](#4-part-a--sign-in-to-aws-and-pick-a-region)
5. [Part B — Launch the EC2 Instance (AWS Console)](#5-part-b--launch-the-ec2-instance-aws-console)
6. [Part C — Prepare Your SSH Key on Your Laptop](#6-part-c--prepare-your-ssh-key-on-your-laptop)
7. [Part D — Connect to the Instance via SSH](#7-part-d--connect-to-the-instance-via-ssh)
8. [Part E — Install Docker on the Instance](#8-part-e--install-docker-on-the-instance)
9. [Part F — Set Up GitHub Access from the Instance](#9-part-f--set-up-github-access-from-the-instance)
10. [Part G — Clone the Project Repository](#10-part-g--clone-the-project-repository)
11. [Part H — Provide the Credentials Files](#11-part-h--provide-the-credentials-files)
12. [Part I — Create an Empty `.env` File](#12-part-i--create-an-empty-env-file)
13. [Part J — Build the Docker Image](#13-part-j--build-the-docker-image)
14. [Part K — Run the Container (the Actual Deployment)](#14-part-k--run-the-container-the-actual-deployment)
15. [Part L — Verify the Outputs on EC2](#15-part-l--verify-the-outputs-on-ec2)
16. [Part M — Copy the Outputs Back to Your Laptop](#16-part-m--copy-the-outputs-back-to-your-laptop)
17. [Part N — Re-Running After Code Changes](#17-part-n--re-running-after-code-changes)
18. [Part O — Stopping vs Terminating the Instance (Cost Control)](#18-part-o--stopping-vs-terminating-the-instance-cost-control)
19. [Troubleshooting](#19-troubleshooting)
20. [Quick Reference — Cheat Sheet](#20-quick-reference--cheat-sheet)
21. [Appendix — Useful Optional Improvements](#21-appendix--useful-optional-improvements)

---

## 1. How to Use This Guide

- **Read [Section 2](#2-foundational-concepts-read-this-first) end-to-end first.** It teaches the vocabulary the rest of the guide uses.
- Each "Part" (A through O) is a discrete deployment step. Do them in order.
- Anything in `monospaced font` is something you type into a terminal or paste into a browser.
- Commands prefixed with `local$` are run **on your laptop**.
- Commands prefixed with `ec2$` are run **inside the EC2 instance after you have SSH'd in**.
- If something does not match what you see on screen, jump to [Troubleshooting](#19-troubleshooting) before re-trying.
- Take your time. Nothing in here is reversible in a destructive way, except where the guide explicitly warns you (e.g., "terminate instance").

---

## 2. Foundational Concepts (read this first)

### 2.1 What is "deployment"?

"Deployment" is the act of taking software that runs on your laptop and getting it to run on a computer somewhere else — typically a computer that runs 24/7 and that you (or other people) can reach over the internet. For this project, "deploying" means: run our Python scraper on an Amazon-owned virtual computer (an EC2 instance) instead of on your MacBook.

### 2.2 What is a server?

A **server** is just a computer whose job is to run software for other computers. It doesn't usually have a monitor or keyboard attached. You interact with it remotely (over the network) using tools like SSH. In our case, the "server" is an EC2 instance.

### 2.3 What is "the cloud"?

"The cloud" is marketing-speak for **renting computers from a big provider** (Amazon, Google, Microsoft, etc.) by the hour. You don't own the hardware; you pay only while you use it. The actual machines live in giant climate-controlled buildings called **data centers** owned by the provider.

### 2.4 What is AWS?

**Amazon Web Services (AWS)** is Amazon's cloud platform. It offers ~200 different services. We will use exactly one of them: **EC2**.

### 2.5 What is EC2?

**EC2 = Elastic Compute Cloud.** It is the AWS service for renting virtual computers. You click some buttons, and a few minutes later you have a Linux computer running on Amazon's hardware that you can SSH into and use.

"Elastic" just means you can create or destroy these computers on demand.

### 2.6 What is an "instance"?

In AWS lingo, one virtual computer that you've rented from EC2 is called an **instance**. So "launching an instance" = "starting up a new virtual computer". "Terminating an instance" = "permanently deleting it" (you stop paying for it, but you also lose everything that was on its disk).

### 2.7 What is an AMI?

An **AMI** (Amazon Machine Image) is a pre-built template for the disk of an instance. It includes the operating system and any pre-installed software. When you launch an instance you pick an AMI; the instance starts with a copy of that AMI's disk.

For us, the AMI will be a standard **Ubuntu** image (think: Ubuntu Linux freshly installed).

### 2.8 What is an instance type?

The **instance type** is the "size" of the virtual computer — how many CPUs, how much RAM. Examples: `t3.micro` (1 CPU, 1 GB RAM, very small), `t3.small` (1 CPU, 2 GB RAM), `t3.medium` (2 CPUs, 4 GB RAM).

Chromium is heavy. We'll pick at least `t3.small`, preferably `t3.medium`. Anything smaller will swap, run very slowly, or crash.

### 2.9 What is an AWS region?

AWS has data centers all around the world, grouped into **regions** (e.g., `us-east-1` Virginia, `us-east-2` Ohio, `us-west-2` Oregon, `eu-west-1` Ireland). You pick one when you create resources. The README mentions `us-east-2`. Pick something physically close to you for lower latency (network "lag") when SSH'ing in.

A region change is **not** harmful, but each region is essentially a separate AWS — instances in one are invisible from another, key pairs are not shared, etc. Stick with one region throughout.

### 2.10 What is a key pair (and a `.pem` file)?

Logging in to a Linux server normally needs a password. EC2 uses something more secure: **public-key cryptography**.

- AWS generates a **key pair**: a public key and a private key.
- The **public key** is placed on the EC2 instance automatically when it boots.
- The **private key** is downloaded to your laptop **once**, as a `.pem` file. **AWS will not let you download it again.** If you lose it, you cannot log in to that instance.
- When you SSH in, your laptop proves it owns the private key, and the server lets you in.

So: a `.pem` file is a small text file with a long secret in it. Guard it like a password. Never commit it to git, never email it.

### 2.11 What is a security group?

A **security group** is a virtual firewall around your instance. It controls which kinds of network traffic are allowed in. By default everything is blocked. To SSH in, you must allow inbound traffic on port 22 (the SSH port).

For this project, we only need port 22 open — and only from your laptop's IP. We don't expose any web server.

### 2.12 What is SSH?

**SSH (Secure Shell)** is a protocol for getting a remote terminal on another computer over the network, encrypted. The `ssh` command on your Mac connects to the EC2 instance and gives you a shell prompt as if you were sitting at the server.

The typical command shape:
```bash
ssh -i path/to/private-key.pem username@server-hostname
```
For Ubuntu EC2 instances the username is always `ubuntu`.

### 2.13 What is Linux / Ubuntu?

**Linux** is a family of free, Unix-like operating systems. **Ubuntu** is one popular distribution of Linux, very common on servers. Once you SSH in, you'll see a `$` prompt — you are now driving an Ubuntu computer by typing commands.

### 2.14 The handful of Linux commands you actually need

| Command | What it does |
|---|---|
| `pwd` | Print the directory you are currently in. |
| `ls` | List files in the current directory. `ls -la` shows hidden files and details. |
| `cd path` | Change directory. `cd ~` goes home; `cd ..` goes up one level. |
| `mkdir name` | Make a new directory. `-p` creates parent dirs too. |
| `cat file` | Print a file's contents to the screen. |
| `nano file` | Open a simple text editor. Save: `Ctrl+O`, then Enter. Exit: `Ctrl+X`. |
| `rm file` | Delete a file. `rm -rf dir/` deletes a folder and everything in it. **Irreversible — use carefully.** |
| `cp src dst` | Copy a file. Add `-r` to copy a folder. |
| `mv src dst` | Move or rename a file. |
| `df -h` | Show free disk space. |
| `free -h` | Show free memory. |
| `exit` | Log out of the SSH session. |
| `sudo cmd` | Run `cmd` as the **superuser** (admin). Needed to install software. |

"Home directory" on Ubuntu EC2 is `/home/ubuntu`, written as `~`.

### 2.15 What is Docker?

**Docker** packages an application together with its operating-system dependencies into a **container** — a self-contained, runnable bundle that behaves identically on any machine that has Docker installed. The big benefit: "It works on my laptop" actually means it will also work on the server.

Key terms:
- **Image** — the recipe / blueprint. Built once via `docker build`. Read-only.
- **Container** — a running instance of an image. Started via `docker run`. Like a tiny, isolated virtual computer that boots fast.
- **Dockerfile** — a text file with the build instructions for an image.

In our project the `Dockerfile` (already written) installs Python 3.14, Chromium, Xvfb, and the project's Python libraries. When you `docker build`, Docker reads the Dockerfile and produces an image. When you `docker run`, Docker starts a container from that image.

When you run a container you can:
- **Mount a directory** from the host (the EC2 instance) into the container with `-v /host/path:/container/path`. Files written inside the container at `/container/path` actually live at `/host/path` on the EC2 disk. We use this so outputs survive after the container exits.
- **Pass environment variables** with `-e KEY=value` or `--env-file file.env`.
- **Use `--rm`** to auto-delete the container when it stops (we want this — we only care about the output files, not the container itself).

### 2.16 What are environment variables and `.env` files?

An **environment variable** is a named value that any program can read. Common ones include `HOME`, `PATH`, `USER`.

A **`.env` file** is a plain-text file containing a list of `KEY=VALUE` lines. Docker's `--env-file FILE` flag reads those and exposes each as an environment variable inside the container.

For this project, **the Python code does not actually read any environment variables** — secrets come from the `credentials/` folder. But the README's `docker run` command still passes `--env-file .env`. If the `.env` file doesn't exist, Docker errors out before the container even starts. So we will create an empty `.env` to satisfy that flag. (See [§12](#12-part-i--create-an-empty-env-file).)

### 2.17 What is Git and what is a "deploy key"?

**Git** is the version-control system used to track source-code changes. **GitHub** is the website that hosts our repository. To pull the code onto the EC2 instance we'll run `git clone` over SSH.

To let the EC2 instance fetch from a **private** GitHub repository, we add the instance's SSH public key to the repo as a **deploy key**. A deploy key is:
- An SSH public key,
- Attached to one specific repository,
- Read-only by default (good — the server should not be able to push).

This is safer than putting your personal GitHub credentials on the server.

---

## 3. Prerequisites Checklist

Gather these **before** Part A. We will reference them by name throughout the guide.

| # | Item | Notes |
|---|---|---|
| 1 | **AWS account** with permission to launch EC2 instances. | Ask whoever manages your team's AWS access if you don't already have a login. |
| 2 | **A web browser** to use the AWS Console. | Chrome / Safari / Firefox all work. |
| 3 | **A terminal application** on your laptop. | macOS: built-in Terminal or iTerm2. |
| 4 | **The OpenAI API key** that can access the `gpt-4.1` model. | Looks like `sk-...`. Keep it private. |
| 5 | **The Google service account JSON file** for the `cookie-banner` sheet. | Will end up at `credentials/google-drive-key.json` on EC2. |
| 6 | **Confirmation** that the Google Sheet named `cookie-banner` is shared with the service account's email and contains `websites` and `pixels` columns. | See [PROJECT_OVERVIEW.md §6.2](PROJECT_OVERVIEW.md#62-srcinput_managerpy--reading-the-google-sheet). |
| 7 | **The GitHub repo URL** and access to add a deploy key to it. | The README references `git@github.com:MarcusBluestone/cookie_detection.git`. |
| 8 | **Your laptop's public IP** (for restricting SSH access). | Find it by visiting <https://whatismyipaddress.com> in your browser. Write it down. |

Once you have all 8, proceed.

---

## 4. Part A — Sign In to AWS and Pick a Region

1. Open <https://console.aws.amazon.com> in a browser.
2. Sign in with the credentials you were given. If your team uses an "AWS Organization", you may need to choose the right **account** after signing in.
3. Look at the **top-right corner** of the AWS Console. You'll see a region name (e.g., "Ohio", "N. Virginia", "Oregon").
4. **Click it and pick one region**, then leave it alone for the rest of this guide. We recommend the same region the team has been using: **US East (Ohio) — `us-east-2`**, since the README references an Ohio host.
5. In the search bar at the top, type **EC2** and click the EC2 service to open the EC2 dashboard.

> **Why pick a region first?** Because EC2 instances, key pairs, and security groups are all *per-region*. If you create a key pair in Ohio and then switch to Virginia, you will not see that key pair anymore.

---

## 5. Part B — Launch the EC2 Instance (AWS Console)

We will create one virtual computer.

### 5.1 Start the wizard

From the EC2 dashboard, click the orange **"Launch instance"** button. This opens a multi-step form.

### 5.2 Name

Under "Name and tags", enter:
```
cookie-detection
```
(Any name works; this just helps you identify it in the console.)

### 5.3 Application and OS Images (AMI)

- Choose **Ubuntu**.
- For the version, pick **Ubuntu Server 24.04 LTS** (or 22.04 LTS — both are fine; LTS = "Long Term Support").
- Architecture: **64-bit (x86)** is the safest default.
- Make sure the AMI is marked **"Free tier eligible"** if you want to keep costs minimal (though we will likely use a slightly larger instance below).

> **Why Ubuntu?** Because the project's `Dockerfile` and `README.md` were written assuming an Ubuntu host with `apt`. Other Linux distros would need different package-installation commands.

### 5.4 Instance type

Click the dropdown. Pick one of:

| Option | Specs | When to pick |
|---|---|---|
| `t3.small` | 2 vCPU, 2 GB RAM | Minimum viable. Will work for short lists of sites. |
| `t3.medium` | 2 vCPU, 4 GB RAM | **Recommended.** Comfortable headroom for Chromium. |
| `t3.large` | 2 vCPU, 8 GB RAM | Use if scraping many sites in one run. |

> **Why not `t3.micro`?** It has only 1 GB RAM. Chromium plus Python plus Xvfb easily exceeds that and the container crashes with cryptic errors.

### 5.5 Key pair

This is the SSH login key (see [§2.10](#210-what-is-a-key-pair-and-a-pem-file)).

- If a key pair already exists for this project (e.g., the README mentions `cookie-banner-automation-key`), **and you have the matching `.pem` file on your laptop**, choose it from the dropdown.
- Otherwise, click **"Create new key pair"**:
  - Name: `cookie-detection-key`
  - Type: **RSA** (the most compatible)
  - Format: **`.pem`** (for macOS / Linux SSH)
  - Click **Create key pair**. Your browser will download `cookie-detection-key.pem` automatically.
  - **Save this file somewhere safe.** Anyone with this file can SSH into your instance. AWS will *not* let you download it again.

### 5.6 Network settings (security group)

Click **Edit** in the "Network settings" panel.

- Leave the VPC and subnet at their defaults.
- Auto-assign public IP: **Enable**. (We need a public IP to SSH in.)
- Under **Firewall (security groups)**, choose **Create security group**:
  - Name: `cookie-detection-sg`
  - Description: `Allow SSH from my laptop`
- Under **Inbound security group rules**, you should see one rule that allows SSH. Configure it:
  - Type: **SSH**
  - Protocol: TCP (auto-filled)
  - Port: 22 (auto-filled)
  - Source: **My IP** (AWS will autodetect your laptop's current IP — handy)

> **Why "My IP" and not "Anywhere"?** Setting source to `0.0.0.0/0` ("Anywhere") would let *the entire internet* attempt to SSH in. With "My IP" only your current public IP can try. If your home IP later changes, edit the security group and update.

### 5.7 Configure storage

Set the root disk to at least **20 GB**:

- Chromium, Xvfb, the Python dependencies, and a few hundred output PNGs all together easily exceed the 8 GB default.
- Volume type: **gp3** (general-purpose SSD — fast and cheap).

### 5.8 Advanced details

Leave everything at defaults.

### 5.9 Launch

In the right-hand "Summary" panel, double-check:

- Number of instances: **1**
- AMI: Ubuntu (LTS)
- Instance type: as chosen above
- Key pair: the one you selected/created
- Security group: `cookie-detection-sg` with one SSH rule
- Storage: 20 GB gp3

Click the orange **"Launch instance"** button.

You'll see a green success banner. Click **"View all instances"**.

### 5.10 Wait until the instance is "Running"

In the instance list, find your `cookie-detection` instance. Watch the **"Instance state"** column. It will go through `Pending` → `Running`. Wait until it says **Running** and the **"Status check"** column says `2/2 checks passed` (a couple of minutes).

### 5.11 Note down the public DNS / IP

Click the instance row. In the details panel below, find:
- **Public IPv4 DNS** — looks like `ec2-3-131-85-149.us-east-2.compute.amazonaws.com`.
- **Public IPv4 address** — looks like `3.131.85.149`.

Either of these works for SSH. **Copy and save the public DNS somewhere** — you'll use it repeatedly.

> **Note:** If you ever **stop** and **start** the instance, the public IP **may change** by default. Use the public DNS or, for stability, attach an Elastic IP (out of scope here).

---

## 6. Part C — Prepare Your SSH Key on Your Laptop

Open the **Terminal** app on your Mac. We'll set up the `.pem` file so SSH will accept it.

### 6.1 Move the `.pem` somewhere sensible

Most people keep SSH keys in `~/.ssh/`. From your terminal:

```bash
local$ mkdir -p ~/.ssh
local$ mv ~/Downloads/cookie-detection-key.pem ~/.ssh/
```

(If you used the existing key, substitute its filename. If your `.pem` is somewhere other than `~/Downloads`, adjust the source path.)

### 6.2 Tighten the file permissions

```bash
local$ chmod 400 ~/.ssh/cookie-detection-key.pem
```

> **Why?** SSH refuses to use a private key if it is readable by anyone other than you. `chmod 400` makes it readable only by your user. Without this, you'll see an error like `WARNING: UNPROTECTED PRIVATE KEY FILE!`.

### 6.3 Verify

```bash
local$ ls -la ~/.ssh/cookie-detection-key.pem
```
You should see `-r--------` at the start of the line, meaning "owner can read, no one else can read or write".

---

## 7. Part D — Connect to the Instance via SSH

### 7.1 The SSH command

In your laptop's terminal, run (replacing the hostname with the **Public IPv4 DNS** from Step 5.11):

```bash
local$ ssh -i ~/.ssh/cookie-detection-key.pem ubuntu@ec2-3-131-85-149.us-east-2.compute.amazonaws.com
```

Breaking that down:
- `ssh` — the SSH client.
- `-i ~/.ssh/cookie-detection-key.pem` — use this private key file.
- `ubuntu@...` — log in as the user `ubuntu` on the EC2 host. (Ubuntu AMIs always use `ubuntu`.)

### 7.2 The "fingerprint" prompt

The first time you connect, SSH will say:

```
The authenticity of host '...' can't be established.
ED25519 key fingerprint is SHA256:...
Are you sure you want to continue connecting (yes/no/[fingerprint])?
```

Type `yes` and press Enter. This is SSH asking you to trust the server's identity. Saying yes adds it to `~/.ssh/known_hosts` so it won't ask again.

### 7.3 Verify you are in

You should now see a prompt like:

```
ubuntu@ip-172-31-...:~$
```

That `~` is the current directory, which is `/home/ubuntu`. You are now operating the remote computer. **From this point on, every command prefixed with `ec2$` is typed at this prompt.**

To confirm, try a couple of harmless commands:

```bash
ec2$ pwd
/home/ubuntu

ec2$ whoami
ubuntu

ec2$ ls -la
total ...
```

### 7.4 To leave the server

Type `exit` or hit `Ctrl+D`. You'll be returned to your laptop's prompt.

---

## 8. Part E — Install Docker on the Instance

Now SSH back in (if you left) and install Docker.

### 8.1 Update the package lists

```bash
ec2$ sudo apt update
```

> **Why?** `apt` is Ubuntu's package manager. `apt update` refreshes its local list of available packages. Without this, `apt install` may not find the latest versions or may fail outright on a fresh instance. `sudo` is the "run as admin" prefix.

You may be asked to confirm with `y` if it pauses.

### 8.2 Install Docker

```bash
ec2$ sudo apt install -y docker.io
```

The `-y` flag means "yes to all prompts". This installs the `docker.io` package — the open-source Docker engine, which is what we need.

### 8.3 Enable and start the Docker service

```bash
ec2$ sudo systemctl enable --now docker
```

- `enable` — Docker will start automatically when the instance reboots.
- `--now` — also start it right now without needing a reboot.

### 8.4 Let your user run Docker without `sudo`

```bash
ec2$ sudo usermod -aG docker ubuntu
```

This adds the `ubuntu` user to the `docker` group. By default Docker requires root, but members of the `docker` group can use it without `sudo`.

> **Important:** this change does **not** take effect in your current SSH session. Either log out and back in, or run `newgrp docker` once. The cleanest option is:
>
> ```bash
> ec2$ exit
> local$ ssh -i ~/.ssh/cookie-detection-key.pem ubuntu@<your-host>
> ```

### 8.5 Verify Docker works

```bash
ec2$ docker --version
Docker version ...

ec2$ docker run --rm hello-world
```

`docker run hello-world` downloads a tiny test image and runs it. You should see "Hello from Docker!" output. If you see "permission denied" — you forgot to log out/in after Step 8.4.

---

## 9. Part F — Set Up GitHub Access from the Instance

We need to let the EC2 instance pull source from our GitHub repo. We'll use a **deploy key**.

### 9.1 Check if an SSH key already exists

```bash
ec2$ cat ~/.ssh/id_ed25519.pub
```

- If you see a long string starting with `ssh-ed25519 AAAA...`, you already have a key. **Copy this entire line** — you'll paste it into GitHub.
- If you see `cat: /home/ubuntu/.ssh/id_ed25519.pub: No such file or directory`, continue to Step 9.2.

### 9.2 Create a new SSH key

```bash
ec2$ ssh-keygen -t ed25519 -C "cookie-detect-ec2-deploy-key"
```

- `-t ed25519` — modern, secure key type.
- `-C "..."` — a comment (any text) so you can identify this key later.

Press **Enter** at each prompt to accept defaults (no passphrase). This creates two files:
- `~/.ssh/id_ed25519` — the private key (stays on EC2; do not share).
- `~/.ssh/id_ed25519.pub` — the public key (you'll paste this into GitHub).

Now show the public key:

```bash
ec2$ cat ~/.ssh/id_ed25519.pub
```

Highlight and copy the **entire line** (starting with `ssh-ed25519`).

### 9.3 Add it as a deploy key on GitHub

1. In your browser, open the GitHub repo (e.g. `https://github.com/MarcusBluestone/cookie_detection`).
2. Click **Settings** (top right, repo settings — not your account settings).
3. In the left sidebar, click **Deploy keys**.
4. Click **Add deploy key**.
5. **Title:** `cookie-detect ec2 instance` (any descriptive name).
6. **Key:** paste the public key you copied.
7. **Allow write access:** **leave unchecked.** The EC2 host only needs to clone/pull, not push.
8. Click **Add key**.

### 9.4 Test the connection

```bash
ec2$ ssh -T git@github.com
```

First time, it asks to confirm GitHub's host key — type `yes`. Then you should see:

```
Hi MarcusBluestone/cookie_detection! You've successfully authenticated, but GitHub does not provide shell access.
```

That "does not provide shell access" message is the success case — it means the key is recognized.

---

## 10. Part G — Clone the Project Repository

Now we'll pull the code onto the instance.

### 10.1 Go to your home directory

```bash
ec2$ cd ~
ec2$ pwd
/home/ubuntu
```

### 10.2 Clone

```bash
ec2$ git clone git@github.com:MarcusBluestone/cookie_detection.git cookie_detect
```

This downloads the repo into a folder called `cookie_detect`. The trailing `cookie_detect` argument renames the folder (the README uses this name; sticking with it keeps subsequent commands identical).

### 10.3 Move into the project folder

```bash
ec2$ cd ~/cookie_detect
ec2$ ls
Dockerfile  PROJECT_OVERVIEW.md  README.md  requirements.txt  src
```

You should see the project files. From here on, all `ec2$` commands assume you are in `~/cookie_detect`.

---

## 11. Part H — Provide the Credentials Files

The scraper expects two files inside a `credentials/` folder. We'll create them now.

### 11.1 Create the credentials folder

```bash
ec2$ mkdir -p ~/cookie_detect/credentials
```

### 11.2 Add the OpenAI API key file

We'll create a plain-text file containing your API key on the first line.

```bash
ec2$ nano ~/cookie_detect/credentials/openai-key.txt
```

`nano` opens a small text editor.

- Paste your OpenAI API key (the long `sk-...` string).
- **Make sure there is no trailing newline or extra spaces** beyond the key. Specifically, the key should be on line 1, and that's all.
- Save: press `Ctrl+O`, then Enter.
- Exit: press `Ctrl+X`.

Verify it looks right:

```bash
ec2$ cat ~/cookie_detect/credentials/openai-key.txt
sk-...
```

### 11.3 Add the Google service account JSON

This is the larger of the two files. The simplest way is to copy it from your laptop to EC2 with `scp` ("secure copy"). **Open a new terminal tab on your laptop** (keep the SSH tab open in the background) and run:

```bash
local$ scp -i ~/.ssh/cookie-detection-key.pem \
    /path/on/your/laptop/google-drive-key.json \
    ubuntu@ec2-3-131-85-149.us-east-2.compute.amazonaws.com:~/cookie_detect/credentials/google-drive-key.json
```

Replace:
- `/path/on/your/laptop/google-drive-key.json` with the actual local path to your JSON file.
- The hostname with **your** EC2 public DNS.

`scp` is "ssh copy" — same `-i key.pem` flag, but copies a file instead of opening a shell. The general shape is `scp -i KEY SOURCE DEST`.

Back in your SSH session, verify:

```bash
ec2$ ls -la ~/cookie_detect/credentials/
total ...
-rw-r--r-- 1 ubuntu ubuntu  ... openai-key.txt
-rw-r--r-- 1 ubuntu ubuntu  ... google-drive-key.json
```

Both files should be present and non-empty.

### 11.4 Sanity-check the JSON

```bash
ec2$ head -3 ~/cookie_detect/credentials/google-drive-key.json
```

You should see something like:
```json
{
  "type": "service_account",
  "project_id": "...",
```

If you see `{` and JSON-looking content, you're good.

> **Reminder:** the `credentials/` folder is `.gitignore`d, so it is not in the repo. We added it manually on the server. We will revisit security of this folder in [§21](#21-appendix--useful-optional-improvements).

---

## 12. Part I — Create an Empty `.env` File

The README's `docker run` command includes `--env-file .env`. Docker will refuse to start if that file doesn't exist. The Python code doesn't read environment variables, so we just need an empty file to satisfy Docker:

```bash
ec2$ touch ~/cookie_detect/.env
```

`touch` creates an empty file (or updates its modification time if it already exists). That's all we need.

> **Why does the README pass `--env-file .env` if the code doesn't read env vars?** Most likely it was placed there in anticipation of future settings (proxy URL, alerting webhook, etc.). For now an empty file is fine.

---

## 13. Part J — Build the Docker Image

From your project folder, build the image:

```bash
ec2$ cd ~/cookie_detect
ec2$ docker build -t cookie-detect .
```

- `docker build` — read the `Dockerfile` and produce an image.
- `-t cookie-detect` — tag (name) the resulting image `cookie-detect`. Without this we'd just get a hash and have to refer to it by that hash.
- `.` — the **build context**. Means "use the current directory's files (respecting `.dockerignore`)". Don't forget the dot.

### 13.1 What you'll see

Docker prints a sequence of steps, each corresponding to a line in the `Dockerfile`:
1. Pulling the `python:3.14-slim` base image.
2. Setting environment variables.
3. `apt-get install chromium xvfb xauth` — this is the slowest step (downloads ~250 MB).
4. Symlinking `/snap/bin/chromium`.
5. `pip install -r requirements.txt` — also slow on first run.
6. `COPY . .` — copying your project files into the image.

Total time: roughly **5–10 minutes** on a `t3.medium`. Subsequent builds are faster because Docker caches each step.

### 13.2 Possible build issues

- **"no space left on device"** — your root disk is too small. See [§5.7](#57-configure-storage); recreate the instance with 20+ GB, or expand the volume.
- **`apt-get update` failures** — sometimes a transient mirror issue. Re-run `docker build`.
- **`pip` errors about missing wheels** — usually means a dependency version mismatch with Python 3.14. Re-read the error, but pinning issues should not occur with the existing `requirements.txt`.

### 13.3 Verify the image was built

```bash
ec2$ docker images
REPOSITORY     TAG       IMAGE ID       CREATED          SIZE
cookie-detect  latest    abc123...      30 seconds ago   ~1.2GB
```

You should see `cookie-detect` listed.

---

## 14. Part K — Run the Container (the Actual Deployment)

This is the moment of truth.

### 14.1 Create the host-side outputs directory

```bash
ec2$ mkdir -p ~/cookie_detect_outputs
```

This folder on the EC2 host will receive the results. We'll mount it into the container at `/app/outputs`.

### 14.2 Start the container

```bash
ec2$ docker run --rm \
    --env-file ~/cookie_detect/.env \
    -v ~/cookie_detect_outputs:/app/outputs \
    cookie-detect
```

Decoding the flags:

- `docker run` — start a new container.
- `--rm` — delete the container automatically when it exits. We only care about the files it produced, not the container itself.
- `--env-file ~/cookie_detect/.env` — load env vars from the empty `.env` file. (As above, this is needed only to keep Docker happy; the file contains nothing.)
- `-v ~/cookie_detect_outputs:/app/outputs` — **bind mount.** Maps the EC2 folder `~/cookie_detect_outputs` to `/app/outputs` inside the container. Anything the program writes to `/app/outputs` actually ends up in `~/cookie_detect_outputs` on the host and survives after the container exits.
- `cookie-detect` — the image name we built.

> **Note:** The `Dockerfile`'s `CMD` already runs `xvfb-run python -u -m src.main` for us, so we don't need to add a command.

### 14.3 What you'll see while it runs

The first thing you should see is:

```
CONTAINER STARTED
```

Then for each website in the spreadsheet:

```
Processing: https://example.com/...
Visiting Website
Simulating Behavior
Screenshotting
Done!
```

Each website takes ~10–20 seconds (the 3 screenshots alone require 10 s of waits). For N websites, total runtime is roughly `N × 15 seconds`. You can leave the SSH session open and just watch.

### 14.4 What if the SSH session disconnects?

If your laptop sleeps or your internet hiccups during a long run, the SSH connection breaks and the container is killed mid-run. To prevent this, see [§21.3](#213-running-long-jobs-without-an-active-ssh-session).

---

## 15. Part L — Verify the Outputs on EC2

Once the container exits and your prompt returns, inspect the outputs.

### 15.1 List per-website folders

```bash
ec2$ ls ~/cookie_detect_outputs
website_000  website_001  website_002 ...
```

One folder per website, numbered in the order they appeared in the spreadsheet.

### 15.2 Inspect one website's results

```bash
ec2$ ls ~/cookie_detect_outputs/website_000
info.json  request_info.json  screenshots
```

Look at the metadata:

```bash
ec2$ cat ~/cookie_detect_outputs/website_000/info.json
```

You should see fields like `website`, `success`, `cookie_banner`, `diagnostic_log`, etc. (See [PROJECT_OVERVIEW.md §11](PROJECT_OVERVIEW.md#11-output-files-produced-by-a-run) for the schema.)

Verify the screenshots exist:

```bash
ec2$ ls ~/cookie_detect_outputs/website_000/screenshots
screenshot_0.png  screenshot_1.png  screenshot_2.png
```

If `info.json.success` is `true` and screenshots exist, the deployment worked.

---

## 16. Part M — Copy the Outputs Back to Your Laptop

We use `scp` again, in the opposite direction.

**Run this on your laptop (not in the SSH session):**

```bash
local$ scp -i ~/.ssh/cookie-detection-key.pem -r \
    ubuntu@ec2-3-131-85-149.us-east-2.compute.amazonaws.com:~/cookie_detect_outputs \
    ~/Desktop/cookie_detect_outputs
```

Replace:
- The hostname with your EC2 public DNS.
- `~/Desktop/cookie_detect_outputs` with wherever on your Mac you want the folder to land.

Flags:
- `-r` — copy recursively (whole folder, not just one file).
- `-i ...pem` — same private key as for SSH.

You should see a stream of file transfers. When it finishes, open the folder in Finder. The PNG screenshots are viewable directly; `info.json` and `request_info.json` open in any text editor (try VS Code).

---

## 17. Part N — Re-Running After Code Changes

When the code in the repo changes (someone merges a PR, or you tweak the spreadsheet), repeat just the relevant steps:

1. **If code changed on GitHub:**
   ```bash
   ec2$ cd ~/cookie_detect
   ec2$ git pull
   ec2$ docker build -t cookie-detect .
   ```
2. **If only the spreadsheet changed (no code change):** skip the rebuild — just re-run the container (see step 4 below).
3. **Save previous outputs** if you want to keep them:
   ```bash
   ec2$ mv ~/cookie_detect_outputs ~/cookie_detect_outputs_$(date +%Y-%m-%d_%H-%M)
   ec2$ mkdir ~/cookie_detect_outputs
   ```
   > **Why?** Each container run **deletes and recreates** `outputs/` inside the container, which is bind-mounted to `~/cookie_detect_outputs`. If you don't rename the host folder first, the old results disappear.
4. **Run again:**
   ```bash
   ec2$ docker run --rm \
       --env-file ~/cookie_detect/.env \
       -v ~/cookie_detect_outputs:/app/outputs \
       cookie-detect
   ```

---

## 18. Part O — Stopping vs Terminating the Instance (Cost Control)

You are billed for the EC2 instance **per hour while it is Running** (and a tiny amount for storage even when stopped).

Three actions, very different consequences:

| Action | Effect | When to use |
|---|---|---|
| **Stop** | Instance powers off. CPU charges stop. The disk and configuration are preserved. You can start it again later. | Done with the run for the day. |
| **Start** | Boot a previously stopped instance back up. Public IP **may change** (Public DNS will too); use the new one in your `ssh` command. | Resume work tomorrow. |
| **Terminate** | Permanently delete the instance and its disk. **Irreversible.** Everything is gone. | You're truly done and want to stop paying. |

To stop/start/terminate via the AWS Console:

1. Go to EC2 → Instances.
2. Click the row for your `cookie-detection` instance.
3. Click **Instance state** in the top-right.
4. Choose **Stop instance** (safe), **Start instance**, or **Terminate (delete) instance** (irreversible).

**Cost orientation** (very rough, US regions, 2025-era pricing):

| Instance type | On-Demand cost / hour | Cost / day if left running |
|---|---|---|
| `t3.small` | ~$0.02 | ~$0.50 |
| `t3.medium` | ~$0.04 | ~$1.00 |
| `t3.large` | ~$0.08 | ~$2.00 |

Plus a few cents per day for EBS storage. Always **stop** instances when you're not using them.

---

## 19. Troubleshooting

### 19.1 SSH errors

| Error | Likely cause | Fix |
|---|---|---|
| `Permission denied (publickey)` | Wrong key file, wrong username, or key not chmod 400. | Use the matching `.pem`. Username is `ubuntu`. Run `chmod 400 ~/.ssh/your.pem`. |
| `WARNING: UNPROTECTED PRIVATE KEY FILE!` | `.pem` is readable by others. | `chmod 400 ~/.ssh/your.pem`. |
| `Operation timed out` / hangs forever | Security group doesn't allow your IP on port 22, or your IP changed. | Update the security group's SSH inbound rule to your current IP. |
| `Connection refused` | Instance is stopped, or SSH daemon not yet ready (just booted). | Wait 1–2 minutes after starting. Confirm "Running" in console. |
| `Host key verification failed` | Server identity changed (new instance using old IP). | `ssh-keygen -R <hostname>` on laptop, then re-SSH. |

### 19.2 Docker build errors

| Symptom | Likely cause | Fix |
|---|---|---|
| `permission denied while trying to connect to the Docker daemon socket` | Forgot to log out/in after `usermod -aG docker ubuntu`. | `exit` and re-SSH. |
| `no space left on device` | Root disk too small or full of old images. | `docker system prune -a` to clean. If still full, recreate with larger disk. |
| `Could not resolve apt.ubuntu.com` | DNS or transient mirror issue. | Re-run `docker build`. |

### 19.3 Container runs but errors out

| Symptom in logs | Likely cause | Fix |
|---|---|---|
| `FileNotFoundError: ... credentials/openai-key.txt` | Credentials folder missing inside the image. | The `COPY . .` step happens *at build time*. Re-build after credentials are in place: `docker build -t cookie-detect .`. Or use a mount (see [§21.1](#211-mounting-credentials-at-runtime-instead-of-baking-them-in)). |
| `gspread.exceptions.SpreadsheetNotFound` | Sheet not shared with the service account, or sheet not named `cookie-banner`. | Check share settings in Google Sheets; the sheet name is case-sensitive. |
| `ValueError: Column 'websites' not found` | First row of the sheet doesn't have a `websites` or `pixels` header. | Fix the spreadsheet headers. |
| `openai.AuthenticationError` | Bad / expired OpenAI key, or wrong model permission. | Replace `openai-key.txt` with a valid key that has `gpt-4.1` access. Rebuild image. |
| `BrowserType.launch_persistent_context: Executable doesn't exist at /snap/bin/chromium` | Symlink missing in image — would happen if Dockerfile was edited. | Make sure the Dockerfile still includes `RUN mkdir -p /snap/bin && ln -s /usr/bin/chromium /snap/bin/chromium`. |
| Container exits silently with no output | The `docker run` had `--env-file .env` but `.env` doesn't exist. | `touch ~/cookie_detect/.env`. |
| Most websites show `"success": false` with timeouts | EC2 region's outbound IP is flagged by anti-bot. | Try a different region, or enable proxy support (out of scope here). |
| Container OOM-killed (logs end abruptly mid-run) | Not enough RAM. | Upgrade instance type to at least `t3.medium`. |

### 19.4 General "I don't know what's going on"

Three things to check, in this order:

1. **Where am I?**
   ```bash
   ec2$ pwd
   ```
2. **Is the file/folder where I think it is?**
   ```bash
   ec2$ ls -la ~/cookie_detect
   ```
3. **What did the last command actually say?** Scroll up in your terminal. Most fixes start by carefully re-reading the error message.

---

## 20. Quick Reference — Cheat Sheet

```bash
# On your laptop ----------------------------------------------------
chmod 400 ~/.ssh/cookie-detection-key.pem

ssh -i ~/.ssh/cookie-detection-key.pem ubuntu@<EC2_PUBLIC_DNS>

scp -i ~/.ssh/cookie-detection-key.pem \
    LOCAL_FILE ubuntu@<EC2_PUBLIC_DNS>:REMOTE_PATH

scp -i ~/.ssh/cookie-detection-key.pem -r \
    ubuntu@<EC2_PUBLIC_DNS>:~/cookie_detect_outputs ~/Desktop/

# On the EC2 instance ----------------------------------------------
# One-time setup
sudo apt update
sudo apt install -y docker.io
sudo systemctl enable --now docker
sudo usermod -aG docker ubuntu   # then exit + re-ssh

# Project setup
cd ~
git clone git@github.com:MarcusBluestone/cookie_detection.git cookie_detect
cd cookie_detect
mkdir -p credentials
nano credentials/openai-key.txt   # paste key, save (Ctrl+O, Enter), exit (Ctrl+X)
# scp google-drive-key.json from laptop into credentials/
touch .env

# Build + run
docker build -t cookie-detect .
mkdir -p ~/cookie_detect_outputs
docker run --rm \
    --env-file .env \
    -v ~/cookie_detect_outputs:/app/outputs \
    cookie-detect

# Update + re-run
cd ~/cookie_detect && git pull && docker build -t cookie-detect .

# Housekeeping
docker images
docker ps -a
docker system prune -a    # frees disk by removing unused images/containers
df -h                     # check disk space
free -h                   # check memory
```

---

## 21. Appendix — Useful Optional Improvements

These are **not required** for a first deployment, but worth knowing about for the future.

### 21.1 Mounting credentials at runtime instead of baking them in

In the current setup, `COPY . .` in the `Dockerfile` copies the `credentials/` folder **into the image** at build time. That means the secrets live inside the image file on disk. If anyone exports or shares the image, they get the secrets too.

A cleaner approach is to **exclude** the folder from the image and mount it at runtime:

1. Add `credentials/` to `.dockerignore`:
   ```
   credentials/
   ```
2. Rebuild the image: `docker build -t cookie-detect .`
3. Run with an extra volume mount:
   ```bash
   docker run --rm \
       --env-file .env \
       -v ~/cookie_detect/credentials:/app/credentials \
       -v ~/cookie_detect_outputs:/app/outputs \
       cookie-detect
   ```

Now the image contains no secrets; the host's credentials folder is mounted at `/app/credentials` only while the container runs.

### 21.2 Sending outputs straight to S3

Right now you `scp` outputs back to your laptop. For automated / scheduled runs, a better pattern is to upload them to an S3 bucket. This is out of scope, but the high-level steps are:

1. Create an S3 bucket in the same region.
2. Attach an **IAM role** to the EC2 instance giving it write access to that bucket.
3. After each run, `aws s3 cp --recursive ~/cookie_detect_outputs s3://your-bucket/...`.

### 21.3 Running long jobs without an active SSH session

If your scrape takes hours and you don't want to keep the SSH session open, use `tmux` (a terminal multiplexer):

```bash
ec2$ sudo apt install -y tmux
ec2$ tmux new -s scrape       # start a tmux session named "scrape"
# ... run docker run inside tmux ...
# To detach without killing it: press Ctrl+B, then D.
# To re-attach later:
ec2$ tmux attach -t scrape
```

Detached tmux sessions keep running even if you disconnect.

### 21.4 Scheduling regular runs

For nightly runs, use `cron`:

```bash
ec2$ crontab -e
```
Add a line such as:
```
0 3 * * *  cd /home/ubuntu/cookie_detect && /usr/bin/docker run --rm --env-file .env -v /home/ubuntu/cookie_detect_outputs:/app/outputs cookie-detect >> /home/ubuntu/scrape.log 2>&1
```
That runs the scraper every day at 03:00 EC2-local time, appending logs to `~/scrape.log`.

Combine with [§21.2](#212-sending-outputs-straight-to-s3) to make the outputs land in S3 automatically.

### 21.5 Trimming the image size

`requirements.txt` includes Jupyter / IPython packages (`ipython`, `ipykernel`, `jupyter_client`, `jupyter_core`) that the scraper does not use at runtime. Removing them from `requirements.txt` will shrink the image significantly and speed up builds. Test thoroughly before committing.

### 21.6 Pinning Chromium

The Dockerfile installs whichever Chromium `apt` happens to have for that base image at build time. If a future Chromium upgrade breaks the scraper, you'll have a hard time reproducing the previous state. To pin, change:
```dockerfile
RUN apt-get install -y --no-install-recommends chromium xvfb xauth
```
to install a specific version (e.g., `chromium=120.0.6099.71-...`). Out of scope for first deploy.

---

When you're ready, do Part A. After you confirm the instance is up, we'll go through B onward together in your terminal — one section at a time, and we'll pause for verification at each step.

</div>