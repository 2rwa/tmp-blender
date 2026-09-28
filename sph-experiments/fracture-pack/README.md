# True-fracture SPH exploratory pack

This pack tests **actual brittle fracture** using the 2026 open-source
[SoliDualSPHysics](https://github.com/naqibr/SoliDualSPHysics) phase-field fracture solver.

It is intentionally separate from the earlier SPlisHSPlasH elastic experiments:
those deform and rebound but do not break topology. SoliDualSPHysics evolves a
phase-field fracture model and includes validated fracture benchmarks.

First probe: five Kalthoff-Winkler-inspired CPU runs on GitHub Actions.

- `kw-baseline`: upstream-like Gc and impact velocity
- `kw-brittle`: lower Gc
- `kw-tough`: higher Gc
- `kw-high-impact`: faster impact
- `kw-extreme-impact`: aggressive impact

These are **exploratory parameter sweeps, not benchmark validation reproductions**.
The workflow uses the upstream prebuilt Linux binaries in CPU mode, converts
results with upstream DSPartVTK, then creates a lightweight x-z particle
projection video and records any fracture/damage-like VTK scalar fields.

References:
- Rahimi & Moutsanidis, *SoliDualSPHysics: An extension of DualSPHysics for solid mechanics with hyperelasticity, plasticity, and fracture*, Computer Physics Communications 327 (2026) 110257.
- Upstream example: `SolidExamples/6_Kalthoff_Winkler_Experiment`.
