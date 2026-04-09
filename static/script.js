function $(sel) {
  return document.querySelector(sel);
}

function pretty(obj) {
  return JSON.stringify(obj, null, 2);
}

function setStatus(text, kind = "muted") {
  const el = $("#status");
  el.textContent = text;
  el.style.color = kind === "ok" ? "var(--ok)" : kind === "bad" ? "var(--bad)" : "var(--muted)";
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderTokens(tokens) {
  const rows = tokens
    .filter((t) => t.type !== "EOF")
    .map(
      (t) =>
        `<tr>
          <td>${escapeHtml(t.type)}</td>
          <td>${escapeHtml(t.value)}</td>
          <td>${escapeHtml(t.line)}</td>
          <td>${escapeHtml(t.col)}</td>
        </tr>`
    )
    .join("");

  $("#tokensTable").innerHTML = `
    <table class="table">
      <thead>
        <tr><th>Type</th><th>Value</th><th>Line</th><th>Col</th></tr>
      </thead>
      <tbody>${rows || ""}</tbody>
    </table>
  `;
}

function renderPipeline(pipeline) {
  const stages = pipeline.stages || [];
  const byCycle = pipeline.by_cycle || [];

  const header = `<tr><th>Cycle</th><th>Active stages</th></tr>`;
  const rows = byCycle
    .map((c) => {
      const active = (c.active || [])
        .map((a) => `${escapeHtml(a.stage)}: ${escapeHtml(a.instruction)}`)
        .join("<br/>");
      return `<tr><td>${c.cycle}</td><td>${active || ""}</td></tr>`;
    })
    .join("");

  $("#pipelineView").innerHTML = `
    <div style="padding: 10px 12px; color: var(--muted); border-bottom: 1px solid var(--border); background: rgba(15, 23, 50, 0.35);">
      Stages: <strong>${escapeHtml(stages.join(" → "))}</strong>
    </div>
    <table class="table">
      <thead>${header}</thead>
      <tbody>${rows || ""}</tbody>
    </table>
  `;
}

async function compile() {
  const pseudocode = $("#pseudocode").value;
  setStatus("Compiling…");

  try {
    const res = await fetch("/compile", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pseudocode }),
    });

    const data = await res.json();
    if (!data.ok) throw new Error(data.error || "Compilation failed");

    $("#cOutput").textContent = data.c_code || "";
    renderTokens(data.tokens || []);
    $("#astView").textContent = pretty(data.syntax_tree || {});
    $("#symbolsView").textContent = pretty((data.semantic && data.semantic.symbols) || {});
    $("#diagnosticsView").textContent = pretty({
      errors: (data.semantic && data.semantic.errors) || [],
      warnings: (data.semantic && data.semantic.warnings) || [],
    });

    $("#tacView").textContent = ((data.intermediate && data.intermediate.tac) || []).join("\n");
    $("#irView").textContent = pretty((data.intermediate && data.intermediate.ir) || []);
    renderPipeline(data.pipeline || {});

    const errs = (data.semantic && data.semantic.errors) || [];
    if (errs.length) {
      setStatus(`Compiled with ${errs.length} semantic error(s).`, "bad");
    } else {
      setStatus("Compilation successful.", "ok");
    }
  } catch (e) {
    setStatus(`Error: ${e.message}`, "bad");
  }
}

function setupTabs() {
  const tabs = Array.from(document.querySelectorAll(".tab"));
  tabs.forEach((t) => {
    t.addEventListener("click", () => {
      tabs.forEach((x) => x.classList.remove("active"));
      t.classList.add("active");

      const target = t.dataset.tab;
      Array.from(document.querySelectorAll(".tabpanel")).forEach((p) => p.classList.remove("active"));
      const panel = document.querySelector(`#tab-${target}`);
      if (panel) panel.classList.add("active");
    });
  });
}

function loadExample() {
  $("#pseudocode").value = ["a = 5", "b = 10", "c = a + b", "print c"].join("\n");
}

window.addEventListener("DOMContentLoaded", () => {
  setupTabs();
  $("#compileBtn").addEventListener("click", compile);
  $("#loadExampleBtn").addEventListener("click", () => {
    loadExample();
    setStatus("Example loaded.");
  });

  loadExample();
});

