import Base
import ./rank2_rf_values.bend as V
import ./rank2_companion_api.bend as Auto
import ./rank2_sources.bend as Sources
import ./companion_orphan_type.bend as O
import ../../transduce.bend as T

# This same-spelled method belongs to the importing module, not Orphan's
# defining module. The owner-only resolver must ignore it.
def Orphan.source(xs: O.Orphan) -> T.Source<U32, O.Orphan,
  (R => r => value => c => c)>:
  T.Source{xs}

def run(xs: O.Orphan) -> U32:
  Auto.transduce(V.take(~U32, 1n), V.sum_rf(), 0, xs)

def main() -> U32:
  run(O.Orphan{1})
