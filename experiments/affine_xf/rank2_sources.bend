import Base
import ../../transduce.bend as T

def list_source(~A: Type, xs: List<A>) ->
  T.Source<A, List<A>, (R => r => ys => c =>
    T.reduce_list_static(~A, ~R, ~r, ys, c))>:
  T.List.source(~A, xs)

def range_source(xs: T.Range) ->
  T.Source<U32, T.Range, (R => r => ys => c =>
    T.reduce_range(~T.State(U32, R, r),
      ~(s => x => T.step(U32, R, r, s, x)), ys, c))>:
  T.Range.source(xs)

def array_source(~A: Type, xs: Array<A>) ->
  T.Source<A, Array<A>, (R => r => ys => c =>
    T.reduce_array(~A, ~T.State(A, R, r),
      ~(s => x => T.step(A, R, r, s, x)), ys, c))>:
  T.Array.source(~A, xs)
