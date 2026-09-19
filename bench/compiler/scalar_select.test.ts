import { strict as assert } from 'node:assert';
import { scalarSelect } from './scalar_select.ts';
const run = (a: string[], b = ['r0 = x;']) => scalarSelect([a, b], new Set(['x', 'y']), ['r0'], 'yes');
assert.deepEqual(run(['u32 z = U32_BIN(x, +, 1ull);', 'r0 = z;']),
  ['r0 = (yes) ? (U32_BIN(U32_BIN(x, +, 1ull), +, 0)) : (x);']);
for (const rhs of ['callback(x)', 'nat_chk(e, x + 1)', 'x / y', 'x << y',
                   'U32_BIN(x, <<, y)', 'f32_rewrap(x)', 'e.mem[x]', 'unknown',
                   '18446744073709551616ull', 'x + y', 'r0']) {
  assert.equal(run([`r0 = ${rhs};`]), null, rhs);
}
assert.equal(run(['heap_free(e, x);', 'r0 = x;']), null);
assert.equal(run(['if (x) {', 'r0 = y;', '}']), null);
assert.equal(run(['r0 = x;', 'r0 = y;']), null);
assert.equal(run(['r0 = x;'], []), null);
assert.equal(run(['r0 = ' + 'U32_BIN('.repeat(300) + 'x;']), null);
assert.equal(run(Array(33).fill('r0 = x;')), null);
assert.equal(scalarSelect([['r0 = x;'], ['r0 = y;']], new Set(['x', 'y', 'r0']), ['r0'], 'yes'), null);
console.log('PASS scalar-select grammar and conservative fallbacks');
