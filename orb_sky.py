#!/usr/bin/env python3
#
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
# Copyright 2011-2014 Marcus Popp                          marcus@popp.mx
# Copyright 2021-2022 Bernd Meiners                 Bernd.Meiners@mail.de
#########################################################################
#  This file is part of SmartHomeNG.    https://github.com/smarthomeNG//
#
#  SmartHomeNG is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  SmartHomeNG is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with SmartHomeNG.  If not, see <http://www.gnu.org/licenses/>.
##########################################################################

import logging
import datetime
import math

from skyfield.almanac import phase_angle

logger = logging.getLogger(__name__)

try:
    from skyfield.api import Loader, wgs84, N, W, E
    from skyfield import almanac
except ImportError as e:
    logger.warning("Could not find/use skyfield!")
    raise

import dateutil.relativedelta
from dateutil.tz import tzutc


class Orb():
    """
    Save an observers location and the name of a celestial body for future use

    The Methods internally use Skyfield for computation

    An `Observer` instance allows to compute the positions of
    celestial bodies as seen from a particular position on the Earth's surface.
    Following attributes can be set after creation (used defaults are given):

        `date` - the moment the `Observer` is created
        `lat` - zero degrees latitude
        `lon` - zero degrees longitude
        `elevation` - 0 meters above sea level
        `horizon` - 0 degrees
        `epoch` - J2000
        `temp` - 15 degrees Celsius
        `pressure` - 1010 mBar
    """

    def __init__(self, orb, lon, lat, elev=False):
        """
        Save location and celestial body

        :param orb: either 'sun' or 'moon'
        :param lon: longitude of observer in degrees
        :param lat: latitude of observer in degrees
        :param elev: elevation of observer in meters
        """
        self.orb = orb
        self.lat = lat
        self.lon = lon
        self.elev = elev

        # Load Skyfield data
        # Ephemeriden laden (mit Kontext-Manager öffnen)
        self.load = Loader('~/.skyfield-data')
        self.planets = self.load('de421.bsp')
        self.ts = self.load.timescale()

        # Define observer's location separately as topos
        self.topos = wgs84.latlon(latitude_degrees=self.lat * N, longitude_degrees=self.lon * E, elevation_m=self.elev)
        self.observer = self.planets['earth'] + self.topos

    def get_observer_and_orb(self):
        """
        Return a tuple of an instance of an observer with location information
        and a celestial body
        Both returned objects are uniquely created to prevent errors in computation

        :return: tuple of observer and celestial body
        """
        if self.orb == 'sun':
            orb = self.planets['sun']
        elif self.orb == 'moon':
            orb = self.planets['moon']
            self.phase = self._phase
            self.light = self._light
        else:
            orb = None
            logger.error(f"Unknown celestial body {self.orb}")
            raise ValueError(f"Unknown celestial body {self.orb}")

        return self.observer, orb

    def _avoid_neverup(self, dt, date_utc, doff):
        """
        When specifying an offset for e.g. a sunset or a sunrise it might well be that the
        offset is too high to be ever reached for a specific location and time
        Therefore this function will limit this offset and return it to the calling function

        :param dt: starting point for calculation
        :type dt: datetime
        :param date_utc: a datetime with utc time
        :type date_utc: datetime
        :param doff: offset in degrees
        :type doff: float
        :return: corrected offset in degrees
        :rtype: float
        """
        originaldoff = doff

        # Get times for noon and midnight
        midnight = self.midnight(0, 0, dt=dt)
        noon = self.noon(0, 0, dt=dt)

        # If the altitudes are calculated from previous or next day, set the correct day for the observer query
        noon = noon if noon >= date_utc else \
            self.noon(0, 0, dt=date_utc + dateutil.relativedelta.relativedelta(days=1))
        midnight = midnight if midnight >= date_utc else \
            self.midnight(0, 0, dt=date_utc - dateutil.relativedelta.relativedelta(days=1))
        # Get lowest and highest altitudes of the relevant day/night
        max_altitude = self.pos(offset=None, degree=True, dt=midnight)[1] if doff <= 0 else \
            self.pos(offset=None, degree=True, dt=noon)[1]

        # Limit degree offset to the highest or lowest possible for the given date
        doff = max(doff, max_altitude + 0.00001) if doff < 0 else min(doff,
                                                                      max_altitude - 0.00001) if doff > 0 else doff
        if not originaldoff == doff:
            logger.notice(f"offset {originaldoff} truncated to {doff}")
        return doff

    def noon(self, doff=0, moff=0, dt=None):
        observer, orb = self.get_observer_and_orb()
        if dt is not None:
            date_utc = dt.replace(tzinfo=tzutc())
        else:
            date_utc = datetime.datetime.utcnow().replace(tzinfo=tzutc())

        t = self.ts.from_datetime(date_utc)
        if not doff == 0:
            doff = self._avoid_neverup(dt, date_utc, doff)

        # Finde den nächsten Transit
        start_time = t
        end_time = self.ts.from_datetime(date_utc + datetime.timedelta(days=1))  # Suche im nächsten Tag

        times = almanac.find_transits(observer, orb, start_time, end_time)

        if len(times) > 0:
            next_transit = times[0].utc_datetime()
        else:
            raise ValueError("Kein Transit gefunden.")

        next_transit = next_transit + dateutil.relativedelta.relativedelta(minutes=moff)
        next_transit = next_transit.replace(tzinfo=tzutc())
        logger.debug(f"skyfield: noon for {self.orb} with doff={doff}, moff={moff}, dt={dt} will be {next_transit}")
        return next_transit

    def midnight(self, doff=0, moff=0, dt=None):
        observer, orb = self.get_observer_and_orb()
        if dt is not None:
            date_utc = dt.replace(tzinfo=tzutc())
        else:
            date_utc = datetime.datetime.utcnow().replace(tzinfo=tzutc())

        t = self.ts.from_datetime(date_utc)
        if not doff == 0:
            doff = self._avoid_neverup(dt, date_utc, doff)

        # Definiere eine Funktion, um Antitransits zu finden
        def is_antitransit(t):
            """Gibt True zurück, wenn der Himmelskörper im Antitransit ist."""
            alt, az, _ = observer.at(t).observe(orb).apparent().altaz()
            return alt.degrees < 0  # Antitransit, wenn der Körper unter dem Horizont ist

        # Finde den nächsten Antitransit
        start_time = t
        end_time = self.ts.from_datetime(date_utc + datetime.timedelta(days=1))  # Suche im nächsten Tag
        #times = almanac.find_transits(observer, orb, start_time, end_time)

        def _transit_ha(latitude, declination, altitude_radians):
            return math.pi
        times, _ = almanac._find(observer, orb, start_time, end_time, 0.0, _transit_ha)

        if len(times) > 0:
            next_antitransit = times[0].utc_datetime()
        else:
            raise ValueError("Kein Antitransit gefunden.")

        next_antitransit = next_antitransit + dateutil.relativedelta.relativedelta(minutes=moff)
        next_antitransit = next_antitransit.replace(tzinfo=tzutc())
        logger.debug(
            f"skyfield: midnight for {self.orb} with doff={doff}, moff={moff}, dt={dt} will be {next_antitransit}")
        return next_antitransit

    def rise(self, doff=0, moff=0, center=True, dt=None):
        """
        Computes the rise of either sun or moon
        :param doff:    degrees offset for the observers horizon
        :param moff:    minutes offset from time of rise (either before or after)
        :param center:  if True then the centerpoint of either sun or moon will be considered to make the transit otherwise the upper limb will be considered
        :param dt:      start time for the search for a rise, if not given the current time will be used
        :return:
        """
        observer, orb = self.get_observer_and_orb()
        if dt is not None:
            date_utc = dt.replace(tzinfo=tzutc())
        else:
            date_utc = datetime.datetime.utcnow().replace(tzinfo=tzutc())

        t = self.ts.from_datetime(date_utc)
        if not doff == 0:
            doff = self._avoid_neverup(dt, date_utc, doff)

        # Verwende almanac.risings_and_settings, um das nächste Set-Ereignis zu berechnen
        times, events = almanac.find_risings(observer, orb, t, t + datetime.timedelta(days=1))

        next_rising = None
        for time, event in zip(times, events):
            if event == True:  # True = Aufgang
                next_rising = time.utc_datetime()
                break

        if next_rising is None:
            raise ValueError("Kein Aufgang gefunden.")

        next_rising = next_rising + dateutil.relativedelta.relativedelta(minutes=moff)
        next_rising = next_rising.replace(tzinfo=tzutc())
        logger.debug(
            f"skyfield: next_rising for {self.orb} with doff={doff}, moff={moff}, center={center}, dt={dt} will be {next_rising}")
        return next_rising

    def set(self, doff=0, moff=0, center=True, dt=None):
        """
        Computes the setting of either sun or moon
        :param doff:    degrees offset for the observers horizon
        :param moff:    minutes offset from time of setting (either before or after)
        :param center:  if True then the centerpoint of either sun or moon will be considered to make the transit otherwise the upper limb will be considered
        :param dt:      start time for the search for a setting, if not given the current time will be used
        :return:
        """
        observer, orb = self.get_observer_and_orb()
        if dt is not None:
            date_utc = dt.replace(tzinfo=tzutc())
        else:
            date_utc = datetime.datetime.utcnow().replace(tzinfo=tzutc())

        t = self.ts.from_datetime(date_utc)
        if not doff == 0:
            doff = self._avoid_neverup(dt, date_utc, doff)

        # Verwende almanac.risings_and_settings, um das nächste Set-Ereignis zu berechnen
        times, events = almanac.find_settings(observer, orb, t, t + datetime.timedelta(days=1))

        next_setting = None
        for time, event in zip(times, events):
            if event == True:  # 0 = Set-Ereignis
                next_setting = time.utc_datetime()
                break

        if next_setting is None:
            raise ValueError("Kein Set-Ereignis gefunden.")

        next_setting = next_setting + dateutil.relativedelta.relativedelta(minutes=moff)
        next_setting = next_setting.replace(tzinfo=tzutc())
        logger.debug(
            f"skyfield: next_setting for {self.orb} with doff={doff}, moff={moff}, center={center}, dt={dt} will be {next_setting}")
        return next_setting

    def pos(self, offset=None, degree=False, dt=None):
        """
        Calculates the position of either sun or moon
        :param offset:  given in minutes, shifts the time of calculation by some minutes back or forth
        :param degree:  if True: return the position of either sun or moon from the observer as degrees, otherwise as radians
        :param dt:      time for which the position needs to be calculated
        :return:        a tuple with azimuth and elevation
        """
        observer, orb = self.get_observer_and_orb()
        if dt is None:
            date = datetime.datetime.utcnow()
        else:
            date = dt.replace(tzinfo=tzutc())
        if offset:
            date += dateutil.relativedelta.relativedelta(minutes=offset)

        t = self.ts.from_datetime(date)
        astrometric = observer.at(t).observe(orb)
        alt, az, _ = astrometric.apparent().altaz()

        if degree:
            return (az.degrees, alt.degrees)
        else:
            return (az.radians, alt.radians)

    def _light(self, offset=None):
        """
        Applies only for moon, returns fraction of lunar surface illuminated when viewed from earth
        for the current time plus an offset
        :param offset: an offset given in minutes
        """
        observer, orb = self.get_observer_and_orb()
        date = datetime.datetime.now(datetime.UTC)# UTC-Zeit mit Zeitzoneninformation
        if offset:
            date += dateutil.relativedelta.relativedelta(minutes=offset)

        t = self.ts.from_datetime(date)  # Konvertiere datetime in Skyfield-Zeit

        # Berechne die Position des Mondes
        moon_position = observer.at(t).observe(orb)

        # Hole das Sun-Objekt aus der Ephemeriden-Datei
        sun = self.planets['sun']

        # Berechne den Phasenwinkel zwischen Mond und Sonne
        phase_angle = moon_position.phase_angle(sun).degrees

        # Berechne den beleuchteten Anteil der Mondoberfläche
        light = (1 + math.cos(math.radians(phase_angle))) / 2 * 100
        return int(round(light))


    def _phase(self, offset=None):
        """
        Applies only for moon, returns the moon phase related to a cycle of approx. 29.5 days
        for the current time plus an offset
        :param offset: an offset given in minutes
        """
        observer, orb = self.get_observer_and_orb()
        date = datetime.datetime.now(datetime.UTC) # UTC-Zeit mit Zeitzoneninformation
        if offset:
            date += dateutil.relativedelta.relativedelta(minutes=offset)

        t = self.ts.from_datetime(date)  # Konvertiere datetime in Skyfield-Zeit

        # Berechne den Phasenwinkel zwischen Mond und Sonne
        phase_angle = almanac.moon_phase(self.planets, t).degrees
        phase = (phase_angle / 360 * 8)
        return int(round(phase))