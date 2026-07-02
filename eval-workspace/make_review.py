#!/usr/bin/env python3
"""Generate a single-page, self-contained review.html for an eval iteration.

One scrollable page per iteration, one section per eval, each containing:
  - the eval prompt
  - the INPUT data (tasks.csv, resources.csv, calendar.csv) as tables
  - the CCPM (with skill) Gantt, summary.md and grading checklist
  - the traditional CPM baseline Gantt and grading checklist

so an expert reviewer can compare input, CCPM and CPM schedules by scrolling
one document — no flipping between runs. Images are base64-embedded; the
file has no external dependencies and can be e-mailed as-is.

Usage: python3 make_review.py <iteration_dir> <inputs_dir> <evals.json> [out.html]
"""
import base64, csv, html, json, os, re, sys
from datetime import date

CSS = """
:root { --bg:#faf9f5; --surface:#fff; --border:#e8e6dc; --text:#141413;
        --muted:#87857c; --accent:#d97757; --green:#788c5d; --green-bg:#eef2e8;
        --red:#c44; --red-bg:#fceaea; }
* { box-sizing:border-box; margin:0; padding:0; }
body { font-family:Georgia,'Lora',serif; background:var(--bg); color:var(--text);
       line-height:1.5; }
header { background:#141413; color:#faf9f5; padding:1.2rem 2rem; }
header h1 { font-family:Helvetica,Arial,sans-serif; font-size:1.3rem; }
header p { opacity:.75; font-size:.85rem; margin-top:.3rem; max-width:70rem; }
nav { position:sticky; top:0; background:#141413ee; padding:.5rem 2rem; z-index:9; }
nav a { color:#faf9f5; text-decoration:none; font-family:Helvetica,Arial,sans-serif;
        font-size:.8rem; margin-right:1.2rem; opacity:.85; }
nav a:hover { opacity:1; text-decoration:underline; }
main { max-width:75rem; margin:0 auto; padding:1.5rem 2rem 4rem; }
section.eval { background:var(--surface); border:1px solid var(--border);
               border-radius:8px; padding:1.5rem 2rem; margin-top:2rem; }
h2 { font-family:Helvetica,Arial,sans-serif; font-size:1.15rem; }
h3 { font-family:Helvetica,Arial,sans-serif; font-size:.95rem; margin:1.4rem 0 .5rem;
     border-bottom:1px solid var(--border); padding-bottom:.25rem; }
h4 { font-family:Helvetica,Arial,sans-serif; font-size:.85rem; margin:.9rem 0 .3rem; }
.prompt { font-style:italic; color:var(--muted); margin:.4rem 0 .2rem; }
table { border-collapse:collapse; font-size:.8rem; margin:.4rem 0;
        font-family:Helvetica,Arial,sans-serif; }
th,td { border:1px solid var(--border); padding:.25rem .55rem; text-align:left; }
th { background:var(--bg); }
img.gantt { width:100%; height:auto; border:1px solid var(--border);
            border-radius:6px; margin:.4rem 0; }
.grades { list-style:none; font-family:Helvetica,Arial,sans-serif; font-size:.8rem; }
.grades li { padding:.2rem .5rem; border-radius:4px; margin:.15rem 0; }
.grades .pass { background:var(--green-bg); }
.grades .fail { background:var(--red-bg); }
.grades .ev { color:var(--muted); }
.badge { display:inline-block; font-family:Helvetica,Arial,sans-serif; font-size:.75rem;
         padding:.1rem .5rem; border-radius:10px; margin-left:.5rem; }
.badge.ok { background:var(--green-bg); color:var(--green); }
.badge.bad { background:var(--red-bg); color:var(--red); }
details { margin:.4rem 0; }
details summary { cursor:pointer; font-family:Helvetica,Arial,sans-serif;
                  font-size:.8rem; color:var(--muted); }
.summary-md { font-size:.9rem; margin:.4rem 0; }
.summary-md li { margin-left:1.4rem; }
.summary-md p { margin:.5rem 0; }
.inputs-grid { display:flex; flex-wrap:wrap; gap:2rem; align-items:flex-start; }
.compare { font-family:Helvetica,Arial,sans-serif; font-size:.85rem; }
footer { text-align:center; color:var(--muted); font-size:.75rem; padding:2rem; }
"""


def esc(s):
    return html.escape(str(s), quote=True)


def csv_table(path, caption):
    if not os.path.exists(path):
        return ""
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    if not rows:
        return ""
    out = [f"<div><h4>{esc(caption)}</h4><table><tr>"]
    out += [f"<th>{esc(h)}</th>" for h in rows[0]] + ["</tr>"]
    for r in rows[1:]:
        out.append("<tr>")
        for cell in r:
            if cell.startswith("http://") or cell.startswith("https://"):
                short = esc(re.sub(r"^https?://", "", cell))
                out.append(f'<td><a href="{esc(cell)}">{short}</a></td>')
            else:
                out.append(f"<td>{esc(cell)}</td>")
        out.append("</tr>")
    out.append("</table></div>")
    return "".join(out)


def img_tag(path, alt):
    if not os.path.exists(path):
        return f"<p><em>({esc(alt)} missing)</em></p>"
    b64 = base64.b64encode(open(path, "rb").read()).decode()
    return f'<img class="gantt" alt="{esc(alt)}" src="data:image/png;base64,{b64}">'


def grading_block(path):
    if not os.path.exists(path):
        return ""
    g = json.load(open(path))
    s = g.get("summary", {})
    badge = ("ok" if s.get("failed", 1) == 0 else "bad")
    out = [f'<span class="badge {badge}">{s.get("passed", "?")}/{s.get("total", "?")} '
           f'checks passed</span><ul class="grades">']
    for e in g.get("expectations", []):
        cls = "pass" if e["passed"] else "fail"
        mark = "✓" if e["passed"] else "✗"
        out.append(f'<li class="{cls}">{mark} {esc(e["text"])} '
                   f'<span class="ev">— {esc(e["evidence"])}</span></li>')
    out.append("</ul>")
    return "".join(out)


def md_to_html(path):
    """Just enough markdown for the generated summary.md: headings, bullets,
    tables, bold, links."""
    if not os.path.exists(path):
        return ""
    def inline(s):
        s = esc(s)
        s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
        s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
        s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
        return s
    out, in_ul, in_tbl = [], False, False
    for line in open(path).read().splitlines():
        if in_ul and not line.startswith("- "):
            out.append("</ul>"); in_ul = False
        if in_tbl and not line.startswith("|"):
            out.append("</table>"); in_tbl = False
        if line.startswith("# "):
            out.append(f"<h4>{inline(line[2:])}</h4>")
        elif line.startswith("- "):
            if not in_ul:
                out.append("<ul>"); in_ul = True
            out.append(f"<li>{inline(line[2:])}</li>")
        elif line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if all(re.fullmatch(r"-{3,}", c) for c in cells):
                continue
            tag = "td" if in_tbl else "th"
            if not in_tbl:
                out.append("<table>"); in_tbl = True
            out.append("<tr>" + "".join(f"<{tag}>{inline(c)}</{tag}>" for c in cells) + "</tr>")
        elif line.strip():
            out.append(f"<p>{inline(line)}</p>")
    if in_ul:
        out.append("</ul>")
    if in_tbl:
        out.append("</table>")
    return f'<div class="summary-md">{"".join(out)}</div>'


def main(it_dir, inputs_dir, evals_path, out_path=None):
    evals = json.load(open(evals_path))["evals"]
    skill = json.load(open(evals_path)).get("skill_name", "skill")
    out_path = out_path or os.path.join(it_dir, "review.html")
    comparison = {}
    cmp_path = os.path.join(it_dir, "comparison.json")
    if os.path.exists(cmp_path):
        comparison = {c["eval"]: c for c in json.load(open(cmp_path))}

    body = []
    nav = []
    for e in evals:
        name = e["eval_name"]
        ed = os.path.join(it_dir, f"eval-{name}")
        if not os.path.isdir(ed):
            continue
        nav.append(f'<a href="#{esc(name)}">{esc(name)}</a>')
        inp = os.path.join(inputs_dir, name)
        ccpm = os.path.join(ed, "with_skill")
        cpm = os.path.join(ed, "cpm_baseline")
        c = comparison.get(f"eval-{name}", {})
        body.append(f'<section class="eval" id="{esc(name)}">')
        body.append(f"<h2>{esc(name)}</h2>")
        body.append(f'<p class="prompt">{esc(e["prompt"])}</p>')

        body.append("<h3>Input data</h3>")
        body.append('<div class="inputs-grid">')
        body.append(csv_table(os.path.join(inp, "tasks.csv"), "tasks.csv"))
        body.append(csv_table(os.path.join(inp, "resources.csv"), "resources.csv"))
        body.append(csv_table(os.path.join(inp, "calendar.csv"),
                              "calendar.csv (capacity overrides, [from, to) days)"))
        body.append("</div>")

        if c:
            body.append("<h3>At a glance</h3>")
            body.append('<table class="compare"><tr><th></th>'
                        "<th>CCPM (with skill)</th><th>Traditional CPM baseline</th></tr>"
                        f"<tr><td>Overloaded resource-days</td>"
                        f"<td>{c['ccpm_overloaded_resource_days']}</td>"
                        f"<td>{c['cpm_overloaded_resource_days']}</td></tr>"
                        f"<tr><td>Work finishes</td><td>day {c['ccpm_work_finish']}</td>"
                        f"<td>day {c['cpm_promise_unprotected']}</td></tr>"
                        f"<tr><td>Promise date</td>"
                        f"<td>day {c['ccpm_promise_buffered']} (buffer-protected)</td>"
                        f"<td>day {c['cpm_promise_unprotected']} (unprotected)</td></tr>"
                        "</table>")

        body.append("<h3>CCPM schedule (with skill)</h3>")
        body.append(grading_block(os.path.join(ccpm, "grading.json")))
        body.append(img_tag(os.path.join(ccpm, "outputs", "gantt.png"),
                            f"{name} CCPM Gantt"))
        body.append(md_to_html(os.path.join(ccpm, "outputs", "summary.md")))
        body.append("<details><summary>schedule.csv</summary>")
        body.append(csv_table(os.path.join(ccpm, "outputs", "schedule.csv"), ""))
        body.append("</details>")

        body.append("<h3>Traditional CPM baseline</h3>")
        body.append(grading_block(os.path.join(cpm, "grading.json")))
        body.append(img_tag(os.path.join(cpm, "outputs", "gantt.png"),
                            f"{name} CPM Gantt"))
        body.append("<details><summary>schedule.csv</summary>")
        body.append(csv_table(os.path.join(cpm, "outputs", "schedule.csv"), ""))
        body.append("</details>")
        body.append("</section>")

    doc = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(skill)} — {esc(os.path.basename(os.path.normpath(it_dir)))} review</title>
<style>{CSS}</style></head><body>
<header><h1>{esc(skill)} — {esc(os.path.basename(os.path.normpath(it_dir)))} review</h1>
<p>Each eval below shows the input data, the CCPM schedule produced with the
skill, and a deliberately naive traditional-CPM baseline (safe durations, no
resource leveling, no buffers, calendars ignored) rendered by the same chart
script. Scroll to compare. Generated {date.today().isoformat()}.</p></header>
<nav>{''.join(nav)}</nav>
<main>{''.join(body)}</main>
<footer>Self-contained report — images embedded, safe to forward.</footer>
</body></html>"""
    with open(out_path, "w") as f:
        f.write(doc)
    print(f"wrote {out_path} ({os.path.getsize(out_path) // 1024} KB, "
          f"{len(nav)} evals)")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(2)
    main(*sys.argv[1:5])
