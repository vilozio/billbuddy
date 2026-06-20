# Deploying BillBuddy to a VPS

BillBuddy is a long-polling Telegram bot, so it needs **no inbound ports** — only
outbound HTTPS to Telegram, OpenAI, and Google. It runs as a `systemd` service in a
Python venv, and GitHub Actions auto-deploys on every push to `main` by SSHing in,
pulling, reinstalling deps, and restarting the service.

Secrets and state live **on the VPS only** (`.env`, `credentials/`, `data/`). They are
git-ignored, so `git pull` never touches them. GitHub only holds the SSH deploy key.

---

## 1. One-time VPS setup

Assumes Ubuntu/Debian. Run as a sudo-capable user.

### 1.1 Install system dependencies

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git poppler-utils
```

> `poppler-utils` is required by `pdf2image` for PDF receipt processing.

### 1.2 Create the deploy user

```bash
sudo adduser --disabled-password --gecos "" billbuddy
```

### 1.3 Create a dedicated deploy SSH key

GitHub Actions logs in as `billbuddy` using this key. Generate it **locally** (or
anywhere), then install the public half on the VPS:

```bash
ssh-keygen -t ed25519 -f billbuddy_deploy -N "" -C "github-actions-billbuddy"
# copy the PUBLIC key into the billbuddy user's authorized_keys on the VPS:
sudo -u billbuddy mkdir -p /home/billbuddy/.ssh
sudo -u billbuddy tee -a /home/billbuddy/.ssh/authorized_keys < billbuddy_deploy.pub
sudo -u billbuddy chmod 700 /home/billbuddy/.ssh
sudo -u billbuddy chmod 600 /home/billbuddy/.ssh/authorized_keys
```

Keep `billbuddy_deploy` (the **private** key) for the `VPS_SSH_KEY` GitHub secret below.

### 1.4 Clone the repo

If the repo is **public**, just clone it:

```bash
sudo -u billbuddy git clone https://github.com/<owner>/billbuddy.git /home/billbuddy/billbuddy
```

#### Private repo — save a GitHub token so `git pull` works unattended

The Actions deploy runs `git pull` as the `billbuddy` user with no interactive prompt, so
the credential must be stored on the VPS. Use a **fine-grained Personal Access Token**
(or a classic token) scoped to read this one repo:

1. GitHub → **Settings → Developer settings → Personal access tokens → Fine-grained
   tokens → Generate new token**.
2. **Repository access:** *Only select repositories* → pick `billbuddy`.
3. **Permissions:** Repository permissions → **Contents: Read-only**.
4. Set an expiry and generate; copy the `github_pat_…` value.

Store it on the VPS via git's credential store so it's used automatically and never
printed in `git remote -v`:

```bash
# clone using the token once
sudo -u billbuddy git clone https://github.com/<owner>/billbuddy.git /home/billbuddy/billbuddy
cd /home/billbuddy/billbuddy

# persist the credential to ~/.git-credentials (chmod 600) for future pulls
sudo -u billbuddy git config --global credential.helper store
sudo -u billbuddy bash -c 'printf "https://x-access-token:%s@github.com\n" "<TOKEN>" > ~/.git-credentials'
sudo -u billbuddy chmod 600 /home/billbuddy/.git-credentials

# verify an unattended pull works
sudo -u billbuddy git -C /home/billbuddy/billbuddy pull --ff-only origin main
```

> Alternative: instead of a token, add a read-only **deploy key** (a separate SSH key)
> to the repo's *Settings → Deploy keys* and clone via the `git@github.com:` URL.
>
> When the token expires, regenerate it and rewrite `~/.git-credentials` with the new
> value (same `printf` line).

### 1.5 Bootstrap the venv

```bash
cd /home/billbuddy/billbuddy
sudo -u billbuddy python3 -m venv .venv
sudo -u billbuddy .venv/bin/pip install -r requirements.txt
```

### 1.6 Place secrets and state (git-ignored — survive every `git pull`)

```bash
cd /home/billbuddy/billbuddy
sudo -u billbuddy mkdir -p data logs credentials

# .env — copy the template and fill in the required vars
sudo -u billbuddy cp .env.example .env
sudo -u billbuddy nano .env
```

Required vars in `.env`: `TELEGRAM_BOT_TOKEN`, `OPENAI_API_KEY`,
`GOOGLE_OAUTH_CLIENT_PATH`, `GOOGLE_DRIVE_FOLDER_ID`, `GOOGLE_SHEET_ID`.

Then copy the Google credentials up from your machine:

```bash
# credentials/oauth-client.json — from Google Cloud Console
scp credentials/oauth-client.json billbuddy@VPS_HOST:/home/billbuddy/billbuddy/credentials/

# credentials/token.pickle — MUST be generated locally; the OAuth flow needs a browser
#   and cannot run headless on the VPS.
python authenticate.py          # run on your laptop, completes the browser consent
scp credentials/token.pickle billbuddy@VPS_HOST:/home/billbuddy/billbuddy/credentials/
```

`data/billbuddy.db` is created automatically on first run.

### 1.7 Verify it runs

```bash
cd /home/billbuddy/billbuddy
sudo -u billbuddy .venv/bin/python -m app.main
# Send the bot a message in Telegram to confirm, then Ctrl+C.
```

---

## 2. Install the systemd service

```bash
sudo cp /home/billbuddy/billbuddy/deploy/billbuddy.service /etc/systemd/system/billbuddy.service
sudo systemctl daemon-reload
sudo systemctl enable --now billbuddy
sudo systemctl status billbuddy        # should show "active (running)"
```

### Let the deploy user restart the service without a password

The GitHub Actions deploy runs `sudo systemctl restart billbuddy`. Grant **exactly** that
one command, password-free. `systemctl status` does **not** need sudo, so it isn't listed.

First find the real path — sudo matches the resolved absolute path as a literal string, so
`/bin/systemctl` will *not* match `/usr/bin/systemctl`:

```bash
command -v systemctl        # e.g. /usr/bin/systemctl  (use this exact path below)
```

```bash
# substitute the path from the command above
echo 'billbuddy ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart billbuddy' \
  | sudo tee /etc/sudoers.d/billbuddy
sudo chmod 440 /etc/sudoers.d/billbuddy
sudo visudo -c            # validate syntax
```

Verify it works without a password (this must print nothing/return 0, not prompt):

```bash
sudo -n -u billbuddy sudo -n /usr/bin/systemctl restart billbuddy
```

> **Gotchas that cause `sudo: a password is required` in the Actions log:**
> - Wrong path (`/bin` vs `/usr/bin`) — the rule must match `command -v systemctl`.
> - Extra flags/args — the rule allows `restart billbuddy` only. The deploy never runs
>   `status` under sudo, so no flag mismatch there.

---

## 3. Configure GitHub Actions secrets

In the GitHub repo: **Settings → Secrets and variables → Actions → New repository secret**.

| Secret        | Value                                              |
| ------------- | -------------------------------------------------- |
| `VPS_HOST`    | VPS public IP or hostname                          |
| `VPS_USER`    | `billbuddy`                                         |
| `VPS_SSH_KEY` | Contents of the **private** deploy key (`billbuddy_deploy`) |
| `VPS_PORT`    | SSH port — only if not `22` (optional)             |

After this, every push to `main` triggers `.github/workflows/deploy.yml`, which pulls,
reinstalls deps, and restarts the service. You can also trigger it manually from the
**Actions** tab ("Run workflow").

---

## 4. Operations

```bash
# Live logs
journalctl -u billbuddy -f

# Recent logs
journalctl -u billbuddy -n 100 --no-pager

# Restart / stop / start
sudo systemctl restart billbuddy
sudo systemctl stop billbuddy
sudo systemctl start billbuddy
```

### Recovering from `invalid_grant` (expired/revoked Google token)

The OAuth flow can't run headless, so regenerate the token on a machine with a browser
and recopy it:

```bash
# on your laptop, in the repo:
rm credentials/token.pickle
python authenticate.py
scp credentials/token.pickle billbuddy@VPS_HOST:/home/billbuddy/billbuddy/credentials/
# on the VPS:
sudo systemctl restart billbuddy
```
