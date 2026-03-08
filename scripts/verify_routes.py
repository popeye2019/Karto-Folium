from __future__ import annotations

import argparse
import ast
import json
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
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
    level_value: int | None


@dataclass
class RuntimeCheck:
    path: str
    status: int
    location: str | None


def _get_str(node: ast.AST, source: str) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    # Fallback to source slice for non-constant expressions.
    try:
        return ast.get_source_segment(source, node) or ""
    except Exception:
        return ""


def _resolve_int_expr(node: ast.AST, constants: dict[str, int]) -> int | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return node.value
    if isinstance(node, ast.Name):
        return constants.get(node.id)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        value = _resolve_int_expr(node.operand, constants)
        return -value if value is not None else None
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd):
        return _resolve_int_expr(node.operand, constants)
    return None


def _extract_module_int_constants(tree: ast.Module) -> dict[str, int]:
    constants: dict[str, int] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            value = _resolve_int_expr(node.value, constants)
            if value is not None:
                constants[node.targets[0].id] = value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
            value = _resolve_int_expr(node.value, constants)
            if value is not None:
                constants[node.target.id] = value
    return constants


def _parse_decorators(
    decs: Iterable[ast.AST], source: str, constants: dict[str, int]
) -> tuple[str, list[str], bool, str | int | None, int | None]:
    rule = ""
    methods: list[str] = []
    login = False
    level: str | int | None = None
    level_value: int | None = None

    for d in decs:
        # @bp.route("/path", methods=["GET", "POST"]) or variants.
        if isinstance(d, ast.Call):
            func = d.func
            if isinstance(func, ast.Attribute) and func.attr == "route":
                # First positional arg: rule.
                if d.args:
                    rule = _get_str(d.args[0], source)
                # Methods kwarg.
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
                        level_value = v.value
                    else:
                        level = _get_str(v, source)
                        level_value = _resolve_int_expr(v, constants)

        # @login_required
        if isinstance(d, ast.Name) and d.id == "login_required":
            login = True
        if isinstance(d, ast.Attribute) and d.attr == "login_required":
            login = True

    return rule, methods or ["GET"], login, level, level_value


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
        constants = _extract_module_int_constants(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.decorator_list:
                rule, methods, login, level, level_value = _parse_decorators(node.decorator_list, src, constants)
                if rule:
                    results.append(
                        RouteInfo(
                            file=str(p),
                            func=node.name,
                            rule=rule,
                            methods=methods,
                            login_required=login,
                            level=level,
                            level_value=level_value,
                        )
                    )
    results.sort(key=lambda r: (r.file, r.rule))
    return results


def maybe_stub_external_modules() -> None:
    # Allow running without optional deps installed.
    try:
        import folium  # noqa: F401
    except Exception:
        import sys as _sys
        import types

        folium = types.ModuleType("folium")

        class _DummyRoot:
            def __init__(self) -> None:
                self.html = types.SimpleNamespace(add_child=lambda *a, **k: None)
                self.script = types.SimpleNamespace(add_child=lambda *a, **k: None)

            def render(self) -> str:
                return ""

        class _Dummy:
            def __init__(self, *a: Any, **k: Any) -> None:
                pass

            def add_to(self, *a: Any, **k: Any) -> "_Dummy":
                return self

        class _DummyMap(_Dummy):
            def get_name(self) -> str:
                return "map"

            def get_root(self) -> _DummyRoot:
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
        import sys as _sys
        import types

        babel = types.ModuleType("babel")
        dates = types.ModuleType("babel.dates")
        dates.format_datetime = lambda *a, **k: ""
        _sys.modules["babel"] = babel
        _sys.modules["babel.dates"] = dates


def try_runtime_checks(root: Path, paths: list[str]) -> list[RuntimeCheck]:
    maybe_stub_external_modules()
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    from app import create_app

    app = create_app()
    client = app.test_client()
    out: list[RuntimeCheck] = []
    for p in paths:
        resp = client.get(p, follow_redirects=False)
        out.append(RuntimeCheck(path=p, status=resp.status_code, location=resp.headers.get("Location")))
    return out


def _render_table(headers: list[str], rows: list[list[str]]) -> str:
    widths = [len(h) for h in headers]
    for row in rows:
        for idx, cell in enumerate(row):
            widths[idx] = max(widths[idx], len(cell))

    def render_row(values: list[str]) -> str:
        return " | ".join(value.ljust(widths[idx]) for idx, value in enumerate(values))

    separator = "-+-".join("-" * width for width in widths)
    lines = [render_row(headers), separator]
    lines.extend(render_row(row) for row in rows)
    return "\n".join(lines)


def _default_runtime_checks() -> list[str]:
    return [
        "/",
        "/edit-sites/",
        "/type-sites/",
        "/regions/",
        "/contrats/liste",
        "/notif/",
        "/maintenance/",
        "/champs/",
    ]


def _normalize_file(file_path: str, root: Path) -> str:
    path = Path(file_path)
    try:
        return str(path.relative_to(root))
    except ValueError:
        return file_path


def _format_routes_table(routes: list[RouteInfo], root: Path) -> str:
    headers = ["#", "File", "Route", "Function", "Methods", "Login", "Level"]
    rows: list[list[str]] = []
    for idx, route in enumerate(routes, start=1):
        if route.level is None:
            level_display = "-"
        elif route.level_value is not None and str(route.level) != str(route.level_value):
            level_display = f"{route.level} ({route.level_value})"
        else:
            level_display = str(route.level)

        rows.append(
            [
                str(idx),
                _normalize_file(route.file, root),
                route.rule,
                route.func,
                ",".join(route.methods),
                "yes" if route.login_required else "no",
                level_display,
            ]
        )
    return _render_table(headers, rows)


def _format_runtime_table(results: list[RuntimeCheck]) -> str:
    headers = ["Path", "Status", "Location"]
    rows = [[item.path, str(item.status), item.location or "-"] for item in results]
    return _render_table(headers, rows)


def build_report(
    root: Path,
    routes: list[RouteInfo],
    runtime_results: list[RuntimeCheck] | None,
    runtime_error: str | None,
) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    by_file = Counter(_normalize_file(route.file, root) for route in routes)
    login_count = sum(1 for route in routes if route.login_required)
    level_count = sum(1 for route in routes if route.level is not None)

    lines = [
        "Route Verification Report",
        "=" * 24,
        f"Generated at: {now}",
        f"Project root: {root}",
        "",
        "Summary",
        "-" * 7,
        f"Total routes: {len(routes)}",
        f"Routes with login_required: {login_count}",
        f"Routes with require_level: {level_count}",
        "",
        "Routes by file",
        "-" * 14,
    ]

    for file_name, count in sorted(by_file.items()):
        lines.append(f"- {file_name}: {count}")

    lines.extend(["", "Route details", "-" * 13, _format_routes_table(routes, root)])

    if runtime_results is not None:
        lines.extend(["", "Runtime checks (anonymous client)", "-" * 33, _format_runtime_table(runtime_results)])
    elif runtime_error:
        lines.extend(["", "Runtime checks", "-" * 14, f"Skipped: {runtime_error}"])

    return "\n".join(lines).rstrip() + "\n"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan Flask routes and generate a verification report.")
    parser.add_argument("--json", action="store_true", help="Print a JSON payload in stdout.")
    parser.add_argument(
        "--report",
        default=None,
        help="Output report path (.txt). Default: scripts/verify_routes_report.txt",
    )
    parser.add_argument("--skip-runtime", action="store_true", help="Skip runtime checks with test client.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> None:
    args = parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    routes = scan_routes(root)

    runtime_results: list[RuntimeCheck] | None = None
    runtime_error: str | None = None
    if not args.skip_runtime:
        try:
            runtime_results = try_runtime_checks(root, _default_runtime_checks())
        except Exception as exc:
            runtime_error = str(exc)

    report_path = Path(args.report) if args.report else (root / "scripts" / "verify_routes_report.txt")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_content = build_report(root, routes, runtime_results, runtime_error)
    report_path.write_text(report_content, encoding="utf-8")

    print(_format_routes_table(routes, root))
    if runtime_results:
        print("\nRuntime checks (anonymous):")
        print(_format_runtime_table(runtime_results))
    elif runtime_error:
        print(f"\nRuntime checks skipped: {runtime_error}")
    print(f"\nReport written to: {report_path}")

    if args.json:
        payload = {
            "routes": [r.__dict__ for r in routes],
            "runtime_checks": [rc.__dict__ for rc in runtime_results] if runtime_results is not None else None,
            "runtime_error": runtime_error,
            "report_file": str(report_path),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main(sys.argv[1:])
