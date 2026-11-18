### All scenarios

| method | scenarios | no solution | violation rate | violation-free | preservation (violation-free) | RC (violation-free) | ms (all) |
|---|---|---|---|---|---|---|---|
| right_shift | 50 | 0 | 60% | 20 | 93.9% | 1.468 | 0.4 |
| greedy | 50 | 0 | 60% | 20 | 76.2% | 4.456 | 0.3 |
| engine | 50 | 5 | 0% | 45 | 90.3% | 1.646 | 170.9 |
| llm_only | 50 | 22 | 89% | 3 | 86.4% | 3.268 | 2950.7 |
| llm_validated | 50 | 45 | 0% | 5 | 89.1% | 2.653 | 4054.8 |

### Violation rate by event (no solution counted separately)

| method | closure | delay | extend | fatigue | weather |
|---|---|---|---|---|---|
| right_shift | 10/10 | 1/10 | 1/10 | 10/10 | 8/10 |
| greedy | 10/10 | 1/10 | 1/10 | 10/10 | 8/10 |
| engine | 0/10 | 0/9 (+1 none) | 0/9 (+1 none) | 0/10 | 0/7 (+3 none) |
| llm_only | 3/5 (+5 none) | 9/10 | 1/1 (+9 none) | 6/6 (+4 none) | 6/6 (+4 none) |
| llm_validated | 0/3 (+7 none) | 0/1 (+9 none) | 0/1 (+9 none) | 0/0 (+10 none) | 0/0 (+10 none) |

### Same 1 scenarios where all methods are violation-free

| method | preservation | RC | dropped (mean) |
|---|---|---|---|
| right_shift | 94.1% | 1.300 | 1.00 |
| greedy | 82.3% | 5.483 | 3.00 |
| engine | 94.1% | 1.300 | 1.00 |
| llm_only | 74.3% | 5.675 | 2.00 |
| llm_validated | 74.3% | 5.675 | 2.00 |
