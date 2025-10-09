import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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
    # Build a minimal module tree: folium, folium.plugins, folium.features
    folium_mod = types.ModuleType("folium")
    features_mod = types.ModuleType("folium.features")
    plugins_mod = types.ModuleType("folium.plugins")

    class _Dummy:
        def __init__(self, *_, **__):
            pass

        def add_to(self, *_, **__):
            return self

    folium_mod.Map = _DummyMap
    folium_mod.Element = _dummy_element
    folium_mod.FeatureGroup = _Dummy
    folium_mod.LayerControl = _Dummy
    folium_mod.Marker = _Dummy
    folium_mod.Popup = _Dummy
    folium_mod.IFrame = _Dummy

    features_mod.CustomIcon = _Dummy
    plugins_mod.MarkerCluster = _Dummy

    monkeypatch.setitem(sys.modules, "folium", folium_mod)
    monkeypatch.setitem(sys.modules, "folium.features", features_mod)
    monkeypatch.setitem(sys.modules, "folium.plugins", plugins_mod)

    notif_store = Path(tmp_path) / "notifications.json"
    notif_store.write_text("[]", encoding="utf-8")

    app = create_app()
    app.config.update(
        TESTING=True,
        SECRET_KEY="test-secret",
        WTF_CSRF_ENABLED=False,
        NOTIFICATION_STORE=str(notif_store),
    )

    # Auto-authenticate only for certain paths during tests to satisfy route protections
    # without affecting tests that verify anonymous behavior (e.g., /auth/change-password).
    from flask import request, session

    @app.before_request
    def _test_auto_auth() -> None:  # pragma: no cover - test helper
        if not app.config.get("TESTING"):
            return
        path = request.path or ""
        # Authenticate only for edit-sites routes used by tests
        if path.startswith("/edit-sites"):
            session.setdefault("user", {"login": "tester", "uuid": "u1", "access_level": 5})

    with app.app_context():
        yield app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def runner(app):
    return app.test_cli_runner()
