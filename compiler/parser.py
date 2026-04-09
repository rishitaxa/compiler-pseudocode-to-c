from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class _Cursor:
    tokens: list[dict[str, Any]]
    i: int = 0

    def peek(self) -> dict[str, Any]:
        return self.tokens[self.i]

    def at(self, typ: str) -> bool:
        return self.peek()["type"] == typ

    def at_any(self, typs: tuple[str, ...]) -> bool:
        return self.peek()["type"] in typs

    def consume(self, typ: str | None = None) -> dict[str, Any]:
        tok = self.peek()
        if typ is not None and tok["type"] != typ:
            raise ValueError(
                f"Parser error at line {tok['line']}, col {tok['col']}: expected {typ}, got {tok['type']}"
            )
        self.i += 1
        return tok

    def skip_newlines(self) -> None:
        while self.at("NEWLINE"):
            self.consume("NEWLINE")


def parse(tokens: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Syntax analysis: builds a tiny AST.

    Grammar (informal):
      program     := (NEWLINE | stmt)* EOF
      stmt        := assignment | print_stmt | if_stmt | while_stmt
      assignment  := lvalue ASSIGN expr
      lvalue      := IDENT (postfix)*
      print_stmt  := PRINT expr
      if_stmt     := IF expr NEWLINE INDENT stmt* DEDENT (ELSE NEWLINE INDENT stmt* DEDENT)? END
      while_stmt  := WHILE expr NEWLINE INDENT stmt* DEDENT END

      expr        := equality
      equality    := comparison ((EQ|NE) comparison)*
      comparison  := xor ((LT|GT|LE|GE) xor)*
      xor         := additive (XOR additive)*
      additive    := term ((PLUS|MINUS) term)*
      term        := unary ((MUL|DIV|MOD) unary)*
      unary       := (MINUS unary) | postfix_expr
      postfix_expr:= primary (postfix)*
      postfix     := LBRACK expr RBRACK | DOT IDENT
      primary     := NUMBER | STRING | NULL | IDENT | INPUT | LPAREN expr RPAREN
    """
    c = _Cursor(tokens=tokens)
    program: list[dict[str, Any]] = []

    c.skip_newlines()
    while not c.at("EOF"):
        if c.at("DEDENT"):
            # Defensive: stray dedents (usually from blank lines) shouldn't crash parsing.
            c.consume("DEDENT")
            c.skip_newlines()
            continue
        program.append(_parse_stmt(c))
        c.skip_newlines()

    c.consume("EOF")
    return {"type": "Program", "body": program}


def _parse_stmt(c: _Cursor) -> dict[str, Any]:
    tok = c.peek()
    if tok["type"] in ("DECLARE", "CREATE", "MAKE"):
        return _parse_declare(c)

    if tok["type"] == "FUNCTION":
        return _parse_function(c)

    if tok["type"] == "RETURN":
        kw = c.consume("RETURN")
        expr = _parse_expr(c)
        return {"type": "Return", "expr": expr, "loc": _loc(kw)}

    if tok["type"] in ("PUSH", "POP", "ENQUEUE", "DEQUEUE", "REMOVE"):
        return _parse_ds_op(c)

    if tok["type"] == "PRINT":
        c.consume("PRINT")
        expr = _parse_print_expr(c)
        return {"type": "Print", "expr": expr, "loc": _loc(tok)}

    if tok["type"] == "IF":
        return _parse_if(c)

    if tok["type"] == "WHILE":
        return _parse_while(c)

    if tok["type"] == "IDENT":
        lv = _parse_lvalue(c)
        eq = c.consume("ASSIGN")
        expr = _parse_expr(c)
        return {"type": "Assign", "target": lv, "expr": expr, "loc": _loc(eq)}

    raise ValueError(
        f"Parser error at line {tok['line']}, col {tok['col']}: expected statement, got {tok['type']}"
    )


def _parse_expr(c: _Cursor) -> dict[str, Any]:
    return _parse_equality(c)


def _parse_equality(c: _Cursor) -> dict[str, Any]:
    node = _parse_comparison(c)
    while c.at_any(("EQ", "NE")):
        op = c.consume()
        rhs = _parse_comparison(c)
        node = {"type": "BinOp", "op": op["type"], "left": node, "right": rhs, "loc": _loc(op)}
    return node


def _parse_comparison(c: _Cursor) -> dict[str, Any]:
    node = _parse_xor(c)
    while c.at_any(("LT", "GT", "LE", "GE")):
        op = c.consume()
        rhs = _parse_xor(c)
        node = {"type": "BinOp", "op": op["type"], "left": node, "right": rhs, "loc": _loc(op)}
    return node


def _parse_xor(c: _Cursor) -> dict[str, Any]:
    node = _parse_additive(c)
    while c.at("XOR"):
        op = c.consume("XOR")
        rhs = _parse_additive(c)
        node = {"type": "BinOp", "op": op["type"], "left": node, "right": rhs, "loc": _loc(op)}
    return node


def _parse_additive(c: _Cursor) -> dict[str, Any]:
    node = _parse_term(c)
    while c.at_any(("PLUS", "MINUS")):
        op = c.consume()
        rhs = _parse_term(c)
        node = {"type": "BinOp", "op": op["type"], "left": node, "right": rhs, "loc": _loc(op)}
    return node


def _parse_term(c: _Cursor) -> dict[str, Any]:
    node = _parse_unary(c)
    while c.at_any(("MUL", "DIV", "MOD")):
        op = c.consume()
        rhs = _parse_unary(c)
        node = {"type": "BinOp", "op": op["type"], "left": node, "right": rhs, "loc": _loc(op)}
    return node


def _parse_unary(c: _Cursor) -> dict[str, Any]:
    if c.at("MINUS"):
        op = c.consume("MINUS")
        inner = _parse_unary(c)
        return {"type": "UnaryOp", "op": "NEG", "expr": inner, "loc": _loc(op)}
    return _parse_postfix_expr(c)


def _parse_postfix_expr(c: _Cursor) -> dict[str, Any]:
    node = _parse_primary(c)
    while True:
        if c.at("LBRACK"):
            lb = c.consume("LBRACK")
            idx = _parse_expr(c)
            c.consume("RBRACK")
            node = {"type": "Index", "base": node, "index": idx, "loc": _loc(lb)}
            continue
        if c.at("DOT"):
            dot = c.consume("DOT")
            name = c.consume("IDENT")
            node = {"type": "Member", "base": node, "field": name["value"], "loc": _loc(dot)}
            continue
        break
    return node


def _parse_primary(c: _Cursor) -> dict[str, Any]:
    tok = c.peek()
    if tok["type"] == "NUMBER":
        t = c.consume("NUMBER")
        return {"type": "Number", "value": int(t["value"]), "loc": _loc(t)}
    if tok["type"] == "STRING":
        t = c.consume("STRING")
        # Keep the raw quoted literal; codegen can reuse it directly.
        return {"type": "String", "value": t["value"], "loc": _loc(t)}
    if tok["type"] == "NULL":
        t = c.consume("NULL")
        return {"type": "Null", "loc": _loc(t)}
    if tok["type"] == "INPUT":
        t = c.consume("INPUT")
        return {"type": "Input", "loc": _loc(t)}
    if tok["type"] == "IDENT":
        t = c.consume("IDENT")
        # Function call: ident '(' args ')'
        if c.at("LPAREN"):
            lp = c.consume("LPAREN")
            args: list[dict[str, Any]] = []
            if not c.at("RPAREN"):
                args.append(_parse_expr(c))
                while c.at("COMMA"):
                    c.consume("COMMA")
                    args.append(_parse_expr(c))
            c.consume("RPAREN")
            return {"type": "Call", "name": t["value"], "args": args, "loc": _loc(lp)}
        return {"type": "Var", "name": t["value"], "loc": _loc(t)}
    if tok["type"] == "LPAREN":
        c.consume("LPAREN")
        node = _parse_expr(c)
        c.consume("RPAREN")
        return node
    raise ValueError(
        f"Parser error at line {tok['line']}, col {tok['col']}: expected expression, got {tok['type']}"
    )


def _parse_lvalue(c: _Cursor) -> dict[str, Any]:
    # LHS must start with IDENT, then can have indexing / field access.
    node = _parse_primary(c)
    node = _parse_postfix_after_primary(c, node)
    if node["type"] not in ("Var", "Index", "Member"):
        tok = c.peek()
        raise ValueError(
            f"Parser error at line {tok['line']}, col {tok['col']}: invalid assignment target"
        )
    return node


def _parse_postfix_after_primary(c: _Cursor, node: dict[str, Any]) -> dict[str, Any]:
    while True:
        if c.at("LBRACK"):
            lb = c.consume("LBRACK")
            idx = _parse_expr(c)
            c.consume("RBRACK")
            node = {"type": "Index", "base": node, "index": idx, "loc": _loc(lb)}
            continue
        if c.at("DOT"):
            dot = c.consume("DOT")
            name = c.consume("IDENT")
            node = {"type": "Member", "base": node, "field": name["value"], "loc": _loc(dot)}
            continue
        break
    return node


def _parse_block(c: _Cursor) -> list[dict[str, Any]]:
    c.consume("NEWLINE")
    c.consume("INDENT")
    body: list[dict[str, Any]] = []
    c.skip_newlines()
    while not c.at("DEDENT"):
        body.append(_parse_stmt(c))
        c.skip_newlines()
    c.consume("DEDENT")
    return body


def _parse_declare(c: _Cursor) -> dict[str, Any]:
    kw = c.consume()
    # Support: "make a queue", "create stack", "declare graph"
    if c.at("IDENT") and c.peek()["value"].lower() in ("a", "an", "the"):
        c.consume("IDENT")

    if not c.at_any(("STACK", "QUEUE", "TREE", "GRAPH")):
        tok = c.peek()
        raise ValueError(
            f"Parser error at line {tok['line']}, col {tok['col']}: expected data structure after {kw['type']}"
        )
    ds = c.consume()

    name = ds["value"].lower()
    # Optional: "declare stack s"
    if c.at("IDENT"):
        name = c.consume("IDENT")["value"]

    return {"type": "Declare", "kind": ds["type"].lower(), "name": name, "loc": _loc(kw)}


def _parse_ds_op(c: _Cursor) -> dict[str, Any]:
    tok = c.peek()

    # Natural language: "remove element from queue" -> dequeue(queue)
    if tok["type"] == "REMOVE":
        kw = c.consume("REMOVE")
        if c.at("ELEMENT"):
            c.consume("ELEMENT")
        if c.at("FROM"):
            c.consume("FROM")
        target = _parse_ds_target(c, default="queue")
        return {"type": "DSOp", "op": "dequeue", "target": target, "value": None, "loc": _loc(kw)}

    if tok["type"] == "DEQUEUE":
        kw = c.consume("DEQUEUE")
        if c.at("FROM"):
            c.consume("FROM")
        target = _parse_ds_target(c, default="queue")
        return {"type": "DSOp", "op": "dequeue", "target": target, "value": None, "loc": _loc(kw)}

    if tok["type"] == "POP":
        kw = c.consume("POP")
        if c.at("FROM"):
            c.consume("FROM")
        target = _parse_ds_target(c, default="stack")
        return {"type": "DSOp", "op": "pop", "target": target, "value": None, "loc": _loc(kw)}

    if tok["type"] == "PUSH":
        kw = c.consume("PUSH")
        value = _parse_expr(c)
        if c.at("INTO"):
            c.consume("INTO")
            target = _parse_ds_target(c, default="stack")
        else:
            # "push 5" defaults to stack
            target = {"type": "Var", "name": "stack", "loc": _loc(kw)}
        return {"type": "DSOp", "op": "push", "target": target, "value": value, "loc": _loc(kw)}

    if tok["type"] == "ENQUEUE":
        kw = c.consume("ENQUEUE")
        value = _parse_expr(c)
        if c.at("INTO"):
            c.consume("INTO")
            target = _parse_ds_target(c, default="queue")
        else:
            target = {"type": "Var", "name": "queue", "loc": _loc(kw)}
        return {"type": "DSOp", "op": "enqueue", "target": target, "value": value, "loc": _loc(kw)}

    raise ValueError(
        f"Parser error at line {tok['line']}, col {tok['col']}: unknown data-structure operation"
    )


def _parse_ds_target(c: _Cursor, default: str) -> dict[str, Any]:
    # Accept: queue/stack keywords, or an identifier name.
    if c.at_any(("STACK", "QUEUE", "TREE", "GRAPH")):
        t = c.consume()
        return {"type": "Var", "name": t["value"].lower(), "loc": _loc(t)}
    if c.at("IDENT"):
        t = c.consume("IDENT")
        return {"type": "Var", "name": t["value"], "loc": _loc(t)}
    # Default: if omitted, use default variable name.
    tok = c.peek()
    return {"type": "Var", "name": default, "loc": _loc(tok)}


def _parse_function(c: _Cursor) -> dict[str, Any]:
    kw = c.consume("FUNCTION")
    name = c.consume("IDENT")
    c.consume("LPAREN")
    params: list[str] = []
    if not c.at("RPAREN"):
        p = c.consume("IDENT")
        params.append(p["value"])
        while c.at("COMMA"):
            c.consume("COMMA")
            p2 = c.consume("IDENT")
            params.append(p2["value"])
    c.consume("RPAREN")
    body = _parse_block(c)
    c.skip_newlines()
    if c.at("END"):
        c.consume("END")
    else:
        tok = c.peek()
        raise ValueError(
            f"Parser error at line {tok['line']}, col {tok['col']}: expected END to close FUNCTION"
        )
    return {"type": "Function", "name": name["value"], "params": params, "body": body, "loc": _loc(kw)}


def _parse_print_expr(c: _Cursor) -> dict[str, Any]:
    """
    Supports:
      print expr
      print queue front   -> queue[front]
      print stack top     -> stack[top]
      print top           -> stack[top] (if 'top' keyword used)
      print front         -> queue[front] (if 'front' keyword used)
    """
    if c.at("TOP"):
        t = c.consume("TOP")
        return {"type": "Index", "base": {"type": "Var", "name": "stack", "loc": _loc(t)}, "index": {"type": "Var", "name": "top", "loc": _loc(t)}, "loc": _loc(t)}
    if c.at("FRONT"):
        t = c.consume("FRONT")
        return {"type": "Index", "base": {"type": "Var", "name": "queue", "loc": _loc(t)}, "index": {"type": "Var", "name": "front", "loc": _loc(t)}, "loc": _loc(t)}

    # "print queue front"
    if c.at_any(("STACK", "QUEUE")):
        ds = c.consume()
        base = {"type": "Var", "name": ds["value"].lower(), "loc": _loc(ds)}
        if c.at("TOP"):
            kw = c.consume("TOP")
            return {"type": "Index", "base": base, "index": {"type": "Var", "name": "top", "loc": _loc(kw)}, "loc": _loc(kw)}
        if c.at("FRONT"):
            kw = c.consume("FRONT")
            return {"type": "Index", "base": base, "index": {"type": "Var", "name": "front", "loc": _loc(kw)}, "loc": _loc(kw)}
        return base

    return _parse_expr(c)


def _parse_if(c: _Cursor) -> dict[str, Any]:
    kw = c.consume("IF")
    cond = _parse_expr(c)
    then_body = _parse_block(c)

    else_body: list[dict[str, Any]] | None = None
    c.skip_newlines()
    if c.at("ELSE"):
        c.consume("ELSE")
        else_body = _parse_block(c)
        c.skip_newlines()

    if c.at("END"):
        c.consume("END")
    else:
        tok = c.peek()
        raise ValueError(
            f"Parser error at line {tok['line']}, col {tok['col']}: expected END to close IF"
        )
    return {"type": "If", "cond": cond, "then": then_body, "else": else_body, "loc": _loc(kw)}


def _parse_while(c: _Cursor) -> dict[str, Any]:
    kw = c.consume("WHILE")
    cond = _parse_expr(c)
    body = _parse_block(c)
    c.skip_newlines()
    if c.at("END"):
        c.consume("END")
    else:
        tok = c.peek()
        raise ValueError(
            f"Parser error at line {tok['line']}, col {tok['col']}: expected END to close WHILE"
        )
    return {"type": "While", "cond": cond, "body": body, "loc": _loc(kw)}


def _loc(tok: dict[str, Any]) -> dict[str, int]:
    return {"line": int(tok["line"]), "col": int(tok["col"])}

