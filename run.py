"""Sample two models on the BrowseComp n=20 tasks (with server-side web search) and save every try.

Usage:
  python run.py --smoke            # 5 tasks x 1 try per model -> results_smoke/
  python run.py                    # all tasks x 3 tries -> results/raw.jsonl
"""
import argparse, asyncio, csv, json, os, random, statistics, sys, time, urllib.request
from pathlib import Path

from dotenv import load_dotenv
import litellm

load_dotenv()
litellm.suppress_debug_info = True

MODELS = ["openrouter/anthropic/claude-haiku-5.5", "openrouter/openai/gpt-5.4-mini"]
DATA = Path("data/browsecomp_n20.csv")
SEARCH_PRICE = 0.007  # $ per Exa search (OpenRouter)
WEB_SEARCH = {"type": "openrouter:web_search",
              "parameters": {"engine": "exa", "max_results": 5, "max_uses": 10}}

SYSTEM_PROMPT = """You are a careful research assistant with a web search tool.
Search the web as many times as you need to find the exact facts the question asks for, and do any calculation yourself.
Rely on primary/official sources and cite the exact URL of the document you used.

End your response with exactly these four lines:
Explanation: <short explanation of how you got the answer>
Exact Answer: <your final answer only>
Sources: <the URL(s) of the documents the answer comes from>
Confidence: <0-100>%"""


def short(model):
    return model.split("/")[-1]


def load_tasks():
    with DATA.open(newline="", encoding="utf-8") as f:
        return [{"task_id": r["Task ID"], "prompt": r["Prompt"], "category": r["Domain"],
                 "workflow": r["Workflow"]} for r in csv.DictReader(f)]


def sample(tasks, n, seed):
    """Stratified by category: shuffle, then take round-robin across categories."""
    if not n or n >= len(tasks):
        return tasks
    rng = random.Random(seed)
    by_cat = {}
    for t in rng.sample(tasks, len(tasks)):
        by_cat.setdefault(t["category"], []).append(t)
    cats = rng.sample(sorted(by_cat), len(by_cat))
    order = [by_cat[c][i] for i in range(max(map(len, by_cat.values())))
             for c in cats if i < len(by_cat[c])]
    return order[:n]


class Log:
    """print() to the screen and to a log file."""
    def __init__(self, path):
        self.f = open(path, "a", encoding="utf-8")

    def __call__(self, *args):
        s = " ".join(str(a) for a in args)
        print(s, flush=True)
        self.f.write(s + "\n"); self.f.flush()


def fetch_prices():
    try:
        with urllib.request.urlopen("https://openrouter.ai/api/v1/models", timeout=30) as r:
            data = json.load(r)["data"]
        return {m["id"]: (float(m["pricing"]["prompt"]), float(m["pricing"]["completion"])) for m in data}
    except Exception as e:
        print("warning: could not fetch prices:", e)
        return {}


def usage_of(resp):
    d = resp.model_dump() if hasattr(resp, "model_dump") else dict(resp)
    u = d.get("usage") or {}
    stu = u.get("server_tool_use_details") or u.get("server_tool_use") or {}
    return (u.get("prompt_tokens") or 0, u.get("completion_tokens") or 0,
            stu.get("web_search_requests") or 0, u.get("cost"))


def citations_of(msg):
    d = msg.model_dump() if hasattr(msg, "model_dump") else dict(msg)
    anns = d.get("annotations") or (d.get("provider_specific_fields") or {}).get("annotations") or []
    urls = [(a.get("url_citation") or {}).get("url") for a in anns if isinstance(a, dict)]
    return list(dict.fromkeys(u for u in urls if u))


class RateLimiter:
    """Space request starts per model: new OpenRouter accounts get 20 requests/min per model."""
    def __init__(self, rpm):
        self.gap, self.next, self.lock = 60 / rpm, {}, asyncio.Lock()

    async def wait(self, model):
        async with self.lock:
            now = time.monotonic()
            start = max(now, self.next.get(model, now))
            self.next[model] = start + self.gap
        await asyncio.sleep(start - now)


LIMITER = None


async def call_with_retries(log, label, **kw):
    for attempt in range(5):
        if LIMITER:
            await LIMITER.wait(kw["model"])
        try:
            return await litellm.acompletion(**kw), None
        except Exception as e:
            err = f"{type(e).__name__}: {str(e)[:300]}"
            log(f"  retry {attempt + 1}/5 {label}: {err[:160]}")
            if attempt < 4:  # rate limits are per minute, so wait longer on 429s
                await asyncio.sleep((20 * (attempt + 1) if "RateLimit" in err else 2 ** attempt) + random.random())
    return None, err


async def run_try(model, task, k, args, prices, sem, log):
    """One agent loop. Search runs server-side, so normally a single call; any
    client-side tool call is unknown and answered with an error."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": task["prompt"]}]
    rec = {"model": model, "task_id": task["task_id"], "try": k, "category": task["category"],
           "status": "ok", "final_answer": "", "citations": [], "turns": 0, "words_per_turn": [],
           "searches": 0, "tool_calls": 0, "tool_calls_failed": 0,
           "input_tokens": 0, "output_tokens": 0, "cost": None, "error": None}
    cost, t0 = 0.0, time.time()
    async with sem:
        for _ in range(args.max_turns):
            resp, err = await call_with_retries(log, f"{short(model)} {task['task_id'][-6:]} #{k}",
                                                model=model, messages=messages, timeout=600,
                                                # via extra_body: litellm mistakes server tools for MCP
                                                extra_body={"tools": [WEB_SEARCH]})
            if resp is None:
                rec.update(status="api_error", error=err)
                break
            rec["turns"] += 1
            tin, tout, srch, billed = usage_of(resp)
            rec["input_tokens"] += tin; rec["output_tokens"] += tout; rec["searches"] += srch
            if billed:  # OpenRouter's billed cost, search included
                cost += billed
            else:
                try:
                    c = litellm.completion_cost(completion_response=resp) or 0.0
                except Exception:
                    c = 0.0
                if not c and model.removeprefix("openrouter/") in prices:
                    pin, pout = prices[model.removeprefix("openrouter/")]
                    c = tin * pin + tout * pout
                cost += c + srch * SEARCH_PRICE
            msg = resp.choices[0].message
            text = msg.content or ""
            rec["words_per_turn"].append(len(text.split()))
            rec["citations"] += [u for u in citations_of(msg) if u not in rec["citations"]]
            calls = msg.tool_calls or []
            messages.append({"role": "assistant", "content": text,
                             **({"tool_calls": [tc.model_dump() for tc in calls]} if calls else {})})
            if not calls:
                rec["final_answer"] = text
                break
            for tc in calls:  # no client-side tools exist in this environment
                rec["tool_calls"] += 1; rec["tool_calls_failed"] += 1
                messages.append({"role": "tool", "tool_call_id": tc.id,
                                 "content": f"Error: unknown tool {tc.function.name}"})
        else:
            rec["status"] = "max_turns"
    if rec["status"] == "ok" and not rec["final_answer"].strip():
        rec["status"] = "empty"
    rec.update(messages=messages, cost=round(cost, 6) if rec["turns"] else None,
               seconds=round(time.time() - t0, 1))
    return rec


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--tries", type=int, default=3)
    ap.add_argument("--concurrency", type=int, default=32)
    ap.add_argument("--max_turns", type=int, default=10)
    ap.add_argument("--rpm", type=float, default=15, help="max requests/min per model")
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()
    global LIMITER
    LIMITER = RateLimiter(args.rpm)
    if args.smoke:
        args.n, args.tries = 5, 1
    out = Path("results_smoke" if args.smoke else "results"); out.mkdir(exist_ok=True)
    log = Log(out / ("smoke_log.txt" if args.smoke else "run_log.txt"))
    raw = out / "raw.jsonl"

    all_tasks = load_tasks()
    tasks = sample(all_tasks, args.n, args.seed)
    log(f"=== run {time.strftime('%Y-%m-%d %H:%M:%S')}  models={MODELS}  tasks={len(tasks)}  tries={args.tries}")
    log("SYSTEM_PROMPT:\n" + SYSTEM_PROMPT)
    log("\nFIRST TASK PROMPT:\n" + tasks[0]["prompt"] + "\n")

    done = set()
    if raw.exists():
        for line in raw.read_text().splitlines():
            r = json.loads(line)
            if r["status"] != "api_error":
                done.add((r["model"], r["task_id"], r["try"]))
    jobs = [(m, t, k) for m in MODELS for t in tasks for k in range(args.tries)
            if (m, t["task_id"], k) not in done]
    log(f"{len(jobs)} tries to run ({len(done)} already saved)")

    prices = fetch_prices()
    sem, results, t0 = asyncio.Semaphore(args.concurrency), [], time.time()
    with raw.open("a", encoding="utf-8") as f:
        for coro in asyncio.as_completed([run_try(m, t, k, args, prices, sem, log) for m, t, k in jobs]):
            rec = await coro
            f.write(json.dumps(rec) + "\n"); f.flush()
            results.append(rec)
            log(f"[{len(results)}/{len(jobs)}] {short(rec['model'])} {rec['task_id'][-6:]} #{rec['try']} "
                f"{rec['status']} {rec['seconds']}s searches={rec['searches']} cost=${rec['cost'] or 0:.4f}")
            if args.smoke:
                log("----- raw response -----\n" + (rec["final_answer"] or rec["error"] or "") +
                    f"\ncitations: {rec['citations']}\n------------------------")
    wall = time.time() - t0
    ok = [r for r in results if r["status"] != "api_error"]
    log(f"\ndone in {wall:.0f}s; total cost ${sum(r['cost'] or 0 for r in results):.3f}")

    if args.smoke and ok:
        n_full = len(all_tasks) * len(MODELS) * 3
        med = statistics.median(r["seconds"] for r in ok)
        waves = max(-(-n_full // args.concurrency), int(n_full / len(MODELS) / args.rpm * 60 / med) + 1)
        log("\n=== SMOKE REPORT ===")
        for m in MODELS:
            rs = [r for r in ok if r["model"] == m]
            if rs:
                log(f"{short(m)}: median {statistics.median(r['seconds'] for r in rs):.0f}s, "
                    f"max {max(r['seconds'] for r in rs):.0f}s, searches/try {statistics.mean(r['searches'] for r in rs):.1f}, "
                    f"cost/try ${statistics.mean(r['cost'] or 0 for r in rs):.4f}")
        log(f"full run = {n_full} tries; est. time = {waves} waves (concurrency {args.concurrency}, {args.rpm:g} rpm/model) x {med:.0f}s median "
            f"= ~{waves * med / 60:.1f} min (slowest try sets the real end)")
        log(f"est. cost = {n_full} x ${statistics.mean(r['cost'] or 0 for r in ok):.4f} "
            f"= ~${n_full * statistics.mean(r['cost'] or 0 for r in ok):.2f}")


if __name__ == "__main__":
    asyncio.run(main())
