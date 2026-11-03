from __future__ import annotations

from pathlib import Path

from launch_delay_watch.snapshot import (
    SNAPSHOT_COLUMNS,
    fetch_upcoming,
    normalize_launch,
    write_snapshot,
)


class _FakeResp:
    def __init__(self, payload: dict):
        self._payload = payload
        self.status_code = 200

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class _FakeSession:
    def __init__(self, payload: dict):
        self.payload = payload
        self.urls: list[str] = []

    def get(self, url: str, timeout: float = 60.0):
        self.urls.append(url)
        return _FakeResp(self.payload)


def test_normalize_launch(upcoming_payload: dict) -> None:
    row = normalize_launch(upcoming_payload["results"][0])
    assert row["id"] == "abc-111"
    assert row["provider"] == "SpaceX"
    assert row["rocket"] == "Falcon 9 Block 5"
    assert "Space Launch Complex 40" in row["pad"]
    assert row["status"] == "Go"
    assert row["net"].endswith("Z")


def test_fetch_upcoming_no_network(upcoming_payload: dict) -> None:
    session = _FakeSession(upcoming_payload)
    df = fetch_upcoming(session=session)
    assert list(df.columns) == SNAPSHOT_COLUMNS
    assert len(df) == 2
    assert df.iloc[0]["provider"] == "SpaceX"
    assert df.iloc[1]["rocket"] == "Electron"
    assert len(session.urls) == 1


def test_write_snapshot(tmp_path: Path, upcoming_payload: dict) -> None:
    session = _FakeSession(upcoming_payload)
    df = fetch_upcoming(session=session)
    path = write_snapshot(df, date="2026-11-03", directory=tmp_path)
    assert path.name == "2026-11-03.csv"
    assert path.is_file()
    text = path.read_text()
    assert "SpaceX" in text
    assert text.splitlines()[0] == ",".join(SNAPSHOT_COLUMNS)
