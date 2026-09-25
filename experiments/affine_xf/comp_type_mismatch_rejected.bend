import Base
import ./rank2_rf_values.bend as V
import ./rank2_static_typed.bend as S

def main() -> U32:
  bad = V.comp3(S.mapped(), V.taking_u32(2n), V.shifted(1))
  0
