from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app


def test_home_page_loads(tmp_path, monkeypatch):
    test_db = tmp_path / "test.db"
    monkeypatch.setattr(app, "DB_PATH", test_db)
    app.init_db()

    html = app.render_page()

    assert "Marketing Initiative Tracker" in html
    assert "No initiatives added yet." in html
