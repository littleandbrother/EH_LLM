# Verifier v1 Power Surrogate

This experiment compares several paper-grounded power surrogate candidates under leave-one-out evaluation.

- literature rows: `52`
- best candidate: `raw_physics_identity`
- runtime enabled: `False`

## Candidate Metrics

- `raw_physics_identity`: MAPE=`199.486%`, median APE=`99.991%`, median |log10(pred/obs)|=`3.860`
- `log_ridge_vload`: MAPE=`62291.545%`, median APE=`98.427%`, median |log10(pred/obs)|=`1.220`
- `log_ridge_power`: MAPE=`62299.099%`, median APE=`98.427%`, median |log10(pred/obs)|=`1.219`
- `global_log_bias`: MAPE=`861056.810%`, median APE=`100.000%`, median |log10(pred/obs)|=`2.105`

## Interpretation

- `raw_physics_identity` uses the current raw verifier load power directly.
- `global_log_bias` applies a single leave-one-out global bias to raw power.
- `log_ridge_power` fits a log-domain ridge regressor over raw outputs, excitation, load, and geometry features.
- `log_ridge_vload` first predicts effective load voltage and then converts it back to power via `V^2 / R`.

If the best candidate still has very high leave-one-out error, the current power literature labels are too heterogeneous to justify a runtime calibration profile.
