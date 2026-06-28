"""Shared mgate HAFAS response fixtures mirroring the real ÖBB mgate format."""

# ---------------------------------------------------------------------------
# Stop IDs (real extId values from ÖBB mgate LocMatch)
# ---------------------------------------------------------------------------
STOP_LARNHAUSERWEG      = "1290401"
STOP_LINZ_HBF           = "8100013"
STOP_INNSBRUCK_HBF      = "8100002"
STOP_INNSBRUCK_BERGISEL = "470304"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _loc_match_response(stops: list[dict]) -> dict:
    return {
        "ver": "1.67", "lang": "deu", "err": "OK",
        "svcResL": [{
            "meth": "LocMatch", "err": "OK",
            "res": {
                "common": {"prodL": [], "opL": [], "icoL": []},
                "match": {"locL": stops},
            },
        }],
    }


def _station_board_response(
    journeys: list[dict],
    prod_list: list[dict],
    op_list: list[dict],
    rem_list: list[dict],
    him_list: list[dict],
) -> dict:
    return {
        "ver": "1.67", "lang": "deu", "err": "OK",
        "svcResL": [{
            "meth": "StationBoard", "err": "OK",
            "res": {
                "common": {
                    "prodL": prod_list,
                    "opL": op_list,
                    "remL": rem_list,
                    "himL": him_list,
                    "icoL": [{"res": "dummy"}],
                },
                "date": None,
                "jnyL": journeys,
            },
        }],
    }


def _prod(name_s: str, cat_out: str, cls: int, op_idx: int = 0) -> dict:
    return {
        "name": name_s,
        "nameS": name_s,
        "icoX": 0,
        "cls": cls,
        "oprX": op_idx,
        "prodCtx": {
            "name": name_s,
            "catOut": cat_out,
            "catOutS": cat_out.strip().lower(),
            "catOutL": cat_out.strip(),
        },
    }


def _op(name: str) -> dict:
    return {"name": name, "icoX": 0}


def _jny(
    prod_x: int,
    dir_txt: str,
    date: str,
    time_s: str,
    time_r: str | None = None,
    tz_offset: int = 120,
    pltf_s: str | None = None,
    cancelled: bool = False,
    msg_list: list | None = None,
    jid: str | None = None,
) -> dict:
    stb: dict = {
        "locX": 0, "idx": 0,
        "dTimeS": time_s,
        "dProgType": "CANCELLED" if cancelled else "PROGNOSED",
        "dTZOffset": tz_offset,
        "type": "N",
    }
    if time_r:
        stb["dTimeR"] = time_r
    if pltf_s:
        stb["dPltfS"] = {"type": "PL", "txt": pltf_s}
        stb["dPltfR"] = {"type": "PL", "txt": pltf_s}
    if cancelled:
        stb["dCncl"] = True
    return {
        "jid": jid or f"jny-{prod_x}-{time_s}",
        "date": date,
        "prodX": prod_x,
        "dirTxt": dir_txt,
        "stbStop": stb,
        "msgL": msg_list or [],
    }


# ---------------------------------------------------------------------------
# Common reference data
# ---------------------------------------------------------------------------
_LINZ_AG_OP  = _op("Linz AG Linien")
_OBB_OP      = _op("ÖBB")
_WESTBAHN_OP = _op("Westbahn")
_IVB_OP      = _op("IVB")

_PROD_TRAM_3      = _prod("3",       "STR", cls=256, op_idx=0)
_PROD_TRAM_4      = _prod("4",       "STR", cls=256, op_idx=0)
_PROD_WB          = _prod("WB 111",  "IC",  cls=2,   op_idx=1)
_PROD_REX         = _prod("REX 1",   "REX", cls=8,   op_idx=2)
_PROD_RJ          = _prod("RJ 123",  "RJ",  cls=1,   op_idx=2)
_PROD_TRAM_LHBF   = _prod("3",       "STR", cls=256, op_idx=0)
_PROD_IVB_1       = _prod("1",       "STR", cls=256, op_idx=0)
_PROD_IVB_3       = _prod("3",       "STR", cls=256, op_idx=0)

# Amenity remarks (should be filtered out)
_REM_NF  = {"type": "A", "code": "OB",  "prio": 0,   "icoX": 0, "txtN": "Niederflurfahrzeug"}
_REM_RO  = {"type": "A", "code": "RO",  "prio": 150, "icoX": 1, "txtN": "Rollstuhlstellplatz"}
# Operational remarks (must be kept)
_REM_OPS  = {"type": "A", "code": "XI", "prio": 400, "icoX": 2, "txtN": "Bahnsteigsperre"}
_REM_OPS2 = {"type": "A", "code": "",   "prio": 400, "icoX": 3, "txtN": "Umleitungsverkehr aktiv"}
# Internal control remark (must be filtered)
_REM_INT  = {"type": "M", "code": "showAsEmergency", "txtN": "true"}

_HIM_DISRUPTION = {
    "hid": "889404", "act": True,
    "head": "Hitzewarnung",
    "lead": "Mögliche Einschränkungen",
    "text": "Aufgrund der Hitze kann es zu Verspätungen kommen.",
    "icoX": 4, "prio": 100,
}

# msgL referencing remarks: indices 0=NF, 1=RO, 2=OPS, 3=OPS2, 4=INT, HIM=0
REMARKS_MSG_LIST = [
    {"type": "REM", "remX": 0, "sty": "I"},
    {"type": "REM", "remX": 1, "sty": "I"},
    {"type": "REM", "remX": 2, "sty": "I"},
    {"type": "REM", "remX": 3, "sty": "I"},
    {"type": "REM", "remX": 4, "sty": "I"},
    {"type": "HIM", "himX": 0, "sty": "M"},
]
REMARKS_WITH_AMENITIES_COMMON = [_REM_NF, _REM_RO, _REM_OPS, _REM_OPS2, _REM_INT]

AMENITY_CODES = {"OB", "RO", "OA", "OC", "EF", "FK", "WV", "K2", "SB",
                 "A", "AE", "BE", "BH", "BO", "BR", "BT", "BU", "FA",
                 "NF", "RK", "RM", "gi", "gc"}

# ---------------------------------------------------------------------------
# Use-case 1: Larnhauserweg trams — no direction filter
# Both directions: Landgutstraße (→ Linz) and Schloss Traun / Trauner Kreuzung (← Linz)
# ---------------------------------------------------------------------------
LARNHAUSERWEG_ALL = _station_board_response(
    journeys=[
        _jny(0, "Landgutstraße",         "20260620", "080000", jid="t3-1"),
        _jny(1, "Landgutstraße",         "20260620", "080400", jid="t4-1"),
        _jny(0, "Schloss Traun",          "20260620", "080500", jid="t3-2"),
        _jny(1, "Trauner Kreuzung P&R",  "20260620", "080900", jid="t4-2"),
        _jny(0, "Landgutstraße",         "20260620", "081500", jid="t3-3"),
    ],
    prod_list=[_PROD_TRAM_3, _PROD_TRAM_4],
    op_list=[_LINZ_AG_OP],
    rem_list=[],
    him_list=[],
)

# With dirLoc=STOP_LINZ_HBF applied server-side — only Landgutstraße-bound trams.
LARNHAUSERWEG_VIA_LINZ_HBF = _station_board_response(
    journeys=[
        _jny(0, "Landgutstraße", "20260620", "080000", jid="t3-1"),
        _jny(1, "Landgutstraße", "20260620", "080400", jid="t4-1"),
        _jny(0, "Landgutstraße", "20260620", "081500", jid="t3-3"),
    ],
    prod_list=[_PROD_TRAM_3, _PROD_TRAM_4],
    op_list=[_LINZ_AG_OP],
    rem_list=[],
    him_list=[],
)

# ---------------------------------------------------------------------------
# Use-case 2: Linz Hbf → Wien (Westbahn / REX, plus RJ delayed, plus tram)
# prodX: 0=WB 111, 1=REX 1, 2=RJ 123, 3=tram 3
# ---------------------------------------------------------------------------
LINZ_HBF_WESTBAHN = _station_board_response(
    journeys=[
        _jny(3, "Landgutstraße",   "20260620", "080200", jid="t3-lhbf"),
        _jny(0, "Wien Westbahnhof","20260620", "081000", jid="wb-1"),
        _jny(1, "Wien Westbahnhof","20260620", "083000", jid="rex-1"),
        _jny(2, "Wien Hbf",        "20260620", "084500", time_r="085000", jid="rj-1"),
    ],
    prod_list=[_PROD_WB, _PROD_REX, _PROD_RJ, _PROD_TRAM_LHBF],
    op_list=[_LINZ_AG_OP, _WESTBAHN_OP, _OBB_OP],
    rem_list=[],
    him_list=[],
)

# ---------------------------------------------------------------------------
# Use-case 3: Innsbruck Hbf trams (IVB) — line 1 → Bergisel, line 3 → Amras
# ---------------------------------------------------------------------------
INNSBRUCK_HBF_TRAM = _station_board_response(
    journeys=[
        _jny(0, "Bergisel", "20260620", "092000", jid="ivb1-1"),
        _jny(1, "Amras",    "20260620", "092200", jid="ivb3-1"),
        _jny(0, "Bergisel", "20260620", "092800", jid="ivb1-2"),
    ],
    prod_list=[_PROD_IVB_1, _PROD_IVB_3],
    op_list=[_IVB_OP],
    rem_list=[],
    him_list=[],
)
