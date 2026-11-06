# Going live: the 4 to-dos (do them in this order)

| # | To-do | Who | Time |
|---|---|---|---|
| 1 | Buy the **OVH server** and prepare it | you (script does the rest) | 30 min |
| 2 | Buy the **domain** and point it at the server | you | 15 min |
| 3 | **Code on GitHub** (code is already cleaned up and committed) | you push | 10 min |
| 4 | **GitHub pipeline**: tests → your approval → deploy to OVH, then go live | you click, pipeline works | 30 min |

Names used below: server IP `SERVER_IP`, domain `tunisiabasket.com`, your GitHub name `YOURNAME`. Replace them.

---

## 1. The OVH server

**Decision: OVHcloud VPS-1.** 2 vCPU, 4 GB RAM, 40 GB NVMe, unlimited traffic, daily backup included, listed from about
$4.54/month (check the price and VAT at checkout). More than this app needs, and France is the closest big hosting region to Tunisia.

**Buy:** <https://www.ovhcloud.com/en/vps/> → VPS-1 →
- **Image:** Ubuntu 24.04.
- **Location:** a French one (Gravelines, Roubaix or Strasbourg, if the order form offers them). To pick the fastest from Tunisia, run
  these three from your connection and choose the lowest: `ping gra.proof.ovh.net`, `ping rbx.proof.ovh.net`, `ping sbg.proof.ovh.net`.
- **SSH key:** paste your public key in the order form (on your Mac: `ssh-keygen -t ed25519`, then `cat ~/.ssh/id_ed25519.pub`).
- Wait for OVH's "your VPS is ready" email: it gives the **IP address** and the default **user** (usually `ubuntu`).

**Can't log in? (forgot the password / "Permission denied")**: a brand-new VPS holds nothing, so reinstall it with your key:
OVH Control Panel → Bare Metal Cloud → VPS → your server → **Reinstall** → Ubuntu 24.04, and choose your **SSH key** if the dialog offers it
(add it first under your account's SSH keys; your public key is the line printed by `cat ~/.ssh/id_ed25519.pub`). Otherwise OVH emails a new password.
Alternative without reinstalling: **Reboot in rescue mode**, then follow OVH's guide to mount the disk and reset the password
([OVH: rescue mode / change the root password](https://support.us.ovhcloud.com/hc/en-us/articles/4412634196115-How-to-Change-the-Root-Password-on-a-VPS)).
Test with: `ssh ubuntu@SERVER_IP` (note the **@**; the colon form `ubuntu@SERVER_IP:` is only for `scp`).

**"Your password has expired… Current password: … Authentication token manipulation error"**: OVH's first password must be changed at the first login, and the
server asks for it twice: at `ubuntu@…'s password:` AND again at `Current password:`. Both times type **the temporary password from OVH's email**
(nothing is shown while you type; copy it from the email so there is no typo), then choose a **new** password (12+ characters, not the old one, not your name)
and type it twice. That error means the "Current password" did not match, most often because a *new* password was typed there by mistake.
If the email is lost: OVH Control Panel → VPS → Reinstall (without an SSH key) sends a fresh password. After you are in, `provision.sh` installs your SSH key for you.

**Prepare the server (once), one command from your Mac.** In the project folder:
```bash
bash deploy/provision.sh SERVER_IP tunisiabasket.com
```
It creates the pipeline's deploy key if you do not have one (`~/.ssh/proastats_deploy`), asks for your Google Drive folder ID (the part after
`/folders/` in your Drive link; Enter skips it and keeps the automatic sync off), copies `setup.sh` to the server and runs it. It installs
Python, Tesseract and Caddy, creates the `deploy` and `proa` users, the folders, the firewall, fail2ban, automatic security updates and nightly
backups. It does not install the app (the pipeline does).

(Typing it by hand? `scp deploy/setup.sh ubuntu@SERVER_IP:` **needs the colon at the end**; without it, scp just makes a local file named `ubuntu@SERVER_IP`.)

**Done when:** the script ends with `SERVER READY`.

---

## 2. The domain

**`basket.com` is taken** (so are `basket.net` and `basketstats.com`). Free when I checked: **`tunisiabasket.com`** (my pick: it says what it is),
`proabasket.com`, `tnbasket.com`, `tunisiabasketball.com`, and the short `.tn` names `basket.tn` and `proabasket.tn`.

**Decision: buy `tunisiabasket.com` at Cloudflare** (at-cost price, about $10–11/year, free DNS/HTTPS/CDN):
1. Create an account at <https://dash.cloudflare.com/sign-up>.
2. Domain Registration → Register Domains → `tunisiabasket.com` → buy. (More about it: <https://www.cloudflare.com/products/registrar/>.)
3. Optional: `basket.tn` can only be bought from an ATI-accredited registrar and you must be a Tunisian resident or company. It would just redirect to the `.com`.
   Skip it for now.
4. Cloudflare → your domain → DNS → add two records, **DNS only (grey cloud)** for now:

| Type | Name | Content |
|---|---|---|
| A | `@` | `SERVER_IP` |
| A | `www` | `SERVER_IP` |

**Done when:** `ping tunisiabasket.com` shows `SERVER_IP`.

---

## 3. The code on GitHub

The code is cleaned up (lint-clean, tests added, one place for file paths, live data kept out of git) and committed on branch `main`.
Nothing secret is in it: no admin token, no logs, no uploads (`data/` is git-ignored).

**Decision (yours): PUBLIC repository, free.** The approval step in to-do 4 needs GitHub "Environments", which on the free plan exist only
for public repositories ([GitHub docs](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments)).
Public is safe here because I checked before publishing: no admin token, no passwords or keys, no live data, no local paths, and **no Google Drive
links** (the Drive folder is set on the server, never in the code). A test (`tests/test_repo_hygiene.py`) fails the pipeline if any of that ever
sneaks back in. The admin is protected by a token that is not in the code, and the pipeline refuses to deploy without a required reviewer.
What the world will see: the code, the 66 official results, the 48 box scores read so far (public sports data), and your commit name/email
(`Khalil <jridikhalil1995@gmail.com>`). To hide the email, use GitHub's "keep my email private" address and run
`git config user.email "<id>+<name>@users.noreply.github.com"` then `git commit --amend --reset-author --no-edit` before the first push.

1. Create the repository: <https://github.com/new> → name `proastats` → **do not** add a README → Public (or Private + Pro) → Create.
2. Let GitHub recognise your computer (one time): <https://github.com/settings/ssh/new> → Title `my Mac` → paste the line printed by
   `cat ~/.ssh/id_ed25519.pub` → Add SSH key. (This is your **personal** key. Never paste the deploy key `proastats_deploy` here.) Test: `ssh -T git@github.com`
   must answer `Hi YOURNAME!`.
3. From the project folder (the remote is already set to `git@github.com:khelilo7/tunisiabasket.git`; note the **colon** after `github.com`):
```bash
git remote -v                # check the address
git push -u origin main
```
4. Right after the push, in the repository: **Settings → Code security** → turn on **Secret scanning** and **Push protection** (free for public
   repos; it blocks you from pushing a key by mistake). Optional: Settings → Branches → protect `main`.

(The first push starts the pipeline: the tests run, the deploy waits or stops because to-do 4 is not set up yet. That is expected.)

**Done when:** the code is on GitHub and the **CI** job is green (Actions tab).

---

## 4. The pipeline: tests → your approval → OVH

What you get: every push to `main` runs the tests; if they pass, GitHub **waits for you to click Approve**; then it copies the new
version to the server, runs a smoke test, switches over, checks the site is healthy, and **rolls back by itself** if it is not.
Live data is never touched by a deploy.

**4a. Tell GitHub about the server: one command.** Install and log in to the GitHub CLI once (`brew install gh`, then `gh auth login`), then:
```bash
bash deploy/configure-github.sh khelilo7/tunisiabasket SERVER_IP tunisiabasket.com
```
It creates the `production` environment with **you as required reviewer** (the human approval) and only `main` allowed to deploy, stores the deploy private
key and the server's host key as secrets, sets the host/user/domain variables, and turns on secret scanning and push protection. Check the result at
`https://github.com/khelilo7/tunisiabasket/settings/environments`.
*By hand instead:* Settings → Environments → New environment `production` → Required reviewers (you) → Deployment branches: `main`; secrets `PROD_SSH_KEY`
(the whole private key file `~/.ssh/proastats_deploy`) and `PROD_SSH_KNOWN_HOSTS` (output of `ssh-keyscan -t ed25519 SERVER_IP`); variables
`PROD_HOST` = `SERVER_IP`, `PROD_USER` = `deploy`, `PRODUCTION_DOMAIN` = `tunisiabasket.com`.

**4b. First deploy.** Actions tab → the failed/waiting **Deploy** run → **Re-run all jobs** (or push any small change). When the `deploy` job
shows "Review pending", click **Review deployments → production → Approve and deploy**. It takes about 2 minutes.

**4c. Create your admin token** (on the server):
```bash
ssh ubuntu@SERVER_IP
sudo proastats-admin new-token        # prints the token once. Copy it somewhere safe.
```

**4d. Switch on Cloudflare protection** (after `http://tunisiabasket.com` answers):
1. Cloudflare → DNS: change both records to **Proxied (orange cloud)**.
2. SSL/TLS → Overview → **Full (strict)**; Edge Certificates → **Always Use HTTPS** on.
3. On the server, allow only Cloudflare to reach the web ports:
```bash
sudo bash /opt/proastats/current/deploy/firewall-cloudflare.sh
```

**4e. Prove the approval gate works.** Change one word in `README.md`, commit, push. Confirm the Deploy run **stops at "Review pending"** and
only continues after you approve. If it deploys by itself, stop and tell me.

**Done when:** `https://tunisiabasket.com` shows the app, `/admin` accepts your token, and a test push waited for your approval.

---

## Everyday

| I want to… | Do this |
|---|---|
| Ship a change | `git push` → open the Actions tab → approve when asked |
| Undo a bad release | Actions → **Rollback** → Run workflow → approve (or on the server: `bash /opt/proastats/current/deploy/release.sh --rollback`) |
| See admin activity | `sudo proastats-admin log` |
| New admin token | `sudo proastats-admin new-token` (logs everyone out) |
| Check the app on the server | `systemctl status proastats` · `journalctl -u proastats -n 100` |
| Copy the data to my Mac (backup) | `ssh ubuntu@SERVER_IP "sudo tar -C /opt/proastats/shared -czf - data" > ~/Backups/proastats-data-$(date +%F).tgz` |

More detail: `deploy/DEPLOY.md`.
