import Base
import ./composable_xf_probe.bend as C
import ./explicit_reducer_types.bend as E
import ../../transduce.bend as T

# The same owned configuration and closed stage recipe can drive a Range.
# This repeats the hand elaboration deliberately: automatic elaboration is
# the feature the experiment is testing for, not a capability Bend has yet.
def run(n: Nat, source: T.Range) -> U32:
  xf = C.compose(
    ~(K => K), ~(K => K), ~C.map_code,
    ~(K => Nat & K), ~(K => T.Taking<K>), ~C.take_code,
    C.mapped(), C.taking(n))
  config = C.configure(
    (K => Nat & K), (K => T.Taking<K>),
    (R => K => S => down =>
      C.map_code(R, Nat & K, T.Taking<S>, C.take_code(R, K, S, down))),
    U32, xf, 0)
  T.transduce(~T.over_range(~U32,
    ~T.map(~U32, ~U32, ~U32, ~E.plus_one,
      ~T.take(~U32, ~U32, ~T.sum()))),
    config, source)

def main() -> U32:
  (run(2n, T.range_between(1, 6))
    + run(0n, T.range_between(1, 6))
    + run(2n, T.range_between(6, 6))
    + run(10n, T.range_between(1, 6)) : U32)
#|25
