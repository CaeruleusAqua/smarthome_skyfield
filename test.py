import unittest
import datetime
from zoneinfo import ZoneInfo  # Für Zeitzonenunterstützung (Python 3.9+)
from orb_eph import Orb as EphemOrb  # Importiere die ephem-basierte Klasse
from orb_sky import Orb as SkyfieldOrb  # Importiere die skyfield-basierte Klasse

# Zeitzone GMT+1 (CET)
TIMEZONE = ZoneInfo("Europe/Berlin")


class TestOrb(unittest.TestCase):
    def setUp(self):
        """
        Initialisiere beide Klassen mit denselben Parametern.
        """
        self.lat = 52.5200  # Berlin
        self.lon = 13.4050
        self.elev = 34  # Meter über dem Meeresspiegel

        # Initialisiere beide Implementierungen
        self.ephem_orb_sun = EphemOrb('sun', self.lon, self.lat, self.elev)
        self.skyfield_orb_sun = SkyfieldOrb('sun', self.lon, self.lat, self.elev)

        self.ephem_orb_moon = EphemOrb('moon', self.lon, self.lat, self.elev)
        self.skyfield_orb_moon = SkyfieldOrb('moon', self.lon, self.lat, self.elev)

    def compare_times(self, time1, time2, tolerance_seconds=60):
        """
        Vergleicht zwei datetime-Objekte und prüft, ob sie innerhalb einer Toleranz liegen.
        :param time1: Erstes datetime-Objekt
        :param time2: Zweites datetime-Objekt
        :param tolerance_seconds: Toleranz in Sekunden
        """
        delta = abs((time1 - time2).total_seconds())
        self.assertLessEqual(delta, tolerance_seconds, f"Zeitdifferenz zu groß: {delta} Sekunden")

    def test_noon_200_timepoints(self):
        """
        Testet die noon-Methode für die Sonne mit 200 Zeitpunkten.
        """
        start_date = datetime.datetime(2023, 1, 1, tzinfo=TIMEZONE)
        delta = datetime.timedelta(hours=1)  # Jede Stunde testen

        current_time = start_date
        for i in range(200):  # 200 Zeitpunkte
            with self.subTest(time=current_time):
                ephem_noon = self.ephem_orb_sun.noon(dt=current_time)
                skyfield_noon = self.skyfield_orb_sun.noon(dt=current_time)
                self.compare_times(ephem_noon, skyfield_noon)
            current_time += delta

    def test_midnight_200_timepoints(self):
        """
        Testet die midnight-Methode für die Sonne mit 200 Zeitpunkten.
        """
        start_date = datetime.datetime(2023, 1, 1, tzinfo=TIMEZONE)
        delta = datetime.timedelta(hours=2)  # Alle zwei Stunden testen

        current_time = start_date
        for i in range(200):  # 200 Zeitpunkte
            with self.subTest(time=current_time):
                ephem_midnight = self.ephem_orb_sun.midnight(dt=current_time)
                skyfield_midnight = self.skyfield_orb_sun.midnight(dt=current_time)
                self.compare_times(ephem_midnight, skyfield_midnight)
            current_time += delta

    def test_rise_200_timepoints(self):
        """
        Testet die rise-Methode für die Sonne mit 200 Zeitpunkten.
        """
        start_date = datetime.datetime(2023, 6, 1, tzinfo=TIMEZONE)
        delta = datetime.timedelta(hours=1)  # Jede Stunde testen

        current_time = start_date
        for i in range(200):  # 200 Zeitpunkte
            with self.subTest(time=current_time):
                ephem_rise = self.ephem_orb_sun.rise(dt=current_time)
                skyfield_rise = self.skyfield_orb_sun.rise(dt=current_time)
                self.compare_times(ephem_rise, skyfield_rise)
            current_time += delta

    def test_set_200_timepoints(self):
        """
        Testet die set-Methode für die Sonne mit 200 Zeitpunkten.
        """
        start_date = datetime.datetime(2023, 6, 1, tzinfo=TIMEZONE)
        delta = datetime.timedelta(hours=1)  # Jede Stunde testen

        current_time = start_date
        for i in range(200):  # 200 Zeitpunkte
            with self.subTest(time=current_time):
                ephem_set = self.ephem_orb_sun.set(dt=current_time)
                skyfield_set = self.skyfield_orb_sun.set(dt=current_time)
                self.compare_times(ephem_set, skyfield_set)
            current_time += delta

    def test_moon_phase_200_timepoints(self):
        """
        Testet die _phase-Methode für den Mond mit 200 Zeitpunkten.
        """
        start_date = datetime.datetime(2023, 1, 1, tzinfo=TIMEZONE)
        delta = datetime.timedelta(hours=2)  # Alle zwei Stunden testen

        current_time = start_date
        for i in range(200):  # 200 Zeitpunkte
            with self.subTest(time=current_time):
                ephem_phase = self.ephem_orb_moon._phase()
                skyfield_phase = self.skyfield_orb_moon._phase()
                self.assertEqual(ephem_phase, skyfield_phase, "Mondphasen stimmen nicht überein")
            current_time += delta

    def test_moon_light_200_timepoints(self):
        """
        Testet die _light-Methode für den Mond mit 200 Zeitpunkten.
        """
        start_date = datetime.datetime(2023, 1, 1, tzinfo=TIMEZONE)
        delta = datetime.timedelta(hours=3)  # Alle 3 Stunden testen

        current_time = start_date
        for i in range(200):  # 200 Zeitpunkte
            with self.subTest(time=current_time):
                ephem_light = self.ephem_orb_moon._light()
                skyfield_light = self.skyfield_orb_moon._light()
                self.assertEqual(ephem_light, skyfield_light, "Mondbeleuchtung stimmt nicht überein")
            current_time += delta

    def test_sun_pos_200_timepoints(self):
        """
        Testet die pos-Methode für die Sonne mit 200 Zeitpunkten.
        """
        start_date = datetime.datetime(2023, 1, 1, tzinfo=TIMEZONE)
        delta = datetime.timedelta(hours=1)  # Jede Stunde testen

        current_time = start_date
        for i in range(200):  # 200 Zeitpunkte
            with self.subTest(time=current_time):
                ephem_pos = self.ephem_orb_sun.pos(dt=current_time, degree=True)
                skyfield_pos = self.skyfield_orb_sun.pos(dt=current_time, degree=True)
                self.assertAlmostEqual(ephem_pos[0], skyfield_pos[0], delta=1, msg="Azimut stimmt nicht überein")
                self.assertAlmostEqual(ephem_pos[1], skyfield_pos[1], delta=1, msg="Höhe stimmt nicht überein")
            current_time += delta


if __name__ == '__main__':
    unittest.main()
