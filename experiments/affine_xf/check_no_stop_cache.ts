// Check that one compiler process does not reuse reachability across books.
import * as fs from 'node:fs';
import * as os from 'node:os';
import * as path from 'node:path';
import * as Bend from '../../../bend/bend2/bend.ts';
import * as Comp from '../../../bend/bend2/comp.ts';

const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'no-stop-cache-'));
const input = path.join(dir, 'input.bend');
const base = `import Base
`;
const choice = `type Choice<-K: Data> is Type:
  Value{item: U32}
  Halted{permit: K, item: U32}
def f(x: Choice<Never>) -> U32:
  match x:
    case Value{item}: item
    case Halted{permit, item}: item
`;
const total = base + `type Never is Data:
` + choice +
  `def main() -> U32:
  f(Value{2})
`;
const stopping = base + `type Never is Data:
  UnitLike{}
` + choice +
  `def main() -> U32:
  f(Halted{UnitLike{}, 3})
`;

async function book(source: string): Promise<Bend.Book> {
  fs.writeFileSync(input, source);
  const result = Bend.book_nil();
  await Bend.book_load(result, input, '', new Map());
  Bend.book_valid(result);
  return result;
}

function expect(args: string[], answer: string): void {
  const run = Bun.spawnSync(args);
  const actual = run.stdout.toString().trim();
  if (run.exitCode !== 0 || actual !== answer) {
    throw new Error(`${args.join(' ')}: ${actual}; ${run.stderr.toString()}`);
  }
}

try {
  const a = await book(total);
  const b = await book(stopping);
  const ca = path.join(dir, 'a.c');
  const cb = path.join(dir, 'b.c');
  fs.writeFileSync(ca, Comp.compile_book(a));
  fs.writeFileSync(cb, Comp.compile_book(b));
  for (const [name, want] of [['a', '2'], ['b', '3']]) {
    expect(['clang', '-O2', path.join(dir, `${name}.c`), '-o',
      path.join(dir, name)], '');
    expect([path.join(dir, name), '--threads', '1', '--gpu', 'off'], want);
  }
  fs.writeFileSync(path.join(dir, 'a.js'), Comp.js_book(a));
  fs.writeFileSync(path.join(dir, 'b.js'), Comp.js_book(b));
  expect(['bun', path.join(dir, 'a.js')], '2');
  expect(['bun', path.join(dir, 'b.js')], '3');
  console.log('PASS: separate books retain their own constructor reachability');
} finally {
  fs.rmSync(dir, { recursive: true, force: true });
}
