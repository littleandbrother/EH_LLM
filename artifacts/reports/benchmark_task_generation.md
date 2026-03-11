# Benchmark Task Generation

- seeds input: `55`
- total paper-grounded tasks: `162`
- frequency_matching: `55`
- constrained_power_maximization: `55`
- feasibility_repair: `52`

## Split Counts

- train: `87`
- val: `23`
- test-id: `24`
- test-ood: `28`

## Difficulty Audit

- frequency tasks retargeted: `15`
- repair tasks with audited infeasible starts: `52`
- repair tasks dropped for triviality: `0`

## Repair Initial Difficulty

- train: `29` tasks, avg error `6.260%`, range `3.119%`-`51.740%`, profile `3.0%`-`7.5%`, tolerance `2.0%`
- val: `7` tasks, avg error `5.247%`, range `3.699%`-`6.500%`, profile `4.5%`-`9.5%`, tolerance `2.0%`
- test-id: `8` tasks, avg error `5.657%`, range `3.209%`-`7.810%`, profile `6.5%`-`14.0%`, tolerance `1.0%`
- test-ood: `8` tasks, avg error `6.347%`, range `3.197%`-`8.014%`, profile `5.5%`-`11.5%`, tolerance `2.0%`
