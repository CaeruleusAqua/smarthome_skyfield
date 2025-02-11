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
import bisect

logger = logging.getLogger(__name__)

try:
    from skyfield.api import Loader, wgs84, N, W, E
    from skyfield import almanac
except ImportError as e:
    logger.warning("Could not find/use skyfield!")
    raise

import dateutil.relativedelta
from dateutil.tz import tzutc


def _find_next_datetime(sorted_datetimes, target):
    index = bisect.bisect_right(sorted_datetimes, target)
    if index < len(sorted_datetimes):
        return sorted_datetimes[index]
    else:
        return None

def merge_sorted_datetimes(list1, list2):
    merged = []
    i = j = 0
    # Vergleiche Elemente und füge das kleinere hinzu
    while i < len(list1) and j < len(list2):
        if list1[i] <= list2[j]:
            merged.append(list1[i])
            i += 1
        else:
            merged.append(list2[j])
            j += 1
    # Füge restliche Elemente hinzu
    merged.extend(list1[i:])
    merged.extend(list2[j:])
    return merged


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
        self.orb_name = orb
        self.lat = lat
        self.lon = lon
        self.elev = elev
        self.rise_cache = dict()
        self.set_cache = dict()
        self.noon_cache = []
        self.midnight_cache = []
        self.max_cache_size = 2000
        self.cache_prefill_horizon = 365

        # Load Skyfield data
        # Ephemeriden laden (mit Kontext-Manager öffnen)
        self.load = Loader('~/.skyfield-data')
        self.planets = self.load('de421.bsp')
        self.ts = self.load.timescale()
        self.orb = self.planets[orb]

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
        if self.orb_name == 'moon':
            self.phase = self._phase
            self.light = self._light

        return self.observer, self.orb

    def noon_cached(self, moff=0, dt=None):
        observer, orb = self.get_observer_and_orb()
        date_utc = self._datetime_in_utc(dt)

        t = self.ts.from_datetime(date_utc)

        if not self.noon_cache:
            start_time = t
            end_time = self.ts.from_datetime(date_utc + datetime.timedelta(days=self.cache_prefill_horizon ))
            times = almanac.find_transits(observer, orb, start_time, end_time)
            self.noon_cache = [time.utc_datetime() for time in times]

        if len(self.noon_cache) > self.max_cache_size:
            self.noon_cache = []

        next_transit = _find_next_datetime(self.noon_cache, date_utc)

        if next_transit is None:
            start_time = t
            end_time = self.ts.from_datetime(date_utc + datetime.timedelta(days=self.cache_prefill_horizon))
            times = almanac.find_transits(observer, orb, start_time, end_time)
            new_times = [time.utc_datetime() for time in times]
            self.noon_cache = merge_sorted_datetimes(self.noon_cache, new_times)
            if times:
                next_transit = times[0].utc_datetime()
            else:
                raise ValueError("No transit found.")

        next_transit += dateutil.relativedelta.relativedelta(minutes=moff)
        logger.debug(f"skyfield: noon (cached) for {self.orb} with moff={moff}, dt={dt} will be {next_transit}")
        return next_transit

    def noon(self, moff=0, dt=None):
        observer, orb = self.get_observer_and_orb()
        date_utc = self._datetime_in_utc(dt)

        t = self.ts.from_datetime(date_utc)

        # Finde den nächsten Transit
        start_time = t
        end_time = self.ts.from_datetime(date_utc + datetime.timedelta(days=2))  # Suche im nächsten Tag

        times = almanac.find_transits(observer, orb, start_time, end_time)

        if times:
            next_transit = times[0].utc_datetime()
        else:
            raise ValueError("No transit found.")

        next_transit = next_transit + dateutil.relativedelta.relativedelta(minutes=moff)
        next_transit = next_transit.astimezone(datetime.UTC)
        logger.debug(f"skyfield: noon for {self.orb} with moff={moff}, dt={dt} will be {next_transit}")
        return next_transit

    def midnight_cached(self, moff=0, dt=None):
        observer, orb = self.get_observer_and_orb()
        date_utc = self._datetime_in_utc(dt)

        t = self.ts.from_datetime(date_utc)

        if not self.midnight_cache:
            start_time = t
            end_time = self.ts.from_datetime(date_utc + datetime.timedelta(days=self.cache_prefill_horizon))

            def _transit_ha(latitude, declination, altitude_radians):
                return math.pi

            times, _ = almanac._find(observer, orb, start_time, end_time, 0, _transit_ha)
            self.midnight_cache = [time.utc_datetime() for time in times]

        if len(self.midnight_cache) > self.max_cache_size:
            self.midnight_cache = []

        next_antitransit = _find_next_datetime(self.midnight_cache, date_utc)

        if next_antitransit is None:
            start_time = t
            end_time = self.ts.from_datetime(date_utc + datetime.timedelta(days=self.cache_prefill_horizon))

            def _transit_ha(latitude, declination, altitude_radians):
                return math.pi

            times, _ = almanac._find(observer, orb, start_time, end_time, 0, _transit_ha)
            new_times = [time.utc_datetime() for time in times]
            self.midnight_cache = merge_sorted_datetimes(self.midnight_cache, new_times)
            if times:
                next_antitransit = times[0].utc_datetime()
            else:
                raise ValueError("No antitransit found.")

        next_antitransit += dateutil.relativedelta.relativedelta(minutes=moff)
        logger.debug(f"skyfield: midnight (cached) for {self.orb} with moff={moff}, dt={dt} will be {next_antitransit}")
        return next_antitransit

    def midnight(self, moff=0, dt=None):
        observer, orb = self.get_observer_and_orb()
        date_utc = self._datetime_in_utc(dt)

        t = self.ts.from_datetime(date_utc)

        start_time = t
        end_time = self.ts.from_datetime(date_utc + datetime.timedelta(days=2))  # Suche im nächsten Tag

        def _transit_ha(latitude, declination, altitude_radians):
            return math.pi
        times, _ = almanac._find(observer, orb, start_time, end_time, 0, _transit_ha)

        if times:
            next_antitransit = times[0].utc_datetime()
        else:
            raise ValueError("No antitransit found.")

        next_antitransit = next_antitransit + dateutil.relativedelta.relativedelta(minutes=moff)
        next_antitransit = next_antitransit.astimezone(datetime.UTC)
        logger.debug(
            f"skyfield: midnight for {self.orb} with moff={moff}, dt={dt} will be {next_antitransit}")
        return next_antitransit

    def rise_cached(self, doff=0, moff=0, center=True, dt=None):
        observer, orb = self.get_observer_and_orb()
        date_utc = self._datetime_in_utc(dt)

        t = self.ts.from_datetime(date_utc)
        if doff not in self.rise_cache:
            times, events = almanac.find_risings(observer, orb, t, t + datetime.timedelta(days=self.cache_prefill_horizon), doff)
            self.rise_cache[doff] = [time.utc_datetime() for time in times]

        if len(self.rise_cache[doff]) > self.max_cache_size:
            self.rise_cache[doff] = []

        next_rise = _find_next_datetime(self.rise_cache[doff], date_utc)

        if next_rise is None:
            times, events = almanac.find_risings(observer, orb, t, t + datetime.timedelta(days=self.cache_prefill_horizon), doff)
            new_times = [time.utc_datetime() for time in times]
            self.rise_cache[doff] = merge_sorted_datetimes(self.rise_cache[doff], new_times)
            if times:
                next_rise = times[0].utc_datetime()
            else:
                raise ValueError("No rise found.")

        next_rise += dateutil.relativedelta.relativedelta(minutes=moff)
        logger.debug(
            f"skyfield: next_rise for {self.orb} with doff={doff}, moff={moff}, center={center}, dt={dt} will be {next_rise}")
        return next_rise

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
        date_utc = self._datetime_in_utc(dt)

        t = self.ts.from_datetime(date_utc)

        times, events = almanac.find_risings(observer, orb, t, t + datetime.timedelta(days=2), doff)
        next_rising = None

        for time, event in zip(times, events):
            if not event:  # True = Aufgang
                logger.info("No rise found, returned time is transit time instead")
            next_rising = time.utc_datetime()
            break

        if next_rising is None:
            # should not happen
            raise ValueError("No rise found.")

        next_rising = next_rising + dateutil.relativedelta.relativedelta(minutes=moff)
        logger.debug(
            f"skyfield: next_rising for {self.orb} with doff={doff}, moff={moff}, center={center}, dt={dt} will be {next_rising}")
        return next_rising

    def set_cached(self, doff=0, moff=0, center=True, dt=None):
        observer, orb = self.get_observer_and_orb()
        date_utc = self._datetime_in_utc(dt)

        t = self.ts.from_datetime(date_utc)
        if doff not in self.set_cache:
            times, events = almanac.find_settings(observer, orb, t, t + datetime.timedelta(days=self.cache_prefill_horizon), doff)
            self.set_cache[doff] = [time.utc_datetime() for time in times]

        if len(self.set_cache.get(doff, [])) > self.max_cache_size:
            self.set_cache[doff] = []

        next_set = _find_next_datetime(self.set_cache.get(doff, []), date_utc)

        if next_set is None:
            times, events = almanac.find_settings(observer, orb, t, t + datetime.timedelta(days=self.cache_prefill_horizon), doff)
            new_times = [time.utc_datetime() for time in times]
            self.set_cache[doff] = merge_sorted_datetimes(self.set_cache.get(doff, []), new_times)
            if times:
                next_set = times[0].utc_datetime()
            else:
                raise ValueError("No set found.")

        next_set += dateutil.relativedelta.relativedelta(minutes=moff)
        logger.debug(
            f"skyfield: next_set (cached) for {self.orb} with doff={doff}, moff={moff}, dt={dt} will be {next_set}")
        return next_set

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
        date_utc = self._datetime_in_utc(dt)

        t = self.ts.from_datetime(date_utc)

        # Verwende almanac.risings_and_settings, um das nächste Set-Ereignis zu berechnen
        times, events = almanac.find_settings(observer, orb, t, t + datetime.timedelta(days=2),doff)

        next_setting = None
        for time, event in zip(times, events):
            if not event:  # True = Aufgang
                logger.info("No setting found, returned time is transit time instead")
            next_setting = time.utc_datetime()
            break

        if next_setting is None:
            raise ValueError("No set found.")

        next_setting = next_setting + dateutil.relativedelta.relativedelta(minutes=moff)
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
        date_utc = self._datetime_in_utc(dt)
        if offset:
            date_utc += dateutil.relativedelta.relativedelta(minutes=offset)

        t = self.ts.from_datetime(date_utc)
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
        date = datetime.datetime.now(datetime.UTC)  # UTC-Zeit mit Zeitzoneninformation
        if offset:
            date += dateutil.relativedelta.relativedelta(minutes=offset)

        t = self.ts.from_datetime(date)  # Konvertiere datetime in Skyfield-Zeit

        # Berechne den Phasenwinkel zwischen Mond und Sonne
        phase_angle = almanac.moon_phase(self.planets, t).radians

        # Berechne den beleuchteten Anteil der Mondoberfläche
        light = (1 - math.cos(phase_angle)) / 2 * 100
        return int(round(light))


    def _phase(self, offset=None):
        """
        Applies only for moon, returns the moon phase related to a cycle of approx. 29.5 days
        for the current time plus an offset
        :param offset: an offset given in minutes
        """
        date = datetime.datetime.now(datetime.UTC) # UTC-Zeit mit Zeitzoneninformation
        if offset:
            date += dateutil.relativedelta.relativedelta(minutes=offset)

        t = self.ts.from_datetime(date)  # Konvertiere datetime in Skyfield-Zeit

        # Berechne den Phasenwinkel zwischen Mond und Sonne
        phase_angle = almanac.moon_phase(self.planets, t).degrees
        phase = (phase_angle / 360 * 8)
        return int(round(phase))

    def _datetime_in_utc(self, dt):
        if dt is not None:
            return dt.astimezone(datetime.UTC)
        else:
            return datetime.datetime.now(datetime.UTC)
