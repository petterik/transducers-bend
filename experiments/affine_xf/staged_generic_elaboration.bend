import Base
import ./composable_xf_probe.bend as C
import ./explicit_reducer_types.bend as E
import ../../transduce.bend as T

# The composed code index is applied in closed template syntax. This tests
# whether generic stage code itself specializes, without spelling T.map/take.
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
  C.run_recipe(~U32, ~(Nat & U32), ~T.Taking<U32>,
    ~C.map_code(U32, Nat & U32, T.Taking<U32>,
      C.take_code(U32, U32, U32, E.sum2())),
    config, xs)

def main() -> U32:
  run(2n, [1, 2, 3])
#|5
