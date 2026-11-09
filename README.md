# Great Circle Explorer

Click two points on a 3D globe (or type their coordinates) and see the real distance between them, flight time, bearings, minimum network latency, sunrise and sunset, time-zone difference and more. **Click any metric to see the full calculation, step by step.**

All geodesy is hand-written in Python with the standard `math` module on a spherical Earth (R = 6371.0088 km). The frontend only draws what the backend returns. The app runs fully offline: no internet or external API is needed once it is installed.

> ### For learning and exploration only
> This project exists to learn and explore how distances and directions on the Earth are calculated. **It is not meant for production use, and it must not be used for real-life navigation**: no flight or voyage planning, no surveying, no safety, legal or civil-time decisions. The Earth is modelled as a sphere (distances can be about 0.5 % off, bearings by a fraction of a degree, more near the poles), flight times ignore wind and airways, and the time-zone and map data are simplified snapshots. The known assumptions and the measured accuracy are listed in [docs/ACCURACY.md](docs/ACCURACY.md).

More detail: [docs/FEATURES.md](docs/FEATURES.md) (everything the app can do), [docs/ACCURACY.md](docs/ACCURACY.md) (assumptions and accuracy), [docs/METRICS.md](docs/METRICS.md), [docs/MATH.md](docs/MATH.md), [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/EXECUTIVE_SUMMARY.md](docs/EXECUTIVE_SUMMARY.md). License: [MIT](LICENSE); data and library notices: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Prerequisites

| Tool | Version | Used for |
|---|---|---|
| Python (with `venv` and `pip`) | 3.11 or newer | backend (FastAPI) |
| Node.js (includes `npm`) | 20.19+ or 22.12+ | frontend (Vite, MapLibre) |
| `bash` | any | `./run.sh` (ships with Linux and macOS) |
| Internet connection | first run only | downloading the Python and npm packages; the app itself runs offline |

Check what you have:
```bash
python3 --version     # 3.11 or newer
node --version        # v20.19+ or v22.12+
npm --version
```

If something is missing, install it as follows.

**Debian / Ubuntu / Kali / Linux Mint**
```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip curl
# The distribution's Node.js is often too old, so install it with nvm (https://github.com/nvm-sh/nvm):
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
# open a new terminal, then:
nvm install 22
```
(`python3-venv` is a separate package on these systems; without it `./run.sh` fails while creating the virtual environment.)

**Fedora**
```bash
sudo dnf install -y python3 python3-pip nodejs npm
```
If `node --version` is older than 20.19, use the nvm method above instead.

**Arch / Manjaro**
```bash
sudo pacman -S --needed python python-pip nodejs npm
```

**macOS** (with [Homebrew](https://brew.sh))
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"   # only if you do not have Homebrew yet
brew install python node
```

**Windows:** `run.sh` needs a Unix shell. Use [WSL](https://learn.microsoft.com/windows/wsl/install) and follow the Debian/Ubuntu steps inside it.

`uv` and `git` are optional; nothing here requires them.

## Run it

**One command:**
```bash
./run.sh
```
Then open http://localhost:5173. The first run creates the Python venv and installs the packages (internet needed once for that); later runs start immediately. Ctrl+C stops both. Under the hood it is still two separate processes (backend on :8000, frontend on :5173), which you can also start by hand:

**Backend** (terminal 1; Python 3.11+):
```bash
cd backend
python3 -m venv .venv && . .venv/bin/activate && pip install -e '.[dev]'    # first time only
uvicorn app.main:app --reload --port 8000
python -m pytest             # run the tests
# (uv users: `uv sync`, `uv run uvicorn …`, `uv run pytest` work too, but uv is not required)
```

**Frontend** (terminal 2; Node.js):
```bash
cd frontend
npm install
npm run dev                  # http://localhost:5173 (proxies /api to :8000)
```

Open http://localhost:5173. Click the globe to place A, click again for B (a third click starts over), drag the pins, or type coordinates in the panel. Click any metric card to see its calculation.

## Using it
- **Set the points:** click the globe (A, then B, a third click starts over), drag the pins, type coordinates, search an airport or city (`CGN`, `Santiago`), use the **Wizard** form, or switch *Enter* to **Start + course** to give a start point, a course and a distance and let the app find the destination. **Copy link** shares both points in the URL.
- **Coordinates** can be entered and shown as decimal degrees, degrees-minutes-seconds or degrees-decimal-minutes. You do not need to type the `° ′ ″` symbols: separate the parts with spaces and use a dot for decimals, e.g. `50.8659 N`, `33 23 34.8 S`, `70 47.148 W`.
- **Read the results** in the left panel: distance (km, nm or mi), the **distance analysis** (the same two points measured ten ways, side by side, each tagged sphere or ellipsoid and compared with the Vincenty reference), the ellipsoid distances, course after take-off and before landing, flight time, route crossings, sun and moon, time zones and more. **Click any card** to see how it is calculated, step by step.
- **Map toolbar:** layer toggles (rhumb line, midpoint, vertex, crossings, antipodes, airports), circles of equal distance, night shading with a date and time picker, and a **Globe | Flat** switch. The pointer's coordinates are shown at the bottom.
- **Options** (in the panel): cruise speed, climb/descent and taxi allowances, a date from 1970 to 2049 (time zones follow today's rules), eye heights, and an extra "project from A" destination.
- **Export PDF** lets you choose the metrics and whether to include the full calculation; the browser's print dialog then opens (choose *Save as PDF*).

The complete list is in [docs/FEATURES.md](docs/FEATURES.md).

Optional checks: with the backend running, `cd frontend && npm run check:tex` renders every formula the API returns with KaTeX in strict mode. `tools/verify_accuracy.py` compares the calculations with independent libraries (GeographicLib, PyEphem, TimezoneFinder; installed separately in their own environment, see the header of the script) and prints the measured accuracy documented in [docs/ACCURACY.md](docs/ACCURACY.md).

## Offline data (already in the repository)
The app needs no internet. The bundled map and time-zone data in `frontend/public/` and `backend/app/data/` were created once with `python3 tools/fetch_data.py` (standard library only; needs internet and takes about a minute). You only need to rerun it to refresh the data.

## Data and attributions
- Country outlines and label positions: [Natural Earth](https://www.naturalearthdata.com/) (public domain).
- Airports: [OurAirports](https://ourairports.com/data/) (public domain); cities: Natural Earth populated places (public domain). Both are filtered by `tools/fetch_data.py` into `backend/app/data/places.json`.
- Time-zone boundaries: [timezone-boundary-builder](https://github.com/evansiroky/timezone-boundary-builder) (ODbL; © its contributors, derived from OpenStreetMap data), simplified by `tools/fetch_data.py`.
- Map label font glyphs: Noto Sans (SIL Open Font License), via the MapLibre demo font set.

## License
The source code is released under the [MIT License](LICENSE). Bundled data and libraries have their own licenses, listed in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md); notably `backend/app/data/timezones.json` is under the ODbL. The software is provided "as is", without warranty of any kind, and you use it at your own risk (see the disclaimer at the top and [docs/ACCURACY.md](docs/ACCURACY.md)).
