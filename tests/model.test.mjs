import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { collectModels, comparison, exactMatch, history, readSmart } from '../web/model.mjs';
const { quarters } = JSON.parse(fs.readFileSync(new URL('../web/data/cohorts.json', import.meta.url)));
const models = collectModels(quarters);
const doc = { json_format_version: [1,0], model_name: 'ST12000NM0007', serial_number: 'private', temperature: { current: 29 } };

test('published comparison includes both sample sizes and denominators', () => {
  const [q1,q2] = history(quarters, doc.model_name);
  assert.deepEqual([q1.row.afr,q1.row.drives,q1.row.days,q1.row.failures], [9.47,1038,92483,24]);
  assert.deepEqual([q2.row.afr,q2.row.drives,q2.row.days,q2.row.failures], [3.58,1014,91801,9]);
});

test('matches exact models and preserves distinct suffixes', () => {
  assert.equal(exactMatch('  tosHIBA  mg08aca16tey  ',models).model,'MG08ACA16TEY');
  assert.equal(exactMatch('MG08ACA16TE',models).model,'MG08ACA16TE');
  assert.equal(exactMatch('ST12000NM0007-1',models), undefined);
  assert.ok(history(quarters, 'HMS5C4040ALE640').some(p => !p.row));
});

test('private file comparison requires consistent identities and chronological order', () => {
  const a = readSmart(doc), b = readSmart({...doc, temperature:{current:31}});
  assert.equal(b.readings.get('temp').value - a.readings.get('temp').value,2);
  assert.equal(comparison(a,b,models).ready,true);
  assert.equal(comparison(a,{...b,serial:'different'},models).ready,false);
  assert.equal(comparison(a,{...b,model:'other'},models).ready,false);
  assert.equal(comparison({...a,time:'2025-02'}, {...b,time:'2025-01'},models).ready,false);
  assert.match(comparison(a,{...b,serial:''},models).note,/omits/);
  assert.throws(() => readSmart({model_name:'something'}));
});
