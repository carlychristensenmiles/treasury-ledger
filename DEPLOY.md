# Deploying to Fly.io

This repo is deploy-ready: a `Dockerfile` (installs Tesseract OCR as a real
system package, which a plain `pip install`-only platform like Vercel's
standard Python runtime can't do) and a `fly.toml` (configures a persistent
volume for the SQLite database, so client data survives restarts and
redeploys — the thing a fully serverless platform can't guarantee).

You do **not** need Docker installed locally — `fly deploy` builds the image
on Fly's own remote builders by default.

## 1. Install the Fly CLI and log in

```bash
curl -L https://fly.io/install.sh | sh
# or: brew install flyctl   (macOS)

fly auth login
```

This opens a browser to sign up / log in. Fly.io requires a credit card on
file even though the smallest usage is a few dollars a month — there's no
truly free tier anymore.

## 2. Create the app

`fly.toml` already has an app name (`treasury-ledger`) and region (`iad`,
US East) picked. If that name is taken on Fly (names are global), either
change `app = "..."` at the top of `fly.toml` first, or let Fly generate one:

```bash
fly apps create treasury-ledger
# if that name is taken:
#   fly apps create --generate-name
#   (then update the `app = "..."` line in fly.toml to match what it picked)
```

Change `primary_region` in `fly.toml` too if `iad` isn't the closest region
to you/your clients — `fly platform regions` lists the options.

## 3. Create the persistent volume

This is the piece that makes the database actually durable — skip it and
the app will still boot, but `/data` won't be backed by real storage.

```bash
fly volumes create treasury_ledger_data -r iad -s 1 -a treasury-ledger
```

`-s 1` is 1GB, plenty of headroom for a SQLite file of fund + client data
(the seeded fund database itself is a few MB). The volume name
(`treasury_ledger_data`) must match the `source` value under `[[mounts]]`
in `fly.toml` — if you changed one, change the other.

## 4. Set the session secret

`SECRET_KEY` signs login session cookies — don't deploy with the placeholder
default baked into `app/main.py`.

```bash
fly secrets set SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')" -a treasury-ledger
```

## 5. Deploy

```bash
fly deploy
```

This builds the Docker image remotely, pushes it, and starts a machine with
the volume attached. First boot seeds the fund database automatically (see
`app/main.py` — it checks if the Fund table is empty and loads
`data/funds_*.csv` if so, specifically so this step doesn't need a manual
`fly ssh console` command after every fresh deploy).

## 6. Check it

```bash
fly status -a treasury-ledger      # is it running?
fly logs -a treasury-ledger        # watch the seed-on-first-boot log line
```

Then visit `https://treasury-ledger.fly.dev` (or whatever your app name
resolved to) — Fly gives you HTTPS on that `.fly.dev` subdomain
automatically. A custom domain can be attached later with `fly certs add
yourdomain.com`.

## Cost

`fly.toml` sets `min_machines_running = 1` — one machine stays warm at all
times rather than scaling to zero, so a login or an OCR-heavy upload never
hits a cold start. That's a deliberate tradeoff: it costs a small amount
continuously (roughly $2/month for the smallest shared-cpu VM, plus about
$0.15/GB/month for the volume — a few dollars total) instead of being free
when idle. If cost matters more than avoiding cold starts, remove
`min_machines_running = 1` from `fly.toml` (or set it to `0`) and Fly will
suspend the machine after periods of no traffic, waking it on the next
request.

## Updating the fund database for a new tax year

The fund CSVs are baked into the Docker image (`COPY data/ ./data/` in the
Dockerfile), so a new tax year's data needs a rebuild-and-redeploy, not a
live edit:

1. Follow `data/README.md` to regenerate `data/funds_*.csv` for the new year.
2. Commit that.
3. `fly deploy` again.

The seed step is idempotent (see `app/seed.py`), so redeploying with updated
CSVs safely refreshes existing rows rather than duplicating them — but it
only runs automatically when the Fund table is *empty*. To force a refresh
against a database that's already seeded (e.g. you fixed a percentage),
run the seed script directly against the running app instead:

```bash
fly ssh console -a treasury-ledger -C "python scripts/seed_db.py"
```
