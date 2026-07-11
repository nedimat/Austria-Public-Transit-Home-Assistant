## Austria Transit

Real-time departure monitor for **ÖBB trains**, **Linz AG trams & buses**, and all other Austrian public transport — powered by the official ÖBB HAFAS mgate API. No API key required.

### Features

- Live departures with delay and cancellation info
- Filter by line (single or multiple: `3,4` or `WB,REX`) and via-stop
- Custom Lovelace cards: departure board + multi-leg commute view
- German and English UI
- Configurable 1–10 departure sensors per stop

### Installation

1. Install via HACS and restart Home Assistant
2. **Settings → Devices & Services → Add Integration → Austria Transit**
3. Register the Lovelace card resource once:
   **Settings → Dashboards → ⋮ → Resources → Add**
   URL: `/austria_transit/austria-transit-card.js` — Type: JavaScript module
