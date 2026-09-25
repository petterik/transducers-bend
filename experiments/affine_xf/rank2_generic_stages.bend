import Base
import ./rank2_rf_values.bend as V
import ./custom_shift.bend as Shift

def small(x: U32) -> Bool:
  U32.is_lt(x, 4)

def even(x: U32) -> Bool:
  U32.is_eq((x % 2 : U32), 0)

def maybe_nat_choose(is_even: Bool, x: U32) -> Maybe<Nat>:
  match is_even:
    case True{}:
      Some{U32.to_nat(x)}
    case False{}:
      None{}

def maybe_nat(+x: U32) -> Maybe<Nat>:
  maybe_nat_choose(even(x), x)

def duplicate(+x: U32) -> List<U32>:
  [x, (x + 10 : U32)]

def five_stages() -> List<Nat>:
  V.into([], V.comp5(
    V.map_with(~U32, ~U32, ~U32, ~Shift.add, 1),
    V.filter(~U32, ~small),
    V.remove(~U32, ~even),
    V.take(~U32, 3n),
    V.map(~U32, ~Nat, ~U32.to_nat)), [1, 2, 3, 4, 5])

def count_mapped() -> Nat:
  V.transduce(V.map(~U32, ~Nat, ~U32.to_nat),
    V.count_nat_rf(), Unit{}, [1, 2, 3])

def kept() -> List<Nat>:
  V.into([], V.keep(~U32, ~Nat, ~(x => maybe_nat(x))), [1, 2, 3, 4])

def flattened() -> List<U32>:
  V.into([], V.comp2(V.mapcat(~U32, ~U32, ~(x => duplicate(x))),
    V.take(~U32, 3n)), [1, 2, 3])

def main() -> List<Nat> & U32 & U32 & Nat & List<U32> & List<Nat>:
  (five_stages(), V.transduce(V.take(~U32, 0n), V.sum_rf(), 0, [1, 2]),
    V.transduce(V.remove(~U32, ~even), V.sum_rf(), 0, [1, 2, 3]),
    count_mapped(), flattened(), kept())
#|([3n], 0, 4, 3n, [2, 11, 1], [4n, 2n])
