export const format = new Intl.NumberFormat('en-US');
export const normalize = value => String(value ?? '').trim().replace(/\s+/g, ' ').toUpperCase();

export function collectModels(quarters) {
  const models = new Map();
  for (const quarter of quarters) {
    for (const row of quarter.rows) {
      models.set(row.model, { model: row.model, maker: row.maker, tb: row.tb });
    }
  }
  return Array.from(models.values()).sort((a, b) => a.maker.localeCompare(b.maker) || a.model.localeCompare(b.model));
}

export function exactMatch(input, models) {
  const name = normalize(input);
  return models.find(m => normalize(m.model) === name || normalize(m.maker + ' ' + m.model) === name);
}

export function history(quarters, model) {
  return quarters.map(q => ({ quarter: q, row: q.rows.find(r => r.model === model) }));
}

const finite = x => typeof x === 'number' && Number.isFinite(x);
const counter = x => Number.isSafeInteger(x) && x >= 0;

export function readSmart(doc) {
  if (!doc || typeof doc !== 'object' || !Array.isArray(doc.json_format_version)) {
    throw Error('Choose a JSON report generated with smartctl -j.');
  }
  const value = [doc.model_name, doc.model_number, doc.product].find(x => typeof x === 'string' && x.trim());
  if (!value) throw Error('This report does not identify a drive model.');
  const readings = new Map();
  const show = (key, label, n, unit, predicate = counter) => {
    if (predicate(n)) readings.set(key, { label, value: n, unit });
  };
  const nv = doc.nvme_smart_health_information_log ?? {};
  show('temp', 'Temperature', doc.temperature?.current ?? nv.temperature, '°C', finite);
  show('hours', 'Power-on time', doc.power_on_time?.hours ?? nv.power_on_hours, 'h');
  show('cycles', 'Power cycles', doc.power_cycle_count ?? nv.power_cycles, '');
  const attributes = Array.isArray(doc.ata_smart_attributes?.table) ? doc.ata_smart_attributes.table : [];
  const definitions = new Map([[5,'Reallocated sectors'],[197,'Pending sectors'],[198,'Offline uncorrectable sectors'],[199,'UltraDMA CRC errors']]);
  for (const item of attributes) {
    if (definitions.has(item?.id)) show('ata' + item.id, definitions.get(item.id), item.raw?.value, '');
  }
  show('media', 'NVMe media errors', nv.media_errors, '');
  show('spare', 'Available spare', nv.available_spare, '%');
  show('wear', 'Percentage used', nv.percentage_used, '%');
  let time = null;
  if (counter(doc.local_time?.time_t)) {
    const date = new Date(doc.local_time.time_t * 1000);
    if (finite(date.getTime())) time = date.toISOString();
  }
  const serial = typeof doc.serial_number === 'string' ? doc.serial_number.trim() : '';
  return { model: value.trim(), serial, readings, time, passed: typeof doc.smart_status?.passed === 'boolean' ? doc.smart_status.passed : null };
}

export function comparison(a, b, models = []) {
  if (!a || !b) return { ready: false, note: '' };
  const canonical = d => exactMatch(d.model, models)?.model ?? normalize(d.model);
  if (canonical(a) !== canonical(b)) return { ready: false, note: 'These reports identify different models. Choose two reports from the same drive.' };
  if (a.serial && b.serial && a.serial !== b.serial) return { ready: false, note: 'The reports identify different physical drives. Choose two reports from the same drive.' };
  if (a.time && b.time && a.time > b.time) return { ready: false, note: 'The second report predates the first. Swap the two files to compare them chronologically.' };
  return { ready: true, note: a.serial && b.serial ? 'Device identity matches locally.' : 'A report omits its serial number. Confirm both reports came from the same drive.' };
}
