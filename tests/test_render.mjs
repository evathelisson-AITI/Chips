// Runs the real app.js against a stub DOM and checks that hostile data values
// are escaped, only http(s) links are rendered, only curated deals are counted,
// and the fallback notice appears when the data file cannot be loaded.
// Usage: node tests/test_render.mjs   (no dependencies)
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';

const script = readFileSync(new URL('../app.js', import.meta.url), 'utf8');
const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');

// CSP (vercel.json) allows only same-origin scripts: no inline code in the page.
assert.ok(!/<script(?![^>]*\bsrc=)[^>]*>/i.test(html), 'index.html must not contain inline <script>');
assert.ok(!/\son[a-z]+\s*=/i.test(html), 'index.html must not contain on*= handlers');
// The CSP allows no inline style either: styles live in styles.css.
assert.ok(!/<style/i.test(html) && !/\sstyle\s*=/i.test(html), 'index.html must not contain inline styles');
const vercel = JSON.parse(readFileSync(new URL('../vercel.json', import.meta.url), 'utf8'));
const csp = vercel.headers[0].headers.find(h => h.key === 'Content-Security-Policy').value;
assert.ok(!/unsafe-|\*|data:/.test(csp), 'CSP must not allow unsafe-*, wildcards or data:');
assert.match(csp, /script-src 'self'(;|$)/);

const XSS = `<img src=x onerror="alert(1)">`;
const QUOTE_BREAK = `x');alert(1);('`;
const DATA = {
  updated: 'test',
  deals: [
    { id: 'a', date: '2026-01', name: 'Curated deal', type: QUOTE_BREAK, amount: '1 M', terms: 't', status: 's',
      ver: 'VERIFIED', src: 'src', url: 'javascript:alert(1)' },
    { id: 'b', date: '2026-02-05', name: 'Reported deal', type: 'Loan', amount: '2 M', terms: 't', status: 's',
      ver: 'REPORTED', src: 'src', url: 'https://example.com/a?x=1&y="2"' },
    { id: 'd', date: '2026-03', name: 'Lien deal', type: 'Loan', amount: '1,500 M', terms: 't', status: 's',
      ver: 'VERIFIED', src: 'src', url: 'https://example.com/d', collateral: 'gpu-lien', amount_musd: 1500,
      lenders: XSS, events: [{ date: '2026-09', kind: 'rating', note: XSS, url: 'javascript:alert(3)' }] },
    { id: 'e', date: '2026-04', name: 'Vendor LOI', type: 'Vendor commitment', amount: 'up to 100,000 M', terms: 't',
      status: 's', ver: 'VERIFIED', src: 'src', url: 'https://example.com/e', collateral: 'none-or-unclear',
      amount_musd: 100000 },
    { id: 'c', date: XSS, name: XSS, type: XSS, amount: XSS, terms: XSS, status: XSS, ver: 'PENDING REVIEW', src: XSS,
      url: 'https://news.example/1',
      sources: [{ outlet: XSS, url: 'https://news.example/2', date: '2026-08-28' },
                { outlet: 'Evil', url: 'javascript:alert(2)', date: '2026-08-28' }] },
  ],
  resale: [['2023-Q1', 300], ['2023-Q4', 280, { src: XSS, url: 'https://example.com/p' }], ['2024-Q2', 260], ['2026-Q2', 75]],
  rental: [['a', 1], ['b', 2]],
  events: [{ d: XSS, t: XSS, x: XSS, k: 'fin' }, { d: '2022-10', t: 't', x: 'x', k: 'vendor' }],
};

async function run(fetchImpl) {
  const els = {};
  const el = id => (els[id] ??= {
    id, innerHTML: '', textContent: '', hidden: true, style: {}, dataset: {},
    addEventListener() {}, classList: { add() {}, remove() {} },
  });
  const sandbox = {
    document: { getElementById: el, querySelectorAll: () => [] },
    window: { scrollTo() {} },
    AbortController, setTimeout, clearTimeout, fetch: fetchImpl,
  };
  vm.createContext(sandbox);
  vm.runInContext(script, sandbox);
  await new Promise(r => setTimeout(r, 20));   // let loadData() finish
  return els;
}

// ---- live data with hostile values
const els = await run(async () => ({ ok: true, json: async () => DATA }));
const all = Object.values(els).map(e => e.innerHTML).join('\n');
assert.ok(all.includes('&lt;img src=x onerror=&quot;alert(1)&quot;&gt;'), 'hostile value should appear escaped');
assert.ok(!/<img/i.test(all), 'no live <img> tag may reach innerHTML');
assert.ok(!/onerror=/i.test(all.replace(/onerror=&quot;/g, '')), 'no live onerror attribute');
assert.ok(!/onclick=/i.test(els['deal-filters'].innerHTML), 'filter buttons must not use inline handlers');
assert.ok(els['deal-filters'].innerHTML.includes('data-type="x&#39;);alert(1);(&#39;"'), 'filter type escaped');

assert.ok(!/javascript:/i.test(all), 'non-http(s) URLs must never be linked');
assert.ok(all.includes('href="https://example.com/a?x=1&amp;y=&quot;2&quot;"'), 'URL escaped inside href');
assert.ok(all.includes('rel="noopener noreferrer"'));
assert.ok(els['pending-rows'].innerHTML.includes('+1 more source<'), 'extra sources listed, unsafe one dropped');

assert.ok(els['deal-rows'].innerHTML.includes('>Jan 2026<'), 'month date formatted');
assert.ok(els['deal-rows'].innerHTML.includes('>5 Feb 2026<'), 'day date formatted');
assert.ok(els['timeline'].innerHTML.includes('Oct 2022'), 'event date formatted');

assert.equal(els['st-deals'].textContent, 3, 'stat counts curated chip-backed deals only');
assert.match(els['st-vol'].textContent, /2 verified · 1 reported · 2 collateral not yet classified · 1 related, not counted · 1 unreviewed/);
assert.match(els['st-sum'].textContent, /USD 1\.5bn stated across 1 of 3 deals/, 'only numeric amounts of counted deals are summed');
assert.ok(els['related-rows'].innerHTML.includes('Vendor LOI'), 'vendor commitment listed as related');
assert.ok(!els['deal-rows'].innerHTML.includes('Vendor LOI'), 'related financing kept out of the registry table');
assert.equal(els['related-count'].textContent, 1);
assert.ok(els['deal-rows'].innerHTML.includes('Secured by GPUs'), 'collateral class shown');
assert.ok(els['deal-rows'].innerHTML.includes('1 later event'), 'later events listed');
assert.match(els['st-resale'].textContent, /≈ −75%/, 'resale stat computed from the series');
assert.match(els['st-resale-src'].textContent, /1 of 4 points sourced/);
assert.ok(els['src-resale'].innerHTML.includes('href="https://example.com/p"'), 'point source linked');
assert.match(els['src-rental'].textContent, /not recorded yet/, 'missing point sources stated');
// Time axis: 2023-Q1 → Q4 is three quarters, Q4 → 2024-Q2 two, so the first gap is wider.
const cx = [...els['chart-resale'].innerHTML.matchAll(/<circle[^>]*cx="([\d.]+)"/g)].map(m => +m[1]);
assert.equal(cx.length, 4);
assert.ok(Math.abs((cx[1] - cx[0]) / (cx[2] - cx[1]) - 1.5) < 1e-6, 'points spaced by time, not by index');
assert.ok(!els['deal-rows'].innerHTML.includes('PENDING REVIEW'), 'pending entries stay out of the registry table');
assert.ok(els['pending-rows'].innerHTML.includes('PENDING REVIEW'), 'pending entries listed separately');
assert.equal(els['pending-count'].textContent, 1);
assert.equal(els['data-notice'].hidden, true, 'no fallback notice when data loads');
assert.ok(!/\sstyle\s*=/i.test(all), 'rendered markup must not use inline styles (CSP)');

// ---- malformed data file: bad parts are ignored, the page still renders
const bad = await run(async () => ({ ok: true, json: async () => ({
  deals: 'not a list', resale: [null, ['x', 'NaN'], ['2026', 5]], events: [null, 42], updated: { x: 1 } }) }));
assert.ok(bad['deal-rows'].innerHTML.includes('VERIFIED'), 'non-array deals fall back to the snapshot');
assert.equal(bad['st-events'].textContent, 0, 'non-object events dropped');
assert.match(bad['updated'].textContent, /embedded snapshot/, 'non-string updated ignored');

// ---- data file unreachable: seed snapshot plus a visible notice
const off = await run(async () => { throw new Error('offline'); });
assert.equal(off['data-notice'].hidden, false, 'fallback notice shown');
assert.match(off['data-notice'].textContent, /embedded snapshot from \d{4}-\d{2}-\d{2}/);
assert.ok(off['deal-rows'].innerHTML.includes('VERIFIED'), 'seed deals rendered');
assert.ok(!off['deal-rows'].innerHTML.includes('PENDING REVIEW'), 'seed holds curated deals only');

console.log('render tests passed');
