# REHASH runtime image: SeisComP 7.x Python API + SKHASH.
#
# Base image note: the SeisComP tarballs ship Python bindings compiled against
# the distro's system Python. ubuntu24.04 builds target Python 3.12, matching
# our requires-python; python:3.12-slim (Debian-based) would NOT be ABI
# compatible with any of the Debian tarballs (py3.11/py3.13).
#
# The SeisComP tarball URL/version can be overridden at build time:
#   docker build --build-arg SEISCOMP_TARBALL_URL=... .
FROM ubuntu:24.04

ARG SEISCOMP_TARBALL_URL=https://www.seiscomp.de/downloader/seiscomp-7.3.1-ubuntu24.04-x86_64.tar.gz

ENV DEBIAN_FRONTEND=noninteractive

# bootstrap only; SeisComP runtime libs are installed by its own deps script
# below. gfortran/python3-dev/pkg-config: SKHASH builds its f2py extension from
# source on Python 3.12 (no prebuilt wheel).
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-dev \
    pkg-config \
    ca-certificates \
    wget \
    gfortran \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# SeisComP (only the Python API and client libraries are used; no daemon runs
# here). Runtime dependencies come from the tarball's own install-base.sh so
# the package list stays correct across SeisComP versions; the script uses
# interactive "apt install", hence the sed to a non-interactive form.
# Afterwards, strip everything not needed to import seiscomp.client/datamodel.
RUN wget -q -O /tmp/seiscomp.tar.gz "${SEISCOMP_TARBALL_URL}" \
    && mkdir -p /opt \
    && tar -xzf /tmp/seiscomp.tar.gz -C /opt \
    && rm /tmp/seiscomp.tar.gz \
    && apt-get update \
    && sed 's/^apt install/apt-get install -y --no-install-recommends/' \
        /opt/seiscomp/share/deps/ubuntu/24.04/install-base.sh | sh \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /opt/seiscomp/share/maps /opt/seiscomp/share/doc /opt/seiscomp/share/deps \
        /opt/seiscomp/include /opt/seiscomp/man /opt/seiscomp/etc/descriptions

ENV SEISCOMP_ROOT=/opt/seiscomp \
    VIRTUAL_ENV=/opt/REHASH \
    PATH=/opt/REHASH/bin:/opt/seiscomp/bin:$PATH \
    LD_LIBRARY_PATH=/opt/seiscomp/lib \
    PYTHONPATH=/opt/seiscomp/lib/python

# uv venv "REHASH", pinned to the system Python 3.12: the SeisComP bindings
# are ABI-tied to it; a uv-managed standalone interpreter would break that.
# meson/ninja are SKHASH build requirements on Python 3.12+.
RUN uv venv /opt/REHASH --python /usr/bin/python3.12
COPY rehash/requirements.txt /tmp/requirements.txt
RUN uv pip install --no-cache meson ninja \
    && uv pip install --no-cache -r /tmp/requirements.txt

# Pre-build SKHASH's f2py gridsearch extension. With use_fortran=True, SKHASH
# looks for it at runtime and otherwise prompts interactively to compile it,
# which fails (EOFError) in a non-interactive container.
RUN cd "$(python -c 'import importlib.util; print(importlib.util.find_spec("SKHASH").submodule_search_locations[0])')/functions" \
    && python -m numpy.f2py -c gridsearch.f -m gridsearch \
    && cd .. \
    && python -c 'import functions.gridsearch' \
    && rm -rf /tmp/tmp*

WORKDIR /app
COPY pyproject.toml ./
COPY rehash/ ./rehash/
COPY velocity_models/ ./velocity_models/
RUN uv pip install --no-cache --no-deps .

# config.yaml (and optionally velocity_models/) are provided as volumes
# (see docker-compose.yml)
CMD ["python", "-m", "rehash", "--config", "/app/config.yaml"]
