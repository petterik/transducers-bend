-- Direct Lean twin of direct.bend. It uses mutable loops for the scalar
-- reference and UInt32 arithmetic for the same wrapping checksum.
def ARRAY_DEPTH : Nat := 8
def BATCH_DEPTH : Nat := 10
def NORMALIZE_ROUNDS : Nat := 32
def REPEATS : Nat := 2

def work (n : Nat) (x : UInt32) : UInt32 :=
  match n with
  | 0 => x
  | n + 1 =>
      work n ((x * 1664525 + 1013904223) ^^^ (x >>> 13))

def feed (acc x : UInt32) : UInt32 :=
  let normalized := work NORMALIZE_ROUNDS (x ^^^ 2654435761)
  if (normalized &&& 3) == 0 then acc
  else acc + normalized

def leafRun (seed : UInt32) : UInt32 := Id.run do
  let mut acc : UInt32 := 0
  for i in [0:2 ^ ARRAY_DEPTH] do
    let s := seed + i.toUInt32
    acc := feed acc s
    acc := feed acc 1664525
    acc := feed acc 1013904223
    acc := feed acc 2654435761
  return acc

def batchRun : Nat → UInt32 → UInt32
  | 0, seed => leafRun seed
  | p + 1, seed =>
      let left := batchRun p seed
      let rightSeed := seed + (1 <<< (ARRAY_DEPTH + p)).toUInt32
      left + batchRun p rightSeed

def main : IO Unit := do
  let mut answer : UInt32 := 0
  for _ in [0:REPEATS] do
    answer := answer + batchRun BATCH_DEPTH 0
  IO.println answer
