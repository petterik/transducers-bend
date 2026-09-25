import Base
import ./composable_xf_probe.bend as C
import ./explicit_reducer_types.bend as E
import ../../transduce.bend as T

# Neither end is registered with transduce.bend. The source folds its two
# elements in order; the destination inserts into an owned, nonempty bag.
type PairSource is Type:
  PairSource{first: U32, second: U32}

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

def bag_insert() -> T.Reducer<U32, Bag>:
  T.Reducer{Bag, Bag, bag => T.Continue{bag},
    bag => x => bag_step(bag, x), bag => bag_finish(bag)}

def second(~r: T.Reducer<U32, Bag>, x: U32,
  c: T.Control<T.State(U32, Bag, r)>) -> T.Control<T.State(U32, Bag, r)>:
  match c:
    case T.Stop{s}:
      T.Stop{s}
    case T.Continue{s}:
      T.step(U32, Bag, r, s, x)

def fold_pair(~r: T.Reducer<U32, Bag>, source: PairSource,
  c: T.Control<T.State(U32, Bag, r)>) -> T.Control<T.State(U32, Bag, r)>:
  match source c:
    case PairSource{a, b} T.Stop{s}:
      T.Stop{s}
    case PairSource{a, b} T.Continue{s}:
      second(~r, b, T.step(U32, Bag, r, s, a))

def run(n: Nat, source: PairSource, dest: Bag) -> Bag:
  xf = C.compose(
    ~(K => K), ~(K => K), ~C.map_code,
    ~(K => Nat & K), ~(K => T.Taking<K>), ~C.take_code,
    C.mapped(), C.taking(n))
  config = C.configure(
    (K => Nat & K), (K => T.Taking<K>),
    (R => K => S => down =>
      C.map_code(R, Nat & K, T.Taking<S>, C.take_code(R, K, S, down))),
    Bag, xf, dest)
  T.transduce(~T.reducible(~PairSource, ~U32, ~Bag,
    ~(u => T.map(~U32, ~U32, ~Bag, ~E.plus_one,
      ~T.take(~U32, ~Bag, ~bag_insert()))),
    ~(src => c => fold_pair(
      ~T.map(~U32, ~U32, ~Bag, ~E.plus_one,
        ~T.take(~U32, ~Bag, ~bag_insert())), src, c))),
    config, source)

def summary(bag: Bag) -> List<U32>:
  match bag:
    case Bag{items, finishes}:
      finishes <> items

def main() -> List<List<U32>>:
  [summary(run(2n, PairSource{1, 2}, Bag{[9], 0})),
   summary(run(1n, PairSource{1, 2}, Bag{[9], 0})),
   summary(run(0n, PairSource{1, 2}, Bag{[9], 0}))]
#|[[1, 3, 2, 9], [1, 2, 9], [1, 9]]
