# BrowseComp n=20: results

Setup: models `openrouter/anthropic/claude-haiku-5.5`, `openrouter/openai/gpt-5.4-mini`; judges `openrouter/deepseek/deepseek-v4-flash`, `openrouter/google/gemini-3.1-flash-lite` (primary = first); web search = OpenRouter `openrouter:web_search` (Exa, max 10 searches); 20 tasks x 3+ tries. Pass = judge says yes to BOTH C1 (source) and C2 (answer). Ranges are 95%; tasks are the data points.

## Headline: pass rate under each judge

|                                              | Judge 1 (deepseek-v4-flash, primary) | Judge 2 (gemini-3.1-flash-lite, check) | Strict: both pass         | Lenient: either passes    | Adjudicated (my read of disagreements) |
| -------------------------------------------- | ------------------------------------ | -------------------------------------- | ------------------------- | ------------------------- | -------------------------------------- |
| claude-haiku-5.5 pass rate                   | 16.7% [2.1–31.3%]                    | 15.0% [0.4–29.6%]                      | 11.7% [0.0–25.3%]         | 20.0% [4.7–35.3%]         | 18.3% [3.7–32.9%]                      |
| gpt-5.4-mini pass rate                       | 3.3% [0.0–7.8%]                      | 1.7% [0.0–4.9%]                        | 1.7% [0.0–4.9%]           | 3.3% [0.0–7.8%]           | 1.7% [0.0–4.9%]                        |
| Gap claude-haiku-5.5 − gpt-5.4-mini (paired) | +13.3 pts [-1.2 to +27.9]            | +13.3 pts [-1.2 to +27.9]              | +10.0 pts [-4.3 to +24.3] | +16.7 pts [+2.1 to +31.3] | +16.7 pts [+2.1 to +31.3]              |

Strict = a pass only if both judges say pass; lenient = a pass if either does. These bracket the lowest and highest believable score; the truth is probably in between. Adjudicated = the judges' verdict where they agree, my own reading (data/adjudication.csv) where they disagree. Ranges are 95% (±1.96·SD/√n over tasks). All other sections and overview.png use judge 1 only.

| verdict    | tries | agreement | Cohen's κ |
| ---------- | ----- | --------- | --------- |
| C1         | 120   | 100.0%    | 1.00      |
| C2         | 120   | 95.0%     | 0.80      |
| final pass | 120   | 95.0%     | 0.70      |

**Verdict: the conclusion DEPENDS on the judge**: Judge 1 (deepseek-v4-flash, primary): can't tell apart; Judge 2 (gemini-3.1-flash-lite, check): can't tell apart; Strict: both pass: can't tell apart; Lenient: either passes: claude-haiku-5.5 better; Adjudicated (my read of disagreements): claude-haiku-5.5 better.

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

## 5. Judge agreement (deepseek-v4-flash = judge 1 vs gemini-3.1-flash-lite = judge 2, 120 graded answers)

**C1 (source)**

|               | Judge 2: pass | Judge 2: fail |
| ------------- | ------------- | ------------- |
| Judge 1: pass | 59            | 0             |
| Judge 1: fail | 0             | 61            |

Agreement 100.0%; chance agreement = 0.49×0.49 + 0.51×0.51 = 0.50; κ = (1.00 − 0.50) ÷ (1 − 0.50) = **1.00** (strong).

**C2 (answer)**

|               | Judge 2: pass | Judge 2: fail |
| ------------- | ------------- | ------------- |
| Judge 1: pass | 15            | 4             |
| Judge 1: fail | 2             | 99            |

Agreement 95.0%; chance agreement = 0.16×0.14 + 0.84×0.86 = 0.74; κ = (0.95 − 0.74) ÷ (1 − 0.74) = **0.80** (strong).

**Final pass**

|               | Judge 2: pass | Judge 2: fail |
| ------------- | ------------- | ------------- |
| Judge 1: pass | 8             | 4             |
| Judge 1: fail | 2             | 106           |

Agreement 95.0%; chance agreement = 0.10×0.08 + 0.90×0.92 = 0.83; κ = (0.95 − 0.83) ÷ (1 − 0.83) = **0.70** (good).

**Does the headline change with the judge?** Winner under judge 1: claude-haiku-5.5; under judge 2: claude-haiku-5.5. The winner does not flip.

### Who was right? (I read all 6 disagreements)

| model            | task   | try | judge 1 | judge 2 | correct | right judge | why they disagreed                                                                                  |
| ---------------- | ------ | --- | ------- | ------- | ------- | ----------- | --------------------------------------------------------------------------------------------------- |
| claude-haiku-5.5 | bf3a09 | 0   | 1       | 0       | 1       | judge 1     | judge 2 graded the reasoning (inferred mapping) instead of the stated answer, which matches exactly |
| claude-haiku-5.5 | a7bf9d | 0   | 0       | 1       | 1       | judge 2     | judge 1 counted a caveat as a hedge; the Exact Answer line commits to $150,600                      |
| claude-haiku-5.5 | 3e4ab5 | 2   | 0       | 1       | 1       | judge 2     | judge 1 counted a caveat as a hedge; the Exact Answer line commits to 588,000                       |
| claude-haiku-5.5 | d6a140 | 1   | 1       | 0       | 1       | judge 1     | answer states the exact value '20.1% (20.09%)'                                                      |
| claude-haiku-5.5 | d6a140 | 2   | 1       | 0       | 0       | judge 2     | task asks for the exact share 20.09%; the answer gives rounded 20.1%                                |
| gpt-5.4-mini     | d6a140 | 1   | 1       | 0       | 0       | judge 2     | task asks for the exact share 20.09%; the answer gives rounded 20.1%                                |

Tally: judge 2 right 4×, judge 1 right 2×. Judge 1 (deepseek-v4-flash) errors: too strict on caveats (counted as hedges), too lenient on rounding (20.1% for an 'exact' 20.09%). Judge 2 (gemini-3.1-flash-lite) error: graded the reasoning instead of the stated answer.

### Bias check: is agreement lower for one model?

| model            | answers | C2 agreement | C2 κ | pass agreement | pass κ | disagreements |
| ---------------- | ------- | ------------ | ---- | -------------- | ------ | ------------- |
| claude-haiku-5.5 | 60      | 91.7%        | 0.75 | 91.7%          | 0.69   | 5             |
| gpt-5.4-mini     | 60      | 98.3%        | 0.90 | 98.3%          | 0.66   | 1             |

κ is unstable when almost every answer fails (few passes to agree on); read the disagreement counts alongside it.

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

## 8a. Source vs answer: C1 × C2 per model (tries)

**claude-haiku-5.5**

|              | Right answer                               | Wrong answer                                         |
| ------------ | ------------------------------------------ | ---------------------------------------------------- |
| Right source | 10 full pass                               | 20 found the document, then misread or miscalculated |
| Wrong source | 3 right answer, wrong source → still fails | 27 lost                                              |

**gpt-5.4-mini**

|              | Right answer                               | Wrong answer                                         |
| ------------ | ------------------------------------------ | ---------------------------------------------------- |
| Right source | 2 full pass                                | 27 found the document, then misread or miscalculated |
| Wrong source | 4 right answer, wrong source → still fails | 27 lost                                              |

Right answer but wrong source: 7 tries. Is the rubric too strict? These fail only because they cited a different page than the rubric's URL: claude-haiku-5.5 93cd4a#0; claude-haiku-5.5 93cd4a#1; claude-haiku-5.5 93cd4a#2; gpt-5.4-mini 93cd4a#0; gpt-5.4-mini 93cd4a#1; gpt-5.4-mini 93cd4a#2; gpt-5.4-mini 07d69d#2.

## 8b. Failure type (tries, judge 1; wrong answers tagged by an LLM, see failure_tags.jsonl)

| model            | full pass | right answer, wrong source | not_found | wrong_value | wrong_math | incomplete |
| ---------------- | --------- | -------------------------- | --------- | ----------- | ---------- | ---------- |
| claude-haiku-5.5 | 10 (17%)  | 3 (5%)                     | 19 (32%)  | 21 (35%)    | 1 (2%)     | 6 (10%)    |
| gpt-5.4-mini     | 2 (3%)    | 4 (7%)                     | 14 (23%)  | 34 (57%)    | 4 (7%)     | 2 (3%)     |

not_found = never located the right document; wrong_value = found it, pulled the wrong number/fact; wrong_math = right inputs, wrong calculation; incomplete = refused, hedged or missing parts.

## 8c. Search behavior: passes vs fails

| model            | outcome | tries | mean searches | median | max | hit the 10-search cap |
| ---------------- | ------- | ----- | ------------- | ------ | --- | --------------------- |
| claude-haiku-5.5 | pass    | 10    | 3.4           | 3      | 8   | 0%                    |
| claude-haiku-5.5 | fail    | 50    | 4.9           | 3      | 12  | 18%                   |
| gpt-5.4-mini     | pass    | 2     | 1.0           | 1      | 1   | 0%                    |
| gpt-5.4-mini     | fail    | 58    | 2.4           | 2      | 7   | 0%                    |

Mean searches by failure type: claude-haiku-5.5: incomplete 7.2, not_found 6.9, wrong_math 1.0, wrong_value 2.9; gpt-5.4-mini: incomplete 2.0, not_found 3.2, wrong_math 2.8, wrong_value 2.2.

## 8d. Tasks no one solved (0 of 6 tries across both models)

| task   | category                                              | expected                                 | any right answer | any right source | gold doc in search results | likely reason                                                                                     |
| ------ | ----------------------------------------------------- | ---------------------------------------- | ---------------- | ---------------- | -------------------------- | ------------------------------------------------------------------------------------------------- |
| 1c54c6 | Sports                                                | 78.6658                                  | no               | yes              | yes                        | document was found but no try got the answer: hard extraction/maths, or check the expected answer |
| 2ce94d | History                                               | 7 May 1997 (Tadić Trial Judgement) and 2 | no               | no               | no                         | gold document never appeared in any search: too hard to find (or URL moved)                       |
| 746cc2 | Science & technology                                  | 5.4125%                                  | no               | yes              | yes                        | document was found but no try got the answer: hard extraction/maths, or check the expected answer |
| d5c83c | TV shows & movies                                     | 25                                       | no               | no               | no                         | gold document never appeared in any search: too hard to find (or URL moved)                       |
| 8dd543 | Music                                                 | 14th Street and Constitution Avenue, NW  | no               | no               | no                         | gold document never appeared in any search: too hard to find (or URL moved)                       |
| 03a7bc | Art                                                   | The problem of carrying the weight of a  | no               | no               | no                         | gold document never appeared in any search: too hard to find (or URL moved)                       |
| 9873e3 | Geography                                             | 20.77 LNM; 30° 29' 22.57" N, 91° 14' 51. | no               | yes              | no                         | document was found but no try got the answer: hard extraction/maths, or check the expected answer |
| ae683b | Science & technology                                  | 80001                                    | no               | no               | no                         | gold document never appeared in any search: too hard to find (or URL moved)                       |
| 368fd8 | Sports                                                | Buprenorphine, Pseudoephedrine, and Spir | no               | yes              | yes                        | document was found but no try got the answer: hard extraction/maths, or check the expected answer |
| cca9ba | Other (Business/Regulatory)                           | 149                                      | no               | yes              | yes                        | document was found but no try got the answer: hard extraction/maths, or check the expected answer |
| 93cd4a | Politics                                              | 16                                       | yes              | no               | no                         | someone got the answer but never with the right source: rubric source may be too strict           |
| 07d69d | Politics                                              | 5,000                                    | yes              | no               | no                         | someone got the answer but never with the right source: rubric source may be too strict           |
| 573859 | Other (Environmental/Natural Resource Administration) | EPA-454/R-23-009                         | no               | yes              | yes                        | document was found but no try got the answer: hard extraction/maths, or check the expected answer |
| 6146f2 | Geography                                             | 1:24000, 1:12000, and 1:24000            | no               | no               | no                         | gold document never appeared in any search: too hard to find (or URL moved)                       |

14 of 20 tasks unsolved. All tasks passed the judge precheck (gold answer passes, empty fails), so these are not broken graders; whether the expected answer itself is right needs a human check.

## 8e. Cost per correct answer

| model            | total cost | passing tries | cost per correct answer |
| ---------------- | ---------- | ------------- | ----------------------- |
| claude-haiku-5.5 | $2.11      | 10            | $0.21                   |
| gpt-5.4-mini     | $1.47      | 2             | $0.74                   |

## 8f. Sample size

Observed paired gap +13.3 pts with per-task SD 33.2 pts. To detect a gap this size (95% confidence, 80% power) we'd need about **49 tasks**; we have 20. Formula: n = ((1.96 + 0.84) × SD / gap)².

Domains are skipped: 12 domains with 1–2 tasks each is too small to show anything.

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
