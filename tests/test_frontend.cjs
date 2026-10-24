// Synthetic DOM/fetch logic tests, NOT real browser or visual verification.
// Node's built-in test runner; no npm dependencies or real article text.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

class Element {
  constructor(tag = 'div') { this.tag = tag; this.textContent = ''; this.children = []; this.listeners = {}; this.attributes = {}; this.value = ''; this.classList = {toggle() {}}; }
  set innerHTML(_) { throw new Error('Unsafe HTML rendering'); }
  appendChild(node) { this.children.push(node); return node; }
  replaceChildren(...nodes) { this.children = nodes; }
  addEventListener(name, handler) { this.listeners[name] = handler; }
  setAttribute(name, value) { this.attributes[name] = value; }
}
function page(fetch) {
  const nodes = new Map();
  const document = {getElementById(id) { if (!nodes.has(id)) nodes.set(id, new Element()); return nodes.get(id); },
                    createElement(tag) { return new Element(tag); }, querySelectorAll() { return []; }};
  const context = vm.createContext({document, fetch, URL, AbortController, setTimeout, clearTimeout, console});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../src/static/copilot.js'), 'utf8'), context);
  return {get: id => document.getElementById(id), context};
}
const status = {retrieval:'ready', documents:6, generation:{message:'Generation not configured'}};
const evidence = {rank:1, score:.82, title:'Synthetic <img src=x onerror=alert(1)>', heading:'Test steps',
                  text:'<script>alert(1)</script>', source_url:'https://support.apple.com/en-us/118428',
                  doc_id:'synthetic', chunk_id:'synthetic-1', content_sha256:'synthetic', start_char:0, end_char:10};

test('loading disables submission; actual response restores it and keeps candidates distinct from citations', async () => {
  let resolve, sent;
  const pending = new Promise(r => { resolve = r; });
  const p = page((url, options) => {
    if (url === '/api/status') return Promise.resolve({json:async () => status});
    sent = JSON.parse(options.body); return pending;
  });
  p.get('question').value = 'Synthetic cancellation question';
  const submit = p.get('question-form').listeners.submit({preventDefault() {}});
  assert.equal(p.get('submit-button').disabled, true);
  assert.equal(p.get('response-panel').attributes['aria-busy'], 'true');
  assert.equal(p.get('request-status').textContent, 'Working…');
  assert.deepEqual(sent, {question:'Synthetic cancellation question'});
  resolve({json:async () => ({status:'generation_not_configured', message:'Not configured', answer:null, sources:[], evidence:[evidence]})});
  await submit;
  assert.equal(p.get('submit-button').disabled, false);
  assert.equal(p.get('response-panel').attributes['aria-busy'], 'false');
  assert.equal(p.get('sources-list').children.length, 0);
  const card = p.get('evidence-list').children[0];
  assert.equal(card.tag, 'details');
  assert.equal(card.children[1].textContent, '<script>alert(1)</script>');
  assert.equal(card.children[2].href, 'https://support.apple.com/en-us/118428');
  assert.equal(card.children[2].rel, 'noopener noreferrer');
});

test('network failure clears stale content, shows safe status and restores submission', async () => {
  const p = page(url => url === '/api/status' ? Promise.resolve({json:async () => status}) : Promise.reject(new Error('PRIVATE_TEST_ERROR')));
  p.get('question').value = 'Synthetic question'; p.get('answer').textContent = 'Old answer';
  await p.get('question-form').listeners.submit({preventDefault() {}});
  assert.equal(p.get('submit-button').disabled, false);
  assert.equal(p.get('answer').textContent, '');
  assert.match(p.get('result-message').textContent, /Check the local service/);
  assert.doesNotMatch(p.get('result-message').textContent, /PRIVATE_TEST_ERROR/);
});

test('engineering empty/budget states render without a topic decision; busy candidates stay unsubmitted', () => {
  const p = page(async () => ({json:async () => status}));
  for (const [state, label] of [['no_evidence', 'No retrieval candidates'], ['context_unavailable', 'Context budget unavailable']]) {
    p.context.result = {status:state, message:'Synthetic engineering outcome', answer:null, sources:[], evidence:[]};
    vm.runInContext('renderResult(result)', p.context);
    assert.equal(p.get('request-status').textContent, label);
    assert.equal(p.get('sources-list').children.length, 0);
  }
  p.context.result = {status:'generation_failed', message:'Busy', answer:null, sources:[],
                      evidence:[{...evidence, used_for_generation:false, citation_id:null}]};
  vm.runInContext('renderResult(result)', p.context);
  const metadata = p.get('evidence-list').children[0].children[0].children[1].textContent;
  assert.match(metadata, /Retrieved candidate/);
  assert.doesNotMatch(metadata, /Sent as context/);
});

test('cited sources render as text; untrusted URL schemes and hosts never become links', () => {
  const p = page(async () => ({json:async () => status}));
  vm.runInContext(`renderResult({status:'generated',message:'Staff check',answer:'<svg onload=alert(1)>',evidence:[],sources:[
    {citation_id:'E1',title:'<img>',heading:'Test',source_url:'https://support.apple.com/en-us/118428'},
    {citation_id:'E2',title:'Test',heading:'Test',source_url:'javascript:alert(1)'},
    {citation_id:'E3',title:'Test',heading:'Test',source_url:'https://support.apple.com.evil.test/'},
    {citation_id:'E4',title:'Test',heading:'Test',source_url:'https://user:pass@support.apple.com/'}]})`, p.context);
  assert.equal(p.get('answer').textContent, '<svg onload=alert(1)>');
  const sources = p.get('sources-list').children;
  assert.equal(sources.length, 4);
  assert.equal(sources[0].tag, 'a');
  assert.equal(sources[0].textContent, '[E1] <img> · Test');
  assert.ok(sources.slice(1).every(node => node.tag === 'span' && !node.href));
});

test('one suggestion area preserves normal, limited, confirmation and conditional prose with empty sources allowed', () => {
  const p = page(async () => ({json:async () => status}));
  const examples = [
    ['Synthetic guidance [E1].', [{citation_id:'E1', title:'Synthetic', heading:'Steps', source_url:evidence.source_url}]],
    ['The evidence does not establish a price. Confirm with staff.', []],
    ['Please confirm the device and software version.', []],
    ['If the prerequisite holds, follow the procedure [E1].\nOtherwise confirm the device. Pricing is not covered.',
     [{citation_id:'E1', title:'Synthetic', heading:'Steps', source_url:evidence.source_url}]],
  ];
  for (const [answer, sources] of examples) {
    p.context.result = {status:'generated', message:'Verify before use', answer, sources, evidence:[]};
    vm.runInContext('renderResult(result)', p.context);
    assert.equal(p.get('answer').textContent, answer);
    assert.equal(p.get('answer').hidden, false);
    assert.equal(p.get('request-status').textContent, 'Suggested response · verify before use');
    assert.equal(p.get('sources-list').children.length, sources.length);
    assert.equal(p.get('sources-empty').hidden, sources.length > 0);
  }
});
