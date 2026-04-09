from __future__ import annotations

from flask import Flask, jsonify, render_template, request

from compiler.lexer import lex
from compiler.parser import parse
from compiler.semantic import analyze
from compiler.intermediate import generate_ir
from compiler.pipeline import simulate_pipeline
from compiler.translator import translate_to_c

app = Flask(__name__)


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/compile")
def compile_endpoint():
    payload = request.get_json(silent=True) or {}
    pseudocode = payload.get("pseudocode", "")

    try:
        tokens = lex(pseudocode)
        ast = parse(tokens)
        semantic = analyze(ast)
        ir = generate_ir(ast)
        pipeline = simulate_pipeline(ir["tac"])
        c_code = translate_to_c(ast, semantic)

        return jsonify(
            {
                "ok": True,
                "tokens": tokens,
                "syntax_tree": ast,
                "semantic": semantic,
                "intermediate": ir,
                "pipeline": pipeline,
                "c_code": c_code,
            }
        )
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


if __name__ == "__main__":
    app.run(debug=True)

