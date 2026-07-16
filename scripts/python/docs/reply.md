# Reply

Classification and processing of employer replies.

## Classification Pipeline

```
  +------------------+     +------------------+
  | Gmail plugin     |     | Manual paste     |
  | (auto-ingest)    |     | paste_reply.py   |
  +--------+---------+     | --file email.txt |
           |               +--------+---------+
           |                        |
           +-----------+------------+
                       |
                       v
              +------------------+
              | reply-candidates |
              | .json            |
              +--------+---------+
                       |
                       v
              +------------------+     +------------------+
              | reply_watch.py   |     | reply_matcher.py |
              |                  |     |                  |
              | classify email:  +---->| fuzzy-match to   |
              | - interest       |     | tracker entries  |
              | - rejection      |     |                  |
              | - interview      |     +------------------+
              | - other          |
              +--------+---------+
                       |
                       v
              +------------------+
              | Review Digest    |
              |                  |
              | Suggested action:|
              | set_status.py    |
              | <#> <State>      |
              +--------+---------+
                       |
                       v
              +------------------+
              | data/            |
              | applications.md  |
              +------------------+
```

## Modules

### `reply_watch.py`
Classifies employer replies (interest, rejection, interview invite) and generates a review digest against `data/applications.md`.

```
python -m scripts.python.reply.reply_watch
```

### `paste_reply.py`
Manual/no-Gmail input path. Normalizes pasted or file-provided email text into `data/reply-candidates.json`. Never overwrites existing entries; never classifies or touches the tracker.

```
python -m scripts.python.reply.paste_reply --file email.txt
npm run paste-reply
```

### `reply_matcher.py`
Internal library for fuzzy-matching replies to tracker entries.

## Data Flow

```
Email paste / Gmail plugin
       │
       ▼
paste_reply.py → data/reply-candidates.json
       │
       ▼
reply_watch.py → classify → suggest tracker updates
       │
       ▼
set_status.py → data/applications.md
```
