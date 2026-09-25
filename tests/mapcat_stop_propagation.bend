import Base
import ../xf.bend as Xf
import ./support/vec_pair_source.bend as Pair

def make_fragment(+x: U32) -> Pair.PairSource:
  Pair.PairSource{x, (x + 10 : U32)}

def run(xs: List<U32>) -> U32:
  Xf.transduce(Xf.comp2(
    Xf.mapcat(~U32, ~U32, ~Pair.PairSource,
      ~(S => advance => inspect => pair => s =>
        Pair.source_pair(~S, ~advance, ~inspect, pair, s)),
      ~(x => make_fragment(x))),
    Xf.take(~U32, 3n)), Xf.sum_rf(), 0, xs)

def main() -> U32:
  run([1, 2, 3, 4])
#|14
