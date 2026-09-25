import Base
import ./composable_xf_probe.bend as C
import ./explicit_reducer_types.bend as E
import ../../transduce.bend as T

# Hand elaboration of a consumed Xf value into runtime config plus a closed
# reducer recipe. The duplicated code index is the intended compiler sugar.
def run(n: Nat, xs: List<U32>) -> U32:
  xf = C.compose(
    ~(K => K), ~(K => K), ~C.map_code,
    ~(K => Nat & K), ~(K => T.Taking<K>), ~C.take_code,
    C.mapped(), C.taking(n))
  config = C.configure(
    (K => Nat & K), (K => T.Taking<K>),
    (R => K => S => down =>
      C.map_code(R, Nat & K, T.Taking<S>, C.take_code(R, K, S, down))),
    U32, xf, 0)
  T.transduce(~T.over_list(~U32, ~U32,
    ~T.map(~U32, ~U32, ~U32, ~E.plus_one,
      ~T.take(~U32, ~U32, ~T.sum()))),
    config, xs)

def main() -> U32:
  run(2n, [1, 2, 3])
#|5
