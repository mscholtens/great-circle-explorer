"""Helpers to build explanation steps: number formatting (TeX and plain) and step/constant dicts."""
def sig(x, n=5):
    """Plain-text number with ~n significant digits (no trailing zeros, thousands unseparated)."""
    if x is None:
        return "undefined"
    if x == 0:
        return "0"
    ax = abs(x)
    if ax >= 1e9 or ax < 1e-4:
        mant, exp = f"{x:.{n - 1}e}".split("e")
        mant = mant.rstrip("0").rstrip(".")
        return f"{mant}×10^{int(exp)}"
    s = f"{x:.{n}g}"
    if "e" in s:  # large values that %g would put in exponent form (e.g. 1.2346e+05)
        s = f"{x:.0f}"
    return s


def tn(x, n=5):
    """TeX number with ~n significant digits."""
    if x is None:
        return r"\text{undefined}"
    if x == 0:
        return "0"
    ax = abs(x)
    if ax >= 1e9 or ax < 1e-4:
        mant, exp = f"{x:.{n - 1}e}".split("e")
        mant = mant.rstrip("0").rstrip(".")
        return rf"{mant}\times 10^{{{int(exp)}}}"
    s = f"{x:.{n}g}"
    if "e" in s:
        s = f"{x:.0f}"
    return s


def tp(x, n=5):
    """TeX number, parenthesized when negative or in scientific notation (safe to raise to a power)."""
    s = tn(x, n)
    return f"({s})" if s.startswith("-") or r"\times" in s else s


def td(x_deg, n=5):
    """TeX number in degrees."""
    return tn(x_deg, n) + r"^{\circ}"


def step(label, tex=None, substituted_tex=None, result=None):
    return {"label": label, "tex": tex, "substituted_tex": substituted_tex, "result": result}


def const(symbol, value, meaning):
    return {"symbol": symbol, "value": value, "meaning": meaning}


def explanation(summary, steps, constants=None, notes=None):
    return {"summary": summary, "steps": steps, "constants": constants or [], "notes": notes or []}


def space_thousands(x, decimals=0):
    """'6 089' style number (non-breaking spaces)."""
    return f"{x:,.{decimals}f}".replace(",", " ")


def hm(hours):
    """Human duration from hours: '10 h 05 min', '42 min', '3.2 s', '0.52 ms'."""
    seconds = hours * 3600.0
    if seconds < 1e-3:
        return f"{seconds * 1e6:.3g} µs"
    if seconds < 1.0:
        return f"{seconds * 1e3:.3g} ms"
    if seconds < 60.0:
        return f"{seconds:.3g} s"
    minutes = round(seconds / 60.0)
    if minutes < 60:
        return f"{minutes} min"
    h, m = divmod(minutes, 60)
    if h >= 100:
        return f"{space_thousands(hours)} h"
    return f"{h} h {m:02d} min"


def latlon_text(lat_deg, lon_deg, decimals=4):
    """'51.2277°N, 6.7735°E'. A value that rounds to 0° (equator, prime meridian) or 180° has no hemisphere letter."""
    def part(v, pos, neg):
        r = round(abs(v), decimals)
        letter = "" if r in (0, 180) else (pos if v >= 0 else neg)
        return f"{r:.{decimals}f}°{letter}"
    return f"{part(lat_deg, 'N', 'S')}, {part(lon_deg, 'E', 'W')}"


def utc_hm(hours):
    """UTC clock time from decimal hours: '07:12 UTC'."""
    if hours is None:
        return "—"
    total = round((hours % 24.0) * 60.0) % (24 * 60)
    return f"{total // 60:02d}:{total % 60:02d} UTC"


def offset_text(hours):
    """UTC offset label: 'UTC+1', 'UTC−5', 'UTC+5:30'."""
    sign = "+" if hours >= 0 else "−"
    total = round(abs(hours) * 60)
    h, m = divmod(total, 60)
    return f"UTC{sign}{h}" + (f":{m:02d}" if m else "")

