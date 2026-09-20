import Base
import ../../../transduce.bend as T

def keep(+x: U32) -> Bool:
  U32.is_gt(x, 1)

def keep_unit(local: Unit, x: U32) -> Bool:
  keep(x)

def pipeline() -> T.Reducer<U32, U32>:
  T.filter(~U32, ~U32, ~Unit, ~keep_unit,
    ~T.take(~U32, ~U32, ~T.sum()))

def build(+n: Nat, xs: List<U32>) -> List<U32>:
  match n:
    case 0n:
      xs
    case 1n+p:
      build(p, U32.from_nat(p) <> xs)

def run(+n: Nat) -> U32:
  T.transduce(~T.over_list(~U32, ~U32, ~pipeline()),
    (Unit{}, (n, 0)), build(n, []))

def main() -> IO(Unit):
  IO.print(U32.show(run(0n)) ++ ":" ++ U32.show(run(1n)) ++ ":" ++
    U32.show(run(32n)) ++ ":" ++ U32.show(run(200000n)))
