import Base
import ../../../transduce.bend as T

def above(t: U32, x: U32) -> Bool:
  U32.is_gt(x, t)

def pipeline() -> T.Reducer<U32, List<U32>>:
  T.filter(~U32, ~List<U32>, ~U32, ~above,
    ~T.take(~U32, ~List<U32>, ~T.into_list(~U32)))

def run(n: Nat) -> List<U32>:
  T.transduce(~T.over_list(~U32, ~List<U32>, ~pipeline()), (3, (n, Unit{})),
    [0, 1, 2, 3, 4, 5])

def main() -> IO(Unit):
  do IO<Unit>:
    IO.print(List.show(~&1, ~U32, ~U32.show, run(0n)))
    IO.print(List.show(~&1, ~U32, ~U32.show, run(2n)))
    IO.print(List.show(~&1, ~U32, ~U32.show, run(32n)))
