/* Chip-Backed Finance Observatory: page script.
   Data come from observatory-data.json, fetched at every visit. If that file
   cannot be loaded (e.g. the page is opened as file://), the SEED snapshot
   below is shown with a visible notice. The snapshot is generated from the
   JSON by `python3 update_seed.py` (the watch workflow runs it), so do not
   edit it by hand. */

/* SEED:BEGIN */
const SEED = {
 "snapshot": "2026-11-12",
 "deals": [
  {
   "date": "2023-08",
   "name": "CoreWeave — first GPU-collateralized debt facility (Magnetar, Blackstone)",
   "type": "GPU-backed loan",
   "amount": "2,300 M",
   "terms": "First use of Nvidia H100 hardware as loan collateral; template for the neocloud financing model",
   "status": "Closed",
   "ver": "REPORTED",
   "src": "Reuters, 08/2023",
   "id": "d211406c9c5"
  },
  {
   "date": "2024-06",
   "name": "Lambda Labs GPU-backed ABS (via Macquarie)",
   "type": "Securitization",
   "amount": "~500 M",
   "terms": "Early GPU-backed ABS; residual values of ~50% after 3 years reportedly assumed",
   "status": "Outstanding",
   "ver": "REPORTED",
   "src": "Press reports, 2024–2026",
   "id": "dd03bc3c133"
  },
  {
   "date": "2025-06",
   "name": "xAI senior secured notes + term loans (Morgan Stanley-led)",
   "type": "Bond / Loan",
   "amount": "5,000 M",
   "terms": "USD 3bn 5y senior secured notes at 12.5% + 2×1bn loans; price talk widened on lukewarm demand",
   "status": "Notes redeemed early 03/2026",
   "ver": "VERIFIED",
   "src": "Reuters; PitchBook LCD, 06/2025",
   "id": "deacf461abf"
  },
  {
   "date": "2025-09",
   "name": "Nvidia — announced intent to invest in OpenAI",
   "type": "Vendor commitment",
   "amount": "up to 100,000 M",
   "terms": "Non-binding letter of intent tied to deployment of Nvidia systems",
   "status": "Announced (LOI)",
   "ver": "VERIFIED",
   "src": "Nvidia announcement, 22/09/2025",
   "id": "dd464c70856"
  },
  {
   "date": "2026-01",
   "name": "Apollo capital solution — Valor Compute Infrastructure (VCI) / xAI",
   "type": "Chip-lease SPV",
   "amount": "3,500 M",
   "terms": "Part of USD 5.4bn acquisition & triple-net lease of compute (incl. GB200) to xAI subsidiary; Nvidia anchor LP in VCI",
   "status": "Closed",
   "ver": "VERIFIED",
   "src": "Apollo press release, 07/01/2026",
   "id": "d86783e0f42"
  },
  {
   "date": "2026-02",
   "name": "Apollo loan #2 — Valor-arranged chip-lease vehicle / xAI",
   "type": "Chip-lease SPV",
   "amount": "~3,400 M",
   "terms": "Reported pricing near 9.5%; syndication expected",
   "status": "Reported near close",
   "ver": "REPORTED",
   "src": "The Information; Reuters, 09/02/2026",
   "id": "da6b1232933"
  },
  {
   "date": "2026-03",
   "name": "CoreWeave DDTL 4.0 — first investment-grade GPU-backed financing",
   "type": "GPU-backed loan",
   "amount": "8,500 M",
   "terms": "Delayed draw term loan; A3 (Moody's), non-recourse; first HPC infrastructure DDTL to reach investment grade",
   "status": "Closed",
   "ver": "VERIFIED",
   "src": "CoreWeave press release, 03/2026",
   "id": "dd336f40b33"
  },
  {
   "date": "2026-05",
   "name": "CoreWeave DDTL 5.0 — first publicly syndicated GPU-backed financing",
   "type": "GPU-backed loan",
   "amount": "3,100 M",
   "terms": "First publicly syndicated HPC infrastructure-backed vehicle, enabling secondary market trading",
   "status": "Closed",
   "ver": "VERIFIED",
   "src": "CoreWeave press release, 05/2026",
   "id": "ddf3423f471"
  },
  {
   "date": "2026-08",
   "name": "CoreWeave DDTL 5.5 — GPU loan with renewal risk underwritten by lenders",
   "type": "GPU-backed loan",
   "amount": "2,600 M",
   "terms": "SOFR+5.50%, ~5y maturity vs ~3y average customer contracts: lenders underwrite GPU residual and re-leasing risk; Ba2/BB+; JPMorgan & MUFG; oversubscribed",
   "status": "Closed 10/08/2026",
   "ver": "VERIFIED",
   "src": "CoreWeave press release / Business Wire, 10/08/2026",
   "id": "db6c25b44e2"
  },
  {
   "date": "2026-08",
   "name": "Nvidia — reported support for up to USD 500bn of AI data-centre financing",
   "type": "Vendor commitment",
   "amount": "up to 500,000 M",
   "terms": "Press-reported vendor backing of GPU collateral in large-scale AI infrastructure financing; unconfirmed by primary source",
   "status": "Reported",
   "ver": "REPORTED",
   "src": "Press reports, 08/2026",
   "id": "d28fc43191d"
  }
 ],
 "resale": [
  [
   "2023-Q1",
   30000
  ],
  [
   "2023-Q4",
   28000
  ],
  [
   "2024-Q2",
   26000
  ],
  [
   "2024-Q4",
   20000
  ],
  [
   "2025-Q2",
   15000
  ],
  [
   "2025-Q4",
   11000
  ],
  [
   "2026-Q2",
   8000
  ]
 ],
 "rental": [
  [
   "2024-Q1",
   8
  ],
  [
   "2024-Q3",
   6
  ],
  [
   "2025-Q1",
   4
  ],
  [
   "2025-Q3",
   2
  ],
  [
   "2025-Q4",
   1.5
  ],
  [
   "2026-Q1",
   2.35
  ]
 ],
 "events": [
  {
   "d": "2022-10",
   "t": "Nvidia H100 (Hopper) volume availability",
   "x": "The reference collateral generation of the first deal vintages.",
   "k": "vendor"
  },
  {
   "d": "2024-03",
   "t": "Nvidia announces Blackwell (GTC 2024)",
   "x": "First scheduled repricing signal for the Hopper installed base.",
   "k": "vendor"
  },
  {
   "d": "2024-06",
   "t": "Early GPU-backed ABS issuance",
   "x": "Securitization channel opens (reported).",
   "k": "fin"
  },
  {
   "d": "2025-H1",
   "t": "Blackwell (B200) volume shipments",
   "x": "Generation step realized; H100 secondary values and rental rates decline through the year.",
   "k": "vendor"
  },
  {
   "d": "2025-06",
   "t": "xAI USD 5bn secured notes and loans priced at 12.5%",
   "x": "Market pricing of borrower risk observable for the first time.",
   "k": "fin"
  },
  {
   "d": "2025-09",
   "t": "Nvidia announces intent to invest up to USD 100bn in OpenAI",
   "x": "Vendor circularity at ecosystem scale (non-binding LOI).",
   "k": "fin"
  },
  {
   "d": "2026-01",
   "t": "Apollo USD 3.5bn capital solution for VCI (Nvidia anchor LP)",
   "x": "Chip-lease SPV structure at scale; triple-net lease to xAI subsidiary.",
   "k": "fin"
  },
  {
   "d": "2026-02",
   "t": "Apollo ~USD 3.4bn second chip-lease loan (reported)",
   "x": "Total commitment ≈ USD 7bn; syndication expected.",
   "k": "fin"
  },
  {
   "d": "2026-27",
   "t": "Rubin generation (announced cadence)",
   "x": "Next scheduled repricing step for the installed base, expected on the vendor's announced annual rhythm.",
   "k": "vendor future"
  },
  {
   "d": "2027",
   "t": "2025–26 vintage seasoning",
   "x": "Lease renewals and realized collateral marks first confront underwriting assumptions at scale.",
   "k": "fin future"
  }
 ]
};
/* SEED:END */

let DEALS = SEED.deals, RESALE = SEED.resale, RENTAL = SEED.rental, EVENTS = SEED.events;
let META = { updated: SEED.snapshot + ' (embedded snapshot)' };

const $ = id => document.getElementById(id);

/* ═══════════ SAFE OUTPUT ═══════════
   Every data value is untrusted (feed headlines end up in the JSON):
   always pass it through esc() before putting it into innerHTML, and only
   link to http(s) URLs. tests/test_render.mjs checks both. */
const ESC_MAP = {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'};
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ESC_MAP[c]);
const safeUrl = u => (typeof u === 'string' && /^https?:\/\//i.test(u)) ? u : null;
const link = (u, label) => {
  const s = safeUrl(u);
  return s ? `<a class="srclink" href="${esc(s)}" target="_blank" rel="noopener noreferrer">${esc(label)}</a>` : '';
};
const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
/* "2026-10-01" -> "1 Oct 2026", "2023-08" -> "Aug 2023"; anything else unchanged. */
function fmtDate(s){
  const m = /^(\d{4})-(\d{2})(?:-(\d{2}))?$/.exec(String(s ?? ''));
  const mon = m && MONTHS[+m[2] - 1];
  if (!mon) return esc(s);
  return m[3] ? `${+m[3]} ${mon} ${m[1]}` : `${mon} ${m[1]}`;
}

/* ═══════════ LIVE DATA LOADING ═══════════ */
const DATA_URL = 'observatory-data.json';
async function loadData(manual){
  const btn = $('refresh-btn');
  if (manual && btn) btn.textContent = '↻ Checking…';
  const notice = $('data-notice');
  try {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 6000);   // never hang: fall back after 6s
    const r = await fetch(DATA_URL + '?t=' + Date.now(), { cache: 'no-store', signal: ctrl.signal });
    clearTimeout(timer);
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const d = await r.json();
    if (!d || typeof d !== 'object') throw new Error('bad data file');
    /* Take only well-formed parts: rows must be objects, series rows pairs. */
    const rows = (v, ok) => Array.isArray(v) ? v.filter(ok) : null;
    const isObj = x => x !== null && typeof x === 'object' && !Array.isArray(x);
    const isPair = x => Array.isArray(x) && x.length >= 2 && Number.isFinite(+x[1]);
    DEALS  = rows(d.deals, isObj)   ?? DEALS;
    RESALE = rows(d.resale, isPair) ?? RESALE;
    RENTAL = rows(d.rental, isPair) ?? RENTAL;
    EVENTS = rows(d.events, isObj)  ?? EVENTS;
    if (typeof d.updated === 'string') META.updated = d.updated;
    if (notice) notice.hidden = true;
    renderAll();
    if (manual && btn) btn.textContent = '✓ Up to date';
  } catch (e) {
    try { renderAll(); } catch (e2) {}
    if (notice) {
      notice.textContent = `The live data file could not be loaded, so this page shows an embedded snapshot from ${SEED.snapshot}. It may be out of date. Use "Check for updates" to try again.`;
      notice.hidden = false;
    }
    if (manual && btn) btn.textContent = '↻ Check for updates';
  }
  const u = $('updated');
  if (u) u.textContent = 'Data as of: ' + META.updated;
  if (manual && btn) setTimeout(() => btn.textContent = '↻ Check for updates', 2500);
}

/* ═══════════ RENDERING ═══════════ */
document.querySelectorAll('.tab').forEach(b => b.addEventListener('click', () => {
  document.querySelectorAll('.tab').forEach(x => x.classList.remove('on'));
  document.querySelectorAll('section').forEach(x => x.classList.remove('on'));
  b.classList.add('on'); $(b.dataset.s).classList.add('on');
  window.scrollTo({top:0});
}));
$('refresh-btn').addEventListener('click', () => loadData(true));

function sourceCell(d){
  let h = `<span class="tag ${d.ver==='VERIFIED'?'ver':(d.ver==='REPORTED'?'rep':'pend')}">${esc(d.ver)}</span>`
        + `<br><span class="srcline">${esc(d.src)}</span>`;
  if (safeUrl(d.url)) h += `<br>${link(d.url, 'Open source ↗')}`;
  const more = Array.isArray(d.sources) ? d.sources.filter(s => s && safeUrl(s.url)) : [];
  if (more.length) {
    h += `<details class="more"><summary>+${more.length} more source${more.length > 1 ? 's' : ''}</summary><ul>`
      + more.map(s => `<li>${link(s.url, s.outlet || 'source')} · ${fmtDate(s.date)}</li>`).join('')
      + `</ul></details>`;
  }
  return h;
}

/* Deals: only curator-flagged entries are part of the registry and its counts.
   The optional `collateral` field (set by the curator) says whether chips secure
   the debt. gpu-lien / spv-owned-leased are counted; contract-cashflows /
   none-or-unclear (vendor commitments, cloud contracts, corporate debt) are
   listed apart as related financings. Rows not yet classified are counted and
   reported as unclassified. */
const isCurated = d => d.ver === 'VERIFIED' || d.ver === 'REPORTED';
const COLLATERAL = {
  'gpu-lien': 'Secured by GPUs',
  'spv-owned-leased': 'Chips owned by SPV, leased out',
  'contract-cashflows': 'Backed by compute contracts, not chips',
  'none-or-unclear': 'No chip collateral shown',
};
const RELATED = new Set(['contract-cashflows', 'none-or-unclear']);
const isRelated = d => RELATED.has(d.collateral);
const isUnclassified = d => !Object.hasOwn(COLLATERAL, d.collateral ?? '');
const DETAIL_FIELDS = [['lenders', 'Lenders'], ['rate', 'Rate'], ['maturity', 'Maturity'], ['rating', 'Rating'],
  ['gpu_generation', 'Collateral GPUs'], ['vendor_role', 'Vendor role'], ['amount_kind', 'Amount is']];
function termsCell(d){
  let h = esc(d.terms);
  const kv = [];
  if (Object.hasOwn(COLLATERAL, d.collateral ?? '')) kv.push(['Collateral', COLLATERAL[d.collateral]]);
  for (const [k, label] of DETAIL_FIELDS) if (typeof d[k] === 'string' && d[k]) kv.push([label, d[k]]);
  if (kv.length) h += `<dl class="kv">${kv.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('')}</dl>`;
  const evs = Array.isArray(d.events) ? d.events.filter(e => e && typeof e === 'object') : [];
  if (evs.length) {
    h += `<details class="more"><summary>${evs.length} later event${evs.length > 1 ? 's' : ''}</summary><ul>`
      + evs.map(e => `<li>${fmtDate(e.date)} · ${esc(e.kind)}: ${esc(e.note)}${safeUrl(e.url) ? ' ' + link(e.url, '↗') : ''}</li>`).join('')
      + `</ul></details>`;
  }
  return h;
}
const dealRow = d => `
    <tr><td class="amount">${fmtDate(d.date)}</td><td><b>${esc(d.name)}</b></td>
    <td><span class="tag type">${esc(d.type)}</span></td>
    <td class="amount">${esc(d.amount)}</td><td>${termsCell(d)}</td><td>${esc(d.status)}</td>
    <td>${sourceCell(d)}</td></tr>`;
const fmtBn = musd => musd >= 1000 ? `USD ${(musd / 1000).toLocaleString('en-US', {maximumFractionDigits: 1})}bn`
                                   : `USD ${Math.round(musd).toLocaleString('en-US')}m`;
let filter = "All";
function renderDeals(){
  const curated = DEALS.filter(isCurated);
  const counted = curated.filter(d => !isRelated(d));
  const related = curated.filter(isRelated);
  const pending = DEALS.filter(d => !isCurated(d));
  const types = ["All", ...new Set(counted.map(d => d.type))];
  if (!types.includes(filter)) filter = "All";
  $('deal-filters').innerHTML = types.map(t => `<button class="fbtn ${t===filter?'on':''}" data-type="${esc(t)}">${esc(t)}</button>`).join('');
  $('deal-rows').innerHTML = counted.filter(d => filter==="All" || d.type===filter).map(dealRow).join('');
  $('related-rows').innerHTML = related.map(dealRow).join('');
  $('related-count').textContent = related.length;
  $('related-wrap').style.display = related.length ? 'block' : 'none';
  $('pending-rows').innerHTML = pending.map(dealRow).join('');
  $('pending-count').textContent = pending.length;
  $('pending-wrap').style.display = pending.length ? 'block' : 'none';
  const nVer = counted.filter(d => d.ver === 'VERIFIED').length;
  const nUncl = counted.filter(isUnclassified).length;
  $('st-deals').textContent = counted.length;
  $('st-vol').textContent = `${nVer} verified · ${counted.length - nVer} reported`
    + (nUncl ? ` · ${nUncl} collateral not yet classified` : '')
    + (related.length ? ` · ${related.length} related, not counted` : '')
    + (pending.length ? ` · ${pending.length} unreviewed leads not counted` : '');
  /* Volume only from the numeric amount_musd field: display strings ("~500 M",
     "up to …") are not added up. */
  const sized = counted.filter(d => typeof d.amount_musd === 'number' && Number.isFinite(d.amount_musd) && d.amount_musd > 0);
  const total = sized.reduce((s, d) => s + d.amount_musd, 0);
  $('st-sum').textContent = sized.length
    ? `${fmtBn(total)} stated across ${sized.length} of ${counted.length} deals (headline amounts, not outstanding balances)`
    : '';
  $('st-events').textContent = EVENTS.length;
}
$('deal-filters').addEventListener('click', e => {
  const b = e.target.closest('.fbtn');
  if (!b) return;
  filter = b.dataset.type;
  renderDeals();
});

/* Charts (plain SVG). Points sit on a real time axis when every label is a
   period ("2024-Q2", "2025-H1", "2026-03", "2026"); otherwise they are spaced
   evenly. Even spacing of irregular quarters bends the slopes. */
function periodYears(label){
  const s = String(label ?? '');
  let m;
  if ((m = /^(\d{4})-Q([1-4])$/.exec(s))) return +m[1] + (+m[2] - 1) / 4;
  if ((m = /^(\d{4})-H([12])$/.exec(s))) return +m[1] + (+m[2] - 1) / 2;
  if ((m = /^(\d{4})-(\d{2})$/.exec(s)) && +m[2] >= 1 && +m[2] <= 12) return +m[1] + (+m[2] - 1) / 12;
  if ((m = /^(\d{4})$/.exec(s))) return +m[1];
  return null;
}
const pointSource = d => (d[2] && typeof d[2] === 'object' && typeof d[2].src === 'string') ? d[2] : null;
function lineChart(el, data, opts){
  const W=760,H=250,P={l:56,r:16,t:14,b:30};
  const ys=data.map(d=>+d[1]);
  const ymax=opts.ymax||Math.max(...ys)*1.1, ymin=0;
  const ts=data.map(d=>periodYears(d[0]));
  const timed=ts.every(t=>t!==null) && Math.max(...ts) > Math.min(...ts);
  const t0=Math.min(...ts), t1=Math.max(...ts);
  const X=i=>P.l+(W-P.l-P.r)*(timed ? (ts[i]-t0)/(t1-t0) : (data.length>1 ? i/(data.length-1) : 0));
  const Y=v=>P.t+(H-P.t-P.b)*(1-(+v-ymin)/(ymax-ymin));
  let g='';
  const steps=opts.gridSteps||5;
  for(let s=0;s<=steps;s++){const v=ymin+(ymax-ymin)*s/steps,y=Y(v);
    g+=`<line x1="${P.l}" y1="${y}" x2="${W-P.r}" y2="${y}" class="grid-line"/>`+
       `<text x="${P.l-8}" y="${y+3}" text-anchor="end">${opts.fmt(v)}</text>`;}
  let path='';
  data.forEach((d,i)=>{path+=(i?'L':'M')+X(i)+' '+Y(d[1])+' ';});
  let dots='',labels='';
  data.forEach((d,i)=>{const ps=pointSource(d);
    dots+=`<circle class="dot ${opts.cls}" cx="${X(i)}" cy="${Y(d[1])}" r="3.5">`
      +`<title>${esc(d[0])}: ${esc(d[1])}${ps ? ' · ' + esc(ps.src) : ''}</title></circle>`;
    labels+=`<text x="${X(i)}" y="${H-8}" text-anchor="${i===data.length-1?'end':'middle'}">${esc(d[0])}</text>`;});
  el.innerHTML=`<svg class="chart-svg" viewBox="0 0 ${W} ${H}" role="img" aria-label="${opts.aria}">
    ${g}<path class="series ${opts.cls}" d="${path}"/>${dots}${labels}</svg>`;
}
/* Under each chart: the sources of its points, or a plain statement that they
   are not recorded yet. Series rows may be [label, value, {src, url, sku}]. */
function seriesSources(el, data){
  if (!el) return;
  const srcs = data.map(pointSource).filter(Boolean);
  if (!srcs.length) {
    el.textContent = 'Sources for individual points are not recorded yet: the series is compiled from published trackers and press analyses.';
    return;
  }
  const seen = new Set(), items = [];
  for (const s of srcs) {
    const k = s.src + '|' + (s.url || '');
    if (seen.has(k)) continue;
    seen.add(k);
    items.push(safeUrl(s.url) ? link(s.url, s.src) : esc(s.src));
  }
  el.innerHTML = `Sources (${srcs.length} of ${data.length} points): ${items.join(' · ')}`;
}
/* Overview stat computed from the resale series, so it can't drift from the data. */
function resaleStat(){
  const pts = RESALE.filter(d => Number.isFinite(+d[1]) && +d[1] > 0);
  if (pts.length < 2) { $('st-resale').textContent = '–'; return; }
  const a = pts[0], b = pts[pts.length - 1];
  const pct = Math.round((+b[1] / +a[1] - 1) * 100);
  $('st-resale').textContent = `≈ ${pct < 0 ? '−' : '+'}${Math.abs(pct)}%`;
  $('st-resale-label').textContent = `H100 resale value change, ${a[0]} → ${b[0]}`;
  const n = pts.filter(pointSource).length;
  $('st-resale-src').textContent = `USD ~${(+a[1]).toLocaleString('en-US')} → ~${(+b[1]).toLocaleString('en-US')} · `
    + (n ? `${n} of ${pts.length} points sourced` : 'press-compiled, point sources not yet recorded');
}
function renderAll(){
  renderDeals();
  resaleStat();
  lineChart($('chart-resale'), RESALE, {cls:'s-teal', ymax:32000, fmt:v=>(v/1000)+'k', gridSteps:4, aria:'H100 resale value series'});
  lineChart($('chart-rental'), RENTAL, {cls:'s-amber', ymax:9, fmt:v=>'$'+v.toFixed(0), gridSteps:3, aria:'H100 rental rate series'});
  seriesSources($('src-resale'), RESALE);
  seriesSources($('src-rental'), RENTAL);
  $('timeline').innerHTML = EVENTS.map(e => { const k = String(e.k ?? ''); return `
  <div class="ev ${k.includes('vendor')?'vendor':''} ${k.includes('future')?'future':''}">
    <div class="ev-date">${fmtDate(e.d)}${k.includes('future')?' · announced / expected':''}</div>
    <div class="ev-t">${esc(e.t)}</div>
    <div class="ev-x">${esc(e.x)}</div>
  </div>`; }).join('');
}
loadData(false);
