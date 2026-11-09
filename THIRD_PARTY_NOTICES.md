# Third-party notices

The source code of this project is under the MIT License (see [LICENSE](LICENSE)). The data files and libraries below have their own licenses. **Learning and exploration only: this project and its data are not suitable for navigation or any real-life decision** (see [docs/ACCURACY.md](docs/ACCURACY.md)).

## Bundled data

| File(s) | Source | License |
|---|---|---|
| `frontend/public/data/countries.json`, `labels.json` | [Natural Earth](https://www.naturalearthdata.com/) 1:50m admin-0 countries, simplified and rounded by `tools/fetch_data.py` | Public domain |
| `backend/app/data/places.json` (cities) | Natural Earth 1:10m populated places (cities of 300 000+ people) | Public domain |
| `backend/app/data/places.json` (airports) | [OurAirports](https://ourairports.com/data/) (large and medium airports with an IATA code and scheduled service) | Public domain (dedicated by its maintainer, no warranty; coordinates are airport reference points) |
| `backend/app/data/timezones.json` | [timezone-boundary-builder](https://github.com/evansiroky/timezone-boundary-builder) release 2026f, © its contributors, derived from OpenStreetMap data (© OpenStreetMap contributors), **simplified** by `tools/fetch_data.py` (Douglas-Peucker, about 3 km) | **ODbL 1.0** ([text](https://opendatacommons.org/licenses/odbl/1-0/)). This simplified file is an adapted database and is itself made available under the ODbL. The rest of the repository is not part of that database. |
| `frontend/public/fonts/Noto Sans Regular/*.pbf` | Noto Sans glyph ranges from the MapLibre demo font set | SIL Open Font License 1.1 |
| IANA time-zone rules (via the `tzdata` package) | [IANA tz database](https://www.iana.org/time-zones) | Public domain (the Python `tzdata` package: Apache-2.0) |

## Libraries (installed from PyPI / npm, not copied into this repository)

| Library | License |
|---|---|
| FastAPI, Pydantic | MIT |
| Starlette, Uvicorn, httpx (tests) | BSD-3-Clause |
| tzdata | Apache-2.0 |
| pytest (tests) | MIT |
| MapLibre GL JS | BSD-3-Clause |
| KaTeX | MIT |
| Vite | MIT |

Run `pip list` / `npm ls` and check each package's own license file for the exact versions you install.

## Formulas and methods

The formulas are standard published methods, re-implemented by hand with Python's `math` module: haversine and spherical trigonometry, Lambert's formula for long lines on an ellipsoid (Lambert, 1942), Mercator and rhumb-line formulas, the low-precision formulas for the Sun and the Moon of the kind published in the Astronomical Almanac, and ray-casting point-in-polygon. No code from other projects is included.

## Used only for checking (not dependencies of the project)

`tools/verify_accuracy.py` compares the results with GeographicLib (MIT), PyEphem (MIT) and TimezoneFinder (MIT). These are installed separately and only when you run that script.
