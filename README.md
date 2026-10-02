# REHASH

[![lint](https://github.com/nkua-seismolab/REHASH/actions/workflows/lint.yml/badge.svg)](https://github.com/nkua-seismolab/REHASH/actions/workflows/lint.yml)
[![tests](https://github.com/nkua-seismolab/REHASH/actions/workflows/tests.yml/badge.svg)](https://github.com/nkua-seismolab/REHASH/actions/workflows/tests.yml)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)

Near real-time focal mechanisms with SKHASH for SeisComP.

REHASH is part of a four-application workflow for automatic weak-event source characterization:

[REPOL](https://github.com/nkua-seismolab/REPOL) / [RESS](https://github.com/nkua-seismolab/RESS) -> **[REHASH](https://github.com/nkua-seismolab/REHASH)** / [REBayFM](https://github.com/nkua-seismolab/REBayFM)

## How it works

REHASH connects to the SeisComP messaging system and listens for new events.
After the configured wait time (allowing upstream polarity and S/P
measurements to finish) it:

1. Collects P first-motion polarities from the picks and S/P amplitude
   ratios from the [REPOL](https://github.com/nkua-seismolab/REPOL) JSON
   comments.
2. Writes the input files for [SKHASH](https://code.usgs.gov/esc/SKHASH)
   and runs the grid search, including the compiled Fortran routines.
3. Sends the preferred mechanism back to SeisComP as a `FocalMechanism`
   (method `REHASH`) with its quality metrics attached as a JSON comment.

No waveform access is needed - REHASH works entirely from the SeisComP
database.

## Requirements

- A running SeisComP system.
- Docker Engine with the Compose plugin.
- Resources: ~2 GB disk for the image; roughly 1 GB RAM during processing.
  No GPU required.

Tested with SeisComP 7.3.0 on Ubuntu 24.04.1.

## Installation

```bash
git clone https://github.com/nkua-seismolab/REHASH.git
cd REHASH
cp config.example.yaml config.yaml
```

Then:

1. Edit `config.yaml`: set `seiscomp.host` and `seiscomp.database` to your
   SeisComP messaging host and database URL, and list your 1-D velocity
   model(s) under `skhash.velocity_models` (an example model ships in
   `velocity_models/`).
2. Start:

   ```bash
   docker compose up -d --build
   docker compose logs -f
   ```

## Configuration

All options live in `config.yaml` and are documented inline in
[config.example.yaml](config.example.yaml). The main sections:

| Section | Purpose |
| ------- | ------- |
| `seiscomp` | Messaging host, database URL, wait time, reprocessing policy |
| `skhash` | SKHASH parameters (see the [SKHASH manual](https://code.usgs.gov/esc/SKHASH)) |
| `output` | Where SKHASH input/output files are kept per event |
| `logging` | Level and optional log file |

## Output

- A `FocalMechanism` (method `REHASH`) with nodal planes, azimuthal gap,
  station polarity count, and misfit, sent to the `FOCMECH` messaging group.
- A JSON comment (id `<fmID>/comment/rehash`) with the quality metrics, e.g.:

  ```json
  {"provenance": {"software": "REHASH", "version": "1.0.0", "stored_at": "..."},
   "quality": "B", "fault_plane_uncertainty_deg": 14.7, "probability": 0.665,
   "sp_misfit": 0.12, "multiple_solutions": false}
  ```

- The SKHASH input/output files of each run under
  `output/<event id>/<processed at>/` (disable with `output.save_files`).

## Getting started

See [GETTING_STARTED.md](GETTING_STARTED.md) for a step-by-step demo run with
the example event `nkua2020abcd` from the demo dataset
([doi:10.5281/zenodo.23105466](https://doi.org/10.5281/zenodo.23105466)).

## License

[GPL-3.0](LICENSE)

## Funding

This work is part of the [TRANSFORM²](https://www.transform2-project.eu/) project which aims to improve physical and digital infrastructure across Near-Fault Observatories (NFOs) in Europe.

TRANSFORM² is funded by the European Union under project number 101188365 within the HORIZON-INFRA-2024-DEV-01-01 call.

<div align="center">
  <img src="https://www.transform2-project.eu/wp-content/uploads/2022/08/Logo_TRANSFORM2-round-logo-100x100-1.png" alt="TRANSFORM² logo">
</div>
