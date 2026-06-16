from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_ROOTS = (
    ROOT / "aiprod_adaptation",
    ROOT / "pipeline",
    ROOT / "production",
)
LIBRARY_ROOT = ROOT / "aiprod_adaptation"
CORE_ROOT = LIBRARY_ROOT / "core"
LIBRARY_PRINT_ALLOWLIST = {
    LIBRARY_ROOT / "cli.py",
}


def _python_files() -> list[Path]:
    files: list[Path] = []
    for source_root in SOURCE_ROOTS:
        files.extend(source_root.rglob("*.py"))
    return sorted(files)


def _is_model_copy_update(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    if not isinstance(node.func, ast.Attribute) or node.func.attr != "model_copy":
        return False
    return any(keyword.arg == "update" for keyword in node.keywords)


def _is_forbidden_core_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    if isinstance(node.func, ast.Name) and node.func.id in {"set", "random"}:
        return True
    if isinstance(node.func, ast.Attribute):
        if node.func.attr == "listdir" and isinstance(node.func.value, ast.Name):
            return node.func.value.id == "os"
        if node.func.attr == "now" and isinstance(node.func.value, ast.Name):
            return node.func.value.id == "datetime"
    return False


def _is_print_call(node: ast.AST) -> bool:
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "print"


def _is_library_file(path: Path) -> bool:
    return (
        path.is_relative_to(LIBRARY_ROOT)
        and "tests" not in path.parts
        and path.suffix == ".py"
    )


def main() -> int:
    violations: list[str] = []
    for path in _python_files():
        source = path.read_text(encoding="utf-8-sig")
        relative = path.relative_to(ROOT)
        for line_number, line in enumerate(source.splitlines(), start=1):
            if "# type: ignore" in line:
                violations.append(f"{relative}:{line_number}: forbidden '# type: ignore'")
        try:
            tree = ast.parse(source, filename=str(relative))
        except SyntaxError as exc:
            violations.append(f"{relative}:{exc.lineno}: syntax error: {exc.msg}")
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                violations.append(f"{relative}:{node.lineno}: forbidden bare except")
            if _is_model_copy_update(node) and "tests" not in path.parts:
                violations.append(
                    f"{relative}:{node.lineno}: forbidden model_copy(update=...) without revalidation"
                )
            if _is_forbidden_core_call(node) and path.is_relative_to(CORE_ROOT):
                violations.append(f"{relative}:{node.lineno}: forbidden nondeterministic core call")
            if _is_print_call(node) and _is_library_file(path) and path not in LIBRARY_PRINT_ALLOWLIST:
                violations.append(f"{relative}:{node.lineno}: forbidden print() in library code")

    if violations:
        print("Source invariant violations:")
        for violation in violations:
            print(f"- {violation}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
