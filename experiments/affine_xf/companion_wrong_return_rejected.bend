import Base
import ./rank2_rf_values.bend as V
import ./rank2_companion_api.bend as Auto

type Wrong is Type:
  Wrong{value: U32}

def Wrong.source(xs: Wrong) -> U32:
  0

def run(xs: Wrong) -> U32:
  Auto.transduce(V.take(~U32, 1n), V.sum_rf(), 0, xs)

def main() -> U32:
  run(Wrong{1})
