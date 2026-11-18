### All scenarios

| method | scenarios | no solution | violation rate | violation-free | preservation (violation-free) | RC (violation-free) | ms (all) |
|---|---|---|---|---|---|---|---|
| right_shift | 50 | 0 | 60% | 20 | 93.9% | 1.468 | 0.5 |
| greedy | 50 | 0 | 60% | 20 | 76.2% | 4.456 | 0.4 |
| engine | 50 | 5 | 0% | 45 | 90.3% | 1.646 | 649.7 |
| llm_only | 50 | 5 | 91% | 4 | 88.2% | 2.450 | 2332.0 |
| llm_validated | 50 | 44 | 0% | 6 | 88.3% | 2.284 | 4110.5 |

### Violation rate by event (no solution counted separately)

| method | closure | delay | extend | fatigue | weather |
|---|---|---|---|---|---|
| right_shift | 10/10 | 1/10 | 1/10 | 10/10 | 8/10 |
| greedy | 10/10 | 1/10 | 1/10 | 10/10 | 8/10 |
| engine | 0/10 | 0/9 (+1 none) | 0/9 (+1 none) | 0/10 | 0/7 (+3 none) |
| llm_only | 4/5 (+5 none) | 9/10 | 8/10 | 10/10 | 10/10 |
| llm_validated | 0/3 (+7 none) | 0/1 (+9 none) | 0/2 (+8 none) | 0/0 (+10 none) | 0/0 (+10 none) |

### Same 3 scenarios where all methods are violation-free

| method | preservation | RC | dropped (mean) |
|---|---|---|---|
| right_shift | 94.1% | 1.266 | 0.33 |
| greedy | 76.5% | 4.766 | 2.00 |
| engine | 94.1% | 1.266 | 0.33 |
| llm_only | 85.2% | 2.888 | 0.33 |
| llm_validated | 85.2% | 2.888 | 0.33 |
