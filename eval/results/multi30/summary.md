### All scenarios

| method | scenarios | no solution | violation rate | violation-free | preservation (violation-free) | RC (violation-free) | ms (all) |
|---|---|---|---|---|---|---|---|
| right_shift | 30 | 0 | 87% | 4 | 97.6% | 1.157 | 0.3 |
| greedy | 30 | 0 | 80% | 6 | 78.8% | 4.144 | 0.2 |
| engine | 30 | 2 | 0% | 28 | 90.5% | 2.568 | 134.4 |

### Violation rate by event (no solution counted separately)

| method | bookingwait | delayrain | rainclosure |
|---|---|---|---|
| right_shift | 10/10 | 6/10 | 10/10 |
| greedy | 10/10 | 4/10 | 10/10 |
| engine | 0/10 | 0/9 (+1 none) | 0/9 (+1 none) |

### Same 4 scenarios where all methods are violation-free

| method | preservation | RC | dropped (mean) |
|---|---|---|---|
| right_shift | 97.6% | 1.157 | 0.25 |
| greedy | 97.6% | 1.157 | 0.25 |
| engine | 100.0% | 0.764 | 0.00 |
