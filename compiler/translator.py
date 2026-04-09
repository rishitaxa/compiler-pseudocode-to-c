from __future__ import annotations

from typing import Any


def translate_to_c(ast: dict[str, Any], semantic: dict[str, Any]) -> str:

    symbols: dict[str, Any] = semantic.get("symbols", {})
    records: dict[str, dict[str, str]] = semantic.get("records", {})
    data_structures: dict[str, dict[str, Any]] = semantic.get("data_structures", {})
    functions: dict[str, dict[str, Any]] = semantic.get("functions", {})
    errors = semantic.get("errors", [])
    if errors:
        err_lines = "\n".join(f"// SEMANTIC ERROR: {e.get('message')}" for e in errors)
    else:
        err_lines = ""

    decl_lines: list[str] = []
    struct_lines: list[str] = []
    func_lines: list[str] = []

    # Struct definitions for record-like variables (e.g., node.data)
    for base_name, fields in records.items():
        struct_name = symbols.get(base_name, {}).get("record") or f"Record_{base_name}"
        struct_lines.append(f"typedef struct {struct_name} {{")
        # stable order for readability
        for field_name in sorted(fields.keys()):
            cty = _field_type_to_c(fields[field_name])
            struct_lines.append(f"  {cty} {field_name};")
        struct_lines.append(f"}} {struct_name};")
        struct_lines.append("")

    body = ast.get("body", [])
    func_nodes = [s for s in body if s.get("type") == "Function"]
    main_nodes = [s for s in body if s.get("type") != "Function"]

    for fn in func_nodes:
        fname = fn["name"]
        params = fn.get("params", [])
        sig = ", ".join([f"int {p}" for p in params]) if params else "void"
        func_lines.append(f"int {fname}({sig}) {{")

        locals_ = functions.get(fname, {}).get("locals", [])
        for lv in locals_:
            func_lines.append(f"  int {lv};")
        if locals_:
            func_lines.append("")

        for st in fn.get("body", []):
            func_lines.extend(_stmt_to_c(st, symbols, indent=2))
        func_lines.append("}")
        func_lines.append("")

    # Variable declarations
    for name, info in symbols.items():
        typ = info.get("type", "int")
        dims = info.get("dims") or []
        record_name = info.get("record")

        if typ == "record" and record_name:
            decl_lines.append(f"{record_name} {name};")
            continue

        if dims:
            # default int arrays (educational)
            suffix = "".join(f"[{d}]" for d in dims)
            decl_lines.append(f"int {name}{suffix};")
            continue

        if typ == "string":
            decl_lines.append(f"const char* {name};")
        elif typ == "ptr":
            decl_lines.append(f"void* {name};")
        else:
            decl_lines.append(f"int {name};")

    # Statement lowering directly from AST for clean C.
    body_lines: list[str] = []
    if any(v.get("kind") == "stack" for v in data_structures.values()):
        body_lines.append("  top = -1;")
    if any(v.get("kind") == "queue" for v in data_structures.values()):
        body_lines.append("  front = 0;")
        body_lines.append("  rear = -1;")
    if body_lines:
        body_lines.append("")

    for st in main_nodes:
        body_lines.extend(_stmt_to_c(st, symbols, indent=2))

    parts: list[str] = [
        "#include <stdio.h>",
        "#include <stdlib.h>",
        "",
    ]

    if err_lines:
        parts.extend(["", "/*", err_lines, "*/", ""])

    if struct_lines:
        parts.extend(struct_lines)

    if func_lines:
        parts.extend(func_lines)

    parts.append("int main() {")

    if decl_lines:
        parts.extend(["  " + line for line in decl_lines])
        parts.append("")

    parts.extend(body_lines)
    parts.extend(["  return 0;", "}", ""])
    return "\n".join(parts)


def _expr_to_c(expr: dict[str, Any]) -> str:
    t = expr["type"]
    if t == "Number":
        return str(expr["value"])
    if t == "String":
        return expr["value"]
    if t == "Null":
        return "NULL"
    if t == "Input":
        # For a pure expression language, we keep it simple: read into a temp.
        # The IR visualizes input separately; for C we do not inline scanf here.
        return "0"
    if t == "Var":
        return expr["name"]
    if t == "Call":
        args = ", ".join(_expr_to_c(a) for a in expr.get("args", []))
        return f"{expr['name']}({args})"
    if t == "Index":
        return f"{_expr_to_c(expr['base'])}[{_expr_to_c(expr['index'])}]"
    if t == "Member":
        return f"{_expr_to_c(expr['base'])}.{expr['field']}"
    if t == "UnaryOp":
        if expr.get("op") == "NEG":
            return f"(-{_expr_to_c(expr['expr'])})"
        return _expr_to_c(expr["expr"])
    if t == "BinOp":
        op_map = {
            "PLUS": "+",
            "MINUS": "-",
            "MUL": "*",
            "DIV": "/",
            "MOD": "%",
            "XOR": "^",
            "LT": "<",
            "GT": ">",
            "LE": "<=",
            "GE": ">=",
            "EQ": "==",
            "NE": "!=",
        }
        op = op_map.get(expr["op"], "?")
        return f"({_expr_to_c(expr['left'])} {op} {_expr_to_c(expr['right'])})"
    raise ValueError(f"Unsupported expr node: {t}")


def _stmt_to_c(stmt: dict[str, Any], symbols: dict[str, Any], indent: int) -> list[str]:
    pad = " " * indent
    st = stmt["type"]

    if st == "Declare":
        return []

    if st == "DSOp":
        op = stmt["op"]
        tgt = _expr_to_c(stmt["target"])
        if op == "push":
            v = _expr_to_c(stmt["value"])
            return [
                f"{pad}top = top + 1;",
                f"{pad}{tgt}[top] = {v};",
            ]
        if op == "pop":
            return [f"{pad}top = top - 1;"]
        if op == "enqueue":
            v = _expr_to_c(stmt["value"])
            return [
                f"{pad}rear = rear + 1;",
                f"{pad}{tgt}[rear] = {v};",
            ]
        if op == "dequeue":
            return [f"{pad}front = front + 1;"]
        return [f"{pad}/* unsupported DS op */"]

    if st == "Assign":
        return [f"{pad}{_expr_to_c(stmt['target'])} = {_expr_to_c(stmt['expr'])};"]

    if st == "Print":
        fmt = _print_format(stmt["expr"], symbols)
        return [f'{pad}printf("{fmt}", {_expr_to_c(stmt["expr"])});']

    if st == "If":
        out: list[str] = []
        cond = _strip_outer_parens(_expr_to_c(stmt["cond"]))
        out.append(f"{pad}if ({cond}) {{")
        for s2 in stmt.get("then", []):
            out.extend(_stmt_to_c(s2, symbols, indent + 2))
        out.append(f"{pad}}}")
        else_body = stmt.get("else")
        if else_body:
            out[-1] = f"{pad}}} else {{"
            for s2 in else_body:
                out.extend(_stmt_to_c(s2, symbols, indent + 2))
            out.append(f"{pad}}}")
        return out

    if st == "While":
        cond = _strip_outer_parens(_expr_to_c(stmt["cond"]))
        out = [f"{pad}while ({cond}) {{"]
        for s2 in stmt.get("body", []):
            out.extend(_stmt_to_c(s2, symbols, indent + 2))
        out.append(f"{pad}}}")
        return out

    if st == "Return":
        return [f"{pad}return {_expr_to_c(stmt['expr'])};"]

    if st == "Function":
        return []

    return [f"{pad}/* unsupported statement */"]


def _strip_outer_parens(s: str) -> str:
    """
    If s is wrapped in a single redundant (...) pair, remove it.
    This is used for if/while conditions to avoid `while ((a < b))`.
    """
    s = s.strip()
    if len(s) < 2 or not (s[0] == "(" and s[-1] == ")"):
        return s

    depth = 0
    for i, ch in enumerate(s):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            # If we close the outermost paren before the end, it's not redundant.
            if depth == 0 and i != len(s) - 1:
                return s
        if depth < 0:
            return s

    if depth != 0:
        return s
    return s[1:-1].strip()


def _print_format(expr: dict[str, Any], symbols: dict[str, Any]) -> str:
    # Determine %d vs %s using lightweight semantic info.
    t = expr["type"]
    if t == "String":
        return "%s"
    if t == "Var":
        info = symbols.get(expr["name"], {})
        if info.get("type") == "string":
            return "%s"
    return "%d"


def _field_type_to_c(ftype: str) -> str:
    if ftype == "string":
        return "const char*"
    if ftype == "ptr":
        return "void*"
    return "int"

