
from flask import Flask, jsonify, render_template
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import time
import json

from sgp4.api import Satrec, jday

from astropy import units as u
from astropy.coordinates import (
    TEME,
    ITRS,
    CartesianRepresentation,
    EarthLocation,
)
from astropy.time import Time

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
TLE_FILE = BASE_DIR / "iss.tle"

TLE_URL = (
    "https://celestrak.org/NORAD/elements/"
    "gp.php?CATNR=25544&FORMAT=TLE"
)

# Reuse orbital data for at least two hours.
CACHE_SECONDS = 2 * 60 * 60

# Block automatic retries after a failed download.
download_blocked = False
last_download_attempt = 0
satellite = None


def load_cached_tle():
    """Load valid ISS orbital data from the local file."""
    if not TLE_FILE.exists():
        return None

    lines = TLE_FILE.read_text(encoding="utf-8").splitlines()

    line1 = next(
        (line.strip() for line in lines if line.startswith("1 ")),
        None,
    )
    line2 = next(
        (line.strip() for line in lines if line.startswith("2 ")),
        None,
    )

    if not line1 or not line2:
        return None

    return Satrec.twoline2rv(line1, line2)


def get_satellite():
    """Use local TLE data; never repeatedly request a blocked source."""
    global satellite, download_blocked, last_download_attempt

    # Use the satellite already loaded into memory.
    if satellite is not None:
        return satellite

    # Try the local file before considering a network request.
    satellite = load_cached_tle()

    if satellite is not None:
        return satellite

    if download_blocked:
        raise RuntimeError(
            "ISS orbital data is unavailable. "
            "CelesTrak access is blocked; automatic retries are disabled."
        )

    if time.time() - last_download_attempt < CACHE_SECONDS:
        raise RuntimeError(
            "No cached ISS orbital data is available. "
            "Wait before another manual download attempt."
        )

    # Record the attempt before contacting the provider.
    last_download_attempt = time.time()

    request = Request(
        TLE_URL,
        headers={"User-Agent": "ISS-Live-Map/1.0"},
    )

    try:
        with urlopen(request, timeout=15) as response:
            lines = response.read().decode("utf-8").splitlines()

    except HTTPError as error:
        # Do not retry HTTP errors automatically.
        download_blocked = True
        raise RuntimeError(
            f"CelesTrak returned HTTP {error.code}. "
            "Automatic retries are disabled."
        ) from error

    except URLError as error:
        raise RuntimeError(
            "Could not reach CelesTrak. "
            "Check your internet connection."
        ) from error

    line1 = next(
        (line.strip() for line in lines if line.startswith("1 ")),
        None,
    )
    line2 = next(
        (line.strip() for line in lines if line.startswith("2 ")),
        None,
    )

    if not line1 or not line2:
        download_blocked = True
        raise RuntimeError("The downloaded data is not a valid ISS TLE.")

    # Write the file only after receiving valid orbital data.
    TLE_FILE.write_text(
        f"ISS (ZARYA)\n{line1}\n{line2}\n",
        encoding="utf-8",
    )

    satellite = Satrec.twoline2rv(line1, line2)
    return satellite


def get_iss_position():
    url = "https://api.wheretheiss.at/v1/satellites/25544"

    request = Request(
        url,
        headers={"User-Agent": "ISS-Live-Map/1.0"}
    )

    with urlopen(request, timeout=15) as response:
        data = json.loads(response.read().decode("utf-8"))

    return {
        "status": "success",
        "latitude": float(data["latitude"]),
        "longitude": float(data["longitude"]),
        "altitude_km": float(data["altitude"]),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }



@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/iss")
def iss_api():
    try:
        return jsonify(get_iss_position())
    except Exception as error:
        return jsonify({
            "status": "error",
            "message": str(error),
        }), 503


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
