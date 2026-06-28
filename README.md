# Austria Transit — Home Assistant Integration

Departure monitor for **ÖBB trains**, **Linz AG trams & buses**, and all other Austrian public transport.

Uses the **ÖBB HAFAS mgate** (`fahrplan.oebb.at`) — the same backend as ÖBB's own journey planner. No API key or account required.

---

## Features

- Real-time departures with delay information
- Supports all Austrian operators: ÖBB, Linz AG, Wiener Linien, S-Bahn, regional buses
- Direction (via-stop) and line filtering per monitor
- Custom Lovelace card with color-coded delays
- Multiple departure sensors per stop (configurable 1–10)
- Works with automations (e.g. notify when train is delayed)

---

## Installation

### Manual (recommended)

1. Download or clone this repository
2. Copy `custom_components/austria_transit/` to your HA `config/custom_components/` folder
3. Copy `www/austria-transit-card.js` to `config/www/`
4. Restart Home Assistant

### Via HACS

HACS only supports GitHub repositories. If you want one-click HACS installation, mirror this repo to GitHub and add it as a custom repository there:

1. In HACS → **Integrations** → ⋮ → **Custom repositories**
2. Add your GitHub mirror URL — Category: **Integration**
3. Install "Austria Transit" and restart Home Assistant

---

## Setup

1. **Settings → Devices & Services → Add Integration → "Austria Transit"**
2. Type a stop name (e.g. `Linz Hbf`, `Simonystraße`, `Wien Westbahnhof`)
3. Pick the correct stop from the list
4. Optionally set a **via-stop** (direction filter by intermediate stop), **line filter** (e.g. `3` or `REX,WB`), or **terminus filter**
5. Choose how many departures to track (1–10) and the refresh interval (default 300 s)

Add multiple entries for multiple stops or directions.

---

## Dashboard Card

After copying `www/austria-transit-card.js`, register the resource in HA:

**Settings → Dashboards → ⋮ → Resources → Add**
- URL: `/local/austria-transit-card.js`
- Type: JavaScript module

### Lovelace YAML

```yaml
type: custom:austria-transit-card
entity: sensor.linz_hbf_next_departure
title: "Linz Hbf → Wien"
max_rows: 5
show_platform: true
show_remarks: true
```

### Card options

| Option | Default | Description |
|---|---|---|
| `entity` | required | The `_next_departure` sensor entity ID |
| `title` | stop name | Card header title |
| `max_rows` | 5 | Max departures shown |
| `show_platform` | true | Show track/platform number |
| `show_remarks` | true | Show delay/alert messages |
| `color_delayed` | `#e67e22` | Colour for delayed departures |
| `color_ontime` | `#2ecc71` | Colour for on-time countdown |
| `color_cancelled` | `#e74c3c` | Colour for cancelled |

---

## Automation Example

Notify when your train is delayed by more than 5 minutes:

```yaml
automation:
  - alias: "Train delay notification"
    trigger:
      - platform: template
        value_template: >
          {{ state_attr('sensor.linz_hbf_next_departure', 'delay_minutes') | int(0) > 5 }}
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "Train delayed"
          message: >
            {{ states('sensor.linz_hbf_next_departure') }} is delayed by
            {{ state_attr('sensor.linz_hbf_next_departure', 'delay_minutes') }} minutes.
```

---

## Finding Stop Names

Use the integration's built-in search or look up stop names at [fahrplan.oebb.at](https://fahrplan.oebb.at).

**Common Linz AG stops:** `Hauptplatz`, `Simonystraße`, `Universität`, `Bulgariplatz`, `Linz Hbf`

**Common ÖBB stops:** `Linz Hbf`, `Wien Hbf`, `Salzburg Hbf`, `Graz Hbf`

---

## Removal

1. **Settings → Devices & Services → Austria Transit** → select the entry → **Delete**
2. Repeat for each configured stop
3. Restart Home Assistant
4. Optionally remove `custom_components/austria_transit/` from your config directory and `www/austria-transit-card.js`

---

## Data Source

- API: ÖBB HAFAS mgate (`fahrplan.oebb.at/bin/mgate.exe`) — the same backend used by ÖBB's own journey planner
- Covers all operators in the Austrian national transport network
- No API key or account required; uses a public client identifier
- Default refresh interval: 300 s (configurable per monitor, minimum 30 s)
- The API base URL is configurable in the integration options if you need to point to a different HAFAS provider
