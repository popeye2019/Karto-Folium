from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass
class RouteInfo:
    file: str
    func: str
    rule: str
    login_required: bool
    level_present: bool


def _get_str(node: ast.AST, source: str) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    try:
        return ast.get_source_segment(source, node) or ""
    except Exception:
        return ""


def _parse_decorators(decs: Iterable[ast.AST], source: str) -> tuple[str, bool, bool]:
    rule = ""
    has_login = False
    has_level = False

    for d in decs:
        if isinstance(d, ast.Call):
            func = d.func
            # .route("/rule")
            if isinstance(func, ast.Attribute) and func.attr == "route":
                if d.args:
                    rule = _get_str(d.args[0], source)
            # require_level(...)
            if (isinstance(func, ast.Name) and func.id == "require_level") or (
                isinstance(func, ast.Attribute) and func.attr == "require_level"
            ):
                has_level = True
        elif isinstance(d, ast.Name) and d.id == "login_required":
            has_login = True
        elif isinstance(d, ast.Attribute) and d.attr == "login_required":
            has_login = True

    return rule, has_login, has_level


def collect_routes() -> list[RouteInfo]:
    root = Path(__file__).resolve().parents[1]
    results: list[RouteInfo] = []
    for p in (root / "app" / "blueprints").rglob("*.py"):
        # Skip auth and backup artifacts
        rel = p.as_posix()
        if rel.endswith("/auth.py") or "backup" in rel:
            continue
        src = p.read_text(encoding="utf-8")
        tree = ast.parse(src, filename=str(p))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.decorator_list:
                rule, has_login, has_level = _parse_decorators(node.decorator_list, src)
                if rule:
                    results.append(
                        RouteInfo(
                            file=str(p),
                            func=node.name,
                            rule=rule,
                            login_required=has_login,
                            level_present=has_level,
                        )
                    )
    return results


def test_routes_are_protected_ast():
    routes = collect_routes()
    failures: list[str] = []
    for r in routes:
        # Require both login and level
        if not r.login_required or not r.level_present:
            failures.append(f"{r.file}:{r.func} {r.rule} login={r.login_required} level={r.level_present}")
    assert not failures, "Unprotected routes found:\n" + "\n".join(failures)


def test_runtime_redirects_anonymous():
    # Stub external deps to allow app import
    import sys, types

    if "folium" not in sys.modules:
        folium = types.ModuleType("folium")

        class _DummyRoot:
            def __init__(self):
                self.html = types.SimpleNamespace(add_child=lambda *a, **k: None)
                self.script = types.SimpleNamespace(add_child=lambda *a, **k: None)

            def render(self):
                return ""

        class _Dummy:
            def __init__(self, *a, **k):
                pass

            def add_to(self, *a, **k):
                return self

        class _DummyMap(_Dummy):
            def get_name(self):
                return "map"

            def get_root(self):
                return _DummyRoot()

        folium.Map = _DummyMap
        folium.Element = lambda *a, **k: None
        folium.FeatureGroup = _Dummy
        folium.LayerControl = _Dummy
        folium.Marker = _Dummy
        folium.Popup = _Dummy
        folium.IFrame = _Dummy
        folium.plugins = types.SimpleNamespace(MarkerCluster=_Dummy)
        folium.features = types.SimpleNamespace(CustomIcon=_Dummy)
        sys.modules["folium"] = folium
        sys.modules["folium.plugins"] = folium.plugins
        sys.modules["folium.features"] = folium.features

    if "babel.dates" not in sys.modules:
        babel = types.ModuleType("babel")
        dates = types.ModuleType("babel.dates")
        dates.format_datetime = lambda *a, **k: ""
        sys.modules["babel"] = babel
        sys.modules["babel.dates"] = dates

    from app import create_app

    app = create_app()
    client = app.test_client()
    paths = [
        "/",
        "/edit-sites/",
        "/type-sites/",
        "/regions/",
        "/contrats/liste",
        "/notif/",
        "/maintenance/",
        "/champs/",
    ]
    for p in paths:
        resp = client.get(p, follow_redirects=False)
        assert resp.status_code == 302, f"Expected redirect for {p}, got {resp.status_code}"
        assert "/auth/" in (resp.headers.get("Location") or ""), f"{p} did not redirect to /auth/"

