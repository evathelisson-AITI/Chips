// Deal review page (served by curate.py on 127.0.0.1). Feed text is untrusted:
// everything is inserted with textContent, and links only accept http(s).
'use strict';

const $ = id => document.getElementById(id);
let S = null;            // last state from the server
let tab = 'leads';
let openKey = null;      // the card whose form is open
let adding = false;
let toastTimer = null;

function safeUrl(u) {
  try { const x = new URL(String(u || '')); return /^https?:$/.test(x.protocol) ? x.href : null; }
  catch { return null; }
}

function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === 'class') el.className = v;
    else if (k === 'text') el.textContent = v;
    else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? '' : v);
  }
  for (const c of kids.flat(Infinity)) if (c != null && c !== false) el.append(c instanceof Node ? c : String(c));
  return el;
}

function ext(href, text, cls) {
  const u = safeUrl(href);
  return u ? h('a', { href: u, target: '_blank', rel: 'noopener noreferrer', class: cls }, text) : null;
}

const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
function fmtDate(s) {
  const m = /^(\d{4})-(\d{2})(?:-(\d{2}))?/.exec(s || '');
  if (!m) return s || '';
  return (m[3] ? +m[3] + ' ' : '') + MONTHS[+m[2] - 1] + ' ' + m[1];
}

const TIERS = { primary: 'Primary source', rating: 'Rating agency', press1: 'Reuters / Bloomberg / FT',
                press2: 'Trade press', other: 'Other outlet', spam: 'Spam outlet' };

function suggestion(text) {
  if (!text || /^REVIEW-manually/.test(text)) return null;
  const m = /^([A-Z-]+?)(?:-(candidate|suggested|ONLY|SOURCE))?\s*(?:\((.*)\))?\s*$/.exec(text);
  let cls = 'neutral', label = text;
  if (/^VERIFIED/.test(text)) { cls = 'good'; label = 'Looks VERIFIED-able'; }
  else if (/^REPORTED/.test(text)) { cls = 'ok'; label = 'Looks REPORTED-able'; }
  else if (/^REJECT/.test(text)) { cls = 'bad'; label = 'Suggested reject'; }
  else if (/^NEEDS-PRIMARY/.test(text)) { cls = 'warn'; label = 'Needs a primary source'; }
  else if (/^COMMENTARY/.test(text)) { cls = 'warn'; label = 'Commentary, no deal'; }
  else if (/^LINK-TO/.test(text)) { cls = 'warn'; label = text.replace(/\s*\(.*/, '').replace('LINK-TO', 'Related to'); }
  const why = m && m[3] ? m[3] : '';
  return h('div', { class: 'sugg ' + cls }, h('b', { text: label }), why ? ' — ' + why : '');
}

// ------------------------------------------------------------ network
async function api(path, body) {
  const opts = body === undefined ? {} : {
    method: 'POST', body: JSON.stringify(body),
    headers: { 'Content-Type': 'application/json', 'X-Curator': '1' },
  };
  let res;
  try { res = await fetch('/api/' + path, opts); }
  catch { throw new Error('Cannot reach curate.py. Is it still running in the terminal?'); }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || 'Request failed (' + res.status + ')');
  return data;
}

async function load() {
  try { S = await api('state'); render(); }
  catch (e) { $('list').replaceChildren(h('p', { class: 'empty err', text: e.message })); }
}

async function send(action, body, after) {
  try {
    const r = await api(action, body);
    S = r.state;
    if (after) after();
    render();
    toast(r.message);
    return true;
  } catch (e) {
    toast(e.message, true);
    return false;
  }
}

function toast(msg, isErr) {
  const t = $('toast');
  $('toast-msg').textContent = msg;
  t.classList.toggle('err', !!isErr);
  $('toast-undo').classList.toggle('hidden', !!isErr || !(S && S.undo));
  t.classList.remove('hidden');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.add('hidden'), isErr ? 9000 : 7000);
}

// ------------------------------------------------------------ form
const EXTRA = ['collateral', 'amount_musd', 'amount_kind', 'lenders', 'rate', 'maturity', 'rating',
  'gpu_generation', 'vendor_role', 'announced', 'closed', 'parent_id'];
const COLLATERAL_OPTS = [
  ['gpu-lien', 'Lien on GPUs / GPU servers'],
  ['spv-owned-leased', 'Chips owned by an SPV and leased out'],
  ['contract-cashflows', 'Backed by compute contracts, not chips (related, not counted)'],
  ['none-or-unclear', 'No chip collateral shown (related, not counted)'],
];
function field(label, input, hint, wide) {
  return h('label', { class: 'f' + (wide ? ' wide' : '') },
    h('span', { class: 'fl', text: label }), input, hint ? h('span', { class: 'fh', text: hint }) : null);
}

function dealForm(item) {
  const d = item.draft;
  const key = item.kind + ':' + item.ref;
  const listId = s => 'dl-' + s;
  const inp = (name, attrs) => h('input', { name, value: d[name] || '', autocomplete: 'off', ...attrs });
  const verChoice = (v, title, sub) => h('label', { class: 'ver-opt ver-' + v.toLowerCase() },
    h('input', { type: 'radio', name: 'ver-' + key, value: v, checked: d.ver === v }),
    h('span', {}, h('b', { text: title }), h('small', { text: sub })));
  const err = h('p', { class: 'form-err', role: 'alert' });
  const isEdit = item.kind === 'published';

  const auto = Array.isArray(item.auto) ? item.auto : [];
  const autoNote = auto.length ? h('p', { class: 'auto-note', text: item.kind === 'published'
      ? `${auto.length} empty detail field${auto.length > 1 ? 's were' : ' was'} suggested from the stored text (highlighted). Check before saving.`
      : `Filled in automatically from the headlines and known sources (highlighted fields). Open the source, correct anything that differs, then choose VERIFIED or REPORTED.` }) : null;
  const form = h('form', { class: 'deal-form', novalidate: true },
    autoNote,
    h('div', { class: 'grid' },
      field('Deal name', inp('name', { placeholder: 'Who borrowed what from whom, e.g. "IREN $2.4bn GPU financing (Blue Owl-led)"' }), null, true),
      field('Date', inp('date', { placeholder: 'YYYY-MM or YYYY-MM-DD', inputmode: 'numeric' }), 'Month is enough'),
      field('Type', inp('type', { list: listId('types'), placeholder: 'Pick or type' })),
      field('Amount', inp('amount', { placeholder: 'e.g. 2,400 M' }), 'USD millions, written like "2,400 M"'),
      field('Status', inp('status', { list: listId('statuses'), placeholder: 'Pick or type' })),
      field('Terms', h('textarea', { name: 'terms', rows: 3,
        placeholder: 'Lenders, rate, tenor, collateral, anything notable. Your own words, not copied text.' }, d.terms || ''), null, true),
      field('Source (as shown on the site)', inp('src', { placeholder: 'e.g. IREN press release, 09/2026' })),
      field('Link to the source', inp('url', { type: 'url', placeholder: 'https://…' }), 'Required for VERIFIED. Best: the filing or the issuer’s press release'),
    ),
    h('details', { class: 'extra', open: EXTRA.some(k => d[k]) },
      h('summary', { text: 'Structured details (optional, used for counts and totals)' }),
      h('div', { class: 'grid' },
        field('Collateral', h('select', { name: 'collateral' },
          h('option', { value: '', text: 'Not classified yet' }),
          COLLATERAL_OPTS.map(([v, label]) => h('option', { value: v, text: label, selected: d.collateral === v }))),
          'Only the first two count as chip-backed debt'),
        field('Amount in USD millions', inp('amount_musd', { placeholder: 'e.g. 2400', inputmode: 'decimal' }), 'A number; used for the total'),
        field('Amount is', inp('amount_kind', { list: listId('amount-kinds'), placeholder: 'committed, drawn, outstanding, up-to' })),
        field('Lenders', inp('lenders', { placeholder: 'e.g. Blackstone, Magnetar (lead)' })),
        field('Rate', inp('rate', { placeholder: 'e.g. SOFR+4.00%' })),
        field('Maturity', inp('maturity', { placeholder: 'e.g. 2031 or 5y' })),
        field('Rating', inp('rating', { placeholder: 'e.g. A3 (Moody’s)' })),
        field('Collateral GPUs', inp('gpu_generation', { placeholder: 'e.g. H100, GB200' })),
        field('Vendor role', inp('vendor_role', { placeholder: 'e.g. Nvidia anchor LP, backstop' })),
        field('Announced', inp('announced', { placeholder: 'YYYY-MM-DD' }), 'Day precision helps event studies'),
        field('Closed', inp('closed', { placeholder: 'YYYY-MM-DD' })),
        field('Related deal id', inp('parent_id', { placeholder: 'e.g. d86783e0f42' }), 'Upsize, refinancing or second tranche of'))),
    h('fieldset', { class: 'ver' },
      h('legend', { text: 'How did you check it?' }),
      verChoice('VERIFIED', 'VERIFIED', 'I read the primary source: a filing or the issuer’s own press release'),
      verChoice('REPORTED', 'REPORTED', 'Press coverage only (Reuters, Bloomberg, FT, trade press)')),
    err,
    h('div', { class: 'form-actions' },
      h('button', { type: 'submit', class: 'btn primary', text: isEdit ? 'Save changes' : 'Publish to site' }),
      h('button', { type: 'button', class: 'btn ghost', text: 'Cancel', onclick: () => { openKey = null; adding = false; render(); } })));

  form.addEventListener('submit', async ev => {
    ev.preventDefault();
    const fd = new FormData(form);
    const values = {};
    for (const k of ['date', 'name', 'type', 'amount', 'terms', 'status', 'src', 'url', ...EXTRA]) values[k] = String(fd.get(k) || '');
    values.ver = String(fd.get('ver-' + key) || '');
    if (!values.ver) { err.textContent = 'Choose VERIFIED or REPORTED.'; return; }
    if (values.ver === 'VERIFIED' && !values.url) { err.textContent = 'VERIFIED needs a link to the primary source.'; return; }
    err.textContent = '';
    const btn = form.querySelector('button[type=submit]');
    btn.disabled = true;
    try {
      const r = await api('approve', { kind: item.kind, ref: item.ref, form: values });
      S = r.state; openKey = null; adding = false;
      render(); toast(r.message);
    } catch (e) {
      err.textContent = e.message;
    } finally { btn.disabled = false; }
  });
  // Highlight guessed fields until the curator touches them.
  for (const k of auto) {
    const el = form.querySelector(`[name="${k}"]`);
    if (!el) continue;
    el.classList.add('auto');
    el.title = 'Auto-filled: check against the source';
    const clear = () => el.classList.remove('auto');
    el.addEventListener('input', clear, { once: true });
    el.addEventListener('change', clear, { once: true });
  }
  return form;
}

// ------------------------------------------------------------ cards
function card(item) {
  const key = item.kind + ':' + item.ref;
  const open = openKey === key;
  const hint = item.hint || {};
  const pub = item.kind === 'published';

  const badges = [];
  if (pub) badges.push(h('span', { class: 'badge ver-' + item.ver.toLowerCase(), text: item.ver }));
  else if (item.kind === 'candidate') badges.push(h('span', { class: 'badge new', text: 'New from watch' }));
  if (item.followup) badges.push(h('span', { class: 'badge', text: 'Follow-up' }));

  const meta = h('div', { class: 'meta-line' },
    h('span', { text: fmtDate(item.date) }),
    item.outlet ? h('span', { text: item.outlet }) : null,
    !pub && hint.tier ? h('span', { class: 'tier tier-' + hint.tier, text: TIERS[hint.tier] || hint.tier }) : null,
    ...badges);

  const links = h('div', { class: 'links' },
    ext(item.url, pub ? 'Source ↗' : 'Open source ↗', 'open'),
    ...(hint.primary_links || []).map(u => ext(u, 'Primary source ↗', 'primary-link')));

  let more = null;
  if (item.sources.length) {
    more = h('details', { class: 'more' },
      h('summary', { text: `${item.sources.length} other article${item.sources.length > 1 ? 's' : ''} on this story` }),
      h('ul', {}, item.sources.map(s => h('li', {},
        h('span', { class: 'muted', text: fmtDate(s.date) + ' · ' }),
        ext(s.url, (s.outlet || 'link') + (s.title ? ': ' + s.title : ''))))));
  }

  let search = null;
  if (!pub && (hint.search_links || []).length) {
    search = h('div', { class: 'search' }, h('span', { class: 'muted', text: 'Find the primary source: ' }),
      hint.search_links.map((u, i) => [i ? ' · ' : '', ext(u, /sec\.gov/.test(u) ? 'SEC EDGAR' : 'Press-release wires')]));
  }

  const body = h('div', { class: 'card-main' },
    meta,
    h('h3', { text: pub ? item.name : (item.draft.name || item.name) }),
    pub ? h('p', { class: 'facts' },
      [item.type, item.amount, item.status].filter(Boolean).join(' · ')) : null,
    pub && item.terms ? h('p', { class: 'terms', text: item.terms }) : null,
    !pub ? suggestion(hint.suggestion) : null,
    !pub && item.excerpt ? h('p', { class: 'excerpt', title: 'Feed excerpt, for you only. Not published.', text: item.excerpt }) : null,
    links, more, search);

  const actions = h('div', { class: 'card-actions' },
    open ? null : h('button', { type: 'button', class: pub ? 'btn' : 'btn primary', text: pub ? 'Edit' : 'Approve…',
      onclick: () => { openKey = key; adding = false; render(); focusForm(key); } }),
    h('button', { type: 'button', class: 'btn ' + (pub ? 'ghost danger' : 'ghost'), text: pub ? 'Remove' : 'Reject',
      onclick: () => {
        if (pub && !confirm('Take "' + item.name + '" off the site?')) return;
        send('reject', { kind: item.kind, ref: item.ref }, () => { if (openKey === key) openKey = null; });
      } }));

  return h('article', { class: 'card' + (open ? ' open' : ''), 'data-key': key },
    h('div', { class: 'card-row' }, body, actions),
    open ? dealForm(item) : null);
}

function focusForm(key) {
  const el = document.querySelector(`[data-key="${CSS.escape(key)}"] input[name=name]`);
  if (el) { el.focus(); el.closest('.card').scrollIntoView({ block: 'nearest', behavior: 'smooth' }); }
}

function newCard() {
  const item = { kind: 'new', ref: '', draft: { date: '', name: '', type: '', amount: '', terms: '', status: '', src: '', url: '', ver: '' } };
  for (const k of EXTRA) item.draft[k] = '';
  return h('article', { class: 'card open new-card', 'data-key': 'new:' },
    h('div', { class: 'card-row' }, h('div', { class: 'card-main' }, h('h3', { text: 'New deal' }),
      h('p', { class: 'muted', text: 'For a deal you found yourself. It goes straight into the published registry.' }))),
    dealForm(item));
}

// ------------------------------------------------------------ page
function datalists() {
  return [
    h('datalist', { id: 'dl-types' }, S.types.map(t => h('option', { value: t }))),
    h('datalist', { id: 'dl-statuses' }, S.statuses.map(t => h('option', { value: t }))),
    h('datalist', { id: 'dl-amount-kinds' }, (S.amount_kinds || []).map(t => h('option', { value: t }))),
  ];
}

function render() {
  if (!S) return;
  $('n-leads').textContent = S.leads.length;
  $('n-published').textContent = S.published.length;
  $('updated').textContent = S.updated ? 'Data file: ' + S.updated : '';
  document.querySelectorAll('.tab').forEach(b => {
    const on = b.dataset.tab === tab;
    b.classList.toggle('on', on);
    b.setAttribute('aria-selected', on);
  });
  $('help-leads').classList.toggle('hidden', tab !== 'leads');
  $('help-published').classList.toggle('hidden', tab !== 'published');

  const items = tab === 'leads' ? S.leads : S.published;
  const kids = [...datalists()];
  if (adding) kids.push(newCard());
  if (!items.length) {
    kids.push(h('p', { class: 'empty', text: tab === 'leads'
      ? 'Nothing left to review. New leads appear here after the next watch run (pull the repo first).'
      : 'No published deals yet.' }));
  }
  kids.push(...items.map(card));
  $('list').replaceChildren(...kids);
}

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.tab').forEach(b => b.addEventListener('click', () => {
    tab = b.dataset.tab; openKey = null; render();
  }));
  $('add').addEventListener('click', () => {
    adding = true; openKey = null; render();
    const el = document.querySelector('.new-card input[name=name]');
    if (el) { el.focus(); el.scrollIntoView({ block: 'center', behavior: 'smooth' }); }
  });
  $('toast-undo').addEventListener('click', () => {
    $('toast').classList.add('hidden');
    send('undo', {});
  });
  load();
});
