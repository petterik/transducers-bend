import Base
import ./rank2_rf_values.bend as V
import ../../transduce.bend as T

# Fast generic variant for Data elements. Explicit &2 keeps Maybe<A> Data,
# allowing Array.new to allocate a vacant half as one flat block.
type VecData<-A: Data> is Type:
  VecData{length: U32, capacity: U32, depth: Nat,
    slots: Array<Maybe<&2, A>>}

def empty(~A: Data) -> VecData<A>:
  VecData{0, 1, 0n, Array.new(Maybe<&2, A>, 0n, None{})}

def grow(~A: Data, slots: Array<Maybe<&2, A>>, depth: Nat) ->
  Array<Maybe<&2, A>>:
  ANode{slots, Array.new(Maybe<&2, A>, depth, None{})}

def push_space(~A: Data, +length: U32, +capacity: U32, +depth: Nat,
  slots: Array<Maybe<&2, A>>, value: A, has_space: Bool) -> VecData<A>:
  match has_space:
    case True{}:
      VecData{U32.add(length, 1), capacity, depth,
        Array.set(Maybe<&2, A>, slots, length, Some{value})}
    case False{}:
      VecData{U32.add(length, 1), U32.add(capacity, capacity),
        Nat.add(depth, 1n),
        Array.set(Maybe<&2, A>, grow(~A, slots, depth),
          length, Some{value})}

def push(~A: Data, vec: VecData<A>, value: A) -> VecData<A>:
  match vec:
    case VecData{+length, +capacity, depth, slots}:
      push_space(~A, length, capacity, depth, slots, value,
        U32.is_lt(length, capacity))

def step(~A: Data, vec: VecData<A>, value: A) -> T.Control<VecData<A>>:
  T.Continue{push(~A, vec, value)}

def reducer(~A: Data) -> T.Reducer<A, VecData<A>>:
  T.Reducer{VecData<A>, VecData<A>, vec => T.Continue{vec},
    vec => value => step(~A, vec, value), vec => vec}

def rf(~A: Data) -> V.Rf<A, VecData<A>, reducer(~A), VecData<A>>:
  V.Rf{vec => vec}

def VecData.destination(~A: Data, vec: VecData<A>) ->
  V.Destination<A, VecData<A>, reducer(~A)>:
  V.Destination{vec, rf(~A)}

def done(~A: Data, ~R: Type, ~r: T.Reducer<A, R>,
  slots: Array<Maybe<&2, A>>, control: T.Control<T.State(A, R, r)>) ->
  T.Control<(Array<Maybe<&2, A>> & T.State(A, R, r))>:
  match control:
    case T.Stop{state}:
      T.Stop{(slots, state)}
    case T.Continue{state}:
      T.Continue{(slots, state)}

def after_get(~A: Data, ~R: Type, ~r: T.Reducer<A, R>,
  state: T.State(A, R, r),
  result: Array<Maybe<&2, A>> & Maybe<&2, A>) ->
  T.Control<(Array<Maybe<&2, A>> & T.State(A, R, r))>:
  (slots, item) = result
  match item:
    case None{}:
      T.Continue{(slots, state)}
    case Some{value}:
      done(~A, ~R, ~r, slots, T.step(A, R, r, state, value))

def fold_step(~A: Data, ~R: Type, ~r: T.Reducer<A, R>,
  pair: Array<Maybe<&2, A>> & T.State(A, R, r), index: U32) ->
  T.Control<(Array<Maybe<&2, A>> & T.State(A, R, r))>:
  (slots, state) = pair
  after_get(~A, ~R, ~r, state,
    Array.get(Maybe<&2, A>, slots, index))

def start(~A: Data, ~R: Type, ~r: T.Reducer<A, R>,
  slots: Array<Maybe<&2, A>>,
  control: T.Control<T.State(A, R, r)>) ->
  T.Control<(Array<Maybe<&2, A>> & T.State(A, R, r))>:
  match control:
    case T.Stop{state}:
      T.Stop{(slots, state)}
    case T.Continue{state}:
      T.Continue{(slots, state)}

def finish(~A: Data, ~R: Type, ~r: T.Reducer<A, R>,
  control: T.Control<(Array<Maybe<&2, A>> & T.State(A, R, r))>) ->
  T.Control<T.State(A, R, r)>:
  match control:
    case T.Stop{(slots, state)}:
      T.Stop{state}
    case T.Continue{(slots, state)}:
      T.Continue{state}

def drive(~A: Data, ~R: Type, ~r: T.Reducer<A, R>,
  vec: VecData<A>, control: T.Control<T.State(A, R, r)>) ->
  T.Control<T.State(A, R, r)>:
  match vec:
    case VecData{length, capacity, depth, slots}:
      finish(~A, ~R, ~r, T.reduce_range(
        ~(Array<Maybe<&2, A>> & T.State(A, R, r)),
        ~(pair => index => fold_step(~A, ~R, ~r, pair, index)),
        T.range_between(0, length),
        start(~A, ~R, ~r, slots, control)))

def VecData.source(~A: Data, vec: VecData<A>) -> T.Source<A, VecData<A>,
  (R => r => v => c => drive(~A, ~R, ~r, v, c))>:
  T.Source{vec}
