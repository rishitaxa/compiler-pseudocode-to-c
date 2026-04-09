from __future__ import annotations

from typing import Any


def generate_ir(ast: dict[str, Any]) -> dict[str, Any]:
    tac: list[str] = []
    ir: list[dict[str, Any]] = []
    tmp_counter = 0
    label_counter = 0

    def new_tmp() -> str:
        nonlocal tmp_counter
        tmp_counter += 1
        return f"t{tmp_counter}"

    def new_label(prefix: str = "L") -> str:
        nonlocal label_counter
        label_counter += 1
        return f"{prefix}{label_counter}"

    def emit(op: str, args: list[str], result: str | None = None) -> str:
        item = {"op": op, "args": args, "result": result}
        ir.append(item)
        if op == "assign":
            tac_line = f"{result} = {args[0]}"
        elif op == "binop":
            tac_line = f"{result} = {args[0]} {args[1]} {args[2]}"
        elif op == "unary":
            tac_line = f"{result} = {args[0]}{args[1]}"
        elif op == "print":
            tac_line = f"print {args[0]}"
        elif op == "label":
            tac_line = f"{args[0]}:"
        elif op == "goto":
            tac_line = f"goto {args[0]}"
        elif op == "ifz":
            tac_line = f"ifz {args[0]} goto {args[1]}"
        elif op == "load_index":
            tac_line = f"{result} = {args[0]}[{args[1]}]"
        elif op == "store_index":
            tac_line = f"{args[0]}[{args[1]}] = {args[2]}"
        elif op == "load_field":
            tac_line = f"{result} = {args[0]}.{args[1]}"
        elif op == "store_field":
            tac_line = f"{args[0]}.{args[1]} = {args[2]}"
        elif op == "declare":
            tac_line = f"declare {args[0]} {args[1]}"
        elif op == "call":
            tac_line = f"{result} = call {args[0]}({', '.join(args[1:])})"
        elif op == "return":
            tac_line = f"return {args[0]}"
        elif op == "push":
            tac_line = f"push {args[0]} into {args[1]}"
        elif op == "pop":
            tac_line = f"pop from {args[0]}"
        elif op == "enqueue":
            tac_line = f"enqueue {args[0]} into {args[1]}"
        elif op == "dequeue":
            tac_line = f"dequeue from {args[0]}"
        elif op == "func":
            tac_line = f"function {args[0]}({', '.join(args[1:])})"
        elif op == "endfunc":
            tac_line = "end function"
        else:
            tac_line = f"{op} " + " ".join(args)
        tac.append(tac_line)
        return result or ""

    def lower_expr(expr: dict[str, Any]) -> str:
        t = expr["type"]
        if t == "Number":
            return str(expr["value"])
        if t == "String":
            return expr["value"]
        if t == "Null":
            return "NULL"
        if t == "Input":
            tmp = new_tmp()
            emit("input", [], tmp)
            return tmp
        if t == "Var":
            return expr["name"]
        if t == "Call":
            args = [lower_expr(a) for a in expr.get("args", [])]
            tmp = new_tmp()
            emit("call", [expr["name"], *args], tmp)
            return tmp
        if t == "Index":
            base = lower_expr(expr["base"])
            idx = lower_expr(expr["index"])
            tmp = new_tmp()
            emit("load_index", [base, idx], tmp)
            return tmp
        if t == "Member":
            base = lower_expr(expr["base"])
            tmp = new_tmp()
            emit("load_field", [base, expr["field"]], tmp)
            return tmp
        if t == "UnaryOp":
            inner = lower_expr(expr["expr"])
            tmp = new_tmp()
            if expr["op"] == "NEG":
                emit("unary", ["-", inner], tmp)
            else:
                emit("unary", ["?", inner], tmp)
            return tmp
        if t == "BinOp":
            left = lower_expr(expr["left"])
            right = lower_expr(expr["right"])
            tmp = new_tmp()
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
            emit("binop", [left, op, right], tmp)
            return tmp
        raise ValueError(f"Unsupported expr node: {t}")

    def lower_lvalue(target: dict[str, Any]) -> tuple[str, list[str], str]:
        """
        Returns (kind, parts, pretty)
        - kind: var|index|field
        - parts: varies
        - pretty: for display
        """
        t = target["type"]
        if t == "Var":
            return ("var", [target["name"]], target["name"])
        if t == "Index":
            base = lower_expr(target["base"])
            idx = lower_expr(target["index"])
            return ("index", [base, idx], f"{base}[{idx}]")
        if t == "Member":
            base = lower_expr(target["base"])
            field = target["field"]
            return ("field", [base, field], f"{base}.{field}")
        raise ValueError(f"Unsupported assignment target: {t}")

    def lower_stmt(stmt: dict[str, Any]) -> None:
        st = stmt["type"]
        if st == "Declare":
            emit("declare", [stmt["kind"], stmt["name"]], None)
            return
        if st == "DSOp":
            op = stmt["op"]
            target_name = lower_expr(stmt["target"])
            if op in ("push", "enqueue"):
                val = lower_expr(stmt["value"])
                emit(op, [val, target_name], None)
            else:
                emit(op, [target_name], None)
            return
        if st == "Function":
            emit("func", [stmt["name"], *stmt.get("params", [])], None)
            for s2 in stmt.get("body", []):
                lower_stmt(s2)
            emit("endfunc", [], None)
            return
        if st == "Return":
            val = lower_expr(stmt["expr"])
            emit("return", [val], None)
            return
        if st == "Assign":
            rhs = lower_expr(stmt["expr"])
            kind, parts, _ = lower_lvalue(stmt["target"])
            if kind == "var":
                emit("assign", [rhs], parts[0])
            elif kind == "index":
                emit("store_index", [parts[0], parts[1], rhs], None)
            elif kind == "field":
                emit("store_field", [parts[0], parts[1], rhs], None)
            return
        if st == "Print":
            val = lower_expr(stmt["expr"])
            emit("print", [val], None)
            return
        if st == "If":
            cond = lower_expr(stmt["cond"])
            else_label = new_label("ELSE")
            end_label = new_label("ENDIF")
            emit("ifz", [cond, else_label], None)
            for s2 in stmt.get("then", []):
                lower_stmt(s2)
            emit("goto", [end_label], None)
            emit("label", [else_label], None)
            for s2 in (stmt.get("else") or []):
                lower_stmt(s2)
            emit("label", [end_label], None)
            return
        if st == "While":
            start = new_label("WHILE")
            end = new_label("ENDWHILE")
            emit("label", [start], None)
            cond = lower_expr(stmt["cond"])
            emit("ifz", [cond, end], None)
            for s2 in stmt.get("body", []):
                lower_stmt(s2)
            emit("goto", [start], None)
            emit("label", [end], None)
            return
        raise ValueError(f"Unsupported statement: {stmt.get('type')}")

    for stmt in ast.get("body", []):
        lower_stmt(stmt)

    return {"tac": tac, "ir": ir}

