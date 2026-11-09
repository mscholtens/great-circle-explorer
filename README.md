# Great Circle Explorer

Click two points on a 3D globe (or type their coordinates) and see the real distance between them, flight time, bearings, minimum network latency, sunrise and sunset, time-zone difference and more. **Click any metric to see the full calculation, step by step.**

All geodesy is hand-written in Python with the standard `math` module on a spherical Earth (R = 6371.0088 km). The frontend only draws what the backend returns. The app runs fully offline: no internet or external API is needed once it is installed.

> Spherical Earth model: good to roughly 0.3% for distances. One metric compares the result with the WGS84 ellipsoid.

More detail: [docs/EXECUTIVE_SUMMARY.md](docs/EXECUTIVE_SUMMARY.md), [docs/METRICS.md](docs/METRICS.md), [docs/MATH.md](docs/MATH.md), [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

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

Coordinates can be entered and shown as decimal degrees (DD), degrees-minutes-seconds (DMS) or degrees-decimal-minutes (DDM); switch with the toggle above the fields. Any format is accepted in any mode, with hemisphere letters. You do not need to type the ° ′ ″ symbols: separate the parts with spaces and use a dot for decimals, e.g. `50.8659 N`, `33 23 34.8 S`, `70 47.148 W`. The **Crossings** card lists where the route crosses the equator, the tropics, the polar circles and the 0° / 180° meridians, with coordinates, and marks them on the globe. Flight time is shown as airborne time (take-off to landing) with the gate-to-gate time next to it, and the course after take-off and before landing sit right below it. Under **Options** you can set the cruise speed, the climb/descent and taxi allowances, and a date between 1 Jan 1970 and 31 Dec 2049 for the sun and time-zone metrics (time zones follow today's rules; later dates assume they stay unchanged). Prefer a form? The **Wizard** button (next to Reset) opens a single scrollable form: choose the point and the format, and the fields (degrees, minutes, seconds, direction) and their help texts adapt to that format, with a live preview of the result.

Optional check (backend must be running): `cd frontend && npm run check:tex` renders every formula the API returns with KaTeX in strict mode.

## Offline data (already in the repository)
The app needs no internet. The bundled map and time-zone data in `frontend/public/` and `backend/app/data/` were created once with `python3 tools/fetch_data.py` (standard library only; needs internet and takes about a minute). You only need to rerun it to refresh the data.

## Data and attributions
- Country outlines and label positions: [Natural Earth](https://www.naturalearthdata.com/) (public domain).
- Time-zone boundaries: [timezone-boundary-builder](https://github.com/evansiroky/timezone-boundary-builder) (ODbL; © its contributors, derived from OpenStreetMap data), simplified by `tools/fetch_data.py`.
- Map label font glyphs: Noto Sans (SIL Open Font License), via the MapLibre demo font set.
