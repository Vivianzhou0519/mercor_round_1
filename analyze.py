"""Analysis of scored.csv -> summary.md, overview.png, judges.png, failures.png, failures.csv.

Tasks are the data points: each task's tries are averaged first (tries on one task are not independent).
Usage: python analyze.py [--smoke]
"""
import argparse, math, re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import grade, run

B = 10_000
RNG = np.random.default_rng(0)
COLORS = ["#2a6fdb", "#e07b39"]


def normal_ci(x, clip=True):
    """mean ± 1.96·SD/√n; rates are clipped to [0, 1] (the normal approximation can overshoot at small n)."""
    x = np.asarray(x, float)
    m = x.mean()
    if len(x) < 2:
        return m, np.nan, np.nan
    h = 1.96 * x.std(ddof=1) / math.sqrt(len(x))
    return (m, max(m - h, 0), min(m + h, 1)) if clip else (m, m - h, m + h)


def boot_ci(x):
    x = np.asarray(x, float)
    means = x[RNG.integers(0, len(x), (B, len(x)))].mean(axis=1)
    return np.percentile(means, [2.5, 97.5])


def pass_at_k(n, c, k):
    return 1 - math.comb(n - c, k) / math.comb(n, k) if n >= k else np.nan


def pass_hat_k(n, c, k):
    return math.comb(c, k) / math.comb(n, k) if n >= k else np.nan


def kappa(a, b):
    a, b = np.asarray(a, int), np.asarray(b, int)
    po = (a == b).mean()
    pe = a.mean() * b.mean() + (1 - a.mean()) * (1 - b.mean())
    return (po - pe) / (1 - pe) if pe < 1 else np.nan


def pct(x, d=1):
    return "" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{100 * x:.{d}f}%"


def rng_str(lo, hi, d=1):
    return "n/a" if np.isnan(lo) else f"{100 * lo:.{d}f}–{100 * hi:.{d}f}%"


def table(headers, rows):
    """Markdown table with every column padded to its widest cell (aligned in the raw file too)."""
    rows = [[str(c) for c in r] for r in rows]
    w = [max(len(str(h)), *(len(r[i]) for r in rows)) if rows else len(str(h)) for i, h in enumerate(headers)]
    line = lambda cells: "| " + " | ".join(c.ljust(w[i]) for i, c in enumerate(cells)) + " |"
    return "\n".join([line([str(h) for h in headers]), "| " + " | ".join("-" * x for x in w) + " |"]
                     + [line(r) for r in rows])


def leader(scores):
    """Name of the top model, or 'tie' when the top scores are equal."""
    best = max(scores.values())
    top = [m for m, s in scores.items() if np.isclose(s, best)]
    return top[0] if len(top) == 1 else "tie"


def kappa_label(k):
    return "n/a" if np.isnan(k) else "strong" if k > .8 else "good" if k >= .6 else "moderate" if k >= .4 else "weak"


def adjudicate(both):
    """Judges' verdict where they agree; my own reading (data/adjudication.csv) where they disagree."""
    out = both.passed.copy()
    adj = Path("data/adjudication.csv")
    if adj.exists():
        a = pd.read_csv(adj).set_index(["model", "task_id", "try"]).correct
        for i, r in both.iterrows():
            key = (r.model, r.task_id, r["try"])
            if key in a.index:
                out[i] = r.c1 * a[key]  # C1 was never disputed
    return out


TYPES = ["full pass", "right answer, wrong source", "not_found", "wrong_value", "wrong_math", "incomplete", "untagged"]


def deep_dive(df, ok, pt, models, out, md):
    """Dataset-specific analysis on judge 1 verdicts. Returns the frames the failure chart needs."""
    t = ok.copy()
    tags = out / "failure_tags.jsonl"
    if tags.exists():
        tg = pd.read_json(tags, lines=True).drop_duplicates(["model", "task_id", "try"], keep="last")
        t = t.merge(tg[["model", "task_id", "try", "type"]], on=["model", "task_id", "try"], how="left")
    else:
        t["type"] = np.nan
    t["outcome"] = np.select([t.passed == 1, (t.c2 == 1) & (t.c1 == 0)], ["full pass", "right answer, wrong source"],
                             default=t.type.fillna("untagged"))

    md.append("## 8a. Source vs answer: C1 × C2 per model (tries)\n")
    for m in models:
        g = t[t.model == m]
        cell = lambda a, b: int(((g.c1 == a) & (g.c2 == b)).sum())
        md.append(f"**{m}**\n")
        md.append(table(["", "Right answer", "Wrong answer"],
                        [["Right source", f"{cell(1, 1)} full pass", f"{cell(1, 0)} found the document, then misread or miscalculated"],
                         ["Wrong source", f"{cell(0, 1)} right answer, wrong source → still fails", f"{cell(0, 0)} lost"]]) + "\n")
    rawc = t[(t.c2 == 1) & (t.c1 == 0)]
    md.append(f"Right answer but wrong source: {len(rawc)} tries. Is the rubric too strict? These fail only because "
              f"they cited a different page than the rubric's URL" +
              (": " + "; ".join(f"{r.model} {r.task_id[-6:]}#{r['try']}" for _, r in rawc.iterrows()) if len(rawc) else "") + ".\n")

    md.append("## 8b. Failure type (tries, judge 1; wrong answers tagged by an LLM, see failure_tags.jsonl)\n")
    ct = pd.crosstab(t.model, t.outcome).reindex(columns=[c for c in TYPES if c in set(t.outcome)], fill_value=0)
    md.append(table(["model"] + list(ct.columns), [[m] + [f"{v} ({v / ct.loc[m].sum():.0%})" for v in ct.loc[m]]
                                                    for m in ct.index]) + "\n")
    md.append("not_found = never located the right document; wrong_value = found it, pulled the wrong number/fact; "
              "wrong_math = right inputs, wrong calculation; incomplete = refused, hedged or missing parts.\n")

    md.append("## 8c. Search behavior: passes vs fails\n")
    rows = []
    for m in models:
        for lab, g in [("pass", t[(t.model == m) & (t.passed == 1)]), ("fail", t[(t.model == m) & (t.passed == 0)])]:
            if len(g):
                rows.append([m, lab, len(g), f"{g.searches.mean():.1f}", f"{g.searches.median():.0f}",
                             f"{g.searches.max():.0f}", f"{(g.searches >= 10).mean():.0%}"])
    md.append(table(["model", "outcome", "tries", "mean searches", "median", "max", "hit the 10-search cap"], rows) + "\n")
    if "type" in t and t.type.notna().any():
        st = t[t.type.notna()].groupby(["model", "type"]).searches.mean().unstack().round(1)
        md.append("Mean searches by failure type: " + "; ".join(
            f"{m}: " + ", ".join(f"{k} {v}" for k, v in st.loc[m].dropna().items()) for m in st.index) + ".\n")

    md.append("## 8d. Tasks no one solved (0 of 6 tries across both models)\n")
    tk = t.groupby("task_id").agg(passes=("passed", "sum"), tries=("passed", "size"), any_c2=("c2", "max"),
                                   any_c1=("c1", "max"), seen=("source_seen", "max"), expected=("expected", "first"),
                                   category=("category", "first")).reset_index()
    dead = tk[tk.passes == 0]
    def why(r):
        if r.any_c2:
            return "someone got the answer but never with the right source: rubric source may be too strict"
        if not (r.seen or r.any_c1):  # judge-confirmed citation also counts as found
            return "gold document never appeared in any search: too hard to find (or URL moved)"
        return "document was found but no try got the answer: hard extraction/maths, or check the expected answer"
    md.append(table(["task", "category", "expected", "any right answer", "any right source", "gold doc in search results", "likely reason"],
                    [[r.task_id[-6:], r.category, str(r.expected)[:40], "yes" if r.any_c2 else "no", "yes" if r.any_c1 else "no",
                      "yes" if r.seen else "no", why(r)] for _, r in dead.iterrows()]) + "\n")
    md.append(f"{len(dead)} of {len(tk)} tasks unsolved. All tasks passed the judge precheck (gold answer passes, "
              f"empty fails), so these are not broken graders; whether the expected answer itself is right needs a human check.\n")

    md.append("## 8e. Cost per correct answer\n")
    rows = []
    for m in models:
        g, a = t[t.model == m], df[df.model == m]
        n_pass = int(g.passed.sum())
        rows.append([m, f"${a.cost.sum():.2f}", n_pass, f"${a.cost.sum() / n_pass:.2f}" if n_pass else "∞ (no passes)"])
    md.append(table(["model", "total cost", "passing tries", "cost per correct answer"], rows) + "\n")

    if len(models) == 2:
        w = pt.pivot(index="task_id", columns="model", values="p").dropna()
        d = (w[models[0]] - w[models[1]]).values
        gap, sd = d.mean(), d.std(ddof=1)
        md.append("## 8f. Sample size\n")
        if gap and sd:
            n80 = math.ceil(((1.96 + 0.84) * sd / abs(gap)) ** 2)
            md.append(f"Observed paired gap {100 * gap:+.1f} pts with per-task SD {100 * sd:.1f} pts. To detect a gap this size "
                      f"(95% confidence, 80% power) we'd need about **{n80} tasks**; we have {len(d)}. "
                      f"Formula: n = ((1.96 + 0.84) × SD / gap)².\n")
    return {"t": t, "tk": tk}


def judges_chart(both, models, out, j1, j2):
    fig, ax = plt.subplots(1, 4, figsize=(20, 5), gridspec_kw={"width_ratios": [1, 1, 1, 1.6]})
    for a, (col, name) in zip(ax[:3], [("c1", "C1 source"), ("c2", "C2 answer"), ("passed", "Final pass")]):
        x, y = both[col].astype(int), both[col + "_j2"].astype(int)
        m2 = np.array([[((x == 1) & (y == 1)).sum(), ((x == 1) & (y == 0)).sum()],
                       [((x == 0) & (y == 1)).sum(), ((x == 0) & (y == 0)).sum()]])
        a.imshow(np.log1p(m2), cmap="Blues")
        for i in range(2):
            for j in range(2):
                a.text(j, i, str(m2[i, j]), ha="center", va="center", fontsize=14,
                       color="white" if m2[i, j] > m2.max() / 2 else "black")
        a.set_xticks([0, 1], [f"{j2}\npass", f"{j2}\nfail"], fontsize=8)
        a.set_yticks([0, 1], [f"{j1}\npass", f"{j1}\nfail"], fontsize=8)
        k = kappa(x, y)
        a.set_title(f"{name}: agree {(x == y).mean():.0%}, κ={k:.2f} ({kappa_label(k)})", fontsize=10)
    cols = [("Judge 1", "passed"), ("Judge 2", "passed_j2"), ("Strict", "strict"), ("Lenient", "lenient"),
            ("Adjudicated", "adjudicated")]
    wdt = 0.8 / len(models)
    for i, m in enumerate(models):
        g = both[both.model == m]
        for j, (lab, c) in enumerate(cols):
            per = g.groupby("task_id")[c].mean()
            mean, lo, hi = normal_ci(per)
            xx = j + (i - (len(models) - 1) / 2) * wdt
            ax[3].bar(xx, 100 * mean, wdt, color=COLORS[i], label=m if j == 0 else None,
                      yerr=[[100 * (mean - lo)], [100 * (hi - mean)]], capsize=3)
            ax[3].text(xx, 100 * hi + 1, f"{100 * mean:.0f}%", ha="center", fontsize=8)
    ax[3].set_xticks(range(len(cols)), [c[0] for c in cols]); ax[3].set_ylim(0, 50)
    ax[3].set_ylabel("pass rate (%)"); ax[3].legend(fontsize=8, loc="upper left")
    ax[3].set_title("Pass rate by judging rule (95% range)")
    fig.tight_layout(); fig.savefig(out / "judges.png", dpi=130); plt.close(fig)


def failures_chart(deep, models, out):
    t, tk = deep["t"], deep["tk"]
    fig, ax = plt.subplot_mosaic([["outcome", "c1c2", "cost"], ["search", "tasks", "tasks"]], figsize=(20, 11))
    a = ax["outcome"]  # outcome mix
    types = [c for c in TYPES if c in set(t.outcome)]
    cmap = dict(zip(TYPES, ["#2e9e44", "#9bd18b", "#7f7f7f", "#e07b39", "#c23b22", "#b9a0d6", "#dddddd"]))
    left = np.zeros(len(models))
    for ty in types:
        v = np.array([(t[t.model == m].outcome == ty).sum() for m in models])
        a.barh(models, v, left=left, color=cmap[ty], label=ty)
        for k, (l, vv) in enumerate(zip(left, v)):
            if vv:
                a.text(l + vv / 2, k, str(vv), ha="center", va="center", fontsize=9)
        left += v
    a.set_xlabel("tries"); a.legend(fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=3)
    a.set_title("Outcome per try: pass, wrong source, or failure type")
    a = ax["c1c2"]  # C1 x C2 per model
    lab = ["right src\nright ans", "right src\nwrong ans", "wrong src\nright ans", "wrong src\nwrong ans"]
    wdt = 0.8 / len(models)
    for i, m in enumerate(models):
        g = t[t.model == m]
        v = [((g.c1 == 1) & (g.c2 == 1)).sum(), ((g.c1 == 1) & (g.c2 == 0)).sum(),
             ((g.c1 == 0) & (g.c2 == 1)).sum(), ((g.c1 == 0) & (g.c2 == 0)).sum()]
        xx = np.arange(4) + (i - (len(models) - 1) / 2) * wdt
        a.bar(xx, v, wdt, color=COLORS[i], label=m)
        for x_, v_ in zip(xx, v):
            a.text(x_, v_ + 0.5, str(v_), ha="center", fontsize=9)
    a.set_xticks(range(4), lab, fontsize=9); a.set_ylabel("tries"); a.legend(fontsize=8)
    a.set_title("Source (C1) × answer (C2)")
    a = ax["search"]  # searches pass vs fail
    pos, labels = [], []
    for i, m in enumerate(models):
        for j, (lab_, sel) in enumerate([("pass", 1), ("fail", 0)]):
            v = t[(t.model == m) & (t.passed == sel)].searches.values
            x = i * 2.5 + j
            if len(v):
                a.boxplot([v], positions=[x], widths=.6, showfliers=False)
                a.scatter(x + RNG.uniform(-.15, .15, len(v)), v, s=14, color=COLORS[i], alpha=.6)
            pos.append(x); labels.append(f"{m}\n{lab_} (n={len(v)})")
    a.set_xticks(pos, labels, fontsize=8); a.set_ylabel("searches per try"); a.set_title("Searches: passes vs fails")
    a = ax["tasks"]  # per-task heatmap
    tk_m = t.groupby(["task_id", "model"]).passed.sum().unstack().reindex(columns=models)
    order = tk_m.sum(axis=1).sort_values(ascending=False).index
    tk_m = tk_m.loc[order]
    a.imshow(tk_m.values.T, cmap="Greens", vmin=0, vmax=3, aspect="auto")
    for i in range(tk_m.shape[0]):
        for j in range(tk_m.shape[1]):
            a.text(i, j, int(tk_m.values[i, j]), ha="center", va="center", fontsize=8)
    a.set_yticks(range(len(models)), models, fontsize=8)
    a.set_xticks(range(len(order)), [x[-4:] for x in order], rotation=90, fontsize=7)
    n_dead = int((tk_m.sum(axis=1) == 0).sum())
    a.set_title(f"Passes per task (of 3 tries); {n_dead} of {len(order)} tasks unsolved by both")
    a = ax["cost"]  # cost per correct
    v = []
    for m in models:
        n_pass = t[t.model == m].passed.sum()
        v.append(t[t.model == m].cost.sum() / n_pass if n_pass else np.nan)
    a.bar(models, v, color=COLORS[:len(models)])
    for i, vv in enumerate(v):
        a.text(i, (0 if np.isnan(vv) else vv) * 1.02 + .01, "no passes" if np.isnan(vv) else f"${vv:.2f}", ha="center")
    a.set_ylabel("$ per passing try"); a.set_title("Cost per correct answer")
    fig.tight_layout(); fig.savefig(out / "failures.png", dpi=120); plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()
    out = Path("results_smoke" if args.smoke else "results")
    df = pd.read_csv(out / "scored.csv")
    ok = df[(df.status != "api_error") & df.passed.notna()].copy()
    models = sorted(ok.model.unique())
    md = []

    # ---- per-task table: tasks are the unit ----
    pt = ok.groupby(["model", "task_id"]).agg(p=("passed", "mean"), c=("passed", "sum"), n=("passed", "size"),
                                              c1=("c1", "mean"), c2=("c2", "mean"), seen=("source_seen", "mean"),
                                              sd=("passed", "std"), category=("category", "first")).reset_index()
    K = int(pt.n.min())
    ids = df.drop_duplicates("model").set_index("model").model_id.to_dict()
    md.append("# BrowseComp n=20: results\n")
    md.append(f"Setup: models {', '.join(f'`{ids[m]}`' for m in models)}; judges "
              f"{', '.join(f'`{j}`' for j in grade.JUDGES)} (primary = first); web search = OpenRouter "
              f"`openrouter:web_search` (Exa, max 10 searches); {pt.task_id.nunique()} tasks x {K}+ tries. "
              f"Pass = judge says yes to BOTH C1 (source) and C2 (answer). Ranges are 95%; tasks are the data points.\n")

    # ---- 0. headline: does the result depend on the judge? ----
    j1, j2 = (run.short(j) for j in grade.JUDGES)
    both = ok[ok.passed_j2.notna()].copy()
    md.append("## Headline: pass rate under each judge\n")
    if len(both):
        both["strict"] = both.passed * both.passed_j2
        both["lenient"] = np.maximum(both.passed, both.passed_j2)
        both["adjudicated"] = adjudicate(both)
        cols = {f"Judge 1 ({j1}, primary)": "passed", f"Judge 2 ({j2}, check)": "passed_j2",
                "Strict: both pass": "strict", "Lenient: either passes": "lenient",
                "Adjudicated (my read of disagreements)": "adjudicated"}
        per = both.groupby(["model", "task_id"])[list(cols.values())].mean().reset_index()
        rows, verdicts = [], {}
        for m in models:
            cells = [f"{m} pass rate"]
            for c in cols.values():
                mean, lo, hi = normal_ci(per[per.model == m][c])
                cells.append(f"{pct(mean)} [{rng_str(lo, hi)}]")
            rows.append(cells)
        if len(models) == 2:
            a_, b_ = models
            cells = [f"Gap {a_} − {b_} (paired)"]
            for name, c in cols.items():
                w = per.pivot(index="task_id", columns="model", values=c).dropna()
                mean, lo, hi = normal_ci(w[a_] - w[b_], clip=False)
                sig = not np.isnan(lo) and (lo > 0 or hi < 0)
                verdicts[name] = f"{a_ if mean > 0 else b_} better" if sig else "can't tell apart"
                cells.append(f"{100 * mean:+.1f} pts [{100 * lo:+.1f} to {100 * hi:+.1f}]" if not np.isnan(lo)
                             else f"{100 * mean:+.1f} pts")
            rows.append(cells)
        md.append(table([""] + list(cols), rows) + "\n")
        md.append("Strict = a pass only if both judges say pass; lenient = a pass if either does. These bracket the "
                  "lowest and highest believable score; the truth is probably in between. Adjudicated = the judges' verdict "
                  "where they agree, my own reading (data/adjudication.csv) where they disagree. "
                  "Ranges are 95% (±1.96·SD/√n over tasks). All other sections and overview.png use judge 1 only.\n")
        rows = [[col.upper() if col != "passed" else "final pass", len(both),
                 pct((both[col] == both[col + "_j2"]).mean()), f"{kappa(both[col], both[col + '_j2']):.2f}"]
                for col in ["c1", "c2", "passed"]]
        md.append(table(["verdict", "tries", "agreement", "Cohen's κ"], rows) + "\n")
        if verdicts:
            same = len(set(verdicts.values())) == 1
            md.append(("**Verdict: the conclusion does not change with the judge**: " if same else
                       "**Verdict: the conclusion DEPENDS on the judge**: ") +
                      "; ".join(f"{k}: {v}" for k, v in verdicts.items()) + ".\n")
    else:
        md.append(f"Judge 2 ({j2}) not graded yet: run `python grade.py --judges 2`. Numbers below use judge 1 only.\n")

    # ---- 1. pass rate ----
    rows, pr = [], {}
    for m in models:
        x = pt[pt.model == m].p
        mean, lo, hi = normal_ci(x)
        blo, bhi = boot_ci(x)
        pr[m] = (mean, lo, hi)
        rows.append([m, len(x), pct(mean), rng_str(lo, hi), rng_str(blo, bhi)])
    md.append("## 1. Pass rate (C1 and C2)\n")
    md.append(table(["model", "tasks", "pass rate", "95% range (±1.96·SD/√n)", "95% bootstrap"], rows) + "\n")

    # ---- 2. pass@k / pass^k ----
    metrics = ["pass@1"] + ([f"pass@{K}", f"pass^{K}"] if K > 1 else [])
    rows, pk = [], {}
    for m in models:
        g = pt[pt.model == m]
        for name in metrics:
            k = int(name[-1])
            f = pass_hat_k if "^" in name else pass_at_k
            v = np.array([f(int(n), int(c), k) for n, c in zip(g.n, g.c)])
            lo, hi = boot_ci(v)
            pk[(m, name)] = (v.mean(), lo, hi)
            rows.append([m, name, pct(v.mean()), rng_str(lo, hi)])
    md.append("## 2. pass@k and pass^k (unbiased, per task then averaged)\n")
    md.append(table(["model", "metric", "value", "95% bootstrap"], rows) + "\n")
    leads = {name: leader({m: pk[(m, name)][0] for m in models}) for name in metrics}
    md.append("Leader by metric: " + ", ".join(f"{k} → {v}" for k, v in leads.items()) +
              (". The ranking is the same across metrics.\n" if len(set(leads.values())) == 1
               else ". **The ranking changes across metrics.**\n"))

    # ---- 3. paired gap ----
    gap = None
    if len(models) == 2:
        a, b = models
        w = pt.pivot(index="task_id", columns="model", values="p").dropna()
        d = (w[a] - w[b]).values
        mean, lo, hi = normal_ci(d, clip=False)
        blo, bhi = boot_ci(d)
        gap = (mean, lo, hi)
        won, lost, tied = int((d > 0).sum()), int((d < 0).sum()), int((d == 0).sum())
        verdict = (f"{a if mean > 0 else b} is better on these tasks" if not np.isnan(lo) and (lo > 0 or hi < 0)
                   else "we can't tell them apart yet")
        md.append(f"## 3. Paired gap ({a} − {b}, same {len(d)} tasks)\n")
        md.append(table(["gap", "95% range (paired)", "95% paired bootstrap", f"{a} won", f"{b} won", "tied"],
                        [[f"{100 * mean:+.1f} pts", f"{100 * lo:+.1f} to {100 * hi:+.1f} pts" if not np.isnan(lo) else "n/a",
                          f"{100 * blo:+.1f} to {100 * bhi:+.1f} pts", won, lost, tied]]) + "\n")
        md.append(f"Verdict: {verdict}.\n")

    # ---- 4. which criterion fails ----
    rows = []
    for m in models:
        g, t = pt[pt.model == m], ok[ok.model == m]
        rows.append([m, pct(g.c1.mean()), pct(g.c2.mean()), pct(g.p.mean()),
                     int(((t.c2 == 1) & (t.c1 == 0)).sum()), int(((t.c1 == 1) & (t.c2 == 0)).sum()),
                     pct(g.seen.mean()), int(((t.source_seen == 1) & (t.c1 == 0)).sum())])
    md.append("## 4. Where tries fail: source (C1) vs answer (C2)\n")
    md.append(table(["model", "C1 source yes", "C2 answer yes", "both (pass)", "tries: right answer, wrong source",
                     "tries: right source, wrong answer", "gold source in search results",
                     "tries: saw gold source but didn't cite it"], rows) + "\n")

    # ---- 5. judge agreement ----
    rows = [[col, len(both), pct((both[col] == both[col + "_j2"]).mean()), f"{kappa(both[col], both[col + '_j2']):.2f}",
             pct(both[col].mean()), pct(both[col + "_j2"].mean())] for col in ["c1", "c2", "passed"]] if len(both) else []
    j1, j2 = (run.short(j) for j in grade.JUDGES)
    sub = ok[ok.source_cited_text.notna()]
    crows = [[m, pct(g.source_cited_text.mean()), pct((g.c1 == g.source_cited_text).mean()),
             int(((g.c1 == 1) & (g.source_cited_text == 0)).sum()), int(((g.c1 == 0) & (g.source_cited_text == 1)).sum()),
             pct(g.cited_grounded.mean()), f"{g.n_cited_urls.mean():.1f}"] for m in models for g in [sub[sub.model == m]]]
    md.append("### Is the cited source real? (deterministic checks, no LLM)\n")
    md.append(table(["model", "gold URL string in response", "judge C1 agrees with string check",
                     "judge yes / string no", "judge no / string yes", "cited URLs that came from its searches",
                     "URLs cited per try"], crows) + "\n")
    md.append("C1 is judged from the response text only (its Sources line), not from the search-result list. "
              "A cited URL that never appeared in the model's search results was probably made up.\n")

    md.append(f"## 5. Judge agreement ({j1} = judge 1 vs {j2} = judge 2, {len(both)} graded answers)\n")
    for col, name in [("c1", "C1 (source)"), ("c2", "C2 (answer)"), ("passed", "Final pass")]:
        a_, b_ = both[col].astype(int), both[col + "_j2"].astype(int)
        po, pa, pb = (a_ == b_).mean(), a_.mean(), b_.mean()
        pe = pa * pb + (1 - pa) * (1 - pb)
        k = (po - pe) / (1 - pe) if pe < 1 else np.nan
        md.append(f"**{name}**\n")
        md.append(table(["", "Judge 2: pass", "Judge 2: fail"],
                        [["Judge 1: pass", int(((a_ == 1) & (b_ == 1)).sum()), int(((a_ == 1) & (b_ == 0)).sum())],
                         ["Judge 1: fail", int(((a_ == 0) & (b_ == 1)).sum()), int(((a_ == 0) & (b_ == 0)).sum())]]) + "\n")
        md.append(f"Agreement {pct(po)}; chance agreement = {pa:.2f}×{pb:.2f} + {1 - pa:.2f}×{1 - pb:.2f} = {pe:.2f}; "
                  f"κ = ({po:.2f} − {pe:.2f}) ÷ (1 − {pe:.2f}) = **{k:.2f}** ({kappa_label(k)}).\n")
    dis = both[(both.c1 != both.c1_j2) | (both.c2 != both.c2_j2)]
    dis[["model", "task_id", "try", "c1", "c1_j2", "c2", "c2_j2", "reason", "reason_j2", "answer_tail"]].to_csv(
        out / "judge_disagreements.csv", index=False)

    win = {}
    for name, col in [("judge 1", "passed"), ("judge 2", "passed_j2")]:
        win[name] = leader({m: both[both.model == m].groupby("task_id")[col].mean().mean() for m in models})
    md.append(f"**Does the headline change with the judge?** Winner under judge 1: {win['judge 1']}; under judge 2: "
              f"{win['judge 2']}. " + ("The winner does not flip." if win["judge 1"] == win["judge 2"]
                                       else "**The winner flips: the result depends on the judge.**") + "\n")

    adj = Path("data/adjudication.csv")
    if adj.exists() and len(dis):
        a = pd.read_csv(adj)
        md.append(f"### Who was right? (I read all {len(a)} disagreements)\n")
        md.append(table(["model", "task", "try", "judge 1", "judge 2", "correct", "right judge", "why they disagreed"],
                        [[r.model, r.task_id[-6:], r["try"], r.judge1, r.judge2, r.correct, r.right_judge, r.cause]
                         for _, r in a.iterrows()]) + "\n")
        tally = a.right_judge.value_counts().to_dict()
        md.append("Tally: " + ", ".join(f"{k} right {v}×" for k, v in tally.items()) +
                  f". Judge 1 ({j1}) errors: too strict on caveats (counted as hedges), too lenient on rounding "
                  f"(20.1% for an 'exact' 20.09%). Judge 2 ({j2}) error: graded the reasoning instead of the stated answer.\n")

    rows = []
    for m in models:
        g = both[both.model == m]
        rows.append([m, len(g), pct((g.c2 == g.c2_j2).mean()), f"{kappa(g.c2, g.c2_j2):.2f}",
                     pct((g.passed == g.passed_j2).mean()), f"{kappa(g.passed, g.passed_j2):.2f}",
                     int(((g.c1 != g.c1_j2) | (g.c2 != g.c2_j2)).sum())])
    md.append("### Bias check: is agreement lower for one model?\n")
    md.append(table(["model", "answers", "C2 agreement", "C2 κ", "pass agreement", "pass κ", "disagreements"], rows) + "\n")
    md.append("κ is unstable when almost every answer fails (few passes to agree on); read the disagreement counts alongside it.\n")

    # ---- 6. run-to-run variance ----
    if K > 1:
        rows = []
        for m in models:
            g = pt[pt.model == m]
            flaky = int(((g.c > 0) & (g.c < g.n)).sum())
            rows.append([m, f"{g.sd.mean():.2f}", flaky, int((g.c == 0).sum()), int((g.c == g.n).sum())])
        md.append("## 6. Run-to-run variance\n")
        md.append(table(["model", "mean per-task SD of tries", "flaky tasks (some pass, some fail)",
                         "never pass", "always pass"], rows) + "\n")

    # ---- 8. dataset-specific deep dive (judge 1) ----
    deep = deep_dive(df, ok, pt, models, out, md)
    md.append("Domains are skipped: 12 domains with 1–2 tasks each is too small to show anything.\n")

    # ---- 9. failures ----
    md.append("## 9. Failures\n")
    rows = [[m, *(int((df[df.model == m].status == s).sum()) for s in ["ok", "empty", "max_turns", "api_error"]),
             int((ok[ok.model == m].passed == 0).sum())] for m in models]
    md.append(table(["model", "ok", "empty", "max_turns", "api_error", "judged fail"], rows) + "\n")
    fails = df[(df.status != "ok") | (df.passed == 0)]
    fails[["model", "task_id", "try", "category", "status", "c1", "c2", "expected", "answer_tail", "reason"]].to_csv(
        out / "failures.csv", index=False)

    # ---- 10. cost and speed ----
    log = out / ("smoke_log.txt" if args.smoke else "run_log.txt")
    walls = re.findall(r"done in (\d+)s", log.read_text()) if log.exists() else []
    md.append("## 10. Cost and speed\n")
    rows = [[m, f"${g.cost.sum():.2f}", f"${g.cost.mean():.4f}", f"{g.input_tokens.mean():,.0f}",
             f"{g.output_tokens.mean():,.0f}", f"{g.searches.mean():.1f}", f"{g.seconds.median():.0f}s",
             f"{g.seconds.quantile(.9):.0f}s"] for m in models for g in [df[df.model == m]]]
    md.append(table(["model", "total cost", "cost/try", "avg input tok", "avg output tok", "searches/try",
                     "median time", "p90 time"], rows) + "\n")
    md.append(f"Total model cost ${df.cost.sum():.2f} (OpenRouter billed, search included; judges not included). "
              f"Run wall time: {' + '.join(walls) + 's' if walls else 'n/a'}.\n")

    # ---- 11. behavior ----
    rows = []
    for m in models:
        g = ok[ok.model == m].assign(tsr=lambda t: np.where(t.tool_calls > 0, 1 - t.tool_calls_failed / t.tool_calls.clip(lower=1), np.nan))
        med = g.groupby("task_id")[["turns", "words_per_turn", "searches", "tsr"]].median().median()
        rows.append([m, f"{med.turns:.0f}", f"{med.words_per_turn:.0f}", f"{med.searches:.0f}",
                     "n/a (no client tools)" if np.isnan(med.tsr) else pct(med.tsr)])
    md.append("## 11. Behavior (median over tasks of per-task medians)\n")
    md.append(table(["model", "turns", "words/turn", "searches", "tool-call success"], rows) + "\n")
    if len(models) and ok.searches.nunique() > 1:
        r = ok[["searches", "passed"]].corr().iloc[0, 1]
        md.append(f"Correlation of searches with pass (all tries): {r:.2f}.\n")

    (out / "summary.md").write_text("\n".join(md))

    # ---- charts ----
    fig, ax = plt.subplots(1, 3, figsize=(19, 6.5))
    for i, m in enumerate(models):
        mean, lo, hi = pr[m]
        err = None if np.isnan(lo) else [[mean - lo], [hi - mean]]
        ax[0].bar(i, 100 * mean, color=COLORS[i], yerr=None if err is None else np.array(err) * 100, capsize=6, label=m)
        ax[0].text(i, 100 * (hi if not np.isnan(hi) else mean) + 2, f"{pct(mean)}\n({rng_str(lo, hi)})", ha="center", va="bottom", fontsize=9)
    ax[0].set_xticks(range(len(models)), models); ax[0].set_ylim(0, 115); ax[0].set_ylabel("% of tasks")
    ax[0].set_title("Pass rate (C1 and C2), 95% range, judge 1")
    wdt = 0.8 / max(len(models), 1)
    for i, m in enumerate(models):
        for j, name in enumerate(metrics):
            v, lo, hi = pk[(m, name)]
            x = j + (i - (len(models) - 1) / 2) * wdt
            ax[1].bar(x, 100 * v, wdt, color=COLORS[i], yerr=[[100 * (v - lo)], [100 * (hi - v)]], capsize=4,
                      label=m if j == 0 else None)
            ax[1].text(x, 100 * hi + 2, f"{100 * v:.0f}%\n({100 * lo:.0f}–{100 * hi:.0f})", ha="center", va="bottom", fontsize=8)
    ax[1].set_xticks(range(len(metrics)), metrics); ax[1].set_ylim(0, 120); ax[1].set_title("pass@1 / pass@k / pass^k (bootstrap 95%), judge 1")
    ax[1].legend(loc="upper left", fontsize=8)
    if gap:
        mean, lo, hi = gap
        ax[2].errorbar([100 * mean], [0], xerr=None if np.isnan(lo) else [[100 * (mean - lo)], [100 * (hi - mean)]],
                       fmt="o", color="black", capsize=8, markersize=9)
        ax[2].axvline(0, color="grey", ls="--")
        lab = f"{100 * mean:+.1f} pts" + ("" if np.isnan(lo) else f"\n(95% range {100 * lo:+.1f} to {100 * hi:+.1f})")
        ax[2].text(100 * mean, 0.15, lab, ha="center", fontsize=10)
        lim = max(30, 100 * np.nanmax(np.abs([lo, hi, mean])) + 10)
        ax[2].set_xlim(-lim, lim); ax[2].set_ylim(-1, 1); ax[2].set_yticks([])
        ax[2].set_xlabel(f"← {models[1]} better     pass-rate gap (pts)     {models[0]} better →")
        ax[2].set_title(f"Paired gap {models[0]} − {models[1]}, judge 1")
    fig.tight_layout(); fig.savefig(out / "overview.png", dpi=130); plt.close(fig)

    if len(both):
        judges_chart(both, models, out, j1, j2)
    failures_chart(deep, models, out)
    print("\n".join(md))
    (out / "by_category.png").unlink(missing_ok=True)
    print(f"\nwrote {out}/summary.md, overview.png, judges.png, failures.png, failures.csv, judge_disagreements.csv")


if __name__ == "__main__":
    main()
