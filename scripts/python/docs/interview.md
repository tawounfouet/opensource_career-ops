# Interview

Interview preparation tools.

## STAR Matching Flow

```
  +------------------+     +------------------+
  | Behavioral Qs    |     | interview-prep/  |
  | from JD /        |     | story-bank.md    |
  | interviewer      |     | (STAR+R stories) |
  +--------+---------+     +--------+---------+
           |                        |
           +-----------+------------+
                       |
                       v
              +------------------+
              | match_star.py    |
              |                  |
              | fuzzy match:     |
              | question -> story|
              |                  |
              | best-fit story   |
              | for each question|
              +--------+---------+
                       |
                       v
              +------------------+
              | Matched Output   |
              |                  |
              | Q: "Tell me about|
              | a time you..."   |
              |                  |
              | Story: "At Acme, |
              | I led X project" |
              +------------------+

  Optional: company-specific prep
  +------------------+
  | interview-prep/  |
  | {co}-{role}.md   |
  +------------------+
```

## Modules

### `match_star.py`
Matches behavioral interview questions to STAR stories from the user's story bank (`interview-prep/story-bank.md`). Uses fuzzy matching to find the best-fit story for each question.

```
python -m scripts.python.interview.match_star
npm run star
```

## Data Sources

- `interview-prep/story-bank.md` — accumulated STAR+R stories
- `interview-prep/{company}-{role}.md` — company-specific interview intel
- `cv.md` — experience and achievements

## CLI Bridge

```bash
python -m scripts.python.interview match-star
```
