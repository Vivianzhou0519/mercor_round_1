# BrowseComp n=20: LLM-as-a-judge eval

Two models (`claude-haiku-5.5`, `gpt-5.4-mini`, via OpenRouter + litellm) answer 20 BrowseComp-style research
tasks with server-side web search, 3 tries each. Two LLM judges grade each try against the task's 2-item rubric:
C1 = cites the correct source, C2 = correct final answer. **Pass = both yes** (0/1, no partial credit).

## Setup
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
echo 'OPENROUTER_API_KEY=sk-or-...' > .env
```

## Run (in order)
```bash
.venv/bin/python grade.py --precheck   # judge sanity: gold answer passes, empty fails, wrong URL fails C1 -> data/dropped.csv
.venv/bin/python run.py                # 20 tasks x 2 models x 3 tries -> results/raw.jsonl (crash-safe, resumable)
.venv/bin/python grade.py              # 2 judges -> results/scored.csv
.venv/bin/python analyze.py            # -> results/summary.md, overview.png, by_category.png, failures.csv
```
Add `--smoke` to `run.py`, `grade.py` and `analyze.py` for a 5 task x 1 try check in `results_smoke/`.

## Files
- `run.py`: sampling loop (asyncio, 15 requests/min/model limiter, retries, JSONL per try)
- `grade.py`: rubric judge (2 judges, temperature 0), precheck
- `analyze.py`: per-task statistics, pass@k / pass^k, paired gap, judge agreement, calibration, charts
