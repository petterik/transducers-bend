import Base
import ../../transduce.bend as T

# A source value owns its input. Its erased index provides a closed fold for
# every downstream reducer, including that reducer's stopping/completion.
type Source<-A: Type, -X: Type,
  -Drive: @-R: Type -> @-r: T.Reducer<A, R> ->
    X -> T.Control<T.State(A, R, r)> ->
      T.Control<T.State(A, R, r)>> is Type:
  Source{input: X}

# Opt in to the experimental owner-companion conversion rule. This marker
# does not run and is not a source implementation itself.
def Source.allow_companion() -> Unit:
  Unit{}

def list_source(~A: Type, xs: List<A>) ->
  Source<A, List<A>, (R => r => ys => c =>
    T.reduce_list_static(~A, ~R, ~r, ys, c))>:
  Source{xs}

# Protocol-owned extension for a Base type: Base cannot import Source.
def List.source(~A: Type, xs: List<A>) ->
  Source<A, List<A>, (R => r => ys => c =>
    T.reduce_list_static(~A, ~R, ~r, ys, c))>:
  list_source(~A, xs)

def range_source(xs: T.Range) ->
  Source<U32, T.Range, (R => r => ys => c =>
    T.reduce_range(~T.State(U32, R, r),
      ~(s => x => T.step(U32, R, r, s, x)), ys, c))>:
  Source{xs}
