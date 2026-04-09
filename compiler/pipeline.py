from __future__ import annotations

from typing import Any


def simulate_pipeline(tac: list[str]) -> dict[str, Any]:
    """
    Back-end visualization: a simple 5-stage pipeline simulation per instruction.
    Stages: IF, ID, EX, MEM, WB
    """
    stages = ["IF", "ID", "EX", "MEM", "WB"]
    steps: list[dict[str, Any]] = []

    # Simple pipeline: instruction i starts at cycle i (1-indexed)
    for idx, instr in enumerate(tac):
        start_cycle = idx + 1
        timeline = [{"cycle": start_cycle + s_idx, "stage": stage} for s_idx, stage in enumerate(stages)]
        steps.append({"instruction": instr, "timeline": timeline})

    # Also produce a cycle-by-cycle table (educational visualization)
    max_cycle = 0
    for s in steps:
        if s["timeline"]:
            max_cycle = max(max_cycle, s["timeline"][-1]["cycle"])

    by_cycle: dict[int, list[dict[str, Any]]] = {c: [] for c in range(1, max_cycle + 1)}
    for i, s in enumerate(steps):
        for t in s["timeline"]:
            by_cycle[t["cycle"]].append({"instruction_index": i, "stage": t["stage"], "instruction": s["instruction"]})

    return {
        "stages": stages,
        "steps": steps,
        "by_cycle": [{"cycle": c, "active": by_cycle[c]} for c in range(1, max_cycle + 1)],
    }

