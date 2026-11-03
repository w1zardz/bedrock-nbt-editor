// Run with: node --test tools/test_nbt_arrays.cjs
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../assets/nbt.js'), 'utf8');

function loadEditor(strings = {}) {
  const elements = new Map();
  function element() {
    const classes = new Set();
    return {
      value: '', textContent: '', style: {}, children: [], listeners: {},
      classList: {
        add(name) { classes.add(name); },
        remove(name) { classes.delete(name); },
        contains(name) { return classes.has(name); }
      },
      addEventListener(name, listener) { this.listeners[name] = listener; },
      appendChild(child) { this.children.push(child); }
    };
  }
  const document = {
    getElementById(id) {
      if (!elements.has(id)) elements.set(id, element());
      return elements.get(id);
    },
    createElement: element,
    addEventListener() {}
  };
  const context = {
    window: { __NBT_STRINGS__: strings }, document, TextEncoder, TextDecoder,
    CompressionStream, DecompressionStream, console, setTimeout() {}
  };
  // Expose private helpers in this isolated test context, not in the shipped API.
  assert.match(source, /\}\)\(\);\s*$/);
  vm.runInNewContext(source.replace(/\}\)\(\);\s*$/,
    'window.testHelpers = {parseArrayText, createDefaultTag, openArrayModal};\n})();'), context);
  return { ...context.window.testHelpers, NBT: context.window.NBT, document };
}

const editor = loadEditor();
const T = editor.NBT.TAG;
const cases = [
  { name: 'int', type: T.INT_ARRAY, min: '-2147483648', max: '2147483647',
    expected: [-2147483648, 2147483647],
    overflow: ['2147483648', '-2147483649', '4294967296', '-4294967296', '999999999999999999999999'] },
  { name: 'long', type: T.LONG_ARRAY, min: '-9223372036854775808', max: '9223372036854775807',
    expected: [-9223372036854775808n, 9223372036854775807n],
    overflow: ['9223372036854775808', '-9223372036854775809', '18446744073709551616',
      '-18446744073709551616', '9223372036854775808L', '-9223372036854775809l',
      '0x8000000000000000'] }
];

for (const c of cases) {
  test(`${c.name} array accepts signed boundaries and separators`, () => {
    assert.deepEqual(Array.from(editor.parseArrayText(c.type, `, ${c.min},\n\t${c.max}, `)), c.expected);
    assert.deepEqual(Array.from(editor.parseArrayText(c.type, ' , \n\t')), []);
    assert.deepEqual(Array.from(editor.createDefaultTag(c.type, `${c.min} ${c.max}`).value), c.expected);
  });

  test(`${c.name} array rejects overflow before typed-array coercion`, () => {
    for (const value of c.overflow) {
      assert.throws(() => editor.parseArrayText(c.type, `0, ${value}, 1`), { name: 'Error' }, value);
      assert.throws(() => editor.createDefaultTag(c.type, value), { name: 'Error' }, value);
    }
  });

  test(`${c.name} array rejects malformed values`, () => {
    for (const value of ['invalid', 'NaN', 'Infinity', '-Infinity']) {
      assert.throws(() => editor.parseArrayText(c.type, value));
    }
  });

  test(`${c.name} array modal preserves existing data when validation fails`, () => {
    const app = loadEditor();
    const tag = app.createDefaultTag(c.type, `${c.min}, ${c.max}`);
    const oldValue = tag.value;
    const valueLabel = { textContent: 'Original array' };
    app.openArrayModal(tag, valueLabel);
    app.document.getElementById('arrayModalText').value = `0, ${c.overflow[0]}`;
    app.document.getElementById('arrayModalConfirm').listeners.click();
    assert.equal(tag.value, oldValue);
    assert.deepEqual(Array.from(tag.value), c.expected);
    assert.equal(valueLabel.textContent, 'Original array');
    assert.equal(app.document.getElementById('arrayModal').classList.contains('visible'), true);
    assert.match(app.document.getElementById('toastContainer').children.at(-1).textContent, /^Invalid array:/);

    // Correcting the value and retrying commits the whole array and closes the modal.
    app.document.getElementById('arrayModalText').value = `${c.max}, ${c.min}`;
    app.document.getElementById('arrayModalConfirm').listeners.click();
    assert.deepEqual(Array.from(tag.value), [...c.expected].reverse());
    assert.equal(app.document.getElementById('arrayModal').classList.contains('visible'), false);
  });

  test(`${c.name} array boundaries round-trip in all five NBT formats`, () => {
    const tag = editor.createDefaultTag(c.type, `${c.min}, ${c.max}`);
    const root = { type: T.COMPOUND, name: '', value: [{ ...tag, name: 'values' }] };
    for (const format of Object.keys(editor.NBT.FORMATS)) {
      const bytes = editor.NBT.serialize(root, format, 8);
      const parsed = editor.NBT.parseWithFormat(bytes, format);
      assert.deepEqual(Array.from(parsed.root.value[0].value), c.expected, format);
    }
  });
}

test('long arrays preserve suffixes, exact precision and supported bases', () => {
  assert.deepEqual(Array.from(editor.parseArrayText(T.LONG_ARRAY,
    '-9223372036854775808L, 9223372036854775807l, 9007199254740993, +1L, 0x7fffffffffffffff, 0b10, 0o10')),
    [-9223372036854775808n, 9223372036854775807n, 9007199254740993n, 1n, 9223372036854775807n, 2n, 8n]);
});

test('byte arrays preserve signed values and unsigned byte aliases', () => {
  assert.deepEqual(Array.from(editor.parseArrayText(T.BYTE_ARRAY, '-128, -1 0 127 128 255')),
    [-128, -1, 0, 127, -128, -1]);
  for (const value of ['-129', '256', 'invalid']) assert.throws(() => editor.parseArrayText(T.BYTE_ARRAY, value));
});

test('array overflow errors use the existing localized messages', () => {
  const app = loadEditor({ err_array_int: 'INT {0}', err_long: 'LONG RANGE' });
  assert.throws(() => app.parseArrayText(T.INT_ARRAY, '2147483648'), /INT 2147483648/);
  assert.throws(() => app.parseArrayText(T.LONG_ARRAY, '9223372036854775808'), /LONG RANGE/);
});
