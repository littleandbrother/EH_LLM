# Verifier v1 Frequency Calibration

This profile calibrates raw verifier resonant frequency predictions using a log-domain ridge regression over paper-grounded literature back-substitution records.

- calibration rows: `52`
- leave-one-out frequency MAPE (%): `10.338`
- leave-one-out median APE (%): `5.325`

Feature groups:
- raw verifier frequency
- excitation / load / geometry scalars
- structure class one-hot terms
- piezo material one-hot terms
