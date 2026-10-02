# Getting started with REHASH

This walkthrough runs REHASH on one demo earthquake using the demo dataset
([doi:10.5281/zenodo.23105466](https://doi.org/10.5281/zenodo.23105466)).

REHASH is the third component of the weak-event source characterization workflow
(REPOL / RESS -> REHASH / REBayFM). It needs no waveforms - only polarities
and S/P ratios in the SeisComP database. The demo dataset ships a
**processed** event file containing exactly that, so you can run REHASH
without REPOL/RESS.

## Prerequisites

- A running SeisComP system with messaging and database.
- Docker Engine with the Compose plugin.
- The demo dataset files.
- The velocity model shipping with REHASH.

## 1. Prepare SeisComP

Import the demo inventory into your SeisComP test system.

## 2. Prepare REHASH

```bash
git clone https://github.com/nkua-seismolab/REHASH.git
cd REHASH
cp config.example.yaml config.yaml
```

In `config.yaml`, set `seiscomp.host` and `seiscomp.database` (defaults may
suit a default SeisComP installation). The shipped
velocity model (`velocity_models/CRL.forhash.txt`) suits the demo event.

Start and watch the logs:

```bash
docker compose up -d --build
docker compose logs -f
```

Wait until you see that REHASH connected and is watching for events.

## 3. Dispatch the demo event

On the SeisComP host:

```bash
scdispatch -i nkua2020abcd_crl_scml_processed.xml -v
```

> Keep the REPOL and RESS containers **stopped** when dispatching the
> processed file, otherwise the event is reprocessed and duplicate
> comments/polarities are added. For the full workflow, dispatch the raw
> `nkua2020abcd_crl_scml.xml` instead with all four containers running.

REHASH picks up the event, waits `seiscomp.wait_time`, collects the
polarities and S/P ratios, and runs SKHASH. Progress appears in the
container logs.

## 4. Check the results

- Open the event in `scolv`: a `FocalMechanism` with method `REHASH` is
  attached.
- The mechanism carries a JSON comment (id `<fmID>/comment/rehash`) with the
  HASH quality grade and misfit metrics.
- The SKHASH input/output files of the run are under
  `output/nkua2020abcd/<processed at>/`.

## 5. Rerun

To remove the dispatched objects and run the demo again:

```bash
scdispatch -i nkua2020abcd_crl_scml_processed.xml -v -O remove
```

Set `seiscomp.reprocess: true` in `config.yaml` (and restart the container)
if you want REHASH to reprocess events it has already handled.
