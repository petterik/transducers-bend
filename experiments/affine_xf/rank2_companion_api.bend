import Base
import ./rank2_rf_values.bend as V
import ./rank2_static_typed.bend as S
import ./rank2_sources.bend as Sources
import ../../transduce.bend as T

# One public spelling for every source accepted by the isolated companion
# candidate. The expected witness types trigger checked, owner-scoped
# conversion of a raw owned collection at the call site.
def transduce(~A: Type, ~B: Type,
  ~P: @-Result: Type -> @-consumer: T.Reducer<B, Result> ->
    T.Reducer<A, Result>,
  ~R: Type, ~Q: T.Reducer<B, R>, ~Init: Type,
  ~X: Type,
  ~Drive: @-Result: Type -> @-recipe: T.Reducer<A, Result> ->
    X -> T.Control<T.State(A, Result, recipe)> ->
      T.Control<T.State(A, Result, recipe)>,
  xf: S.Xf<A, B, P>, rf: V.Rf<B, R, Q, Init>,
  initial: Init, source: T.Source<A, X, Drive>) -> R:
  V.transduce_from(~A, ~B, ~P, ~R, ~Q, ~Init, ~X, ~Drive,
    xf, rf, initial, source)

def into(~A: Type, ~B: Type,
  ~P: @-Result: Type -> @-consumer: T.Reducer<B, Result> ->
    T.Reducer<A, Result>,
  ~D: Type, ~Q: T.Reducer<B, D>, ~X: Type,
  ~Drive: @-Result: Type -> @-recipe: T.Reducer<A, Result> ->
    X -> T.Control<T.State(A, Result, recipe)> ->
      T.Control<T.State(A, Result, recipe)>,
  dest: V.Destination<B, D, Q>, xf: S.Xf<A, B, P>,
  source: T.Source<A, X, Drive>) -> D:
  V.into_from(~A, ~B, ~P, ~D, ~Q, ~X, ~Drive,
    dest, xf, source)
