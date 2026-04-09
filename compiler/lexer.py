from __future__ import annotations

import re
from typing import Any


_KEYWORDS = {
    # Control flow / builtins
    "if": "IF",
    "else": "ELSE",
    "while": "WHILE",
    "for": "FOR",
    "print": "PRINT",
    "input": "INPUT",
    "end": "END",
    "null": "NULL",

    # Declarations (human-friendly)
    "declare": "DECLARE",
    "create": "CREATE",
    "make": "MAKE",

    # Data structure words
    "stack": "STACK",
    "queue": "QUEUE",
    "tree": "TREE",
    "graph": "GRAPH",

    # DS operations
    "push": "PUSH",
    "pop": "POP",
    "enqueue": "ENQUEUE",
    "dequeue": "DEQUEUE",

    # Functions
    "function": "FUNCTION",
    "return": "RETURN",

    # Natural-language glue
    "into": "INTO",
    "from": "FROM",
    "front": "FRONT",
    "rear": "REAR",
    "top": "TOP",
    "remove": "REMOVE",
    "element": "ELEMENT",
}

# Order matters: longer operators must come first.
_TOKEN_SPECS: list[tuple[str, str]] = [
    ("LE", r"<="),
    ("GE", r">="),
    ("EQ", r"=="),
    ("NE", r"!="),
    ("LT", r"<"),
    ("GT", r">"),
    ("ASSIGN", r"="),
    ("PLUS", r"\+"),
    ("MINUS", r"-"),
    ("MUL", r"\*"),
    ("DIV", r"/"),
    ("MOD", r"%"),
    ("XOR", r"\^"),
    ("LPAREN", r"\("),
    ("RPAREN", r"\)"),
    ("LBRACK", r"\["),
    ("RBRACK", r"\]"),
    ("DOT", r"\."),
    ("COMMA", r","),
    ("NUMBER", r"\d+"),
    ("IDENT", r"[A-Za-z_]\w*"),
]

_MASTER_RE = re.compile("|".join(f"(?P<{name}>{pattern})" for name, pattern in _TOKEN_SPECS))
_STRING_RE = re.compile(r'"([^"\\]|\\.)*"')


def _indent_width(prefix: str) -> int:
    # Tabs are treated as 4 spaces (simple, educational).
    width = 0
    for ch in prefix:
        width += 4 if ch == "\t" else 1
    return width


def lex(source: str) -> list[dict[str, Any]]:
    """
    Lexical analysis: turns pseudocode text into a token stream.
    Emits NEWLINE tokens to separate statements.

    Also emits INDENT/DEDENT tokens (Python-style) based on leading whitespace.
    Blocks can be closed by writing `end` (recommended) and/or dedenting.
    """
    tokens: list[dict[str, Any]] = []
    lines = source.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    indent_stack = [0]

    for line_no, line in enumerate(lines, start=1):
        # Strip comments starting with '#'
        raw = line
        if "#" in raw:
            raw = raw.split("#", 1)[0]

        if raw.strip() == "":
            # Blank line: don't affect indentation, but keep statement separation.
            tokens.append({"type": "NEWLINE", "value": "\\n", "line": line_no, "col": 1})
            continue

        prefix = re.match(r"[ \t]*", raw).group(0)  # type: ignore[union-attr]
        indent = _indent_width(prefix)

        if indent > indent_stack[-1]:
            indent_stack.append(indent)
            tokens.append({"type": "INDENT", "value": "", "line": line_no, "col": 1})
        else:
            while indent < indent_stack[-1]:
                indent_stack.pop()
                tokens.append({"type": "DEDENT", "value": "", "line": line_no, "col": 1})
            if indent != indent_stack[-1]:
                raise ValueError(f"Lexer error at line {line_no}: inconsistent indentation")

        i = len(prefix)
        line = raw  # continue scanning the non-comment part
        while i < len(line):
            ch = line[i]
            if ch in (" ", "\t"):
                i += 1
                continue

            if ch == '"':
                mstr = _STRING_RE.match(line, i)
                if not mstr:
                    raise ValueError(f"Lexer error at line {line_no}, col {i+1}: unterminated string literal")
                lit = mstr.group(0)
                tokens.append({"type": "STRING", "value": lit, "line": line_no, "col": i + 1})
                i = mstr.end()
                continue

            m = _MASTER_RE.match(line, i)
            if not m:
                raise ValueError(f"Lexer error at line {line_no}, col {i+1}: unexpected character {ch!r}")

            typ = m.lastgroup or "UNKNOWN"
            val = m.group(typ)

            if typ == "IDENT":
                typ = _KEYWORDS.get(val.lower(), "IDENT")

            tokens.append({"type": typ, "value": val, "line": line_no, "col": i + 1})
            i = m.end()

        tokens.append({"type": "NEWLINE", "value": "\\n", "line": line_no, "col": len(line) + 1})

    # Close any open indentation blocks.
    while len(indent_stack) > 1:
        indent_stack.pop()
        tokens.append({"type": "DEDENT", "value": "", "line": len(lines) + 1, "col": 1})

    tokens.append({"type": "EOF", "value": "", "line": len(lines) + 1, "col": 1})
    return tokens

