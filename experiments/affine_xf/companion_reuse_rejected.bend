import Base
import ./rank2_companion_raw.bend as P
import ./rank2_auto_sources.bend as Sources

def twice(pair: Sources.SamplePair) -> U32:
  (P.pair_sum(pair) + P.pair_sum(pair) : U32)

def main() -> U32:
  twice(Sources.SamplePair{1, 2})
