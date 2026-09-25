import Base
import ./rank2_rf_values.bend as V
import ./rank2_sources.bend as Sources
import ./rank2_static_typed.bend as S
import ../../transduce.bend as T

# This source and destination live outside the transducer library.
type SamplePair is Type:
  SamplePair{first: U32, second: U32}

def second(~R: Type, ~r: T.Reducer<U32, R>, x: U32,
  c: T.Control<T.State(U32, R, r)>) -> T.Control<T.State(U32, R, r)>:
  match c:
    case T.Stop{s}:
      T.Stop{s}
    case T.Continue{s}:
      T.step(U32, R, r, s, x)

def fold_pair(~R: Type, ~r: T.Reducer<U32, R>, pair: SamplePair,
  c: T.Control<T.State(U32, R, r)>) -> T.Control<T.State(U32, R, r)>:
  match pair c:
    case SamplePair{a, b} T.Stop{s}:
      T.Stop{s}
    case SamplePair{a, b} T.Continue{s}:
      second(~R, ~r, b, T.step(U32, R, r, s, a))

def pair_source(input: SamplePair) -> Sources.Source<U32, SamplePair,
  (R => r => pair => c => fold_pair(~R, ~r, pair, c))>:
  Sources.Source{input}

type Bag is Type:
  Bag{items: List<U32>, finishes: U32}

def bag_step(bag: Bag, x: U32) -> T.Control<Bag>:
  match bag:
    case Bag{items, finishes}:
      T.Continue{Bag{x <> items, finishes}}

def bag_finish(bag: Bag) -> Bag:
  match bag:
    case Bag{items, finishes}:
      Bag{items, (finishes + 1 : U32)}

def bag_reducer() -> T.Reducer<U32, Bag>:
  T.Reducer{Bag, Bag, bag => T.Continue{bag},
    bag => x => bag_step(bag, x), bag => bag_finish(bag)}

def bag_rf() -> V.Rf<U32, Bag, bag_reducer(), Bag>:
  V.Rf{initial => initial}

def bag_destination(bag: Bag) -> V.Destination<U32, Bag, bag_reducer()>:
  V.Destination{bag, bag_rf()}

def main() -> U32 & U32 & Bag & Bag & Nat & Bag:
  range_sum = V.transduce_from(
    V.compose(V.shifted(1), V.taking_u32(2n)), V.sum_rf(), 0,
    Sources.range_source(T.range_between(1, 4)))
  pair_sum = V.transduce_from(
    V.compose(V.shifted(1), V.taking_u32(2n)), V.sum_rf(), 0,
    pair_source(SamplePair{1, 2}))
  range_bag = V.into_from(bag_destination(Bag{[9], 0}),
    V.taking_u32(1n), Sources.range_source(T.range_between(1, 4)))
  pair_bag = V.into_from(bag_destination(Bag{[9], 0}),
    V.taking_u32(0n), pair_source(SamplePair{1, 2}))
  pair_count = V.transduce_from(S.mapped(), V.count_nat_rf(), Unit{},
    pair_source(SamplePair{1, 2}))
  composed_stop = V.into_from(bag_destination(Bag{[9], 0}),
    V.comp5(V.shifted(1), V.taking_u32(0n), V.shifted(2),
      V.shifted(3), V.shifted(4)),
    Sources.range_source(T.range_between(1, 4)))
  (range_sum, pair_sum, range_bag, pair_bag, pair_count, composed_stop)
#|(5, 5, Bag{[1, 9], 1}, Bag{[9], 1}, 2n, Bag{[9], 1})
