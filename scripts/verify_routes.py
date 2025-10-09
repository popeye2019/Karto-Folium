from __future__ import annotations

import ast
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass
class RouteInfo:
    file: str
    func: str
    rule: str
    methods: list[str]
    login_required: bool
    level: str | int | None


def _get_str(node: ast.AST, source: str) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    # Fallback to source slice for non-constant expressions
    try:
        return ast.get_source_segment(source, node) or ""
    except Exception:
        return ""


def _parse_decorators(decs: Iterable[ast.AST], source: str) -> tuple[str, list[str], bool, str | int | None]:
    rule = ""
    methods: list[str] = []
    login = False
    level: str | int | None = None

    for d in decs:
        # @bp.route("/path", methods=["GET","POST"]) or variants
        if isinstance(d, ast.Call):
            func = d.func
            if isinstance(func, ast.Attribute) and func.attr == "route":
                # first positional arg: rule
                if d.args:
                    rule = _get_str(d.args[0], source)
                # methods kw
                for kw in d.keywords or []:
                    if kw.arg == "methods":
                        try:
                            vals = []
                            if isinstance(kw.value, (ast.List, ast.Tuple, ast.Set)):
                                for elt in kw.value.elts:
                                    s = _get_str(elt, source)
                                    if s:
                                        vals.append(s.strip("'\""))
                            methods = vals
                        except Exception:
                            methods = methods or []

            # @require_level(1)
            if (isinstance(func, ast.Name) and func.id == "require_level") or (
                isinstance(func, ast.Attribute) and func.attr == "require_level"
            ):
                if d.args:
                    v = d.args[0]
                    if isinstance(v, ast.Constant) and isinstance(v.value, int):
                        level = v.value
                    else:
                        level = _get_str(v, source)

        # @login_required
        if isinstance(d, ast.Name) and d.id == "login_required":
            login = True
        if isinstance(d, ast.Attribute) and d.attr == "login_required":
            login = True

    return rule, methods or ["GET"], login, level


def scan_routes(root: Path) -> list[RouteInfo]:
    results: list[RouteInfo] = []
    for p in (root / "app" / "blueprints").rglob("*.py"):
        if p.name == "auth.py":
            continue
        src = p.read_text(encoding="utf-8")
        try:
            tree = ast.parse(src, filename=str(p))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.decorator_list:
                rule, methods, login, level = _parse_decorators(node.decorator_list, src)
                if rule:
                    results.append(
                        RouteInfo(
                            file=str(p),
                            func=node.name,
                            rule=rule,
                            methods=methods,
                            login_required=login,
                            level=level,
                        )
                    )
    results.sort(key=lambda r: (r.file, r.rule))
    return results


def maybe_stub_external_modules() -> None:
    # Allow running without optional deps installed
    try:
        import folium  # noqa: F401
    except Exception:
        import types, sys as _sys

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
        _sys.modules["folium"] = folium
        _sys.modules["folium.plugins"] = folium.plugins
        _sys.modules["folium.features"] = folium.features

    try:
        from babel.dates import format_datetime  # noqa: F401
    except Exception:
        import types, sys as _sys

        babel = types.ModuleType("babel")
        dates = types.ModuleType("babel.dates")
        dates.format_datetime = lambda *a, **k: ""
        _sys.modules["babel"] = babel
        _sys.modules["babel.dates"] = dates


def try_runtime_checks(paths: list[str]) -> list[dict[str, Any]]:
    maybe_stub_external_modules()
    from app import create_app

    app = create_app()
    client = app.test_client()
    out: list[dict[str, Any]] = []
    for p in paths:
        resp = client.get(p, follow_redirects=False)
        out.append({"path": p, "status": resp.status_code, "location": resp.headers.get("Location")})
    return out


def main(argv: list[str]) -> None:
    root = Path(__file__).resolve().parents[1]
    routes = scan_routes(root)
    # Print table
    print("File | Route | Func | Methods | login | level")
    for r in routes:
        m = ",".join(r.methods)
        print(f"{r.file} | {r.rule} | {r.func} | {m} | {r.login_required} | {r.level}")

    # Runtime sanity check for common entry points (GET expected to redirect 302 when protected)
    checks = [
        "/",
        "/edit-sites/",
        "/type-sites/",
        "/regions/",
        "/contrats/liste",
        "/notif/",
        "/maintenance/",
        "/champs/",
    ]
    try:
        results = try_runtime_checks(checks)
        print("\nRuntime checks (anonymous):")
        for item in results:
            print(f"{item['path']} -> {item['status']} {item['location'] or ''}")
    except Exception as exc:
        print(f"Runtime checks skipped: {exc}")

    if any(arg == "--json" for arg in argv):
        payload = {
            "routes": [r.__dict__ for r in routes],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main(sys.argv[1:])

