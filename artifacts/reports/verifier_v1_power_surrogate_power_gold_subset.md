# Verifier v1 Power Surrogate

This experiment compares several paper-grounded power surrogate candidates under leave-one-out evaluation.

- literature rows: `18`
- papers filter: `power_gold_subset_papers.json`
- best candidate: `raw_physics_identity`
- runtime enabled: `False`

## Candidate Metrics

- `raw_physics_identity`: MAPE=`98.939%`, median APE=`99.999%`, median |log10(pred/obs)|=`5.369`
- `global_log_bias`: MAPE=`4511574.213%`, median APE=`165.044%`, median |log10(pred/obs)|=`2.106`
- `log_ridge_vload`: MAPE=`11093313958.617%`, median APE=`100.000%`, median |log10(pred/obs)|=`2.701`
- `log_ridge_power`: MAPE=`11376985300.558%`, median APE=`100.000%`, median |log10(pred/obs)|=`2.708`

## Interpretation

- `raw_physics_identity` uses the current raw verifier load power directly.
- `global_log_bias` applies a single leave-one-out global bias to raw power.
- `log_ridge_power` fits a log-domain ridge regressor over raw outputs, excitation, load, and geometry features.
- `log_ridge_vload` first predicts effective load voltage and then converts it back to power via `V^2 / R`.

If the best candidate still has very high leave-one-out error, the current power literature labels are too heterogeneous to justify a runtime calibration profile.
