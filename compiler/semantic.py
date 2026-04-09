from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class _Symbol:
    name: str
    # scalar types: int, string, ptr
    typ: str = "int"
    declared_at: dict[str, int] | None = None
    assigned: bool = False
    # array dimensions (0 for scalar). For 2D arrays, dims=[100,100]
    dims: list[int] | None = None
    # record/struct name if this symbol is used with member access.
    record: str | None = None


def analyze(ast: dict[str, Any]) -> dict[str, Any]:
    """
    Semantic analysis:
    - builds a small symbol table (int/string/pointer + arrays + record-like variables)
    - checks use-before-assign
    - infers minimal types for educational code generation
    """
    symbols: dict[str, _Symbol] = {}
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    records: dict[str, dict[str, str]] = {}  # recordVar -> field -> fieldType
    data_structures: dict[str, dict[str, Any]] = {}  # name -> {kind, meta}
    functions: dict[str, dict[str, Any]] = {}  # name -> {params, locals}

    def sym(name: str, loc: dict[str, int] | None = None) -> _Symbol:
        if name not in symbols:
            symbols[name] = _Symbol(name=name, declared_at=loc)
        return symbols[name]

    def ensure_record(base_name: str) -> None:
        s = sym(base_name)
        if s.record is None:
            s.record = f"Record_{base_name}"
        records.setdefault(base_name, {})

    def set_field_type(base_name: str, field: str, ftype: str) -> None:
        ensure_record(base_name)
        records[base_name][field] = _merge_type(records[base_name].get(field), ftype)

    def mark_assigned_target(target: dict[str, Any]) -> None:
        # Any assignment makes the base variable "assigned" (for use-before-assign).
        base = _base_var_name(target)
        if base is not None:
            sym(base, target.get("loc")).assigned = True

    def infer_target_shape(target: dict[str, Any]) -> None:
        # Detect array dimensions from nested indexing: graph[u][v] => dims=2
        base = _base_var_name(target)
        if base is None:
            return
        depth = _index_depth(target)
        if depth > 0:
            s = sym(base, target.get("loc"))
            s.dims = s.dims or []
            if len(s.dims) < depth:
                # default educational size
                s.dims = [100] * depth

        # Detect record usage: node.data = 10
        if _contains_member(target):
            ensure_record(base)
            sym(base).typ = "record"

    def walk_stmt(stmt: dict[str, Any]) -> None:
        st = stmt["type"]
        if st == "Declare":
            kind = stmt["kind"]
            name = stmt["name"]
            data_structures[name] = {"kind": kind}

            if kind == "stack":
                sym(name, stmt.get("loc")).dims = [100]
                sym(name).assigned = True
                sym("top", stmt.get("loc")).typ = "int"
                sym("top").assigned = True
            elif kind == "queue":
                sym(name, stmt.get("loc")).dims = [100]
                sym(name).assigned = True
                sym("front", stmt.get("loc")).typ = "int"
                sym("rear", stmt.get("loc")).typ = "int"
                sym("front").assigned = True
                sym("rear").assigned = True
            elif kind == "graph":
                sym(name, stmt.get("loc")).dims = [100, 100]
                sym(name).assigned = True
            elif kind == "tree":
                # Minimal: declare a record-like node named `node` (educational default).
                base = name
                ensure_record(base)
                sym(base).typ = "record"
                set_field_type(base, "data", "int")
                set_field_type(base, "left", "ptr")
                set_field_type(base, "right", "ptr")
                sym(base).assigned = True
            else:
                warnings.append({"message": f"Unknown declaration kind: {kind}"})
            return

        if st == "DSOp":
            op = stmt["op"]
            target = stmt["target"]
            value = stmt.get("value")
            base = _base_var_name(target) or target.get("name") or "unknown"

            # Auto-declare if user uses ops without an explicit declare.
            if op in ("push", "pop") and base not in data_structures:
                warnings.append({"message": "Using stack without declaration; auto-declaring `stack`.", "loc": stmt.get("loc")})
                data_structures["stack"] = {"kind": "stack"}
                sym("stack").dims = [100]
                sym("top").assigned = True
            if op in ("enqueue", "dequeue") and base not in data_structures:
                warnings.append({"message": "Using queue without declaration; auto-declaring `queue`.", "loc": stmt.get("loc")})
                data_structures["queue"] = {"kind": "queue"}
                sym("queue").dims = [100]
                sym("front").assigned = True
                sym("rear").assigned = True

            if value is not None:
                _check_expr(value, symbols, errors)
            return

        if st == "Function":
            fname = stmt["name"]
            params = stmt.get("params", [])
            local_symbols: dict[str, _Symbol] = {}

            def local_sym(n: str, loc: dict[str, int] | None = None) -> _Symbol:
                if n not in local_symbols:
                    local_symbols[n] = _Symbol(name=n, declared_at=loc)
                return local_symbols[n]

            # Params are "assigned"
            for p in params:
                local_sym(p).assigned = True
                local_sym(p).typ = "int"

            def check_expr_scoped(expr: dict[str, Any]) -> None:
                # Resolve vars: prefer locals, else globals.
                t = expr["type"]
                if t == "Var":
                    n = expr["name"]
                    if n in local_symbols:
                        if not local_symbols[n].assigned:
                            errors.append({"message": f"Variable '{n}' used before assignment", "loc": expr.get("loc")})
                        return
                    if n in symbols:
                        if not symbols[n].assigned:
                            errors.append({"message": f"Variable '{n}' used before assignment", "loc": expr.get("loc")})
                        return
                    errors.append({"message": f"Variable '{n}' used before assignment", "loc": expr.get("loc")})
                    return
                if t in ("Number", "String", "Null", "Input"):
                    return
                if t == "Call":
                    for a in expr.get("args", []):
                        check_expr_scoped(a)
                    if expr.get("name") not in functions and expr.get("name") != fname:
                        warnings.append({"message": f"Call to unknown function '{expr.get('name')}'", "loc": expr.get("loc")})
                    return
                if t == "Index":
                    check_expr_scoped(expr["base"])
                    check_expr_scoped(expr["index"])
                    return
                if t == "Member":
                    check_expr_scoped(expr["base"])
                    return
                if t == "UnaryOp":
                    check_expr_scoped(expr["expr"])
                    return
                if t == "BinOp":
                    check_expr_scoped(expr["left"])
                    check_expr_scoped(expr["right"])
                    return

            def walk_func_stmt(s: dict[str, Any]) -> None:
                tt = s["type"]
                if tt == "Assign":
                    target = s["target"]
                    expr = s["expr"]
                    check_expr_scoped(expr)
                    if target["type"] == "Var":
                        local_sym(target["name"]).assigned = True
                    return
                if tt == "Return":
                    check_expr_scoped(s["expr"])
                    return
                if tt == "Print":
                    check_expr_scoped(s["expr"])
                    return
                if tt == "If":
                    check_expr_scoped(s["cond"])
                    for x in s.get("then", []):
                        walk_func_stmt(x)
                    for x in (s.get("else") or []):
                        walk_func_stmt(x)
                    return
                if tt == "While":
                    check_expr_scoped(s["cond"])
                    for x in s.get("body", []):
                        walk_func_stmt(x)
                    return
                if tt == "DSOp":
                    if s.get("value") is not None:
                        check_expr_scoped(s["value"])
                    return
                if tt == "Declare":
                    # Allow declarations inside functions, treated as locals.
                    local_sym(s["name"]).assigned = True
                    return

            for s2 in stmt.get("body", []):
                walk_func_stmt(s2)

            functions[fname] = {
                "params": params,
                "locals": sorted([n for n in local_symbols.keys() if n not in params]),
            }
            return

        if st == "Return":
            _check_expr(stmt["expr"], symbols, errors)
            return

        if st == "Assign":
            target = stmt["target"]
            expr = stmt["expr"]
            infer_target_shape(target)
            _check_expr(expr, symbols, errors)
            mark_assigned_target(target)

            # Infer types for scalars / fields when possible.
            expr_type = _infer_expr_type(expr, symbols)
            if target["type"] == "Var":
                s = sym(target["name"], stmt.get("loc"))
                s.typ = _merge_type(s.typ, expr_type)
            elif target["type"] == "Member":
                base_name = _base_var_name(target)
                if base_name:
                    set_field_type(base_name, target["field"], expr_type)
            elif target["type"] == "Index":
                base_name = _base_var_name(target)
                if base_name:
                    sym(base_name).typ = _merge_type(sym(base_name).typ, "int")
        elif st == "Print":
            _check_expr(stmt["expr"], symbols, errors)
        elif st == "If":
            _check_expr(stmt["cond"], symbols, errors)
            for s2 in stmt.get("then", []):
                walk_stmt(s2)
            for s2 in (stmt.get("else") or []):
                walk_stmt(s2)
        elif st == "While":
            _check_expr(stmt["cond"], symbols, errors)
            for s2 in stmt.get("body", []):
                walk_stmt(s2)
        else:
            warnings.append({"message": f"Unknown statement type: {stmt.get('type')}"})

    for stmt in ast.get("body", []):
        walk_stmt(stmt)

    return {
        "symbols": {
            k: {
                "type": v.typ,
                "declared_at": v.declared_at,
                "assigned": v.assigned,
                "dims": v.dims or [],
                "record": v.record,
            }
            for k, v in symbols.items()
        },
        "records": records,
        "data_structures": data_structures,
        "functions": functions,
        "errors": errors,
        "warnings": warnings,
    }


def _check_expr(expr: dict[str, Any], symbols: dict[str, _Symbol], errors: list[dict[str, Any]]) -> None:
    t = expr["type"]
    if t == "Number":
        return
    if t == "String":
        return
    if t == "Null":
        return
    if t == "Input":
        return
    if t == "Call":
        for a in expr.get("args", []):
            _check_expr(a, symbols, errors)
        return
    if t == "Var":
        name = expr["name"]
        sym = symbols.get(name)
        if sym is None:
            errors.append({"message": f"Variable '{name}' used before assignment", "loc": expr.get("loc")})
        elif not sym.assigned:
            errors.append({"message": f"Variable '{name}' used before assignment", "loc": expr.get("loc")})
        return
    if t == "Index":
        _check_expr(expr["base"], symbols, errors)
        _check_expr(expr["index"], symbols, errors)
        return
    if t == "Member":
        _check_expr(expr["base"], symbols, errors)
        return
    if t == "UnaryOp":
        _check_expr(expr["expr"], symbols, errors)
        return
    if t == "BinOp":
        _check_expr(expr["left"], symbols, errors)
        _check_expr(expr["right"], symbols, errors)
        return


def _infer_expr_type(expr: dict[str, Any], symbols: dict[str, _Symbol]) -> str:
    t = expr["type"]
    if t == "Number":
        return "int"
    if t == "String":
        return "string"
    if t == "Null":
        return "ptr"
    if t == "Input":
        return "int"
    if t == "Var":
        s = symbols.get(expr["name"])
        return s.typ if s else "int"
    if t == "Call":
        return "int"
    if t == "Index":
        return "int"
    if t == "Member":
        return "int"
    if t == "UnaryOp":
        return _infer_expr_type(expr["expr"], symbols)
    if t == "BinOp":
        op = expr.get("op")
        if op in ("LT", "GT", "LE", "GE", "EQ", "NE"):
            return "int"
        return "int"
    return "int"


def _merge_type(existing: str | None, new: str) -> str:
    if existing is None:
        return new
    if existing == new:
        return existing
    # Keep it simple: record dominates scalar; string dominates int for printing.
    if existing == "record" or new == "record":
        return "record"
    if existing == "string" or new == "string":
        return "string"
    if existing == "ptr" or new == "ptr":
        return "ptr"
    return "int"


def _base_var_name(node: dict[str, Any]) -> str | None:
    t = node["type"]
    if t == "Var":
        return node["name"]
    if t in ("Index", "Member"):
        return _base_var_name(node["base"])
    return None


def _index_depth(node: dict[str, Any]) -> int:
    if node["type"] == "Index":
        return 1 + _index_depth(node["base"])
    if node["type"] == "Member":
        return _index_depth(node["base"])
    return 0


def _contains_member(node: dict[str, Any]) -> bool:
    if node["type"] == "Member":
        return True
    if node["type"] == "Index":
        return _contains_member(node["base"])
    return False

