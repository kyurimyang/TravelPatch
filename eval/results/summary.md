### All scenarios

| method | scenarios | no solution | violation rate | violation-free | preservation (violation-free) | RC (violation-free) | ms (all) |
|---|---|---|---|---|---|---|---|
| right_shift | 50 | 0 | 62% | 19 | 93.8% | 1.405 | 0.3 |
| greedy | 50 | 0 | 62% | 19 | 75.4% | 4.524 | 0.2 |
| engine | 50 | 5 | 0% | 45 | 90.2% | 1.686 | 147.6 |
| llm_only | 50 | 21 | 83% | 5 | 78.2% | 4.026 | 2743.1 |
| llm_validated | 50 | 42 | 0% | 8 | 82.9% | 3.368 | 4651.4 |

### Violation rate by event (no solution counted separately)

| method | closure | delay | extend | fatigue | weather |
|---|---|---|---|---|---|
| right_shift | 10/10 | 2/10 | 1/10 | 10/10 | 8/10 |
| greedy | 10/10 | 2/10 | 1/10 | 10/10 | 8/10 |
| engine | 0/10 | 0/9 (+1 none) | 0/9 (+1 none) | 0/10 | 0/7 (+3 none) |
| llm_only | 5/7 (+3 none) | 8/10 | 1/1 (+9 none) | 4/5 (+5 none) | 6/6 (+4 none) |
| llm_validated | 0/4 (+6 none) | 0/2 (+8 none) | 0/1 (+9 none) | 0/1 (+9 none) | 0/0 (+10 none) |

### Same 2 scenarios where all methods are violation-free

| method | preservation | RC | dropped (mean) |
|---|---|---|---|
| right_shift | 88.2% | 2.142 | 1.00 |
| greedy | 55.9% | 9.483 | 4.50 |
| engine | 88.2% | 2.142 | 1.00 |
| llm_only | 73.0% | 4.804 | 1.50 |
| llm_validated | 73.0% | 4.804 | 1.50 |
