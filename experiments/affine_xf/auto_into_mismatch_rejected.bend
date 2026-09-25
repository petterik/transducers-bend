import Base
import ./rank2_rf_values.bend as V

def main() -> List<Bool>:
  V.into([True{}], V.shifted(1), [1, 2])
