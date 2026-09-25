import Base
import ./rank2_static_typed.bend as S
import ./rank2_rf_values.bend as V
import ./rank2_auto_sources.bend as P
import ./rank2_companion_api.bend as Auto
import ../../transduce.bend as T

# This is deliberately an experiment in the library, not a compiler rule.
# Drive performs an inner fold without starting or finishing the consumer.
def cat_source_step(~B: Type, ~X: Type,
  ~Drive: @-R: Type -> @-r: T.Reducer<B, R> ->
    X -> T.Control<T.State(B, R, r)> -> T.Control<T.State(B, R, r)>,
  ~R: Type, ~down: T.Reducer<B, R>,
  src: T.Source<B, X, Drive>, state: T.State(B, R, down)) ->
  T.Control<T.State(B, R, down)>:
  match src:
    case T.Source{input}:
      Drive(R, down, input, T.Continue{state})

def cat_source(~B: Type, ~X: Type,
  ~Drive: @-R: Type -> @-r: T.Reducer<B, R> ->
    X -> T.Control<T.State(B, R, r)> -> T.Control<T.State(B, R, r)>,
  ~R: Type, ~down: T.Reducer<B, R>) ->
  T.Reducer<T.Source<B, X, Drive>, R>:
  T.Reducer{T.Config(B, R, down), T.State(B, R, down),
    c => T.start(B, R, down, c),
    s => src => cat_source_step(~B, ~X, ~Drive, ~R, ~down, src, s),
    s => T.finish(B, R, down, s)}

def mapcat_source(~A: Type, ~B: Type, ~X: Type,
  ~Drive: @-R: Type -> @-r: T.Reducer<B, R> ->
    X -> T.Control<T.State(B, R, r)> -> T.Control<T.State(B, R, r)>,
  ~R: Type, ~f: A -> T.Source<B, X, Drive>,
  ~down: T.Reducer<B, R>) -> T.Reducer<A, R>:
  T.map(~A, ~T.Source<B, X, Drive>, ~R, ~f,
    ~cat_source(~B, ~X, ~Drive, ~R, ~down))

def pair_source(+x: U32) -> T.Source<U32, P.SamplePair,
  (R => r => pair => c => P.fold_pair(~R, ~r, pair, c))>:
  P.SamplePair.source(P.SamplePair{x, (x + 10 : U32)})

def pair_stage() -> S.Xf<U32, U32,
  (R => down => mapcat_source(~U32, ~U32, ~P.SamplePair,
    ~(Result => recipe => pair => c =>
      P.fold_pair(~Result, ~recipe, pair, c)),
    ~R, ~(x => pair_source(x)), ~down))>:
  S.Xf{R => down => config => config}

def list_pair(+x: U32) -> List<U32>:
  [x, (x + 10 : U32)]

def via_source(xs: List<U32>) -> U32:
  Auto.transduce(pair_stage(), V.sum_rf(), 0, xs)

def via_list(xs: List<U32>) -> U32:
  Auto.transduce(V.mapcat(~U32, ~U32, ~(x => list_pair(x))),
    V.sum_rf(), 0, xs)

def take_source(xs: List<U32>, n: Nat) -> U32:
  Auto.transduce(V.comp2(pair_stage(), V.take(~U32, n)),
    V.sum_rf(), 0, xs)

def take_list(xs: List<U32>, n: Nat) -> U32:
  Auto.transduce(V.comp2(V.mapcat(~U32, ~U32,
    ~(x => list_pair(x))), V.take(~U32, n)),
    V.sum_rf(), 0, xs)

def retain_source(dest: List<U32>, xs: List<U32>) -> List<U32>:
  Auto.into(dest, pair_stage(), xs)

def retain_list(dest: List<U32>, xs: List<U32>) -> List<U32>:
  Auto.into(dest, V.mapcat(~U32, ~U32, ~(x => list_pair(x))), xs)

def bag_finish_count(dest: P.Bag, xs: List<U32>) -> P.Bag:
  Auto.into(dest, V.comp2(pair_stage(), V.take(~U32, 3n)), xs)

def main() -> U32 & U32 & U32 & U32 & List<U32> & List<U32> & P.Bag:
  (via_source([1, 2, 3]), via_list([1, 2, 3]),
   take_source([1, 2, 3], 3n), take_list([1, 2, 3], 3n),
   retain_source([], [1, 2]), retain_list([], [1, 2]),
   bag_finish_count(P.Bag{[9], 0}, [1, 2, 3]))
#|(42, 42, 14, 14, [12, 2, 11, 1], [12, 2, 11, 1], rank2_auto_sources.Bag{[2, 11, 1, 9], 1})
