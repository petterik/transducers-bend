import Base
import ./rank2_rf_values.bend as V

def reusable(+x: U32) -> Maybe<U32>:
  Some{x}

def main() -> List<U32>:
  V.into([], V.keep(~U32, ~U32, ~reusable), [1, 2])
