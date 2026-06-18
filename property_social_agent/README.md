# Property Social Agent

An AI agent that runs **on your own computer** and, on a weekly schedule:

1. **Scans** your property photo folders and **selects** the best photos for one property.
2. **Reads** that property's description file and **summarizes** it with Claude.
3. **Generates** ready-to-post Instagram + Facebook captions and hashtags.
4. **Emails you the draft + photos for approval.**
5. **Posts on your behalf** to Instagram and your Facebook Page once you reply `APPROVE`.

It rotates between properties week to week and avoids reusing photos it recently posted.

```
scan folders → pick property → select photos → read + summarize copy (Claude)
   → write captions (Claude) → email you → wait for "APPROVE" → post to IG + FB
```

> **Why this runs on your machine:** scanning local folders and posting to your
> accounts both need access to your computer and your credentials. This project
> is the agent you run locally — it is not a hosted service.

---

## Quick start

```bash
cd property_social_agent
python3 -m venv .venv && source .venv/bin/activate     # optional but recommended
pip install -r requirements.txt

cp .env.example .env                # fill in secrets
cp config.example.yaml config.yaml  # edit paths + preferences

# See which property folders the agent can find:
python -m property_social_agent list-properties

# Test the whole pipeline WITHOUT calling Claude, emailing, or posting:
python -m property_social_agent run --dry-run

# Do it for real (selects, generates, emails you, waits for approval, posts):
python -m property_social_agent run
```

`.env`, `config.yaml`, and `agent_state.json` are git-ignored — your secrets stay local.

---

## Folder layout the agent expects

Point `photos_root` in `config.yaml` at a folder containing one subfolder per property.
Put the property's description (the "copy") in the same folder:

```
/Users/you/Properties/
├── 123-main-st/
│   ├── front.jpg
│   ├── kitchen.jpg
│   ├── backyard.jpg
│   └── description.md      ← the copy the agent summarizes
└── 45-ocean-ave/
    ├── ...
    └── description.txt
```

Recognized description filenames and photo extensions are configurable in `config.yaml`.
`.txt`, `.md`, and `.pdf` descriptions are supported.

---

## How photos are selected

- **heuristic** mode ranks photos by resolution + sharpness (via Pillow) and skips
  any photo posted within `reuse_after_days`.
- **vision** mode additionally asks Claude to pick the most appealing shots from a
  shortlist (needs `ANTHROPIC_API_KEY`). Falls back to heuristic on any error.

`photos_per_post` controls how many are included (Instagram carousels allow up to 10).

---

## Configuration

- **`config.yaml`** — folder paths, property rotation, photo count, brand voice,
  hashtags, which platforms are on, image hosting, and approval-email settings.
  Start from `config.example.yaml`, which is fully commented.
- **`.env`** — all secrets (API keys, tokens, email passwords). Start from `.env.example`.

The content model defaults to `claude-opus-4-8`; set `content.model` to
`claude-sonnet-4-6` for a cheaper option.

---

## Meta (Instagram + Facebook) setup

Posting to Instagram and a Facebook Page uses the **Meta Graph API**. One-time setup:

1. Create a **Meta app** at <https://developers.facebook.com/> (Business type).
2. Connect a **Facebook Page** and an **Instagram Business/Creator account** that is
   **linked to that Page** (Instagram personal accounts cannot be posted to via API).
3. Grant these permissions: `pages_manage_posts`, `pages_read_engagement`,
   `instagram_basic`, `instagram_content_publish`.
4. Generate a **long-lived Page access token** → put it in `META_ACCESS_TOKEN`.
5. Find your **Facebook Page ID** (`FB_PAGE_ID`) and **Instagram Business Account ID**
   (`IG_BUSINESS_ACCOUNT_ID`) via the Graph API Explorer, and set them in `.env`.

### Instagram needs public image URLs

Instagram's API fetches post images from a **public URL** (you can't upload raw bytes).
Choose an `image_host` in `config.yaml`:

- **`s3`** — the agent uploads the selected photos to an S3-compatible bucket
  (AWS S3, Cloudflare R2, MinIO) and uses those URLs. Fill in the `S3_*` vars in `.env`.
- **`base_url`** — if you already serve your `photos_root` at a public URL, set
  `image_host.base_url` and the agent maps file paths to that URL. No upload needed.
- **`none`** — skips Instagram image hosting. Facebook still works (it accepts direct
  uploads), but Instagram posting will be disabled.

---

## Email approval

The agent emails the draft (captions + photo attachments) to `approval.recipient`,
then watches that inbox for your reply.

- Reply containing **`APPROVE <token>`** → it posts.
- Reply containing **`REJECT <token>`** → it posts nothing.
- No reply within `approval.timeout_minutes` → it posts nothing.

The `<token>` is unique per run and appears in the email subject and body.

**Gmail:** create an [App Password](https://myaccount.google.com/apppasswords) and use
it for both `SMTP_PASSWORD` and `IMAP_PASSWORD` (not your normal password).

---

## Running it weekly

The agent runs one cycle per invocation; schedule it with your OS scheduler.

**macOS / Linux (cron)** — every Monday at 9am:

```cron
0 9 * * 1  cd /path/to/property_social_agent && /path/to/.venv/bin/python -m property_social_agent run >> agent.log 2>&1
```

**macOS (launchd)** — create `~/Library/LaunchAgents/com.you.propertyagent.plist`
with a `StartCalendarInterval` for Weekday 1, Hour 9, pointing `ProgramArguments` at
your venv python, `-m`, `property_social_agent`, `run`; then `launchctl load` it.

**Windows (Task Scheduler)** — create a Weekly task (Monday 9:00am) whose action runs
`...\.venv\Scripts\python.exe -m property_social_agent run` with "Start in" set to the
project folder.

Because approval is by email, the machine just needs to be on and online at the
scheduled time; you can approve from your phone whenever the email arrives.

---

## Commands

| Command | Description |
| --- | --- |
| `python -m property_social_agent list-properties` | List property folders + when each was last posted |
| `python -m property_social_agent run --dry-run` | Select + draft only; no Claude call, no email, no posting |
| `python -m property_social_agent run` | Full cycle: select → generate → email → approve → post |

Use `-c path/to/config.yaml` and `-s path/to/state.json` to override file locations.

---

## How it stays organized across weeks

`agent_state.json` records which property was featured and which photos were posted,
so rotation (`property_selection: rotate`) advances to the least-recently-posted
property and photos aren't reused within `reuse_after_days`.

---

## Project layout

```
property_social_agent/
├── README.md
├── requirements.txt
├── .env.example            # secrets template
├── config.example.yaml     # settings template
└── property_social_agent/
    ├── config.py           # loads config.yaml + .env
    ├── state.py            # rotation / posted-photo history
    ├── photo_selector.py   # scan + score + pick photos
    ├── copy_reader.py      # read description files (txt/md/pdf)
    ├── content_generator.py# Claude: summarize + write captions + rank photos
    ├── image_host.py       # public image hosting for Instagram (s3 / base_url)
    ├── approval.py         # email the draft, poll inbox for APPROVE/REJECT
    ├── agent.py            # orchestrator
    ├── cli.py              # command-line entry point
    └── publishers/
        ├── facebook.py     # Facebook Page multi-photo post
        └── instagram.py    # Instagram single image / carousel
```
