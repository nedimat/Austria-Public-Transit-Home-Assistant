"""Shared HAFAS API response fixtures mirroring the real oebb.transport.rest schema."""
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dep(
    line_name: str,
    product: str,
    direction: str,
    when: str = "2026-06-20T08:00:00+02:00",
    planned_when: str | None = None,
    delay: int = 0,
    operator: str = "Linz Linien AG",
    trip_id: str = "trip-1",
    remarks: list | None = None,
    prognosis_type: str | None = None,
    platform: str | None = None,
    stopovers: list | None = None,
) -> dict:
    """Build a departure dict matching the HAFAS REST response shape."""
    return {
        "tripId": trip_id,
        "direction": direction,
        "when": when,
        "plannedWhen": planned_when or when,
        "delay": delay,
        "prognosisType": prognosis_type,
        "platform": platform,
        "plannedPlatform": platform,
        "line": {
            "type": "line",
            "id": line_name.lower(),
            "name": line_name,
            "product": product,
            "productName": product,
            "mode": "train" if product not in ("bus", "tram") else product,
            "operator": {"type": "operator", "id": "linz-ag", "name": operator},
        },
        "remarks": remarks or [],
        "stopovers": stopovers,
        "origin": None,
        "destination": {"type": "stop", "id": "dest-1", "name": direction},
    }


# ---------------------------------------------------------------------------
# Stop IDs (real values from the API)
# ---------------------------------------------------------------------------
STOP_LARNHAUSERWEG = "410390"
STOP_LINZ_HBF = "8100013"
STOP_INNSBRUCK_HBF = "8100002"
STOP_INNSBRUCK_BERGISEL = "470304"

# ---------------------------------------------------------------------------
# Larnhauserweg departures (no direction filter)
# Both directions appear: Landgutstraße (→ Linz) and Schloss Traun / Trauner Kreuzung (← from Linz)
# ---------------------------------------------------------------------------
LARNHAUSERWEG_ALL = {
    "departures": [
        _dep("3", "tram", "Landgutstraße", when="2026-06-20T08:00:00+02:00", trip_id="t3-1"),
        _dep("4", "tram", "Landgutstraße", when="2026-06-20T08:04:00+02:00", trip_id="t4-1"),
        _dep("3", "tram", "Schloss Traun",  when="2026-06-20T08:05:00+02:00", trip_id="t3-2"),
        _dep("4", "tram", "Trauner Kreuzung P&R", when="2026-06-20T08:09:00+02:00", trip_id="t4-2"),
        _dep("3", "tram", "Landgutstraße", when="2026-06-20T08:15:00+02:00", trip_id="t3-3"),
    ],
}

# Larnhauserweg with direction=8100013 applied server-side:
# API only returns trips passing through Linz Hbf, i.e. the Landgutstraße-bound trams.
LARNHAUSERWEG_VIA_LINZ_HBF = {
    "departures": [
        _dep("3", "tram", "Landgutstraße", when="2026-06-20T08:00:00+02:00", trip_id="t3-1"),
        _dep("4", "tram", "Landgutstraße", when="2026-06-20T08:04:00+02:00", trip_id="t4-1"),
        _dep("3", "tram", "Landgutstraße", when="2026-06-20T08:15:00+02:00", trip_id="t3-3"),
    ],
}

# ---------------------------------------------------------------------------
# Linz Hbf departures towards Wien (Westbahn / REX)
# ---------------------------------------------------------------------------
LINZ_HBF_WESTBAHN = {
    "departures": [
        _dep("WB 111", "nationalExpress", "Wien Westbahnhof", when="2026-06-20T08:10:00+02:00",
             operator="Westbahn", trip_id="wb-1"),
        _dep("REX 1", "regional", "Wien Westbahnhof",  when="2026-06-20T08:30:00+02:00",
             operator="ÖBB", trip_id="rex-1"),
        _dep("RJ 123", "nationalExpress", "Wien Hbf",   when="2026-06-20T08:45:00+02:00",
             delay=180, operator="ÖBB", trip_id="rj-1"),
        _dep("3",   "tram", "Landgutstraße",            when="2026-06-20T08:02:00+02:00",
             operator="Linz Linien AG", trip_id="t3-lhbf"),
    ],
}

# ---------------------------------------------------------------------------
# Innsbruck Hbf tram departures (IVB lines 1 and 3)
# Line 1: Hbf ↔ Bergisel  |  Line 3: Hbf ↔ Amras
# ---------------------------------------------------------------------------
INNSBRUCK_HBF_TRAM = {
    "departures": [
        _dep("1", "tram", "Bergisel", when="2026-06-20T09:20:00+02:00", operator="IVB", trip_id="ivb1-1"),
        _dep("1", "tram", "Bergisel", when="2026-06-20T09:28:00+02:00", operator="IVB", trip_id="ivb1-2"),
        _dep("3", "tram", "Amras",    when="2026-06-20T09:22:00+02:00", operator="IVB", trip_id="ivb3-1"),
    ],
}

# ---------------------------------------------------------------------------
# Remarks fixture: realistic ÖBB amenity remarks that should be filtered out
# ---------------------------------------------------------------------------
REMARKS_WITH_AMENITIES = [
    {"type": "hint", "code": "OB",  "text": "Niederflurfahrzeug"},
    {"type": "hint", "code": "RO",  "text": "Rollstuhlstellplatz"},
    {"type": "hint", "code": "BF",  "text": "Bahnsteigsperre"},         # operational
    {"type": "warning", "code": None, "text": "Fahrt fällt aus"},
    {"type": "hint", "code": None,  "text": "Umleitungsverkehr aktiv"}, # operational, no code
]

AMENITY_CODES = {"OB", "RO", "A", "AE", "BE", "BH", "BO", "BR", "BT", "BU", "FA", "FK", "NF", "RK", "RM", "WV"}
