# Frequency FEM Transfer

This report compares the calibrated verifier against an independent 1D Euler-Bernoulli beam FEM frequency model over the paper-grounded frequency tasks.

## Reference-Solution Transfer

- evaluated reference designs: `52`
- FEM vs literature frequency MAPE (%): `750.625`
- FEM vs literature median APE (%): `191.523`
- calibrated verifier vs FEM frequency MAPE (%): `71.009`
- calibrated verifier vs FEM frequency decision consistency: `0.712`

## Audited Reference Subset

- subset count (no defaulted thickness/material placeholders): `18`
- audited FEM vs literature frequency MAPE (%): `261.727`
- audited FEM vs literature median APE (%): `46.097`
- audited calibrated verifier vs FEM frequency MAPE (%): `63.152`
- audited calibrated verifier vs FEM decision consistency: `0.778`

## Local Ranking Transfer

- frequency tasks probed: `52`
- mean Spearman rho: `0.104`
- median Spearman rho: `0.339`

## Notes

- The FEM model here is intentionally independent from the runtime verifier: it uses Euler-Bernoulli beam finite elements rather than the runtime lumped tip-stiffness approximation.
- This is a frequency-only transfer study; it does not yet provide an electromechanical power FEM.
- The aim is benchmark credibility, not full multiphysics replacement.
