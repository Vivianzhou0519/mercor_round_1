# BrowseComp n=20: results

Setup: models `openrouter/anthropic/claude-haiku-5.5`, `openrouter/openai/gpt-5.4-mini`; judges `openrouter/deepseek/deepseek-v4-flash`, `openrouter/google/gemini-3.1-flash-lite` (primary = first); web search = OpenRouter `openrouter:web_search` (Exa, max 10 searches); 20 tasks x 3+ tries. Pass = judge says yes to BOTH C1 (source) and C2 (answer). Ranges are 95%; tasks are the data points.

## Headline: pass rate under each judge

|                                              | Judge 1 (deepseek-v4-flash, primary) | Judge 2 (gemini-3.1-flash-lite, check) | Strict: both pass         | Lenient: either passes    |
| -------------------------------------------- | ------------------------------------ | -------------------------------------- | ------------------------- | ------------------------- |
| claude-haiku-5.5 pass rate                   | 16.7% [2.1–31.3%]                    | 15.0% [0.4–29.6%]                      | 11.7% [0.0–25.3%]         | 20.0% [4.7–35.3%]         |
| gpt-5.4-mini pass rate                       | 3.3% [0.0–7.8%]                      | 1.7% [0.0–4.9%]                        | 1.7% [0.0–4.9%]           | 3.3% [0.0–7.8%]           |
| Gap claude-haiku-5.5 − gpt-5.4-mini (paired) | +13.3 pts [-1.2 to +27.9]            | +13.3 pts [-1.2 to +27.9]              | +10.0 pts [-4.3 to +24.3] | +16.7 pts [+2.1 to +31.3] |

Strict = a pass only if both judges say pass; lenient = a pass if either does. These bracket the lowest and highest believable score; the truth is probably in between. Ranges are 95% (±1.96·SD/√n over tasks).

| verdict    | tries | agreement | Cohen's κ |
| ---------- | ----- | --------- | --------- |
| C1         | 120   | 100.0%    | 1.00      |
| C2         | 120   | 95.0%     | 0.80      |
| final pass | 120   | 95.0%     | 0.70      |

**Verdict: the conclusion DEPENDS on the judge**: Judge 1 (deepseek-v4-flash, primary): can't tell apart; Judge 2 (gemini-3.1-flash-lite, check): can't tell apart; Strict: both pass: can't tell apart; Lenient: either passes: claude-haiku-5.5 better.

## 1. Pass rate (C1 and C2)

| model            | tasks | pass rate | 95% range (±1.96·SD/√n) | 95% bootstrap |
| ---------------- | ----- | --------- | ----------------------- | ------------- |
| claude-haiku-5.5 | 20    | 16.7%     | 2.1–31.3%               | 3.3–31.7%     |
| gpt-5.4-mini     | 20    | 3.3%      | 0.0–7.8%                | 0.0–8.3%      |

## 2. pass@k and pass^k (unbiased, per task then averaged)

| model            | metric | value | 95% bootstrap |
| ---------------- | ------ | ----- | ------------- |
| claude-haiku-5.5 | pass@1 | 16.7% | 3.3–31.7%     |
| claude-haiku-5.5 | pass@3 | 25.0% | 10.0–45.0%    |
| claude-haiku-5.5 | pass^3 | 10.0% | 0.0–25.0%     |
| gpt-5.4-mini     | pass@1 | 3.3%  | 0.0–8.3%      |
| gpt-5.4-mini     | pass@3 | 10.0% | 0.0–25.0%     |
| gpt-5.4-mini     | pass^3 | 0.0%  | 0.0–0.0%      |

Leader by metric: pass@1 → claude-haiku-5.5, pass@3 → claude-haiku-5.5, pass^3 → claude-haiku-5.5. The ranking is the same across metrics.

## 3. Paired gap (claude-haiku-5.5 − gpt-5.4-mini, same 20 tasks)

| gap       | 95% range (paired) | 95% paired bootstrap | claude-haiku-5.5 won | gpt-5.4-mini won | tied |
| --------- | ------------------ | -------------------- | -------------------- | ---------------- | ---- |
| +13.3 pts | -1.2 to +27.9 pts  | +0.0 to +28.3 pts    | 5                    | 1                | 14   |

Verdict: we can't tell them apart yet.

## 4. Where tries fail: source (C1) vs answer (C2)

| model            | C1 source yes | C2 answer yes | both (pass) | tries: right answer, wrong source | tries: right source, wrong answer | gold source in search results | tries: saw gold source but didn't cite it |
| ---------------- | ------------- | ------------- | ----------- | --------------------------------- | --------------------------------- | ----------------------------- | ----------------------------------------- |
| claude-haiku-5.5 | 50.0%         | 21.7%         | 16.7%       | 3                                 | 20                                | 50.0%                         | 3                                         |
| gpt-5.4-mini     | 48.3%         | 10.0%         | 3.3%        | 4                                 | 27                                | 53.3%                         | 5                                         |

### Is the cited source real? (deterministic checks, no LLM)

| model            | gold URL string in response | judge C1 agrees with string check | judge yes / string no | judge no / string yes | cited URLs that came from its searches | URLs cited per try |
| ---------------- | --------------------------- | --------------------------------- | --------------------- | --------------------- | -------------------------------------- | ------------------ |
| claude-haiku-5.5 | 50.0%                       | 100.0%                            | 0                     | 0                     | 97.9%                                  | 2.8                |
| gpt-5.4-mini     | 48.3%                       | 100.0%                            | 0                     | 0                     | 96.7%                                  | 1.6                |

C1 is judged from the response text only (its Sources line), not from the search-result list. A cited URL that never appeared in the model's search results was probably made up.

## 5. Judge agreement (deepseek-v4-flash vs gemini-3.1-flash-lite)

| verdict | tries | agreement | Cohen's κ | yes rate deepseek-v4-flash | yes rate gemini-3.1-flash-lite |
| ------- | ----- | --------- | --------- | -------------------------- | ------------------------------ |
| c1      | 120   | 100.0%    | 1.00      | 49.2%                      | 49.2%                          |
| c2      | 120   | 95.0%     | 0.80      | 15.8%                      | 14.2%                          |
| passed  | 120   | 95.0%     | 0.70      | 10.0%                      | 8.3%                           |

Pass rate under each judge: claude-haiku-5.5: 16.7% vs 15.0%; gpt-5.4-mini: 3.3% vs 1.7%. 6 disagreeing tries → judge_disagreements.csv.

## 6. Run-to-run variance

| model            | mean per-task SD of tries | flaky tasks (some pass, some fail) | never pass | always pass |
| ---------------- | ------------------------- | ---------------------------------- | ---------- | ----------- |
| claude-haiku-5.5 | 0.09                      | 3                                  | 15         | 2           |
| gpt-5.4-mini     | 0.06                      | 2                                  | 18         | 0           |

## 7. Calibration: stated confidence vs actual pass

| model            | confidence bin | tries | mean confidence | pass rate |
| ---------------- | -------------- | ----- | --------------- | --------- |
| claude-haiku-5.5 | (-0.001, 0.25] | 12    | 16%             | 0%        |
| claude-haiku-5.5 | (0.25, 0.5]    | 2     | 45%             | 0%        |
| claude-haiku-5.5 | (0.5, 0.75]    | 14    | 62%             | 43%       |
| claude-haiku-5.5 | (0.75, 1.0]    | 32    | 85%             | 12%       |
| claude-haiku-5.5 | Brier score    | 60    |                 | 0.412     |
| gpt-5.4-mini     | (-0.001, 0.25] | 2     | 20%             | 0%        |
| gpt-5.4-mini     | (0.25, 0.5]    | 1     | 34%             | 0%        |
| gpt-5.4-mini     | (0.5, 0.75]    | 1     | 52%             | 0%        |
| gpt-5.4-mini     | (0.75, 1.0]    | 56    | 95%             | 4%        |
| gpt-5.4-mini     | Brier score    | 60    |                 | 0.825     |

## 8. By category (Domain)

| model            | category                                              | tasks | pass rate | 95% range | note               |
| ---------------- | ----------------------------------------------------- | ----- | --------- | --------- | ------------------ |
| claude-haiku-5.5 | Art                                                   | 2     | 17%       | 0–49%     | small, a lead only |
| claude-haiku-5.5 | Geography                                             | 2     | 0%        | 0–0%      | small, a lead only |
| claude-haiku-5.5 | History                                               | 2     | 50%       | 0–100%    | small, a lead only |
| claude-haiku-5.5 | Music                                                 | 1     | 0%        | n/a       | small, a lead only |
| claude-haiku-5.5 | Other (Business/Regulatory)                           | 2     | 0%        | 0–0%      | small, a lead only |
| claude-haiku-5.5 | Other (Consumer/Retail Trends)                        | 1     | 100%      | n/a       | small, a lead only |
| claude-haiku-5.5 | Other (Environmental/Natural Resource Administration) | 1     | 0%        | n/a       | small, a lead only |
| claude-haiku-5.5 | Politics                                              | 2     | 0%        | 0–0%      | small, a lead only |
| claude-haiku-5.5 | Science & technology                                  | 2     | 0%        | 0–0%      | small, a lead only |
| claude-haiku-5.5 | Sports                                                | 2     | 0%        | 0–0%      | small, a lead only |
| claude-haiku-5.5 | TV shows & movies                                     | 2     | 33%       | 0–99%     | small, a lead only |
| claude-haiku-5.5 | Video Games                                           | 1     | 33%       | n/a       | small, a lead only |
| gpt-5.4-mini     | Art                                                   | 2     | 0%        | 0–0%      | small, a lead only |
| gpt-5.4-mini     | Geography                                             | 2     | 0%        | 0–0%      | small, a lead only |
| gpt-5.4-mini     | History                                               | 2     | 0%        | 0–0%      | small, a lead only |
| gpt-5.4-mini     | Music                                                 | 1     | 0%        | n/a       | small, a lead only |
| gpt-5.4-mini     | Other (Business/Regulatory)                           | 2     | 17%       | 0–49%     | small, a lead only |
| gpt-5.4-mini     | Other (Consumer/Retail Trends)                        | 1     | 0%        | n/a       | small, a lead only |
| gpt-5.4-mini     | Other (Environmental/Natural Resource Administration) | 1     | 0%        | n/a       | small, a lead only |
| gpt-5.4-mini     | Politics                                              | 2     | 0%        | 0–0%      | small, a lead only |
| gpt-5.4-mini     | Science & technology                                  | 2     | 0%        | 0–0%      | small, a lead only |
| gpt-5.4-mini     | Sports                                                | 2     | 0%        | 0–0%      | small, a lead only |
| gpt-5.4-mini     | TV shows & movies                                     | 2     | 17%       | 0–49%     | small, a lead only |
| gpt-5.4-mini     | Video Games                                           | 1     | 0%        | n/a       | small, a lead only |

## 9. Failures

| model            | ok | empty | max_turns | api_error | judged fail |
| ---------------- | -- | ----- | --------- | --------- | ----------- |
| claude-haiku-5.5 | 60 | 0     | 0         | 0         | 50          |
| gpt-5.4-mini     | 60 | 0     | 0         | 0         | 58          |

## 10. Cost and speed

| model            | total cost | cost/try | avg input tok | avg output tok | searches/try | median time | p90 time |
| ---------------- | ---------- | -------- | ------------- | -------------- | ------------ | ----------- | -------- |
| claude-haiku-5.5 | $2.11      | $0.0351  | 56,405        | 2,453          | 4.6          | 135s        | 232s     |
| gpt-5.4-mini     | $1.47      | $0.0245  | 14,829        | 266            | 2.3          | 306s        | 607s     |

Total model cost $3.58 (OpenRouter billed, search included; judges not included). Run wall time: 716 + 21s.

## 11. Behavior (median over tasks of per-task medians)

| model            | turns | words/turn | searches | tool-call success     |
| ---------------- | ----- | ---------- | -------- | --------------------- |
| claude-haiku-5.5 | 1     | 238        | 3        | n/a (no client tools) |
| gpt-5.4-mini     | 1     | 71         | 2        | n/a (no client tools) |

Correlation of searches with pass (all tries): -0.06.
