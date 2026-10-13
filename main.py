import webbrowser
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from sgp4.api import Satrec, jday
# Astropy is used for coordinate transformations and time handling
from astropy import units as u
from astropy.coordinates import TEME, ITRS, CartesianRepresentation, EarthLocation
from astropy.time import Time

# STEP 1: Download the latest available ISS orbital data
url = "https://celestrak.org/NORAD/elements/gp.php?CATNR=25544&FORMAT=TLE"

request = Request(
    url,
    headers={"User-Agent": "ISS-Tracker-Learning-Project"}
)

try:
    with urlopen(request, timeout=20) as response:
        data = response.read().decode("utf-8").strip()

    lines = data.splitlines()

    # Find the two TLE lines
    line1 = next(line.strip() for line in lines if line.startswith("1 "))
    line2 = next(line.strip() for line in lines if line.startswith("2 "))

    print("Downloaded latest available ISS orbital data.")

except Exception as error:
    print("Could not download ISS data:", error)
    raise SystemExit(1)

# STEP 2: Create the satellite object from the real TLE
satellite = Satrec.twoline2rv(line1, line2)

# STEP 3: Get the current UTC time
now = datetime.now(timezone.utc)

# STEP 4: Convert current time to Julian date
jd, fr = jday(
    now.year,
    now.month,
    now.day,
    now.hour,
    now.minute,
    now.second + now.microsecond / 1_000_000
)

# STEP 5: Calculate the ISS position and velocity
error, position, velocity = satellite.sgp4(jd, fr)


# STEP 6: Display the results
print("\n--- ISS Satellite Tracker ---")
print("Calculation time (UTC):", now.isoformat())
print("TLE epoch (UTC):", satellite.jdsatepoch)

if error == 0:
    print("Position (TEME, km):", position)
    print("Velocity (TEME, km/s):", velocity)

    
    # Convert SGP4 position into Astropy coordinates
    teme_position = TEME(
        CartesianRepresentation(
            position[0] * u.km,
            position[1] * u.km,
            position[2] * u.km
        ),
        obstime=Time(now)
    )

    # Convert TEME to Earth-fixed coordinates
    itrs_position = teme_position.transform_to(ITRS(obstime=Time(now)))

    # Convert Earth-fixed coordinates to latitude/longitude/altitude
    location = EarthLocation.from_geocentric(
        itrs_position.cartesian.x,
        itrs_position.cartesian.y,
        itrs_position.cartesian.z
    )

    print("Latitude:", location.lat.deg)
    print("Longitude:", location.lon.deg)
    print("Altitude (km):", location.height.to_value(u.km))
          
    latitude = location.lat.deg
    longitude = location.lon.deg

    map_url = (
        f"https://www.openstreetmap.org/"
        f"?mlat={latitude}&mlon={longitude}"
        f"#map=5/{latitude}/{longitude}"
    )

    webbrowser.open(map_url)



else:
    print("SGP4 calculation error code:", error)
