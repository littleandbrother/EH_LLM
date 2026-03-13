# AutoRA POC Assessment

## Scope

This POC tests whether AutoRA can serve as a light orchestration layer around the
existing VEHBench verifier, without replacing the current benchmark runtime.

Implemented pieces:

- `VehBenchState` built on AutoRA `StandardState`
- AutoRA random experimentalist for initial proposal batches
- VEHBench verifier wrapped as an AutoRA-style experiment runner
- AutoRA theorist via `estimator_on_state(RandomForestRegressor)`
- Surrogate-guided proposal loop for synthetic `frequency_matching`

## What Was Run

- Single-task smoke:
  - `pg_seed::10_1016_j_apenergy_2020_115518::syn::0000::frequency_matching`
- Small OOD batch:
  - first `5` synthetic `test-ood` frequency tasks from
    `data_registry/benchmark/synthetic_pilot_v3_tasks_frequency_matching.jsonl`

## Observed Result

- Single-task smoke:
  - feasible solution found in `9` queries
  - best frequency error: `0.328403%`
  - best cycle: `guided_1`
- Batch result:
  - task count: `5`
  - feasible rate: `1.0`
  - mean best frequency error: `0.391699%`

## Assessment

This is worth continuing, but only in a narrow role.

What worked well:

- AutoRA `State + on_state + experimentalist + theorist` was enough to run a
  genuine closed loop on top of the existing VEHBench verifier.
- The integration cost was low. The adapter layer is small and does not require
  changes to the main VEHBench runtime.
- The abstraction is a reasonable fit for future active-design or surrogate-loop
  experiments.

What did not change:

- AutoRA did not replace the need for the existing VEHBench benchmark runtime,
  split logic, budget accounting, or leaderboard reporting.
- This POC only validates `frequency_matching`. It does not yet demonstrate that
  AutoRA is useful for `repair`, `power`, or full benchmark evaluation.

## Recommendation

Keep AutoRA as an optional research branch for:

- active discovery loops
- surrogate-guided candidate selection
- theorist/experimentalist comparisons

Do not migrate the main benchmark runtime onto AutoRA at this stage.
