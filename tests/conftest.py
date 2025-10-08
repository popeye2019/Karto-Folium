import sys
import types
from pathlib import Path

import pytest

from app import create_app


class _DummyElement:
    def __init__(self, content: str):
        self.content = content

    def render(self) -> str:
        return self.content


class _DummyContainer:
    def __init__(self):
        self.children: list[_DummyElement] = []

    def add_child(self, element: _DummyElement) -> None:
        self.children.append(element)


class _DummyRoot:
    def __init__(self):
        self.html = _DummyContainer()
        self.script = _DummyContainer()

    def render(self) -> str:
        return "<div>dummy folium map</div>"


class _DummyMap:
    _counter = 0

    def __init__(self, *_, **__):
        type(self)._counter += 1
        self._name = f"dummy_map_{type(self)._counter}"
        self._root = _DummyRoot()

    def get_name(self) -> str:
        return self._name

    def get_root(self) -> _DummyRoot:
        return self._root


def _dummy_element(content: str) -> _DummyElement:
    return _DummyElement(content)


@pytest.fixture()
def app(tmp_path, monkeypatch):
    """Create a Flask app instance configured for tests."""
    # Provide a lightweight stand-in for folium so blueprints import cleanly.
    dummy_folium = types.SimpleNamespace(Map=_DummyMap, Element=_dummy_element)
    monkeypatch.setitem(sys.modules, "folium", dummy_folium)

    notif_store = Path(tmp_path) / "notifications.json"
    notif_store.write_text("[]", encoding="utf-8")

    app = create_app()
    app.config.update(
        TESTING=True,
        SECRET_KEY="test-secret",
        WTF_CSRF_ENABLED=False,
        NOTIFICATION_STORE=str(notif_store),
    )

    with app.app_context():
        yield app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def runner(app):
    return app.test_cli_runner()
