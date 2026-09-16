"""
tests/check_undefined_names.py
=================================
Catches names that are USED at module level but never imported or
defined -- the class of bug `py_compile` cannot see.

Why this exists: `py_compile` only compiles. A missing import is not a
syntax error, so a file referencing an unimported `BaseModel` compiles
cleanly and then raises `NameError` the moment the module is imported.
That shipped once and took the service down at startup, restart-looping
under systemd. Compiling is not importing, and this closes the gap
without needing the real dependencies installed.

Scope, deliberately narrow to stay useful rather than noisy:
  * Module-level code only -- base classes, decorators, default
    arguments, annotations that are evaluated, and module-level calls.
    Names inside function bodies resolve at call time and are a
    different (much less fatal) problem.
  * Reports a name only when it is absent from imports, module-level
    assignments, defs/classes, and builtins.

Run:  python3 tests/check_undefined_names.py
"""
from __future__ import annotations

import ast
import builtins
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCAN_DIRS = ["app", "installer"]

BUILTINS = set(dir(builtins)) | {"__name__", "__file__", "__doc__", "__package__"}


def _module_level_bindings(tree: ast.Module) -> set:
    """Everything a module-level expression could legally reference."""
    names: set = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                for sub in ast.walk(target):
                    if isinstance(sub, ast.Name):
                        names.add(sub.id)
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            if isinstance(node.target, ast.Name):
                names.add(node.target.id)
        elif isinstance(node, (ast.For, ast.comprehension)):
            target = getattr(node, "target", None)
            if target is not None:
                for sub in ast.walk(target):
                    if isinstance(sub, ast.Name):
                        names.add(sub.id)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            names.add(node.name)
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                if item.optional_vars is not None:
                    for sub in ast.walk(item.optional_vars):
                        if isinstance(sub, ast.Name):
                            names.add(sub.id)
        elif isinstance(node, ast.Lambda):
            for arg in list(node.args.args) + list(node.args.kwonlyargs):
                names.add(arg.arg)
    return names


def _bindings_of(node) -> set:
    """Every name bound directly by this function: parameters, plus
    anything assigned, imported or defined anywhere inside it."""
    bound: set = set()
    args = node.args
    for arg in (
        list(args.args) + list(args.kwonlyargs) + list(getattr(args, "posonlyargs", []))
        + ([args.vararg] if args.vararg else [])
        + ([args.kwarg] if args.kwarg else [])
    ):
        bound.add(arg.arg)

    for sub in ast.walk(node):
        if isinstance(sub, (ast.Import, ast.ImportFrom)):
            for alias in sub.names:
                bound.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(sub.name)
        elif isinstance(sub, ast.Name) and isinstance(sub.ctx, (ast.Store, ast.Del)):
            bound.add(sub.id)
        elif isinstance(sub, ast.ExceptHandler) and sub.name:
            bound.add(sub.name)
        elif isinstance(sub, (ast.Global, ast.Nonlocal)):
            bound.update(sub.names)
        elif isinstance(sub, ast.Lambda):
            for arg in list(sub.args.args) + list(sub.args.kwonlyargs):
                bound.add(arg.arg)
    return bound


def _function_scope_check(tree: ast.Module, module_bound: set) -> list:
    """
    Names used INSIDE a function that are bound nowhere it could see.

    The original version of this checker deliberately skipped function
    bodies, reasoning that a name resolved at call time is less fatal
    than one resolved at import. That was wrong in practice: a missing
    module-level import used inside a request handler is invisible
    until someone exercises that endpoint, and then it is a 500 in
    production. Exactly that shipped -- `entitlements` was imported
    inside one function and used in another, and this checker passed
    it.

    **Scopes nest**, which the first attempt at this got wrong and two
    false positives immediately exposed: a closure variable from an
    enclosing function, and a parameter of a nested function. Each
    function is therefore checked against its own bindings PLUS every
    enclosing function's, walked as a stack.

    Only `name.attribute` usages are reported -- a bare name has too
    many legitimate ways to be bound for a static pass to judge, and
    the failure this exists to catch always looks like a module
    reference.
    """
    problems: list = []

    def _nested_functions(node) -> list:
        """Functions defined directly inside `node`, at any depth of
        statement nesting but not inside a further function."""
        found = []

        def scan(parent):
            for child in ast.iter_child_nodes(parent):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    found.append(child)
                elif not isinstance(child, ast.ClassDef):
                    scan(child)

        scan(node)
        return found

    def walk(node, enclosing: set) -> None:
        visible = enclosing | _bindings_of(node) | BUILTINS
        nested = _nested_functions(node)

        # Nodes belonging to a nested function are NOT inspected here.
        # They are checked in that function's own pass, where its
        # parameters are in scope -- inspecting them from the outer
        # function reports every nested parameter as undefined, which
        # is what the first attempt did.
        skip: set = set()
        for inner in nested:
            for sub in ast.walk(inner):
                skip.add(id(sub))

        for sub in ast.walk(node):
            if id(sub) in skip:
                continue
            if (
                isinstance(sub, ast.Attribute)
                and isinstance(sub.value, ast.Name)
                and isinstance(sub.value.ctx, ast.Load)
                and sub.value.id not in visible
            ):
                problems.append((sub.value.id, getattr(sub, "lineno", 0), f"inside {node.name}()"))

        for inner in nested:
            walk(inner, visible)

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            walk(node, module_bound)
        elif isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    walk(item, module_bound)

    return problems


def _module_level_used(tree: ast.Module) -> list:
    """
    Names referenced by module-level constructs that are evaluated at
    import time. Function BODIES are skipped -- a name resolved at call
    time is not what takes a service down on boot.
    """
    used: list = []

    def record(node, context):
        for sub in ast.walk(node):
            if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
                used.append((sub.id, getattr(sub, "lineno", 0), context))

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for base in node.bases:
                record(base, f"base class of {node.name}")
            for dec in node.decorator_list:
                record(dec, f"decorator on {node.name}")
            # Evaluated annotations/defaults inside the class body.
            for item in node.body:
                if isinstance(item, ast.AnnAssign) and item.value is not None:
                    record(item.value, f"{node.name} field default")
                elif isinstance(item, ast.Assign):
                    record(item.value, f"{node.name} attribute")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in node.decorator_list:
                record(dec, f"decorator on {node.name}")
            for default in node.args.defaults + [d for d in node.args.kw_defaults if d]:
                record(default, f"default argument of {node.name}")
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            if getattr(node, "value", None) is not None:
                record(node.value, "module-level assignment")
        elif isinstance(node, ast.Expr):
            record(node.value, "module-level expression")

    return used


def check_file(path: Path) -> list:
    try:
        tree = ast.parse(path.read_text(errors="ignore"))
    except SyntaxError as exc:
        return [f"{path}: SYNTAX ERROR {exc}"]

    bound = _module_level_bindings(tree) | BUILTINS
    problems = []
    for name, lineno, context in _module_level_used(tree):
        if name not in bound:
            problems.append(
                f"{path.relative_to(REPO_ROOT)}:{lineno}: '{name}' used as {context} "
                f"but never imported or defined"
            )

    module_bound = _module_level_bindings(tree)
    for name, lineno, context in _function_scope_check(tree, module_bound):
        problems.append(
            f"{path.relative_to(REPO_ROOT)}:{lineno}: '{name}.…' used {context} "
            f"but never imported or defined in that scope"
        )
    return problems


def main() -> int:
    problems = []
    scanned = 0
    for directory in SCAN_DIRS:
        root = REPO_ROOT / directory
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.py")):
            if "__pycache__" in str(path):
                continue
            scanned += 1
            problems.extend(check_file(path))

    print(f"Scanned {scanned} modules for module-level undefined names.")
    if problems:
        print(f"\n{len(problems)} PROBLEM(S):")
        for p in problems:
            print("  " + p)
        return 1
    print("No undefined module-level names found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
