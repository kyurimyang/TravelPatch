### All scenarios

| method | scenarios | no solution | violation rate | violation-free | preservation (violation-free) | RC (violation-free) | ms (all) |
|---|---|---|---|---|---|---|---|
| right_shift | 50 | 0 | 62% | 19 | 93.8% | 1.405 | 0.2 |
| greedy | 50 | 0 | 62% | 19 | 75.4% | 4.524 | 0.2 |
| engine | 50 | 5 | 0% | 45 | 90.2% | 1.686 | 114.6 |
| llm_only | 50 | 22 | 96% | 1 | 97.4% | 0.819 | 2596.5 |
| llm_validated | 50 | 49 | 0% | 1 | 97.4% | 0.819 | 3541.0 |

### Violation rate by event (no solution counted separately)

| method | closure | delay | extend | fatigue | weather |
|---|---|---|---|---|---|
| right_shift | 10/10 | 2/10 | 1/10 | 10/10 | 8/10 |
| greedy | 10/10 | 2/10 | 1/10 | 10/10 | 8/10 |
| engine | 0/10 | 0/9 (+1 none) | 0/9 (+1 none) | 0/10 | 0/7 (+3 none) |
| llm_only | 5/6 (+4 none) | 10/10 | 1/1 (+9 none) | 3/3 (+7 none) | 8/8 (+2 none) |
| llm_validated | 0/1 (+9 none) | 0/0 (+10 none) | 0/0 (+10 none) | 0/0 (+10 none) | 0/0 (+10 none) |

### Same 0 scenarios where all methods are violation-free

| method | preservation | RC | dropped (mean) |
|---|---|---|---|
