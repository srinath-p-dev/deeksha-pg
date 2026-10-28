# Deploying to a VPS

The whole app runs with one command (`docker compose up -d`) on any Linux server.
Expect 1–2 hours the first time.

## 0. What you need

| Item | Notes |
|---|---|
| A VPS | Ubuntu 24.04, **2 GB RAM minimum** (4 GB comfortable), 25 GB disk. Free: Oracle Cloud "Always Free" (Mumbai/Hyderabad). Paid ~₹400–600/mo: Hetzner, DigitalOcean (Bangalore), etc. |
| A free domain | https://www.duckdns.org — e.g. `yourpg.duckdns.org` |
| Bot SIM | A new prepaid SIM with WhatsApp installed on a spare phone |
| Gmail App Password | For "WhatsApp disconnected" emails (optional but recommended) |
| GitHub account | Private repo for the code |

## 1. Put the code on GitHub (on your PC)

```powershell
git init
git add .
git status          # make sure .env is NOT listed
git commit -m "PG Manager"
# create an empty PRIVATE repo on github.com, then:
git remote add origin https://github.com/<you>/<repo>.git
git push -u origin main
```

## 2. Prepare the server

```bash
ssh root@<server-ip>

# Updates + firewall (only SSH and web open)
apt update && apt upgrade -y
apt install -y ufw git gpg rclone
ufw allow OpenSSH && ufw allow 80 && ufw allow 443 && ufw --force enable

# Docker
curl -fsSL https://get.docker.com | sh

# A normal user to run the app
adduser deploy && usermod -aG docker deploy
su - deploy
```

> Oracle Cloud: also open ports 80 and 443 in the VCN "Security List" (web console), not just ufw.

## 3. Point the domain at the server

On duckdns.org: create a subdomain (e.g. `yourpg`), put the server's public IP in "current ip", click update.
Check from your PC: `ping yourpg.duckdns.org` should show the server IP.

## 4. Configure

```bash
git clone https://github.com/<you>/<repo>.git pg-app
cd pg-app
cp .env.production.example .env
openssl rand -hex 24   # run 3 times; paste into POSTGRES_PASSWORD, WHATSAPP_TOKEN, BACKUP_PASSPHRASE
nano .env              # set DOMAIN, secrets, SMTP_* (see step 7)
chmod 600 .env
```

**Write `BACKUP_PASSPHRASE` down somewhere safe** (password manager). Without it, backups can't be opened.

## 5. Start

```bash
docker compose up -d --build        # first build takes ~5–10 minutes
docker compose ps                   # all "Up"; api "healthy"
docker compose logs -f caddy        # watch for "certificate obtained successfully", then Ctrl+C
```

Open `https://yourpg.duckdns.org` — the public site should load with a padlock.

## 6. First-time data

```bash
docker compose exec api python -m app.cli seed
docker compose exec api python -m app.cli create-user --email <owner email> --name "<Owner name>" --role owner --alerts
docker compose exec api python -m app.cli create-user --email <admin email> --name "<Admin name>" --role admin   # optional
```

Then in the dashboard:

1. **Website** → PG name, address, phone, WhatsApp, maps link, about text, photos.
2. **Rates** → fill in the rent for each category / sharing type (leave 6th floor empty = enter per tenant).
3. **Settings** → owner WhatsApp number (gets alerts); payment details (UPI id) for reminders.
4. **Tenants** → add everyone. For tenants with older unpaid months, use "+ Add month" on their page.

## 7. Email alerts (Gmail)

1. Google Account → Security → turn on **2-Step Verification**.
2. https://myaccount.google.com/apppasswords → create one called "PG app".
3. In `.env`: `SMTP_USER=<gmail address>`, `SMTP_PASSWORD=<16-char app password>`, `SMTP_FROM=<same address>`.
4. `docker compose up -d worker` to apply.

Alerts go to users created with `--alerts` (the owner).

## 8. Link WhatsApp

1. Put the new SIM in the spare phone, install WhatsApp, register the number.
2. **Warm it up for ~1 week**: save it as a contact on tenants' phones (ask them), chat normally a bit. Brand-new numbers that suddenly message 50 people are the most likely to get banned.
3. Dashboard → **WhatsApp** → a QR code appears. On the bot phone: Settings → Linked devices → Link a device → scan.
4. Click **Send test message to owner**.

Keep the bot phone charged and online now and then — WhatsApp unlinks devices if the phone is offline for ~14 days.

## 9. Backups

```bash
# Connect rclone to Google Drive (headless server):
rclone config        # n (new) → name: gdrive → storage: drive → defaults…
                     # "Use auto config?" → n → it prints a command; run that on your PC
                     # (install rclone on Windows from rclone.org), log in, paste the token back
chmod +x scripts/*.sh
./scripts/backup.sh                       # test it once; check Google Drive for the file

crontab -e                                # add this line (server clock is UTC → 21:00 UTC = 2:30 AM IST):
0 21 * * * /home/deploy/pg-app/scripts/backup.sh >> /home/deploy/backup.log 2>&1
```

**Test a restore** once (on a test server or locally) so you know it works:
`./scripts/restore.sh backups/pgapp-YYYYMMDD-HHMM.tar.gpg`

## 10. Updating the app later

```bash
cd ~/pg-app
git pull
docker compose up -d --build     # rebuilds changed parts; migrations run automatically
```

## Troubleshooting

| Problem | Check |
|---|---|
| Site doesn't load / no HTTPS | `docker compose logs caddy` — DNS must point to the server, ports 80/443 open |
| "WhatsApp service is not running" banner | `docker compose ps whatsapp`, `docker compose logs whatsapp` |
| WhatsApp keeps showing QR | Phone unlinked it — scan again. If the number got banned, use a new SIM |
| Messages stuck in "pending" | WhatsApp disconnected, or the daily limit (`WA_DAILY_LIMIT`) was reached |
| Message shows "unknown" | Server restarted mid-send; check with the tenant, then "Send again" if needed |
| Forgot password | `docker compose exec api python -m app.cli set-password --email you@example.com` |
| Out of memory | `free -h`; 2 GB servers can add swap: `fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile` |

Useful: `docker compose logs -f worker` shows reminders being queued and sent.
