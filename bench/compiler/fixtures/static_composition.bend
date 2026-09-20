import Base
import ../../../transduce.bend as T

# This binding deliberately removes the Unit -> Reducer recipe delay. It is an
# experiment, not a second public API: the probe asks whether the current
# specializer can resolve a closed reducer directly without the library's
# staging workaround.
def over_list_eager(~A: Type, ~R: Type, ~r: T.Reducer<A, R>) -> T.Reduction:
  T.Reduction{u => List<A>, u => R, u => T.Config(A, R, r),
    config => xs => T.finish_control(~A, ~R, ~r,
      T.reduce_list_static(~A, ~R, ~r, xs, T.start(A, R, r, config)))}

def inc(x: U32) -> U32:
  (x + 1 : U32)

def above(t: U32, x: U32) -> Bool:
  U32.is_gt(x, t)

def pipeline() -> T.Reducer<U32, U32>:
  T.map(~U32, ~U32, ~U32, ~inc,
    ~T.filter(~U32, ~U32, ~U32, ~above,
      ~T.take(~U32, ~U32, ~T.sum())))

def normal() -> U32:
  T.transduce(~T.over_list(~U32, ~U32,
    ~T.map(~U32, ~U32, ~U32, ~inc, ~T.sum())), 0, [1, 2, 3])

def eager() -> U32:
  T.transduce(~over_list_eager(~U32, ~U32,
    ~T.map(~U32, ~U32, ~U32, ~inc, ~T.sum())), 0, [1, 2, 3])

def complex() -> U32:
  T.transduce(~T.over_list(~U32, ~U32, ~pipeline()),
    (2, (2n, 0)), [1, 2, 3, 4, 5])

def complex_eager() -> U32:
  T.transduce(~over_list_eager(~U32, ~U32, ~pipeline()),
    (2, (2n, 0)), [1, 2, 3, 4, 5])

def buffered() -> Nat:
  T.transduce(~T.over_list(~U32, ~Nat,
    ~T.partition_all(~U32, ~Nat, ~T.count(~List<U32>))),
    (2n, Unit{}), [1, 2, 3, 4, 5])

def buffered_eager() -> Nat:
  T.transduce(~over_list_eager(~U32, ~Nat,
    ~T.partition_all(~U32, ~Nat, ~T.count(~List<U32>))),
    (2n, Unit{}), [1, 2, 3, 4, 5])

def main() -> List<U32>:
  [normal(), eager(), complex(), complex_eager(),
   U32.from_nat(buffered()), U32.from_nat(buffered_eager())]
#|[9, 9, 7, 7, 3, 3]
