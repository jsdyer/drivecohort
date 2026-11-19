import { collectModels, comparison, exactMatch, format, history, readSmart } from './model.mjs';

const byId = id => document.getElementById(id);
const text = (id, value) => { byId(id).textContent = value; };
const create = (tag, value = '') => { const el = document.createElement(tag); el.textContent = value; return el; };
const link = (label, url) => { const el = create('a', label); el.href = url; return el; };
const periodLabel = id => id.split('-').reverse().join(' ');
const show = (id, visible) => { byId(id).hidden = !visible; };
const reports = [null, null];
const errors = ['', ''];
const versions = [0, 0];
let dataset, models, timeline = [], activeModel;
const initial = 'ST12000NM0007';

function drawQuarter() {
  if (!activeModel) return;
  const selected = timeline.find(({quarter}) => quarter.id === byId('quarter').value);
  const { row, quarter } = selected;
  show('metrics', Boolean(row));
  show('empty', !row);
  if (row) {
    text('afr', row.afr.toFixed(2) + '%');
    for (const id of ['drives', 'days', 'failures']) text(id, format.format(row[id]));
  } else text('empty', 'This model has no published cohort for the selected quarter.');
  byId('rowSource').replaceChildren(create('span', quarter.start + ' — ' + quarter.end), link('Open Backblaze table ↗', quarter.source));
  const tbody = byId('trends');
  tbody.replaceChildren();
  for (const period of [...timeline].reverse()) {
    const tr = create('tr');
    if (period.quarter.id === quarter.id) tr.className = 'selected';
    const heading = create('th', periodLabel(period.quarter.id));
    heading.scope = 'row';
    tr.append(heading);
    if (period.row) {
      const r = period.row;
      for (const val of [r.afr.toFixed(2) + '%', format.format(r.failures), format.format(r.days), format.format(r.drives)]) tr.append(create('td', val));
      tr.children[1].className = 'rate';
    } else {
      const missing = create('td', 'No published cohort');
      missing.colSpan = 4;
      tr.append(missing);
    }
    const cite = create('td');
    const a = link('Table ↗', period.quarter.source);
    a.setAttribute('aria-label', 'Backblaze source table for ' + periodLabel(period.quarter.id));
    cite.append(a);
    tr.append(cite);
    tbody.append(tr);
  }
}

function selectModel(input, requestedQuarter) {
  activeModel = exactMatch(input, models);
  byId('search').value = activeModel?.model ?? input;
  text('modelname', activeModel?.model ?? input);
  text('maker', activeModel ? activeModel.maker + '  /  ' + activeModel.tb + ' TB' : 'Exact-model search');
  for (const id of ['quarterLabel', 'history', 'rowSource']) show(id, Boolean(activeModel));
  if (!activeModel) {
    timeline = [];
    show('metrics', false);
    show('empty', true);
    text('empty', 'No matching cohort in the indexed quarters. Check the complete model number or browse indexed models.');
    return;
  }
  timeline = history(dataset.quarters, activeModel.model);
  byId('quarter').replaceChildren();
  for (const { quarter } of [...timeline].reverse()) byId('quarter').append(new Option(periodLabel(quarter.id), quarter.id));
  byId('quarter').value = timeline.some(x => x.quarter.id === requestedQuarter) ? requestedQuarter : timeline.filter(x => x.row).at(-1).quarter.id;
  drawQuarter();
}

function showReports() {
  const [a,b] = reports;
  const tableWrap = byId('reportTable');
  tableWrap.replaceChildren();
  show('clear', Boolean(a || b || errors.some(Boolean)));
  const messages = errors.map((issue, i) => issue ? (i ? 'Later report' : 'Earlier report') + ' — ' + issue : '').filter(Boolean);
  const check = comparison(a, b, models);
  for (const [i, report] of reports.entries()) {
    if (!report) continue;
    const label = i ? 'Later' : 'Earlier';
    const parts = [label + ' — ' + report.model];
    if (report.time) parts.push(report.time.replace('T', ' ').replace('.000Z', ' UTC'));
    if (report.passed !== null) parts.push('SMART status ' + (report.passed ? 'passed' : 'failed'));
    messages.push(parts.join(' · '));
  }
  if (check.note) messages.push(check.note);
  text('reportMsg', messages.join('\n'));
  if ((!a && !b) || (a && b && !check.ready)) return;
  const keys = new Set([...(a?.readings.keys() ?? []), ...(b?.readings.keys() ?? [])]);
  if (!keys.size) {
    tableWrap.append(create('p', 'No supported numeric SMART readings were available.'));
    return;
  }
  const table = create('table');
  const head = table.createTHead().insertRow();
  for (const title of ['Reading', 'Earlier', 'Later', 'Change']) head.append(create('th', title));
  const tbody = table.createTBody();
  const display = (val, unit) => typeof val === 'number' ? format.format(val) + (unit ? ' ' + unit : '') : '—';
  for (const key of keys) {
    const left = a?.readings.get(key);
    const right = b?.readings.get(key);
    const {label, unit} = left ?? right;
    const row = tbody.insertRow();
    row.append(create('th', label));
    let change = '—';
    if (left && right) {
      const delta = right.value - left.value;
      change = (delta > 0 ? '+' : '') + display(delta, unit);
    }
    [display(left?.value, unit), display(right?.value, unit), change].forEach(s => row.append(create('td', s)));
  }
  tableWrap.append(table);
}

async function importFile(i) {
  const ticket = ++versions[i];
  const file = byId('file' + i).files[0];
  reports[i] = null;
  errors[i] = '';
  showReports();
  if (!file) return;
  try {
    if (file.size > 8 * 1024 * 1024) throw Error('Choose a report smaller than 8 MiB.');
    let json;
    try { json = JSON.parse(await file.text()); } catch { throw Error('The file contains invalid JSON.'); }
    const report = readSmart(json);
    if (ticket !== versions[i]) return;
    reports[i] = report;
    if (models) selectModel(report.model);
  } catch (err) {
    if (ticket !== versions[i]) return;
    errors[i] = err.message;
  }
  showReports();
}

for (const i of [0,1]) byId('file' + i).addEventListener('change', () => importFile(i));
byId('clear').addEventListener('click', () => {
  for (const i of [0,1]) {
    ++versions[i];
    reports[i] = null;
    errors[i] = '';
    byId('file' + i).value = '';
  }
  if (models) selectModel(initial);
  showReports();
});
byId('quarter').addEventListener('change', drawQuarter);
byId('lookup').addEventListener('submit', e => {
  e.preventDefault();
  const query = byId('search').value.trim();
  if (query) selectModel(query);
  else byId('search').focus();
});

try {
  const response = await fetch('./data/cohorts.json');
  if (!response.ok) throw Error('Unavailable snapshot');
  dataset = await response.json();
  models = collectModels(dataset.quarters);
  for (const item of models) {
    const option = create('option');
    option.value = item.model;
    option.label = item.maker + ' · ' + item.tb + ' TB';
    byId('models').append(option);
    const button = create('button', item.model);
    button.title = option.label;
    button.addEventListener('click', () => { selectModel(item.model); byId('browse').open = false; });
    byId('catalogue').append(button);
  }
  const {status, quarters} = dataset;
  text('coverage', periodLabel(quarters[0].id) + ' – ' + periodLabel(quarters.at(-1).id));
  text('scope', status.models + ' models · ' + status.quarters + ' quarters');
  text('edition', 'Published scope: ' + status.start + ' through ' + status.end + '. Retrieved ' + status.retrieved + ' · ' + status.rows + ' quarterly model rows.');
  selectModel((reports[1] ?? reports[0])?.model ?? initial);
  showReports();
  show('fleet', true);
  show('loading', false);
} catch {
  text('loading', 'The public cohort snapshot could not be opened. Reload the page to try again. Local report readings are still available.');
  text('coverage', 'Snapshot unavailable');
}
