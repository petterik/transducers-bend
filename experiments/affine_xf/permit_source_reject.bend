import Base
import ../../transduce_core.bend as T

# A source with an abstract permit cannot invent a downstream stop.
def forged(~K: Data, ~S: Type, state: S) -> T.Checked<K, S>:
  T.Halted{Unit{}, state}
