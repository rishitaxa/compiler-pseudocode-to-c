from __future__ import annotations

import json

import streamlit as st

from compiler.intermediate import generate_ir
from compiler.lexer import lex
from compiler.parser import parse
from compiler.pipeline import simulate_pipeline
from compiler.semantic import analyze
from compiler.translator import translate_to_c


st.set_page_config(page_title="Compiler Visualizer", layout="wide")

st.title("Compiler Visualizer")
st.caption("Educational pseudocode → C compiler simulator (lexing, parsing, semantics, IR, pipeline).")


EXAMPLE = """declare queue

enqueue 5 into queue
enqueue 10 into queue

remove element from queue

print queue front
"""


left, right = st.columns(2, gap="large")
with left:
    pseudocode = st.text_area("Pseudocode (input)", value=EXAMPLE, height=360)
    compile_clicked = st.button("Compile", type="primary")

with right:
    st.subheader("Generated C (output)")
    c_out = st.empty()


def _pretty(x: object) -> str:
    return json.dumps(x, indent=2, ensure_ascii=False)


if compile_clicked:
    try:
        tokens = lex(pseudocode)
        ast = parse(tokens)
        semantic = analyze(ast)
        ir = generate_ir(ast)
        pipeline = simulate_pipeline(ir["tac"])
        c_code = translate_to_c(ast, semantic)

        c_out.code(c_code, language="c")

        tabs = st.tabs(
            [
                "Lexical Tokens",
                "Syntax Tree",
                "Semantic Output",
                "Intermediate Code",
                "Pipeline",
            ]
        )

        with tabs[0]:
            st.write("Tokens")
            st.dataframe(tokens, use_container_width=True)

        with tabs[1]:
            st.write("AST")
            st.code(_pretty(ast), language="json")

        with tabs[2]:
            st.write("Semantic output")
            st.code(_pretty(semantic), language="json")

        with tabs[3]:
            st.write("Three-address code (TAC)")
            st.code("\n".join(ir["tac"]), language="text")
            st.write("Structured IR")
            st.code(_pretty(ir["ir"]), language="json")

        with tabs[4]:
            st.write("Pipeline steps (cycle by cycle)")
            st.dataframe(pipeline["by_cycle"], use_container_width=True)

        errs = semantic.get("errors") or []
        if errs:
            st.error(f"Compiled with {len(errs)} semantic error(s).")
        else:
            st.success("Compilation successful.")

    except Exception as e:
        st.error(f"Compilation failed: {e}")

