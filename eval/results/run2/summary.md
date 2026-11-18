### All scenarios

| method | scenarios | no solution | violation rate | violation-free | preservation (violation-free) | RC (violation-free) | ms (all) |
|---|---|---|---|---|---|---|---|
| right_shift | 50 | 0 | 60% | 20 | 93.9% | 1.468 | 0.4 |
| greedy | 50 | 0 | 60% | 20 | 76.2% | 4.456 | 0.3 |
| engine | 50 | 5 | 0% | 45 | 90.3% | 1.646 | 184.9 |
| llm_only | 50 | 24 | 96% | 1 | 93.6% | 1.391 | 3123.4 |
| llm_validated | 50 | 46 | 0% | 4 | 88.3% | 2.829 | 29516.5 |

### Violation rate by event (no solution counted separately)

| method | closure | delay | extend | fatigue | weather |
|---|---|---|---|---|---|
| right_shift | 10/10 | 1/10 | 1/10 | 10/10 | 8/10 |
| greedy | 10/10 | 1/10 | 1/10 | 10/10 | 8/10 |
| engine | 0/10 | 0/9 (+1 none) | 0/9 (+1 none) | 0/10 | 0/7 (+3 none) |
| llm_only | 4/5 (+5 none) | 10/10 | 1/1 (+9 none) | 4/4 (+6 none) | 6/6 (+4 none) |
| llm_validated | 0/1 (+9 none) | 0/0 (+10 none) | 0/2 (+8 none) | 0/0 (+10 none) | 0/1 (+9 none) |

### Same 0 scenarios where all methods are violation-free

| method | preservation | RC | dropped (mean) |
|---|---|---|---|
