"""Analysis of scored.csv -> summary.md, overview.png, by_category.png, failures.csv.

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
    both = ok[ok.passed_j2.notna()]
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

    md.append(f"## 5. Judge agreement ({j1} vs {j2})\n")
    md.append(table(["verdict", "tries", "agreement", "Cohen's κ", f"yes rate {j1}", f"yes rate {j2}"], rows) + "\n")
    dis = both[(both.c1 != both.c1_j2) | (both.c2 != both.c2_j2)]
    dis[["model", "task_id", "try", "c1", "c1_j2", "c2", "c2_j2", "reason", "reason_j2", "answer_tail"]].to_csv(
        out / "judge_disagreements.csv", index=False)
    rows = []
    for m in models:
        mm = pt[pt.model == m].p
        s = both[both.model == m].groupby("task_id").passed_j2.mean()
        rows.append([m, pct(mm.mean()), pct(s.mean())])
    md.append(f"Pass rate under each judge: " + "; ".join(f"{r[0]}: {r[1]} vs {r[2]}" for r in rows) +
              f". {len(dis)} disagreeing tries → judge_disagreements.csv.\n")

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

    # ---- 7. calibration ----
    cal = ok[ok.confidence.notna()].copy()
    if len(cal):
        cal["conf"] = cal.confidence.clip(0, 100) / 100
        cal["bin"] = pd.cut(cal.conf, [0, .25, .5, .75, 1.0], include_lowest=True)
        rows = []
        for m in models:
            g = cal[cal.model == m]
            for bn, gg in g.groupby("bin", observed=True):
                rows.append([m, str(bn), len(gg), pct(gg.conf.mean(), 0), pct(gg.passed.mean(), 0)])
            rows.append([m, "Brier score", len(g), "", f"{((g.conf - g.passed) ** 2).mean():.3f}"])
        md.append("## 7. Calibration: stated confidence vs actual pass\n")
        md.append(table(["model", "confidence bin", "tries", "mean confidence", "pass rate"], rows) + "\n")

    # ---- 8. by category ----
    rows = []
    for m in models:
        for cat, g in pt[pt.model == m].groupby("category"):
            mean, lo, hi = normal_ci(g.p)
            rows.append([m, cat, len(g), pct(mean, 0), rng_str(lo, hi, 0), "small, a lead only" if len(g) < 30 else ""])
    md.append("## 8. By category (Domain)\n")
    md.append(table(["model", "category", "tasks", "pass rate", "95% range", "note"], rows) + "\n")

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
    ax[0].set_title("Pass rate (C1 and C2), 95% range")
    wdt = 0.8 / max(len(models), 1)
    for i, m in enumerate(models):
        for j, name in enumerate(metrics):
            v, lo, hi = pk[(m, name)]
            x = j + (i - (len(models) - 1) / 2) * wdt
            ax[1].bar(x, 100 * v, wdt, color=COLORS[i], yerr=[[100 * (v - lo)], [100 * (hi - v)]], capsize=4,
                      label=m if j == 0 else None)
            ax[1].text(x, 100 * hi + 2, f"{100 * v:.0f}%\n({100 * lo:.0f}–{100 * hi:.0f})", ha="center", va="bottom", fontsize=8)
    ax[1].set_xticks(range(len(metrics)), metrics); ax[1].set_ylim(0, 120); ax[1].set_title("pass@1 / pass@k / pass^k (bootstrap 95%)")
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
        ax[2].set_title(f"Paired gap {models[0]} − {models[1]}")
    fig.tight_layout(); fig.savefig(out / "overview.png", dpi=130); plt.close(fig)

    cats = sorted(pt.category.unique())
    fig, ax = plt.subplots(figsize=(10, 0.55 * len(cats) + 1.5))
    for i, m in enumerate(models):
        g = pt[pt.model == m].groupby("category").p.mean().reindex(cats)
        y = np.arange(len(cats)) + (i - (len(models) - 1) / 2) * wdt
        ax.barh(y, 100 * g.values, wdt, color=COLORS[i], label=m)
        for yy, v in zip(y, g.values):
            if not np.isnan(v):
                ax.text(100 * v + 1, yy, f"{100 * v:.0f}%", va="center", fontsize=8)
    n_per = pt[pt.model == models[0]].groupby("category").size().reindex(cats)
    ax.set_yticks(range(len(cats)), [f"{c} (n={n})" for c, n in zip(cats, n_per)], fontsize=8)
    ax.set_xlim(0, 110); ax.set_xlabel("pass rate (%)"); ax.invert_yaxis(); ax.legend(loc="lower right")
    ax.set_title("Pass rate by category: 1–2 tasks each, a lead only")
    fig.tight_layout(); fig.savefig(out / "by_category.png", dpi=130); plt.close(fig)
    print("\n".join(md))
    print(f"\nwrote {out}/summary.md, overview.png, by_category.png, failures.csv, judge_disagreements.csv")


if __name__ == "__main__":
    main()
