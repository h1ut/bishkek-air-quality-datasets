from __future__ import annotations
import argparse
import datetime as _dt
from pathlib import Path

from qa.loaders import load_context
from qa.checks import structure, plausibility, agreement, reference

_MODULES = [("structure", structure), ("plausibility", plausibility),
            ("agreement", agreement), ("reference", reference)]
_ICON = {"PASS": "OK", "INFO": "..", "WARN": "!!", "FAIL": "XX"}


def run_all(ctx) -> list:
    out = []
    for _, mod in _MODULES:
        out.extend(mod.run(ctx))
    return out


def render(findings, ctx, generated_at: str) -> str:
    counts = {k: sum(1 for f in findings if f.level == k) for k in ("PASS", "INFO", "WARN", "FAIL")}
    lines = [f"# QA report — {generated_at}", "",
             f"{counts['PASS']} PASS / {counts['INFO']} INFO / {counts['WARN']} WARN / {counts['FAIL']} FAIL",
             "",
             f"- stations rows: {len(ctx.stations)}  grid rows: {len(ctx.grid)}  "
             f"Bishkek grid cell: {ctx.bishkek_cell_id}",
             ""]
    by_mod = {}
    for f in findings:
        by_mod.setdefault(f.check_id.split(".")[0], []).append(f)
    for name, _ in _MODULES:
        lines.append(f"## {name}")
        for f in by_mod.get(name, []):
            lines.append(f"- **[{_ICON[f.level]} {f.level}] {f.check_id}** — {f.summary}")
            if f.table:
                lines += ["", f.table, ""]
        lines.append("")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="qa/QA_REPORT.md")
    args = ap.parse_args(argv)
    ctx = load_context()
    findings = run_all(ctx)
    txt = render(findings, ctx, _dt.date.today().isoformat())
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(txt, encoding="utf-8")
    rc = 1 if any(f.level == "FAIL" for f in findings) else 0
    print(f"[qa] wrote {args.out}; FAIL={rc}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
