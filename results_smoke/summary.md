# BrowseComp n=20: results

Setup: models `openrouter/anthropic/claude-haiku-5.5`, `openrouter/openai/gpt-5.4-mini`; judges `openrouter/google/gemini-3.1-flash-lite`, `openrouter/deepseek/deepseek-v4-flash` (primary = first); web search = OpenRouter `openrouter:web_search` (Exa, max 10 searches); 5 tasks x 1+ tries. Pass = judge says yes to BOTH C1 (source) and C2 (answer). Ranges are 95%; tasks are the data points.

## 1. Pass rate (C1 and C2)

| model            | tasks | pass rate | 95% range (±1.96·SD/√n) | 95% bootstrap |
| ---------------- | ----- | --------- | ----------------------- | ------------- |
| claude-haiku-5.5 | 5     | 20.0%     | 0.0–59.2%               | 0.0–60.0%     |
| gpt-5.4-mini     | 3     | 0.0%      | 0.0–0.0%                | 0.0–0.0%      |

## 2. pass@k and pass^k (unbiased, per task then averaged)

| model            | metric | value | 95% bootstrap |
| ---------------- | ------ | ----- | ------------- |
| claude-haiku-5.5 | pass@1 | 20.0% | 0.0–60.0%     |
| gpt-5.4-mini     | pass@1 | 0.0%  | 0.0–0.0%      |

Leader by metric: pass@1 → claude-haiku-5.5. The ranking is the same across metrics.

## 3. Paired gap (claude-haiku-5.5 − gpt-5.4-mini, same 3 tasks)

| gap       | 95% range (paired) | 95% paired bootstrap | claude-haiku-5.5 won | gpt-5.4-mini won | tied |
| --------- | ------------------ | -------------------- | -------------------- | ---------------- | ---- |
| +33.3 pts | -32.0 to +98.7 pts | +0.0 to +100.0 pts   | 1                    | 0                | 2    |

Verdict: we can't tell them apart yet.

## 4. Where tries fail: source (C1) vs answer (C2)

| model            | C1 source yes | C2 answer yes | both (pass) | tries: right answer, wrong source | tries: right source, wrong answer | gold source in search results | tries: saw gold source but didn't cite it |
| ---------------- | ------------- | ------------- | ----------- | --------------------------------- | --------------------------------- | ----------------------------- | ----------------------------------------- |
| claude-haiku-5.5 | 60.0%         | 20.0%         | 20.0%       | 0                                 | 2                                 | 40.0%                         | 0                                         |
| gpt-5.4-mini     | 33.3%         | 0.0%          | 0.0%        | 0                                 | 1                                 | 66.7%                         | 1                                         |

### Is the cited source real? (deterministic checks, no LLM)

| model            | gold URL string in response | judge C1 agrees with string check | judge yes / string no | judge no / string yes | cited URLs that came from its searches | URLs cited per try |
| ---------------- | --------------------------- | --------------------------------- | --------------------- | --------------------- | -------------------------------------- | ------------------ |
| claude-haiku-5.5 | 40.0%                       | 80.0%                             | 1                     | 0                     | 90.0%                                  | 2.4                |
| gpt-5.4-mini     | 33.3%                       | 100.0%                            | 0                     | 0                     | 100.0%                                 | 1.3                |

C1 is judged from the response text only (its Sources line), not from the search-result list. A cited URL that never appeared in the model's search results was probably made up.

## 5. Judge agreement (gemini-3.1-flash-lite vs deepseek-v4-flash)

| verdict | tries | agreement | Cohen's κ | yes rate gemini-3.1-flash-lite | yes rate deepseek-v4-flash |
| ------- | ----- | --------- | --------- | ------------------------------ | -------------------------- |
| c1      | 8     | 87.5%     | 0.75      | 50.0%                          | 37.5%                      |
| c2      | 8     | 87.5%     | 0.60      | 12.5%                          | 25.0%                      |
| passed  | 8     | 100.0%    | 1.00      | 12.5%                          | 12.5%                      |

Pass rate under each judge: claude-haiku-5.5: 20.0% vs 20.0%; gpt-5.4-mini: 0.0% vs 0.0%. 1 disagreeing tries → judge_disagreements.csv.

## 7. Calibration: stated confidence vs actual pass

| model            | confidence bin | tries | mean confidence | pass rate |
| ---------------- | -------------- | ----- | --------------- | --------- |
| claude-haiku-5.5 | (-0.001, 0.25] | 2     | 10%             | 0%        |
| claude-haiku-5.5 | (0.5, 0.75]    | 3     | 71%             | 33%       |
| claude-haiku-5.5 | Brier score    | 5     |                 | 0.222     |
| gpt-5.4-mini     | (0.75, 1.0]    | 3     | 95%             | 0%        |
| gpt-5.4-mini     | Brier score    | 3     |                 | 0.897     |

## 8. By category (Domain)

| model            | category                       | tasks | pass rate | 95% range | note               |
| ---------------- | ------------------------------ | ----- | --------- | --------- | ------------------ |
| claude-haiku-5.5 | Geography                      | 1     | 0%        | n/a       | small, a lead only |
| claude-haiku-5.5 | Other (Consumer/Retail Trends) | 1     | 100%      | n/a       | small, a lead only |
| claude-haiku-5.5 | Politics                       | 1     | 0%        | n/a       | small, a lead only |
| claude-haiku-5.5 | TV shows & movies              | 1     | 0%        | n/a       | small, a lead only |
| claude-haiku-5.5 | Video Games                    | 1     | 0%        | n/a       | small, a lead only |
| gpt-5.4-mini     | Other (Consumer/Retail Trends) | 1     | 0%        | n/a       | small, a lead only |
| gpt-5.4-mini     | Politics                       | 1     | 0%        | n/a       | small, a lead only |
| gpt-5.4-mini     | Video Games                    | 1     | 0%        | n/a       | small, a lead only |

## 9. Failures

| model            | ok | empty | max_turns | api_error | judged fail |
| ---------------- | -- | ----- | --------- | --------- | ----------- |
| claude-haiku-5.5 | 5  | 0     | 0         | 0         | 4           |
| gpt-5.4-mini     | 3  | 0     | 0         | 2         | 3           |

## 10. Cost and speed

| model            | total cost | cost/try | avg input tok | avg output tok | searches/try | median time | p90 time |
| ---------------- | ---------- | -------- | ------------- | -------------- | ------------ | ----------- | -------- |
| claude-haiku-5.5 | $0.23      | $0.0452  | 88,523        | 3,730          | 6.0          | 30s         | 33s      |
| gpt-5.4-mini     | $0.10      | $0.0325  | 16,798        | 172            | 1.8          | 17s         | 40s      |

Total model cost $0.32 (OpenRouter billed, search included; judges not included). Run wall time: 40s.

## 11. Behavior (median over tasks of per-task medians)

| model            | turns | words/turn | searches | tool-call success     |
| ---------------- | ----- | ---------- | -------- | --------------------- |
| claude-haiku-5.5 | 1     | 281        | 4        | n/a (no client tools) |
| gpt-5.4-mini     | 1     | 49         | 2        | n/a (no client tools) |

Correlation of searches with pass (all tries): -0.28.
