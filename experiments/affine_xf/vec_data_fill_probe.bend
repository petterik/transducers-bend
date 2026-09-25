import Base
import ./rank2_rf_values.bend as V
import ../../transduce.bend as T

# Data can be copied, so a caller-provided filler permits one-block growth
# without a Maybe tag. The filler never appears in the initialized prefix.
type VecFill<-A: Data> is Type:
  VecFill{length: U32, capacity: U32, depth: Nat,
    filler: A, slots: Array<A>}

def empty(~A: Data, +filler: A) -> VecFill<A>:
  VecFill{0, 1, 0n, filler, Array.new(A, 0n, filler)}

def reserve_after_size(~A: Data, filler: A, depth: Nat,
  result: Array<A> & U32) -> VecFill<A>:
  (slots, capacity) = result
  VecFill{0, capacity, depth, filler, slots}

def reserve(~A: Data, +depth: Nat, +filler: A) -> VecFill<A>:
  reserve_after_size(~A, filler, depth,
    Array.size(A, Array.new(A, depth, filler)))

def grow(~A: Data, slots: Array<A>, depth: Nat, filler: A) -> Array<A>:
  ANode{slots, Array.new(A, depth, filler)}

def push_space(~A: Data, +length: U32, +capacity: U32, +depth: Nat,
  +filler: A, slots: Array<A>, value: A, has_space: Bool) -> VecFill<A>:
  match has_space:
    case True{}:
      VecFill{U32.add(length, 1), capacity, depth, filler,
        Array.set(A, slots, length, value)}
    case False{}:
      VecFill{U32.add(length, 1), U32.add(capacity, capacity),
        Nat.add(depth, 1n), filler,
        Array.set(A, grow(~A, slots, depth, filler), length, value)}

def push(~A: Data, vec: VecFill<A>, value: A) -> VecFill<A>:
  match vec:
    case VecFill{+length, +capacity, depth, +filler, slots}:
      push_space(~A, length, capacity, depth, filler, slots, value,
        U32.is_lt(length, capacity))

def get_after(~A: Data, length: U32, capacity: U32, depth: Nat,
  filler: A, result: Array<A> & A) -> VecFill<A> & Maybe<&2, A>:
  (slots, value) = result
  (VecFill{length, capacity, depth, filler, slots}, Some{value})

def get_if(~A: Data, length: U32, capacity: U32, depth: Nat,
  filler: A, slots: Array<A>, index: U32, valid: Bool) ->
  VecFill<A> & Maybe<&2, A>:
  match valid:
    case True{}:
      get_after(~A, length, capacity, depth, filler,
        Array.get(A, slots, index))
    case False{}:
      (VecFill{length, capacity, depth, filler, slots}, None{})

def get(~A: Data, vec: VecFill<A>, +index: U32) ->
  VecFill<A> & Maybe<&2, A>:
  match vec:
    case VecFill{+length, capacity, depth, filler, slots}:
      get_if(~A, length, capacity, depth, filler, slots, index,
        U32.is_lt(index, length))

type UpdateResult<-A: Data> is Type:
  Updated{vec: VecFill<A>, old: A}
  Invalid{vec: VecFill<A>, value: A}

def set_after(~A: Data, length: U32, capacity: U32, depth: Nat,
  filler: A, result: Array<A> & A) -> UpdateResult<A>:
  (slots, old) = result
  Updated{VecFill{length, capacity, depth, filler, slots}, old}

def set_if(~A: Data, length: U32, capacity: U32, depth: Nat,
  filler: A, slots: Array<A>, index: U32, value: A,
  valid: Bool) -> UpdateResult<A>:
  match valid:
    case True{}:
      set_after(~A, length, capacity, depth, filler,
        Array.swap(A, slots, index, value))
    case False{}:
      Invalid{VecFill{length, capacity, depth, filler, slots}, value}

def set(~A: Data, vec: VecFill<A>, +index: U32, value: A) ->
  UpdateResult<A>:
  match vec:
    case VecFill{+length, capacity, depth, filler, slots}:
      set_if(~A, length, capacity, depth, filler, slots, index,
        value, U32.is_lt(index, length))

def step(~A: Data, vec: VecFill<A>, value: A) -> T.Control<VecFill<A>>:
  T.Continue{push(~A, vec, value)}

def reducer(~A: Data) -> T.Reducer<A, VecFill<A>>:
  T.Reducer{VecFill<A>, VecFill<A>, vec => T.Continue{vec},
    vec => value => step(~A, vec, value), vec => vec}

def rf(~A: Data) -> V.Rf<A, VecFill<A>, reducer(~A), VecFill<A>>:
  V.Rf{vec => vec}

def VecFill.destination(~A: Data, vec: VecFill<A>) ->
  V.Destination<A, VecFill<A>, reducer(~A)>:
  V.Destination{vec, rf(~A)}

def done(~A: Data, ~R: Type, ~r: T.Reducer<A, R>,
  slots: Array<A>, control: T.Control<T.State(A, R, r)>) ->
  T.Control<(Array<A> & T.State(A, R, r))>:
  match control:
    case T.Stop{state}:
      T.Stop{(slots, state)}
    case T.Continue{state}:
      T.Continue{(slots, state)}

def after_get(~A: Data, ~R: Type, ~r: T.Reducer<A, R>,
  state: T.State(A, R, r), result: Array<A> & A) ->
  T.Control<(Array<A> & T.State(A, R, r))>:
  (slots, value) = result
  done(~A, ~R, ~r, slots, T.step(A, R, r, state, value))

def fold_step(~A: Data, ~R: Type, ~r: T.Reducer<A, R>,
  pair: Array<A> & T.State(A, R, r), index: U32) ->
  T.Control<(Array<A> & T.State(A, R, r))>:
  (slots, state) = pair
  after_get(~A, ~R, ~r, state, Array.get(A, slots, index))

def start(~A: Data, ~R: Type, ~r: T.Reducer<A, R>,
  slots: Array<A>, control: T.Control<T.State(A, R, r)>) ->
  T.Control<(Array<A> & T.State(A, R, r))>:
  match control:
    case T.Stop{state}:
      T.Stop{(slots, state)}
    case T.Continue{state}:
      T.Continue{(slots, state)}

def finish(~A: Data, ~R: Type, ~r: T.Reducer<A, R>,
  control: T.Control<(Array<A> & T.State(A, R, r))>) ->
  T.Control<T.State(A, R, r)>:
  match control:
    case T.Stop{(slots, state)}:
      T.Stop{state}
    case T.Continue{(slots, state)}:
      T.Continue{state}

def drive(~A: Data, ~R: Type, ~r: T.Reducer<A, R>,
  vec: VecFill<A>, control: T.Control<T.State(A, R, r)>) ->
  T.Control<T.State(A, R, r)>:
  match vec:
    case VecFill{length, capacity, depth, filler, slots}:
      finish(~A, ~R, ~r, T.reduce_range(
        ~(Array<A> & T.State(A, R, r)),
        ~(pair => index => fold_step(~A, ~R, ~r, pair, index)),
        T.range_between(0, length), start(~A, ~R, ~r, slots, control)))

def VecFill.source(~A: Data, vec: VecFill<A>) -> T.Source<A, VecFill<A>,
  (R => r => v => c => drive(~A, ~R, ~r, v, c))>:
  T.Source{vec}
