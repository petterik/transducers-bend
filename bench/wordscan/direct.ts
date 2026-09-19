// Direct TypeScript twin of direct.bend. The arithmetic is explicitly kept
// in uint32 space so its checksum matches Bend and the C twin.
const ARRAY_DEPTH = 8;
const BATCH_DEPTH = 6;
const NORMALIZE_ROUNDS = 32;
const REPEATS = 1;

const u32 = (x: number): number => x >>> 0;

function work(input: number): number {
  let x = u32(input);
  for (let i = 0; i < NORMALIZE_ROUNDS; i++) {
    x = u32(Math.imul(x, 1664525) + 1013904223 ^ (x >>> 13));
  }
  return x;
}

function feed(acc: number, x: number): number {
  const normalized = work(u32(x ^ 2654435761));
  return (normalized & 3) === 0 ? acc : u32(acc + normalized);
}

function leafRun(seed: number): number {
  let acc = 0;
  const n = 1 << ARRAY_DEPTH;
  for (let i = 0; i < n; i++) {
    const s = u32(seed + i);
    acc = feed(acc, s);
    acc = feed(acc, 1664525);
    acc = feed(acc, 1013904223);
    acc = feed(acc, 2654435761);
  }
  return acc;
}

function batchRun(p: number, seed: number): number {
  if (p === 0) return leafRun(seed);
  const left = batchRun(p - 1, seed);
  const rightSeed = u32(seed + (1 << (ARRAY_DEPTH + p - 1)));
  return u32(left + batchRun(p - 1, rightSeed));
}

let answer = 0;
for (let i = 0; i < REPEATS; i++) {
  answer = u32(answer + batchRun(BATCH_DEPTH, 0));
}
console.log(answer);
