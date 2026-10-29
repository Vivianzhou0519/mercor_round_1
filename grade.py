"""LLM-as-a-judge grading of every try against the task rubric (C1 source, C2 answer), with 2 judges.

Usage:
  python grade.py --precheck       # judge sanity check on synthetic gold / empty / wrong-URL answers
  python grade.py [--smoke]        # grade results/raw.jsonl (or results_smoke/) -> scored.csv
"""
import argparse, asyncio, csv, json, re, sys
from pathlib import Path
from urllib.parse import urlsplit

import pandas as pd

import run

JUDGES = ["openrouter/deepseek/deepseek-v4-flash", "openrouter/google/gemini-3.1-flash-lite"]  # primary first

JUDGE_PROMPT = """You are grading a research assistant's response against a rubric. Grade each criterion independently as met (true) or not met (false). No partial credit.

Rules:
- Source criterion: met only if the response itself names/links the required document (same document: ignore http/https, "www.", query strings, #page anchors, trailing slashes; a different page that merely quotes it does NOT count).
- Answer criterion: met only if the response's final answer matches the expected answer. Equivalent formatting, units or rounding to the stated precision count. Every part of a multi-part answer must be present and correct. A hedge between several answers, a refusal, or "unable to determine" is not met.
- Judge only what the response says; do not use your own knowledge of the answer.

QUESTION:
{question}

RUBRIC:
{criteria}

RESPONSE:
<<<
{response}
>>>

Return only JSON: {{"criteria": [{{"id": 1, "met": true or false, "reason": "<one sentence>"}}, {{"id": 2, "met": true or false, "reason": "<one sentence>"}}]}}"""


def load_rubrics():
    out = {}
    with run.DATA.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            crits = [next(iter(c.values())) for c in json.loads(r["Rubric JSON"])]
            out[r["Task ID"]] = {"question": r["Prompt"], "criteria": crits}
    return out


def norm_url(u):
    s = urlsplit(u.strip().rstrip(".,;)"))
    return (s.netloc.lower().removeprefix("www.") + s.path.rstrip("/")).lower()


def source_urls(rubric):
    return [norm_url(u) for u in re.findall(r"https?://[^\s)\]]+", rubric["criteria"][0]["description"])]


def exact_answer(text):
    m = re.findall(r"Exact Answer:\s*\**\s*(.+)", text or "")
    return m[-1].strip().strip("*").strip() if m else ""


def write_answers_md(df, rubrics, path):
    """Human-readable view: per task, the expected answer and every try's answer + verdicts + full reply."""
    md = ["# Model answers by task\n"]
    for tid, g in df.groupby("task_id", sort=False):
        rb = rubrics[tid]
        md += [f"## {g.category.iloc[0]} · `{tid}`\n", f"**Question:** {rb['question']}\n",
               f"**Expected:** {answer_of(rb)}  \n**Source:** {rb['criteria'][0]['description'].split(':', 1)[-1].strip()}\n"]
        for _, r in g.iterrows():
            if r.status == "api_error":
                md.append(f"- **{r.model} try {r['try']}**: api_error\n"); continue
            v = lambda x: "✅" if x == 1 else "❌" if x == 0 else "?"
            md += [f"### {r.model} · try {r['try']} · {'PASS' if r.passed == 1 else 'FAIL'}",
                   f"Answer: **{r.exact_answer or '(no Exact Answer line)'}**  ",
                   f"Judge 1: C1 {v(r.c1)} C2 {v(r.c2)}: {r.reason}  ",
                   f"Judge 2: C1 {v(r.c1_j2)} C2 {v(r.c2_j2)}: {r.reason_j2}  ",
                   f"searches {r.searches}, {r.seconds}s, gold source in search results: {'yes' if r.source_seen else 'no'}\n",
                   "<details><summary>full reply</summary>\n\n" + (r.final_answer or "") + "\n\n</details>\n"]
    Path(path).write_text("\n".join(md))


def answer_of(rubric):
    return rubric["criteria"][1]["description"].split("correct answer:", 1)[-1].strip()


async def judge(judge_model, rubric, response, log):
    crits = "\n".join(f"{i}. {c['description']}" for i, c in enumerate(rubric["criteria"], 1))
    prompt = JUDGE_PROMPT.format(question=rubric["question"], criteria=crits, response=response or "(empty)")
    for _ in range(2):  # one extra try if the JSON is unreadable
        resp, err = await run.call_with_retries(log, f"judge {run.short(judge_model)}", model=judge_model,
                                                messages=[{"role": "user", "content": prompt}],
                                                temperature=0, timeout=180)
        if resp is None:
            return None
        text = resp.choices[0].message.content or ""
        m = re.search(r"\{.*\}", text, re.S)
        try:
            items = {c["id"]: c for c in json.loads(m.group(0))["criteria"]}
            return {"c1": int(bool(items[1]["met"])), "c2": int(bool(items[2]["met"])),
                    "reason": f"C1: {items[1]['reason']} | C2: {items[2]['reason']}"}
        except Exception:
            continue
    return None


async def grade_one(rubric, response, log):
    res = await asyncio.gather(*(judge(j, rubric, response, log) for j in JUDGES))
    row = {}
    for suffix, r in zip(["", "_j2"], res):
        if r is None:
            row.update({f"c1{suffix}": None, f"c2{suffix}": None, f"passed{suffix}": None, f"reason{suffix}": "judge_error"})
        else:
            row.update({f"c1{suffix}": r["c1"], f"c2{suffix}": r["c2"], f"passed{suffix}": r["c1"] * r["c2"],
                        f"reason{suffix}": r["reason"]})
    return row


async def precheck(log):
    rubrics = load_rubrics()
    cases = []
    for tid, rb in rubrics.items():
        url = rb["criteria"][0]["description"].split(":", 1)[-1].strip()
        cases += [(tid, "gold", f"Explanation: found it in the official document.\nExact Answer: {answer_of(rb)}\nSources: {url}\nConfidence: 90%", (1, 1)),
                  (tid, "empty", "", (0, 0)),
                  (tid, "wrong_url", f"Explanation: found it online.\nExact Answer: {answer_of(rb)}\nSources: https://en.wikipedia.org/wiki/Main_Page\nConfidence: 90%", (0, 1))]
    rows = await asyncio.gather(*(grade_one(rubrics[t], resp, log) for t, _, resp, _ in cases))
    bad = []
    for (tid, kind, _, (e1, e2)), r in zip(cases, rows):
        for suffix in ["", "_j2"]:
            got = (r[f"c1{suffix}"], r[f"c2{suffix}"])
            if got != (e1, e2):
                j = run.short(JUDGES[0 if not suffix else 1])
                bad.append({"task_id": tid, "case": kind, "judge": j, "expected": f"{e1}{e2}",
                            "got": f"{got[0]}{got[1]}", "reason": r[f"reason{suffix}"]})
    for b in bad:
        log(f"PRECHECK FAIL {b['task_id'][-6:]} {b['case']:9s} {b['judge']:24s} expected c1c2={b['expected']} got {b['got']}  {b['reason'][:150]}")
    pd.DataFrame(bad, columns=["task_id", "case", "judge", "expected", "got", "reason"]).to_csv("data/dropped.csv", index=False)
    log(f"precheck: {len(cases) * 2 - len(bad)}/{len(cases) * 2} judge verdicts as expected; "
        f"{len({b['task_id'] for b in bad})} tasks flagged -> data/dropped.csv")


def load_cache(out, j):
    """Verdicts of one judge, keyed by (model, task_id, try); also reads the older combined cache."""
    cache, short = {}, run.short(j)
    old = out / "judge_cache.jsonl"
    if old.exists():
        for line in old.read_text().splitlines():
            c = json.loads(line)
            names = [run.short(x) for x in c["judges"].split("|")]
            if short in names:
                sfx = "" if names.index(short) == 0 else "_j2"
                cache[(c["model"], c["task_id"], c["try"])] = {k: c["g"][f"{k}{sfx}"] for k in ("c1", "c2", "reason")}
    path = out / f"judge_cache_{short}.jsonl"
    if path.exists():
        for line in path.read_text().splitlines():
            c = json.loads(line)
            cache[(c["model"], c["task_id"], c["try"])] = c["g"]
    return cache, path


def write_scored(out, recs, rubrics, log):
    caches = [load_cache(out, j)[0] for j in JUDGES]
    rows = []
    for r in recs:
        rb, key, text = rubrics[r["task_id"]], (r["model"], r["task_id"], r["try"]), r["final_answer"] or ""
        g = {}
        if r["status"] != "api_error":
            for sfx, cache in zip(["", "_j2"], caches):
                v = cache.get(key)
                g.update({f"c1{sfx}": v and v["c1"], f"c2{sfx}": v and v["c2"],
                          f"passed{sfx}": v and v["c1"] * v["c2"], f"reason{sfx}": v["reason"] if v else ""})
        conf = re.search(r"Confidence:\s*\**\s*([\d.]+)", text)
        seen = {norm_url(u) for u in r["citations"]}  # every search result OpenRouter surfaced
        cited = {norm_url(u) for u in re.findall(r"https?://[^\s)\]>\"'<,;*]+", text)}  # URLs the model wrote
        rows.append({"model": run.short(r["model"]), "model_id": r["model"], "task_id": r["task_id"], "try": r["try"],
                "category": r["category"], "status": r["status"], **g,
                "has_answer": int("Exact Answer:" in text), "confidence": float(conf.group(1)) if conf else None,
                "source_seen": int(any(s in seen for s in source_urls(rb))),
                "source_cited_text": int(any(s in cited for s in source_urls(rb))),
                "n_cited_urls": len(cited),
                "cited_grounded": len(cited & seen) / len(cited) if cited else None,
                "exact_answer": exact_answer(text), "answer_tail": text[-200:], "expected": answer_of(rb),
                "final_answer": text,
                "turns": r["turns"], "words_per_turn": sum(r["words_per_turn"]) / max(len(r["words_per_turn"]), 1),
                "searches": r["searches"], "tool_calls": r["tool_calls"], "tool_calls_failed": r["tool_calls_failed"],
                "input_tokens": r["input_tokens"], "output_tokens": r["output_tokens"], "cost": r["cost"],
                "seconds": r["seconds"]})
    df = pd.DataFrame(rows).sort_values(["model", "task_id", "try"])
    df.to_csv(out / "scored.csv", index=False)
    write_answers_md(df, rubrics, out / "answers.md")
    ok = df[df.status != "api_error"]
    log(f"scored.csv: {len(df)} tries ({(df.status == 'api_error').sum()} api_error); "
        f"judge 1 graded {ok.passed.notna().sum()}, judge 2 graded {ok.passed_j2.notna().sum()}; "
        f"'Exact Answer:' line in {ok.has_answer.mean():.0%} of tries")
    log(df.groupby("model")[["c1", "c2", "passed", "passed_j2", "source_seen", "source_cited_text",
                             "cited_grounded"]].mean().round(2).to_string())


async def grade(out, log, which):
    """Grade with one judge at a time (primary first), saving each verdict as it arrives."""
    rubrics = load_rubrics()
    recs = {}
    for line in (out / "raw.jsonl").read_text().splitlines():
        r = json.loads(line)
        recs[(r["model"], r["task_id"], r["try"])] = r  # last line wins (re-runs)
    recs = list(recs.values())
    for j in [JUDGES[i - 1] for i in which]:
        cache, path = load_cache(out, j)
        todo = [r for r in recs if r["status"] != "api_error" and (r["model"], r["task_id"], r["try"]) not in cache]
        log(f"judge {run.short(j)}: {len(todo)} tries to grade ({len(cache)} already saved)")
        done, f = [0], path.open("a", encoding="utf-8")

        async def one(r):
            v = await judge(j, rubrics[r["task_id"]], r["final_answer"], log)
            if v:
                f.write(json.dumps({"model": r["model"], "task_id": r["task_id"], "try": r["try"], "g": v}) + "\n")
                f.flush()
            done[0] += 1
            if done[0] % 20 == 0 or done[0] == len(todo):
                log(f"  {run.short(j)}: graded {done[0]}/{len(todo)}")

        await asyncio.gather(*(one(r) for r in todo))
        f.close()
        write_scored(out, recs, rubrics, log)  # results updated after each judge


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--precheck", action="store_true")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--rpm", type=float, default=20)
    ap.add_argument("--judges", default="1,2", help="which judges, in order: 1 = primary, 2 = second")
    args = ap.parse_args()
    run.LIMITER = None
    out = Path("results_smoke" if args.smoke else "results"); out.mkdir(exist_ok=True)
    log = run.Log(out / "grade_log.txt")

    async def go():
        run.LIMITER = run.RateLimiter(args.rpm)
        await (precheck(log) if args.precheck else grade(out, log, [int(x) for x in args.judges.split(",")]))
    asyncio.run(go())


if __name__ == "__main__":
    main()
