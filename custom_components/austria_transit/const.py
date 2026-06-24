DOMAIN = "austria_transit"

# /api prefix is required by oebb.transport.rest
API_BASE = "https://v6.oebb.transport.rest/api"

CONF_STOP_ID = "stop_id"
CONF_STOP_NAME = "stop_name"
CONF_DIRECTION_FILTER = "direction_filter"
CONF_LINE_FILTER = "line_filter"
CONF_VIA_STOP = "via_stop"          # user-facing search text
CONF_VIA_STOP_ID = "via_stop_id"    # resolved stop ID used for matching
CONF_VIA_STOP_NAME = "via_stop_name"  # resolved display name
CONF_MAX_DEPARTURES = "max_departures"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_MAX_DEPARTURES = 5
DEFAULT_SCAN_INTERVAL = 60  # seconds
DEFAULT_DURATION = 120  # minutes to look ahead

# Exact product values returned by oebb.transport.rest line.product field
PRODUCT_NAMES = {
    "nationalExpress": "RailJet/ICE",
    "national": "Intercity/EC",
    "interregional": "Interregional",
    "regional": "Regional",
    "suburban": "S-Bahn",
    "bus": "Bus",
    "ferry": "Ferry",
    "subway": "U-Bahn",
    "tram": "Tram",
    "onCall": "Rufbus",
}
