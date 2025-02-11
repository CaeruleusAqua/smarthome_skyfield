import datetime
from zoneinfo import ZoneInfo  # Für Zeitzonenunterstützung (Python 3.9+)
from orb_eph import Orb as EphemOrb  # Importiere die ephem-basierte Klasse
from orb_sky import Orb as SkyfieldOrb  # Importiere die skyfield-basierte Klasse
import time  # Für Zeitmessung

# Zeitzone GMT+1 (CET)
TIMEZONE = ZoneInfo("Europe/Berlin")

# Start und Ende des Jahres 2024
START_DATE = datetime.datetime(2024, 1, 1, 0, 0, 0, tzinfo=TIMEZONE)
END_DATE = datetime.datetime(2025, 1, 1, 0, 0, 0, tzinfo=TIMEZONE)
DELTA = datetime.timedelta(hours=1)  # Schrittgröße: eine Stunde


class BenchmarkResult:
    def __init__(self):
        self.data = {}

    def add_result(self, class_name, method_name, time_taken):
        if class_name not in self.data:
            self.data[class_name] = {}
        if method_name not in self.data[class_name]:
            self.data[class_name][method_name] = []
        self.data[class_name][method_name].append(time_taken)

    def print_results(self):
        print(f"{'Class':<15} {'Method':<20} {'Average Time (s)':<20} {'Calls':<10}")
        print("-" * 65)
        for class_name, methods in self.data.items():
            for method_name, timings in methods.items():
                avg_time = sum(timings) / len(timings)
                print(f"{class_name:<15} {method_name:<20} {avg_time:<20.6f} {len(timings):<10}")


def benchmark_orbs():
    lat = 52.5200  # Berlin (Latitude)
    lon = 13.4050  # Berlin (Longitude)
    elev = 34  # Meter über dem Meeresspiegel

    benchmark_result = BenchmarkResult()

    # Initialisiere die Objekte
    ephem_orb_sun = EphemOrb('sun', lon, lat, elev)
    skyfield_orb_sun = SkyfieldOrb('sun', lon, lat, elev)

    ephem_orb_moon = EphemOrb('moon', lon, lat, elev)
    skyfield_orb_moon = SkyfieldOrb('moon', lon, lat, elev)

    current_time = START_DATE

    while current_time < END_DATE:
        # Benchmark für jede Methode
        for class_name, orb in [
            #("EphemOrb", ephem_orb_sun),
            ("SkyfieldOrb", skyfield_orb_sun),
        ]:
            for method, args in [
                ("noon", (0,current_time,)),
                ("noon_cached", (0,current_time,)),
                ("midnight", (0,current_time,)),
                ("midnight_cached", (0,current_time,)),
                ("rise", (0,0,True,current_time,)),
                ("rise_cached", (0,0,True,current_time,)),
                ("set", (0,0,True,current_time,)),
                ("set_cached", (0,0,True,current_time,)),
                ("pos", (None,False,current_time,)),
            ]:
                try:
                    start_time = time.perf_counter()
                    getattr(orb, method)(*args)
                    end_time = time.perf_counter()
                    time_taken = end_time - start_time

                    benchmark_result.add_result(class_name, method, time_taken)
                except Exception as e:
                    print(f"Fehler in {class_name}.{method} @ {current_time}: {e}")

        for class_name, orb in [
            ("EphemOrb", ephem_orb_moon),
            ("SkyfieldOrb", skyfield_orb_moon),
        ]:
            for method, args in [
                ("_phase", ()),
                ("_light", ()),
            ]:
                try:
                    start_time = time.perf_counter()
                    getattr(orb, method)(*args)
                    end_time = time.perf_counter()
                    time_taken = end_time - start_time

                    benchmark_result.add_result(class_name, method, time_taken)
                except Exception as e:
                    print(f"Fehler in {class_name}.{method} @ {current_time}: {e}")

        # Nächste Stunde
        current_time += DELTA

    # Ergebnisse ausgeben
    benchmark_result.print_results()


if __name__ == '__main__':
    benchmark_orbs()
