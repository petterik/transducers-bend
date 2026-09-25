import Base
import ./rank2_rf_values.bend as V
import ./rank2_companion_api.bend as Auto
import ./rank2_auto_sources.bend as P

# These calls pass raw owned values. The isolated candidate inserts the
# owner-qualified companion methods when Source/Destination are expected.
def pair_sum(pair: P.SamplePair) -> U32:
  Auto.transduce(V.comp2(V.shifted(1), V.take(~U32, 2n)),
    V.sum_rf(), 0, pair)

def into_pair(bag: P.Bag, pair: P.SamplePair) -> P.Bag:
  Auto.into(bag, V.take(~U32, 1n), pair)

def list_sum(xs: List<U32>) -> U32:
  Auto.transduce(V.take(~U32, 2n), V.sum_rf(), 0, xs)

def pair_count(pair: P.SamplePair) -> Nat:
  Auto.transduce(V.map(~U32, ~Nat, ~U32.to_nat),
    V.count_nat_rf(), Unit{}, pair)

def into_list(dest: List<U32>, xs: List<U32>) -> List<U32>:
  Auto.into(dest, V.take(~U32, 2n), xs)

def make_pair() -> P.SamplePair:
  P.SamplePair{1, 2}

def make_list() -> List<U32>:
  [1, 2, 3]

def make_dest() -> List<U32>:
  [9]

def direct_calls() -> U32 & List<U32>:
  (Auto.transduce(V.take(~U32, 2n), V.sum_rf(), 0, make_pair()),
    Auto.into(make_dest(), V.take(~U32, 2n), make_list()))

def bag_summary(bag: P.Bag) -> U32 & U32:
  match bag:
    case P.Bag{items, finishes}:
      match items:
        case Nil{}:
          (0, finishes)
        case h <> t:
          (h, finishes)

def main() -> U32 & (U32 & U32) & U32 & List<U32> & Nat & (U32 & List<U32>):
  (pair_sum(P.SamplePair{1, 2}),
    bag_summary(into_pair(P.Bag{[9], 0}, P.SamplePair{1, 2})),
    list_sum([1, 2, 3]), into_list([9], [1, 2, 3]),
    pair_count(P.SamplePair{1, 2}), direct_calls())
#|(5, (1, 1), 3, [2, 1, 9], 2n, 3, [2, 1, 9])
