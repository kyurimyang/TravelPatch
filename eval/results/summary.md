### All scenarios

| method | scenarios | no solution | violation rate | violation-free | preservation (violation-free) | RC (violation-free) | ms (all) |
|---|---|---|---|---|---|---|---|
| right_shift | 50 | 0 | 60% | 20 | 93.9% | 1.468 | 0.2 |
| greedy | 50 | 0 | 60% | 20 | 93.9% | 1.468 | 0.1 |
| engine | 50 | 5 | 0% | 45 | 90.2% | 1.673 | 87.3 |

### Violation rate by event (no solution counted separately)

| method | closure | delay | extend | fatigue | weather |
|---|---|---|---|---|---|
| right_shift | 10/10 | 1/10 | 1/10 | 10/10 | 8/10 |
| greedy | 10/10 | 1/10 | 1/10 | 10/10 | 8/10 |
| engine | 0/10 | 0/9 (+1 none) | 0/9 (+1 none) | 0/10 | 0/7 (+3 none) |

### Same 20 scenarios where all methods are violation-free

| method | preservation | RC | dropped (mean) |
|---|---|---|---|
| right_shift | 93.9% | 1.468 | 0.60 |
| greedy | 93.9% | 1.468 | 0.60 |
| engine | 93.7% | 1.399 | 0.60 |
