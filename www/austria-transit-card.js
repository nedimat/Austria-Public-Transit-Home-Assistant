// Remark codes that are purely accessibility/amenity info — never operationally relevant
const AMENITY_CODES = new Set([
  'OB','RO','OA','EF','OC','FR','FK','J2','OJ','CT','GP','SW','LW','MN','MC','WV',
]);

function operationalRemarks(remarks) {
  if (!remarks) return [];
  return remarks.filter(r => r && !AMENITY_CODES.has(r.code));
}

const TRANSLATIONS = {
  de: {
    entity_label: 'Entität (Nächste-Abfahrt-Sensor)',
    entity_placeholder: '— kein Sensor gefunden —',
    title_label: 'Titel (optional – Standard: Haltestellenname)',
    title_placeholder: 'z. B. Linz Hbf → Wien',
    max_rows_label: 'Anzahl der Abfahrten',
    display_section: 'Anzeigeoptionen',
    toggle_hero: 'Hero-Countdown',
    toggle_platform: 'Gleis anzeigen',
    toggle_product: 'Verkehrsmittel anzeigen',
    toggle_remarks: 'Betriebliche Hinweise',
    toggle_operator: 'Betreiber anzeigen',
    updated: 'aktualisiert',
    further: 'Weitere Abfahrten',
    no_departures: 'Keine Abfahrten gefunden',
    now: 'jetzt',
    cancelled: 'Ausfall',
    min: 'Min',
    platform: 'Gl.',
    products: {
      nationalExpress: 'RailJet/ICE', national: 'IC/EC',
      interregional: 'IR', regional: 'Regional',
      suburban: 'S-Bahn', bus: 'Bus', tram: 'Tram',
      ferry: 'Schiff', subway: 'U-Bahn', onCall: 'Rufbus',
    },
  },
  en: {
    entity_label: 'Entity (Next Departure sensor)',
    entity_placeholder: '— no sensor found —',
    title_label: 'Title (optional — defaults to stop name)',
    title_placeholder: 'e.g. Linz Hbf → Vienna',
    max_rows_label: 'Number of departures',
    display_section: 'Display options',
    toggle_hero: 'Hero countdown',
    toggle_platform: 'Show platform',
    toggle_product: 'Show vehicle type',
    toggle_remarks: 'Operational remarks',
    toggle_operator: 'Show operator',
    updated: 'updated',
    further: 'More departures',
    no_departures: 'No departures found',
    now: 'now',
    cancelled: 'Cancelled',
    min: 'min',
    platform: 'Pl.',
    products: {
      nationalExpress: 'RailJet/ICE', national: 'IC/EC',
      interregional: 'IR', regional: 'Regional',
      suburban: 'S-Bahn', bus: 'Bus', tram: 'Tram',
      ferry: 'Ferry', subway: 'Subway', onCall: 'On-call bus',
    },
  },
};

function t(hass, key) {
  const lang = ((hass && hass.language) || 'en').split('-')[0].toLowerCase();
  const dict = TRANSLATIONS[lang] || TRANSLATIONS['en'];
  const val = key.split('.').reduce((o, k) => (o && o[k] !== undefined ? o[k] : null), dict);
  if (val !== null) return val;
  return key.split('.').reduce((o, k) => (o && o[k] !== undefined ? o[k] : null), TRANSLATIONS['en']) ?? key;
}

function esc(s) {
  if (s == null) return '';
  return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}


// ─── Departure board card editor ──────────────────────────────────────────────

class AustriaTransitCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = config;
    this._rendered = false;
  }

  set hass(hass) {
    const needsRender = !this._hass || this._hass.language !== hass.language;
    this._hass = hass;
    if (!this._rendered || needsRender) this._render();
  }

  _render() {
    this._rendered = true;
    const c = this._config || {};
    const hass = this._hass;
    const entities = hass
      ? Object.keys(hass.states).filter(e => e.startsWith('sensor.') && e.endsWith('_next_departure')).sort()
      : [];

    const opts = entities.length
      ? entities.map(e => `<option value="${e}"${c.entity === e ? ' selected' : ''}>${e}</option>`).join('')
      : `<option value="${c.entity || ''}">${t(hass, 'entity_placeholder')}</option>`;

    this.innerHTML = `
      <style>
        .ed { display:flex; flex-direction:column; gap:16px; padding:4px 0; }
        .f { display:flex; flex-direction:column; gap:4px; }
        .f label { font-size:12px; font-weight:500; color:var(--secondary-text-color); }
        .f select,.f input[type=text],.f input[type=number] {
          width:100%; padding:8px 10px; font-size:14px;
          border:1px solid var(--divider-color,rgba(0,0,0,.2));
          border-radius:4px; background:var(--card-background-color);
          color:var(--primary-text-color); box-sizing:border-box;
        }
        .tg { display:grid; grid-template-columns:1fr 1fr; gap:8px; }
        .tl { display:flex; align-items:center; justify-content:space-between;
          padding:8px 10px; border:1px solid var(--divider-color,rgba(0,0,0,.12));
          border-radius:4px; font-size:13px; cursor:pointer; color:var(--primary-text-color); }
        .tl input { margin:0; cursor:pointer; width:16px; height:16px; }
        .sec { font-size:11px; font-weight:500; text-transform:uppercase;
          letter-spacing:.06em; color:var(--secondary-text-color); margin-bottom:-8px; }
      </style>
      <div class="ed">
        <div class="f"><label>${t(hass,'entity_label')}</label><select id="entity">${opts}</select></div>
        <div class="f"><label>${t(hass,'title_label')}</label>
          <input type="text" id="title" placeholder="${t(hass,'title_placeholder')}" value="${esc(c.title||'')}">
        </div>
        <div class="f" style="max-width:140px"><label>${t(hass,'max_rows_label')}</label>
          <input type="number" id="max_rows" min="1" max="10" value="${c.max_rows??5}">
        </div>
        <div class="sec">${t(hass,'display_section')}</div>
        <div class="tg">
          ${this._tgl('show_next_hero', t(hass,'toggle_hero'),    c.show_next_hero !== false)}
          ${this._tgl('show_platform',  t(hass,'toggle_platform'), c.show_platform  !== false)}
          ${this._tgl('show_product',   t(hass,'toggle_product'),  c.show_product   !== false)}
          ${this._tgl('show_remarks',   t(hass,'toggle_remarks'),  c.show_remarks   !== false)}
          ${this._tgl('show_operator',  t(hass,'toggle_operator'), c.show_operator  === true)}
        </div>
      </div>`;

    this.querySelectorAll('select,input').forEach(el => el.addEventListener('change', () => this._changed()));
  }

  _tgl(id, label, checked) {
    return `<label class="tl"><span>${label}</span><input type="checkbox" id="${id}"${checked ? ' checked' : ''}></label>`;
  }

  _changed() {
    const entity = this.querySelector('#entity').value;
    if (!entity) return;
    const title = this.querySelector('#title').value.trim();
    const cfg = {
      ...this._config,
      entity,
      max_rows:       parseInt(this.querySelector('#max_rows').value) || 5,
      show_next_hero: this.querySelector('#show_next_hero').checked,
      show_platform:  this.querySelector('#show_platform').checked,
      show_product:   this.querySelector('#show_product').checked,
      show_remarks:   this.querySelector('#show_remarks').checked,
      show_operator:  this.querySelector('#show_operator').checked,
    };
    if (title) cfg.title = title; else delete cfg.title;
    this.dispatchEvent(new CustomEvent('config-changed', { detail: { config: cfg }, bubbles: true, composed: true }));
  }
}

customElements.define('austria-transit-card-editor', AustriaTransitCardEditor);


// ─── Departure board card ─────────────────────────────────────────────────────

class AustriaTransitCard extends HTMLElement {
  static getConfigElement() { return document.createElement('austria-transit-card-editor'); }

  static getStubConfig(hass) {
    const entity = Object.keys(hass.states).find(e => e.startsWith('sensor.') && e.endsWith('_next_departure')) || '';
    return { entity, show_next_hero: true, show_platform: true, show_product: true, show_remarks: true, max_rows: 5 };
  }

  setConfig(config) {
    if (!config.entity) throw new Error('Required: entity');
    this._config = {
      entity:         config.entity,
      title:          config.title || null,
      max_rows:       config.max_rows || 5,
      show_next_hero: config.show_next_hero !== false,
      show_platform:  config.show_platform !== false,
      show_product:   config.show_product !== false,
      show_remarks:   config.show_remarks !== false,
      show_operator:  config.show_operator || false,
    };
  }

  set hass(hass) {
    if (!this._root) this._initShadow();
    this._hass = hass;
    this._render();
  }

  getCardSize() { return 4; }

  _initShadow() {
    const shadow = this.attachShadow({ mode: 'open' });
    shadow.innerHTML = `<style>${css()}</style><div id="r"></div>`;
    this._root = shadow.getElementById('r');
  }

  _render() {
    const hass = this._hass;
    const state = hass.states[this._config.entity];
    if (!state) {
      this._root.innerHTML = `<ha-card><div class="error">Entity not found: ${esc(this._config.entity)}</div></ha-card>`;
      return;
    }
    const attrs = state.attributes;
    const departures = (attrs.departure_list || []).slice(0, this._config.max_rows);
    const title = this._config.title || attrs.stop_name || state.entity_id;
    const updated = state.last_updated
      ? `${t(hass,'updated')} ${new Date(state.last_updated).toLocaleTimeString(hass.language||'de-AT',{hour:'2-digit',minute:'2-digit'})}`
      : '';

    const hero = this._config.show_next_hero && departures.length
      ? renderHero(departures[0], this._config, hass) : '';
    const rest = this._config.show_next_hero ? departures.slice(1) : departures;

    this._root.innerHTML = `
      <ha-card>
        <div class="hdr">
          <div class="hdr-t"><ha-icon icon="mdi:train"></ha-icon><span>${esc(title)}</span></div>
          <span class="hdr-u">${updated}</span>
        </div>
        ${hero}
        ${rest.length ? `<div class="sec-lbl">${t(hass,'further')}</div>${rest.map(d => renderRow(d, this._config, hass)).join('')}` : ''}
        ${!departures.length ? `<div class="empty">${t(hass,'no_departures')}</div>` : ''}
      </ha-card>`;
  }
}

customElements.define('austria-transit-card', AustriaTransitCard);


// ─── Commute card editor ──────────────────────────────────────────────────────

class AustriaTransitCommuteEditor extends HTMLElement {
  setConfig(config) { this._config = config; this._rendered = false; }

  set hass(hass) {
    const needsRender = !this._hass || this._hass.language !== hass.language;
    this._hass = hass;
    if (!this._rendered || needsRender) this._render();
  }

  _render() {
    this._rendered = true;
    const c = this._config || {};
    const hass = this._hass;
    const entities = hass
      ? Object.keys(hass.states).filter(e => e.startsWith('sensor.') && e.endsWith('_next_departure')).sort()
      : [];
    const legs = c.legs || [{}];

    const legHtml = legs.map((leg, i) => {
      const opts = entities.map(e => `<option value="${e}"${leg.entity===e?' selected':''}>${e}</option>`).join('');
      return `
        <div class="leg" data-i="${i}">
          <div class="leg-head">
            <span style="font-size:12px;font-weight:500;color:var(--secondary-text-color)">Leg ${i+1}</span>
            ${i > 0 ? `<button class="rm" data-i="${i}">✕</button>` : ''}
          </div>
          <div class="f"><label>Sensor</label><select class="leg-entity">${opts}</select></div>
          <div class="f"><label>Label</label><input type="text" class="leg-label" placeholder="e.g. Tram 3 → Linz Hbf" value="${esc(leg.label||'')}"></div>
        </div>`;
    }).join('');

    this.innerHTML = `
      <style>
        .ed{display:flex;flex-direction:column;gap:16px;padding:4px 0}
        .f{display:flex;flex-direction:column;gap:4px}
        .f label{font-size:12px;font-weight:500;color:var(--secondary-text-color)}
        .f select,.f input[type=text]{width:100%;padding:8px 10px;font-size:14px;
          border:1px solid var(--divider-color,rgba(0,0,0,.2));border-radius:4px;
          background:var(--card-background-color);color:var(--primary-text-color);box-sizing:border-box}
        .leg{border:1px solid var(--divider-color,rgba(0,0,0,.12));border-radius:6px;padding:12px;display:flex;flex-direction:column;gap:10px}
        .leg-head{display:flex;align-items:center;justify-content:space-between}
        .rm{background:none;border:none;cursor:pointer;color:var(--secondary-text-color);font-size:14px;padding:0}
        .add{padding:8px;border:1px dashed var(--divider-color,rgba(0,0,0,.2));border-radius:6px;
          background:none;cursor:pointer;color:var(--primary-color);font-size:13px;width:100%}
      </style>
      <div class="ed">
        <div class="f"><label>Title (optional)</label>
          <input type="text" id="title" placeholder="My commute" value="${esc(c.title||'')}">
        </div>
        ${legHtml}
        <button class="add" id="add-leg">+ Add leg</button>
      </div>`;

    this.querySelector('#add-leg').addEventListener('click', () => {
      const cur = (this._config.legs || [{}]).slice();
      cur.push({});
      this._fire({ ...this._config, legs: cur });
    });
    this.querySelectorAll('.rm').forEach(btn => btn.addEventListener('click', e => {
      const i = parseInt(e.target.dataset.i);
      const cur = (this._config.legs || []).filter((_, idx) => idx !== i);
      this._fire({ ...this._config, legs: cur });
    }));
    this.querySelectorAll('input,select').forEach(el => el.addEventListener('change', () => this._changed()));
  }

  _changed() {
    const title = this.querySelector('#title').value.trim();
    const legs = [...this.querySelectorAll('.leg')].map(leg => ({
      entity: leg.querySelector('.leg-entity').value,
      label:  leg.querySelector('.leg-label').value.trim() || undefined,
    }));
    const cfg = { ...this._config, legs };
    if (title) cfg.title = title; else delete cfg.title;
    this._fire(cfg);
  }

  _fire(cfg) {
    this._config = cfg;
    this.dispatchEvent(new CustomEvent('config-changed', { detail: { config: cfg }, bubbles: true, composed: true }));
  }
}

customElements.define('austria-transit-commute-editor', AustriaTransitCommuteEditor);


// ─── Commute card ─────────────────────────────────────────────────────────────

class AustriaTransitCommuteCard extends HTMLElement {
  static getConfigElement() { return document.createElement('austria-transit-commute-editor'); }

  static getStubConfig(hass) {
    const first = Object.keys(hass.states).find(e => e.startsWith('sensor.') && e.endsWith('_next_departure')) || '';
    return { legs: [{ entity: first, label: 'Leg 1' }] };
  }

  setConfig(config) {
    if (!config.legs || !config.legs.length) throw new Error('At least one leg required');
    this._config = config;
  }

  set hass(hass) {
    if (!this._root) this._initShadow();
    this._hass = hass;
    this._render();
  }

  getCardSize() { return Math.max(3, this._config.legs.length + 1); }

  _initShadow() {
    const shadow = this.attachShadow({ mode: 'open' });
    shadow.innerHTML = `<style>${css()}${commuteCss()}</style><div id="r"></div>`;
    this._root = shadow.getElementById('r');
  }

  _render() {
    const hass = this._hass;
    const title = this._config.title || (hass.language||'').startsWith('de') ? 'Mein Pendlerweg' : 'My commute';

    const legsHtml = this._config.legs.map((leg, i) => {
      const state = leg.entity ? hass.states[leg.entity] : null;
      if (!state) return `<div class="cl-leg cl-err">Entity not found: ${esc(leg.entity)}</div>`;

      const attrs = state.attributes;
      const deps = attrs.departure_list || [];
      const first = deps[0];
      const second = deps[1];
      const label = leg.label || attrs.stop_name || leg.entity;
      const isLast = i === this._config.legs.length - 1;

      let mainHtml;
      if (!first) {
        mainHtml = `<div class="cl-none">${t(hass,'no_departures')}</div>`;
      } else {
        const mins = first.minutes_until;
        const delayed = first.delay_minutes > 0;
        const cancelled = first.cancelled;
        const remarks = operationalRemarks(first.remarks || []);

        let timeStr;
        if (cancelled) timeStr = `<span class="cl-cancel">${t(hass,'cancelled')}</span>`;
        else if (mins === 0) timeStr = `<span class="cl-now">${t(hass,'now')}</span>`;
        else if (mins < 60) timeStr = `<span class="${delayed?'cl-delay':'cl-ok'}">${mins} ${t(hass,'min')}</span>${delayed?` <span class="cl-dlt">+${first.delay_minutes}</span>`:''}`;
        else timeStr = `<span class="${delayed?'cl-delay':''}">${esc(first.time)}</span>${delayed?` <span class="cl-dlt">+${first.delay_minutes}</span>`:''}`;

        const nextDep = second
          ? `<span class="cl-next">${t(hass,'further').replace('Weitere ','')||'next'}: ${second.minutes_until < 60 ? second.minutes_until+' '+t(hass,'min') : esc(second.time)}</span>`
          : '';

        mainHtml = `
          <div class="cl-main">
            <span class="badge ${first.product||''}">${esc(first.line)}</span>
            <div class="cl-info">
              <div class="cl-dir">${esc(first.direction)}</div>
              <div class="cl-sub">${first.platform ? `${t(hass,'platform')} ${esc(first.platform)} · ` : ''}${nextDep}</div>
              ${remarks.length ? `<div class="remark">⚠ ${esc(remarks[0].text)}</div>` : ''}
            </div>
            <div class="cl-time">${timeStr}</div>
          </div>`;
      }

      return `
        <div class="cl-leg">
          <div class="cl-label">${esc(label)}</div>
          ${mainHtml}
        </div>
        ${!isLast ? '<div class="cl-arrow">↓</div>' : ''}`;
    }).join('');

    this._root.innerHTML = `
      <ha-card>
        <div class="hdr">
          <div class="hdr-t"><ha-icon icon="mdi:map-marker-path"></ha-icon><span>${esc(title)}</span></div>
        </div>
        <div class="cl-body">${legsHtml}</div>
      </ha-card>`;
  }
}

customElements.define('austria-transit-commute-card', AustriaTransitCommuteCard);


// ─── Shared render helpers ────────────────────────────────────────────────────

function renderHero(dep, cfg, hass) {
  const mins = dep.minutes_until;
  const delayed = dep.delay_minutes > 0;
  const cancelled = dep.cancelled;
  const remarks = operationalRemarks(dep.remarks || []);

  let countdown;
  if (cancelled) {
    countdown = `<div class="hero-mins cancelled">${t(hass,'cancelled')}</div>`;
  } else if (mins === 0) {
    countdown = `<div class="hero-mins now">${t(hass,'now')}</div>`;
  } else {
    countdown = `<div class="hero-mins${delayed?' delayed':''}">${mins}</div>
      <div class="hero-mins-label">${t(hass,'min')}${delayed?` <span class="delay-tag">+${dep.delay_minutes}</span>`:''}</div>`;
  }

  const sub = [
    cfg.show_product ? t(hass,`products.${dep.product}`) : null,
    cfg.show_platform && dep.platform ? `${t(hass,'platform')} ${esc(dep.platform)}` : null,
    cfg.show_operator && dep.operator ? esc(dep.operator) : null,
  ].filter(Boolean).join(' · ');

  return `
    <div class="hero${cancelled?' cancelled':''}">
      <div class="hero-left">
        <span class="badge ${dep.product||''}">${esc(dep.line)}</span>
        <div>
          <div class="hero-direction">${esc(dep.direction)}</div>
          ${sub ? `<div class="hero-sub">${sub}</div>` : ''}
          ${cfg.show_remarks && remarks.length ? `<div class="remark">⚠ ${esc(remarks[0].text)}</div>` : ''}
        </div>
      </div>
      <div class="hero-right">${countdown}</div>
    </div>`;
}

function renderRow(dep, cfg, hass) {
  const mins = dep.minutes_until;
  const delayed = dep.delay_minutes > 0;
  const cancelled = dep.cancelled;
  const remarks = operationalRemarks(dep.remarks || []);

  let timeEl;
  if (cancelled) {
    timeEl = `<div class="time cancelled">${esc(dep.scheduled_time||dep.time)}</div>
              <div class="delay" style="color:var(--error-color,#f44336)">${t(hass,'cancelled')}</div>`;
  } else if (mins === 0) {
    timeEl = `<div class="time-now">${t(hass,'now')}</div>`;
  } else if (mins < 60) {
    timeEl = `<div class="time${delayed?' delayed':''}">${mins} ${t(hass,'min')}</div>`;
    if (delayed) timeEl += `<div class="delay">+${dep.delay_minutes} ${t(hass,'min')}</div>`;
  } else {
    timeEl = `<div class="time${delayed?' delayed':''}">${esc(dep.time)}</div>`;
    if (delayed) timeEl += `<div class="delay">+${dep.delay_minutes} ${t(hass,'min')}</div>`;
  }

  const sub = [
    cfg.show_product ? t(hass,`products.${dep.product}`) : null,
    cfg.show_platform && dep.platform ? `${t(hass,'platform')} ${esc(dep.platform)}` : null,
  ].filter(Boolean).join(' · ');

  return `
    <div class="row${cancelled?' cancelled':''}">
      <span class="badge ${dep.product||''}">${esc(dep.line)}</span>
      <div class="row-meta">
        <div class="row-direction">${esc(dep.direction)}</div>
        ${sub||remarks.length ? `<div class="row-sub">${sub}${cfg.show_remarks&&remarks.length?` ${sub?'· ':''}<span class="remark-inline">⚠ ${esc(remarks[0].text)}</span>`:''}</div>` : ''}
      </div>
      <div class="row-time">${timeEl}</div>
    </div>`;
}


// ─── Shared CSS ───────────────────────────────────────────────────────────────

function css() {
  return `
    :host{display:block}
    ha-card{overflow:hidden}
    .error{padding:16px;color:var(--error-color,red);font-size:13px}
    .empty{padding:20px 16px;text-align:center;font-size:13px;color:var(--secondary-text-color);font-style:italic}
    .hdr{display:flex;align-items:center;justify-content:space-between;padding:12px 16px;border-bottom:1px solid var(--divider-color,rgba(0,0,0,.12))}
    .hdr-t{display:flex;align-items:center;gap:8px;font-size:14px;font-weight:500;color:var(--primary-text-color)}
    .hdr-t ha-icon{--mdc-icon-size:18px;color:var(--secondary-text-color)}
    .hdr-u{font-size:11px;color:var(--secondary-text-color)}
    .hero{display:flex;align-items:center;justify-content:space-between;padding:14px 16px;gap:12px;border-bottom:1px solid var(--divider-color,rgba(0,0,0,.12))}
    .hero.cancelled{opacity:.6}
    .hero-left{display:flex;align-items:center;gap:12px;flex:1;min-width:0}
    .hero-direction{font-size:15px;font-weight:500;color:var(--primary-text-color)}
    .hero-sub{font-size:12px;color:var(--secondary-text-color);margin-top:2px}
    .hero-right{text-align:right;flex-shrink:0}
    .hero-mins{font-size:30px;font-weight:500;line-height:1;color:var(--primary-text-color)}
    .hero-mins.now{font-size:14px;font-weight:500;background:var(--success-color,#4caf50);color:#fff;padding:4px 10px;border-radius:12px}
    .hero-mins.delayed{color:var(--warning-color,#ff9800)}
    .hero-mins.cancelled{font-size:13px;color:var(--error-color,#f44336);font-weight:500}
    .hero-mins-label{font-size:11px;color:var(--secondary-text-color);margin-top:3px}
    .delay-tag{color:var(--warning-color,#ff9800);font-weight:500}
    .sec-lbl{font-size:10px;font-weight:500;letter-spacing:.06em;color:var(--secondary-text-color);padding:8px 16px 2px;text-transform:uppercase}
    .row{display:grid;grid-template-columns:48px 1fr auto;align-items:center;gap:10px;padding:9px 16px;border-bottom:1px solid var(--divider-color,rgba(0,0,0,.08))}
    .row:last-child{border-bottom:none}
    .row.cancelled{opacity:.55}
    .row-meta{min-width:0}
    .row-direction{font-size:13px;font-weight:500;color:var(--primary-text-color);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    .row-sub{font-size:11px;color:var(--secondary-text-color);margin-top:1px}
    .row-time{text-align:right;white-space:nowrap}
    .badge{display:inline-flex;align-items:center;justify-content:center;font-size:11px;font-weight:500;padding:3px 7px;border-radius:4px;min-width:36px;text-align:center;color:#fff;background:#555}
    .badge.tram{background:#b91c1c}
    .badge.bus{background:#1d4ed8}
    .badge.suburban{background:#15803d}
    .badge.national,.badge.nationalExpress{background:#7e22ce}
    .badge.regional,.badge.interregional{background:#0e7490}
    .badge.subway{background:#92400e}
    .badge.onCall{background:#71717a}
    .time{font-size:14px;font-weight:500;color:var(--primary-text-color)}
    .time.delayed{color:var(--warning-color,#ff9800)}
    .time.cancelled{text-decoration:line-through;color:var(--error-color,#f44336)}
    .time-now{font-size:12px;font-weight:500;background:var(--success-color,#4caf50);color:#fff;padding:2px 8px;border-radius:10px}
    .delay{font-size:11px;color:var(--warning-color,#ff9800);margin-top:1px}
    .remark{font-size:11px;color:var(--warning-color,#ff9800);margin-top:3px}
    .remark-inline{color:var(--warning-color,#ff9800)}
  `;
}

function commuteCss() {
  return `
    .cl-body{padding:12px 16px;display:flex;flex-direction:column;gap:0}
    .cl-leg{padding:10px 0}
    .cl-label{font-size:11px;font-weight:500;text-transform:uppercase;letter-spacing:.06em;color:var(--secondary-text-color);margin-bottom:6px}
    .cl-main{display:flex;align-items:center;gap:10px}
    .cl-info{flex:1;min-width:0}
    .cl-dir{font-size:14px;font-weight:500;color:var(--primary-text-color);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    .cl-sub{font-size:11px;color:var(--secondary-text-color);margin-top:1px}
    .cl-time{white-space:nowrap;text-align:right;font-size:14px;font-weight:500}
    .cl-ok{color:var(--success-color,#4caf50)}
    .cl-delay{color:var(--warning-color,#ff9800)}
    .cl-dlt{font-size:11px;color:var(--warning-color,#ff9800)}
    .cl-cancel{color:var(--error-color,#f44336)}
    .cl-now{font-size:12px;font-weight:500;background:var(--success-color,#4caf50);color:#fff;padding:2px 8px;border-radius:10px}
    .cl-next{color:var(--secondary-text-color)}
    .cl-none{font-size:13px;color:var(--secondary-text-color);font-style:italic}
    .cl-err{font-size:13px;color:var(--error-color,red)}
    .cl-arrow{text-align:center;font-size:16px;color:var(--divider-color,rgba(0,0,0,.3));padding:2px 0;line-height:1}
  `;
}


// ─── Registration ─────────────────────────────────────────────────────────────

window.customCards = window.customCards || [];
window.customCards.push(
  { type: 'austria-transit-card', name: 'Austria Transit', description: 'Departure monitor for ÖBB & Linz AG' },
  { type: 'austria-transit-commute-card', name: 'Austria Transit: Commute', description: 'Multi-leg commute view' },
);
