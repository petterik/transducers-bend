import ./common.bend as W

# The runner substitutes W.transduced with W.staged or W.direct for
# the other Bend variants. Keeping one driver makes the timing and batch
# semantics identical across all three comparisons.
def leaf_run(seed: U32) -> U32:
  W.transduced(W.build(ARRAY_DEPTHn, seed))

def batch(+p: Nat, +seed: U32) -> U32:
  match p:
    case 0n:
      leaf_run(seed)
    case 1n+q:
      a b = batch(q, seed)
        batch(q, U32.add(seed, U32.shln(1, Nat.add(q, ARRAY_DEPTHn))))
      U32.add(a, b)

def repeat(n: Nat, +acc: U32) -> U32:
  match n:
    case 0n:
      acc
    case 1n+p:
      repeat(p, U32.add(acc, batch!(BATCH_DEPTHn, 0)))

def measure(n: Nat) -> IO(Unit):
  match n:
    case 0n:
      IO.pure(Unit, Unit{})
    case 1n+p:
      do IO<Unit>:
        before : Nat <- IO.now()
        answer : U32 = repeat(REPEATSn, 0)
        after : Nat <- IO.now()
        IO.print(U32.show(answer) ++ ":" ++ Nat.show(Nat.sub(after, before)))
        measure(p)

def main() -> IO(Unit):
  measure(SAMPLESn)
