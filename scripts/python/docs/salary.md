# Salary

Compensation gap analysis.

## Analysis Flow

```
  +------------------+     +------------------+     +------------------+
  | config/          |     | reports/*.md     |     | data/            |
  | profile.yml      |     | Block E:         |     | salary-          |
  | desired range    |     | advertised_comp  |     | observations.tsv |
  +--------+---------+     +--------+---------+     +--------+---------+
           |                        |                        |
           +------------------------+------------------------+
                                    |
                                    v
                          +------------------+
                          | salary_gap.py    |
                          |                  |
                          | gap = desired    |
                          |     - advertised |
                          |     - actual     |
                          +--------+---------+
                                   |
                            +------+------+
                            |             |
                            v             v
                     +-----------+  +-----------+
                     | JSON      |  | --summary |
                     | machine   |  | table +   |
                     | readable  |  | data-qty  |
                     +-----------+  +-----------+
```

## Modules

### `salary_gap.py`
Analyzes desired vs advertised vs actual compensation gaps. Folds report `advertised_comp` + `data/salary-observations.tsv`.

```
python -m scripts.python.salary.salary_gap             # JSON output
python -m scripts.python.salary.salary_gap --summary   # Table + data-quality section
```

## Data Sources

- `config/profile.yml` — desired salary range
- `reports/*.md` — advertised compensation (parsed from Block E)
- `data/salary-observations.tsv` — append-only observation log

## CLI Bridge

```bash
python -m scripts.python.salary salary-gap --summary
```
