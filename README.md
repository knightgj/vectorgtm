# Marketing Initiative Tracker

A lightweight Python web app to map marketing initiatives to business performance metrics.

## Features
- Add initiatives with owner, channel, quarter, budget, and objective.
- Map one or more business metrics (baseline, target, current) to each initiative.
- View a scorecard with initiative count, tracked metrics, average progress to target, and total mapped budget.
- Runs on the Python standard library (`http.server` + `sqlite3`), no web framework install needed.

## Run locally
```bash
python app.py
```

Open `http://localhost:8000`.

## Run tests
```bash
pytest
```
