import Base
import ../../transduce.bend as T
import ./group_fold_probe.bend as G

# Adversarial fixture: group_fold's input elements and fold state may be
# affine. Each Array is consumed exactly once by Array.get; the returned owner
# is dropped after the selected element is read.
def affine_array_values(n: Nat, arrays: List<Array<U32>>) -> List<Array<U32>>:
  match n:
    case 0n:
      arrays
    case 1n++p:
      value = U32.from_nat(p)
      array = [value : U32*1n]
      affine_array_values(p, array <> arrays)

def array_sum_advance_after(total: U32, result: Array<U32> & U32) -> U32:
  (unused, value) = result
  (total + value : U32)

def array_sum_advance(total: U32, array: Array<U32>) -> U32:
  array_sum_advance_after(total, Array.get(U32, array, 0))

def affine_group_sum(width: Nat, budget: Nat,
  arrays: List<Array<U32>>) -> U32:
  T.transduce(~T.over_list(~Array<U32>, ~U32,
    ~G.group_fold(~Array<U32>, ~U32, ~U32, ~U32, ~G.sum_start,
      ~array_sum_advance, ~G.sum_finish,
      ~T.take(~U32, ~U32,
        ~T.reducing(~U32, ~U32, ~U32, ~G.add_group_sum, ~(s => s))))),
    (width, (budget, 0)), arrays)

def main() -> List<Bool>:
  [U32.is_eq(affine_group_sum(3n, 4n, affine_array_values(10n, [])), 45),
   U32.is_eq(affine_group_sum(3n, 2n, affine_array_values(10n, [])), 15),
   U32.is_eq(affine_group_sum(0n, 4n, affine_array_values(10n, [])), 0)]
