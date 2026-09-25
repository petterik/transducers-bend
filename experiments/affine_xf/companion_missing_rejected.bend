import Base
import ./rank2_rf_values.bend as V
import ./rank2_companion_api.bend as Auto

type Missing is Type:
  Missing{value: U32}

def run(xs: Missing) -> U32:
  Auto.transduce(V.take(~U32, 1n), V.sum_rf(), 0, xs)

def main() -> U32:
  run(Missing{1})
