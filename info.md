## Austria Transit

Real-time departure monitor for **ÖBB trains**, **Linz AG trams & buses**, and all other Austrian public transport — powered by the free [oebb.transport.rest](https://v6.oebb.transport.rest/) HAFAS API. No API key required.

### Features

- Live departures with delay and cancellation info
- Filter by line (single or multiple: `3,4` or `WB,REX`) and via-stop
- Custom Lovelace cards: departure board + multi-leg commute view
- German and English UI
- Configurable 1–10 departure sensors per stop

### Installation

Copy `custom_components/austria_transit/` to `config/custom_components/` and `www/austria-transit-card.js` to `config/www/`, then restart Home Assistant.

After restart: **Settings → Devices & Services → Add Integration → Austria Transit**

Register the card as a Lovelace resource: **Settings → Dashboards → ⋮ → Resources → Add** → URL `/local/austria-transit-card.js` → JavaScript module
