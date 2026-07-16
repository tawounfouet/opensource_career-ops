# Export

Dashboard and data export utilities.

## Dashboard Build Flow

```
  +------------------+
  | applications.md  |
  | pipeline.md      |
  | reports/*.md     |
  +--------+---------+
           |
           v
  +------------------+     +------------------+     +------------------+
  | build_dashboard  |     | dashboard/       |     | TUI Dashboard    |
  | .py              +---->| Go binary        +---->|                  |
  | data aggregation |     | (build)          |     | interactive      |
  +------------------+     +------------------+     | pipeline view    |
                                                    +------------------+
  Commands:
    npm run build:dashboard    # Build Go binary
    npm run serve:dashboard    # Launch TUI
```

## Modules

### `build_dashboard.py`
Builds the Go TUI dashboard from application data.

```
python -m scripts.python.export.build_dashboard
npm run build:dashboard
```

The dashboard itself is a Go application in `dashboard/`, served via:
```
npm run serve:dashboard
```

## CLI Bridge

```bash
python -m scripts.python.export build-dashboard
```
