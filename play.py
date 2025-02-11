import datetime
from zoneinfo import ZoneInfo  # Für Zeitzonenunterstützung (Python 3.9+)
from orb_eph import Orb as EphemOrb  # Importiere die ephem-basierte Klasse
from orb_sky import Orb as SkyfieldOrb  # Importiere die skyfield-basierte Klasse

import logging
import datetime


logger = logging.getLogger(__name__)

from skyfield.api import Loader, wgs84, N, W, E




load = Loader('~/.skyfield-data')
planets = load('de421.bsp')
ts = load.timescale()

lat = 52.5200  # Berlin
lon = 13.4050
elev = 34

TIMEZONE = ZoneInfo("Europe/Berlin")

# Define observer's location separately as topos
topos = wgs84.latlon(latitude_degrees=lat * N, longitude_degrees=lon * E, elevation_m=elev)
observer = planets['earth'] + topos

ephem_orb_sun = EphemOrb('sun', lon, lat, elev)
skyfield_orb_sun = SkyfieldOrb('sun', lon, lat, elev)

ephem_orb_moon = EphemOrb('moon', lon, lat, elev)
skyfield_orb_moon = SkyfieldOrb('moon', lon, lat, elev)



start_date = datetime.datetime(2023, 6, 1, tzinfo=TIMEZONE)
delta = datetime.timedelta(hours=1)  # Jede Stunde testen

current_time = start_date
for i in range(200):  # 200 Zeitpunkte
    ephem_rise = ephem_orb_sun.rise(dt=current_time)
    skyfield_rise = skyfield_orb_sun.rise(dt=current_time)
    ephem_rise2 = ephem_rise.astimezone(TIMEZONE)
    skyfield_rise2 = skyfield_rise.astimezone(TIMEZONE)

    print("CT: " + str(i))
    print("sky: " + str(skyfield_rise2))
    print("emp: " + str(ephem_rise2))
    ##self.compare_times(ephem_rise, skyfield_rise)
    diff = abs((ephem_rise - skyfield_rise).total_seconds())
    print(diff)
    print("")
    current_time += delta