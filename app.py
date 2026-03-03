from __future__ import annotations

import html
import sqlite3
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "marketing_tracker.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS initiatives (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                channel TEXT NOT NULL,
                owner TEXT NOT NULL,
                quarter TEXT NOT NULL,
                budget REAL NOT NULL,
                objective TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS performance_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                initiative_id INTEGER NOT NULL,
                metric_name TEXT NOT NULL,
                baseline_value REAL NOT NULL,
                target_value REAL NOT NULL,
                current_value REAL NOT NULL,
                FOREIGN KEY (initiative_id) REFERENCES initiatives(id)
            );
            """
        )


def fetch_dashboard_data() -> tuple[list[sqlite3.Row], list[sqlite3.Row], sqlite3.Row]:
    with get_connection() as conn:
        initiatives = conn.execute(
            """
            SELECT i.*, COUNT(pm.id) AS metric_count
            FROM initiatives i
            LEFT JOIN performance_metrics pm ON pm.initiative_id = i.id
            GROUP BY i.id
            ORDER BY i.id DESC
            """
        ).fetchall()
        metrics = conn.execute(
            """
            SELECT pm.*, i.name AS initiative_name
            FROM performance_metrics pm
            JOIN initiatives i ON i.id = pm.initiative_id
            ORDER BY pm.id DESC
            """
        ).fetchall()
        scorecard = conn.execute(
            """
            SELECT
                COUNT(DISTINCT i.id) AS initiatives,
                COUNT(pm.id) AS metrics,
                ROUND(AVG((pm.current_value / NULLIF(pm.target_value, 0)) * 100), 1) AS avg_target_progress,
                ROUND(SUM(i.budget), 2) AS total_budget
            FROM initiatives i
            LEFT JOIN performance_metrics pm ON pm.initiative_id = i.id
            """
        ).fetchone()
    return initiatives, metrics, scorecard


def esc(value: object) -> str:
    return html.escape(str(value if value is not None else ""))


def render_page() -> str:
    initiatives, metrics, scorecard = fetch_dashboard_data()

    initiative_options = "".join(
        f'<option value="{i["id"]}">{esc(i["name"])} ({esc(i["quarter"])})</option>' for i in initiatives
    )
    initiatives_rows = "".join(
        "<tr>"
        f"<td>{esc(i['name'])}</td><td>{esc(i['channel'])}</td><td>{esc(i['owner'])}</td>"
        f"<td>{esc(i['quarter'])}</td><td>${i['budget']:.2f}</td><td>{i['metric_count']}</td><td>{esc(i['objective'])}</td>"
        "</tr>"
        for i in initiatives
    ) or '<tr><td colspan="7">No initiatives added yet.</td></tr>'

    metric_rows = "".join(
        "<tr>"
        f"<td>{esc(m['initiative_name'])}</td><td>{esc(m['metric_name'])}</td><td>{m['baseline_value']}</td>"
        f"<td>{m['target_value']}</td><td>{m['current_value']}</td>"
        f"<td>{(m['current_value'] / m['target_value'] * 100) if m['target_value'] else 0:.1f}%</td>"
        "</tr>"
        for m in metrics
    ) or '<tr><td colspan="6">No metrics mapped yet.</td></tr>'

    return f"""<!doctype html>
<html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Marketing Initiative Tracker</title><link rel='stylesheet' href='/static/style.css'></head>
<body><main class='layout'>
<header><h1>Marketing Initiative Tracker</h1><p>Map campaigns to business outcomes and keep progress visible for every quarter.</p></header>
<section class='scorecards'>
<article><h2>{scorecard['initiatives'] or 0}</h2><p>Active initiatives</p></article>
<article><h2>{scorecard['metrics'] or 0}</h2><p>Tracked metrics</p></article>
<article><h2>{scorecard['avg_target_progress'] or 0}%</h2><p>Average target progress</p></article>
<article><h2>${(scorecard['total_budget'] or 0):.2f}</h2><p>Total budget mapped</p></article>
</section>
<section class='forms-grid'>
<form method='post' action='/initiatives' class='card'>
<h3>Add initiative</h3>
<label>Name<input name='name' required></label>
<label>Channel<input name='channel' required></label>
<label>Owner<input name='owner' required></label>
<label>Quarter<input name='quarter' required placeholder='2026-Q2'></label>
<label>Budget<input type='number' step='0.01' min='0' name='budget' required></label>
<label>Objective<textarea name='objective' rows='3' required></textarea></label>
<button type='submit'>Save initiative</button></form>
<form method='post' action='/metrics' class='card'>
<h3>Map performance metric</h3>
<label>Initiative<select name='initiative_id' required>{initiative_options}</select></label>
<label>Metric name<input name='metric_name' required></label>
<label>Baseline value<input type='number' step='0.01' name='baseline_value' required></label>
<label>Target value<input type='number' step='0.01' name='target_value' required></label>
<label>Current value<input type='number' step='0.01' name='current_value' required></label>
<button type='submit' {'disabled' if not initiatives else ''}>Save metric</button>
{'<p class="hint">Create an initiative first to map metrics.</p>' if not initiatives else ''}
</form></section>
<section class='tables-grid'>
<article class='card'><h3>Initiatives</h3><table><thead><tr><th>Name</th><th>Channel</th><th>Owner</th><th>Quarter</th><th>Budget</th><th>Metrics</th><th>Objective</th></tr></thead><tbody>{initiatives_rows}</tbody></table></article>
<article class='card'><h3>Metrics mapped to initiatives</h3><table><thead><tr><th>Initiative</th><th>Metric</th><th>Baseline</th><th>Target</th><th>Current</th><th>% to target</th></tr></thead><tbody>{metric_rows}</tbody></table></article>
</section></main></body></html>"""


class AppHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/":
            page = render_page().encode()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(page)))
            self.end_headers()
            self.wfile.write(page)
            return

        if self.path == "/static/style.css":
            css = (BASE_DIR / "static" / "style.css").read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/css; charset=utf-8")
            self.send_header("Content-Length", str(len(css)))
            self.end_headers()
            self.wfile.write(css)
            return

        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        data = {k: v[0] for k, v in parse_qs(body).items()}

        if self.path == "/initiatives":
            with get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO initiatives (name, channel, owner, quarter, budget, objective)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        data["name"],
                        data["channel"],
                        data["owner"],
                        data["quarter"],
                        float(data["budget"]),
                        data["objective"],
                    ),
                )
            return self.redirect_home()

        if self.path == "/metrics":
            with get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO performance_metrics (initiative_id, metric_name, baseline_value, target_value, current_value)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        int(data["initiative_id"]),
                        data["metric_name"],
                        float(data["baseline_value"]),
                        float(data["target_value"]),
                        float(data["current_value"]),
                    ),
                )
            return self.redirect_home()

        self.send_error(HTTPStatus.NOT_FOUND)

    def redirect_home(self) -> None:
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", "/")
        self.end_headers()


def run_server(port: int = 8000) -> None:
    init_db()
    server = ThreadingHTTPServer(("0.0.0.0", port), AppHandler)
    print(f"Server running at http://localhost:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run_server()
