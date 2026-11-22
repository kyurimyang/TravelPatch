### All scenarios

| method | scenarios | no solution | violation rate | violation-free | preservation (violation-free) | RC (violation-free) | ms (all) |
|---|---|---|---|---|---|---|---|
| right_shift | 50 | 0 | 62% | 19 | 93.8% | 1.405 | 0.4 |
| greedy | 50 | 0 | 62% | 19 | 75.4% | 4.524 | 0.3 |
| engine | 50 | 5 | 0% | 45 | 90.2% | 1.686 | 168.2 |
| llm_only | 50 | 20 | 80% | 6 | 74.9% | 4.984 | 5784.5 |
| llm_validated | 50 | 42 | 0% | 8 | 77.3% | 4.470 | 4050.5 |

### Violation rate by event (no solution counted separately)

| method | closure | delay | extend | fatigue | weather |
|---|---|---|---|---|---|
| right_shift | 10/10 | 2/10 | 1/10 | 10/10 | 8/10 |
| greedy | 10/10 | 2/10 | 1/10 | 10/10 | 8/10 |
| engine | 0/10 | 0/9 (+1 none) | 0/9 (+1 none) | 0/10 | 0/7 (+3 none) |
| llm_only | 2/6 (+4 none) | 9/10 | 1/1 (+9 none) | 5/6 (+4 none) | 7/7 (+3 none) |
| llm_validated | 0/5 (+5 none) | 0/2 (+8 none) | 0/0 (+10 none) | 0/1 (+9 none) | 0/0 (+10 none) |

### Same 1 scenarios where all methods are violation-free

| method | preservation | RC | dropped (mean) |
|---|---|---|---|
| right_shift | 94.1% | 1.300 | 1.00 |
| greedy | 82.3% | 5.483 | 3.00 |
| engine | 94.1% | 1.300 | 1.00 |
| llm_only | 62.5% | 6.833 | 2.00 |
| llm_validated | 62.5% | 6.833 | 2.00 |
