import Base
import ./xf.bend as V
import ./transduce.bend as T
import ./vec_capacity.bend as Capacity

# Filler-free ordered Data collection. Explicit &2 keeps Maybe<A> Data,
# allowing Array.new to allocate vacant slots as one flat block. This is
# the general Data destination when the caller cannot supply a filler.
# It has an extra tag and branch per element compared with vec.bend.
type VecMaybe<-A: Data> is Type:
  VecMaybe{length: U32, capacity: U32, depth: Nat,
    slots: Array<Maybe<&2, A>>}

def empty(~A: Data) -> VecMaybe<A>:
  VecMaybe{0, 1, 0n, Array.new(Maybe<&2, A>, 0n, None{})}

def reserve_after_size(~A: Data, depth: Nat,
  result: Array<Maybe<&2, A>> & U32) -> VecMaybe<A>:
  (slots, capacity) = result
  VecMaybe{0, capacity, depth, slots}

def reserve_depth(~A: Data, +depth: Nat) -> VecMaybe<A>:
  reserve_after_size(~A, depth,
    Array.size(Maybe<&2, A>,
      Array.new(Maybe<&2, A>, depth, None{})))

def reserve_items_at(~A: Data, choice: Maybe<Nat>) ->
  Maybe<VecMaybe<A>>:
  match choice:
    case None{}:
      None{}
    case Some{depth}:
      Some{reserve_depth(~A, depth)}

def with_capacity(~A: Data, requested: U32) -> Maybe<VecMaybe<A>>:
  reserve_items_at(~A, Capacity.depth_for_items(requested))

def grow(~A: Data, slots: Array<Maybe<&2, A>>, depth: Nat) ->
  Array<Maybe<&2, A>>:
  ANode{slots, Array.new(Maybe<&2, A>, depth, None{})}

def push_space(~A: Data, +length: U32, +capacity: U32, +depth: Nat,
  slots: Array<Maybe<&2, A>>, value: A, has_space: Bool) -> VecMaybe<A>:
  match has_space:
    case True{}:
      VecMaybe{U32.add(length, 1), capacity, depth,
        Array.set(Maybe<&2, A>, slots, length, Some{value})}
    case False{}:
      VecMaybe{U32.add(length, 1), U32.add(capacity, capacity),
        Nat.add(depth, 1n),
        Array.set(Maybe<&2, A>, grow(~A, slots, depth),
          length, Some{value})}

def push(~A: Data, vec: VecMaybe<A>, value: A) -> VecMaybe<A>:
  match vec:
    case VecMaybe{+length, +capacity, depth, slots}:
      push_space(~A, length, capacity, depth, slots, value,
        U32.is_lt(length, capacity))

def get_after(~A: Data, length: U32, capacity: U32, depth: Nat,
  result: Array<Maybe<&2, A>> & Maybe<&2, A>) ->
  VecMaybe<A> & Maybe<&2, A>:
  (slots, value) = result
  (VecMaybe{length, capacity, depth, slots}, value)

def get_if(~A: Data, length: U32, capacity: U32, depth: Nat,
  slots: Array<Maybe<&2, A>>, index: U32, valid: Bool) ->
  VecMaybe<A> & Maybe<&2, A>:
  match valid:
    case True{}:
      get_after(~A, length, capacity, depth,
        Array.get(Maybe<&2, A>, slots, index))
    case False{}:
      (VecMaybe{length, capacity, depth, slots}, None{})

def get_sized(~A: Data, +length: U32, capacity: U32, depth: Nat,
  result: Array<Maybe<&2, A>> & U32, +index: U32) ->
  VecMaybe<A> & Maybe<&2, A>:
  (slots, actual) = result
  get_if(~A, length, capacity, depth, slots, index,
    Bool.and(U32.is_lt(index, length), U32.is_lt(index, actual)))

def get(~A: Data, vec: VecMaybe<A>, +index: U32) ->
  VecMaybe<A> & Maybe<&2, A>:
  match vec:
    case VecMaybe{+length, capacity, depth, slots}:
      get_sized(~A, length, capacity, depth,
        Array.size(Maybe<&2, A>, slots), index)

type UpdateResult<-A: Data> is Type:
  Updated{vec: VecMaybe<A>, old: Maybe<&2, A>}
  Invalid{vec: VecMaybe<A>, value: A}

def set_after(~A: Data, length: U32, capacity: U32, depth: Nat,
  result: Array<Maybe<&2, A>> & Maybe<&2, A>) -> UpdateResult<A>:
  (slots, old) = result
  Updated{VecMaybe{length, capacity, depth, slots}, old}

def set_if(~A: Data, length: U32, capacity: U32, depth: Nat,
  slots: Array<Maybe<&2, A>>, index: U32, value: A,
  valid: Bool) -> UpdateResult<A>:
  match valid:
    case True{}:
      set_after(~A, length, capacity, depth,
        Array.swap(Maybe<&2, A>, slots, index, Some{value}))
    case False{}:
      Invalid{VecMaybe{length, capacity, depth, slots}, value}

def set_sized(~A: Data, +length: U32, capacity: U32, depth: Nat,
  result: Array<Maybe<&2, A>> & U32, +index: U32,
  value: A) -> UpdateResult<A>:
  (slots, actual) = result
  set_if(~A, length, capacity, depth, slots, index, value,
    Bool.and(U32.is_lt(index, length), U32.is_lt(index, actual)))

def set(~A: Data, vec: VecMaybe<A>, +index: U32, value: A) ->
  UpdateResult<A>:
  match vec:
    case VecMaybe{+length, capacity, depth, slots}:
      set_sized(~A, length, capacity, depth,
        Array.size(Maybe<&2, A>, slots), index, value)

def step(~A: Data, vec: VecMaybe<A>, value: A) -> T.Control<VecMaybe<A>>:
  T.Continue{push(~A, vec, value)}

def reducer(~A: Data) -> T.Reducer<A, VecMaybe<A>>:
  T.Reducer{VecMaybe<A>, VecMaybe<A>, vec => T.Continue{vec},
    vec => value => step(~A, vec, value), vec => vec}

def rf(~A: Data) -> V.Rf<A, VecMaybe<A>, reducer(~A), VecMaybe<A>>:
  V.Rf{vec => vec}

def VecMaybe.destination(~A: Data, vec: VecMaybe<A>) ->
  V.Destination<A, VecMaybe<A>, reducer(~A)>:
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
    Array.swap(Maybe<&2, A>, slots, index, None{}))

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

def drive_sized(~A: Data, ~R: Type, ~r: T.Reducer<A, R>,
  length: U32, result: Array<Maybe<&2, A>> & U32,
  control: T.Control<T.State(A, R, r)>) ->
  T.Control<T.State(A, R, r)>:
  (slots, actual) = result
  finish(~A, ~R, ~r, T.reduce_range(
    ~(Array<Maybe<&2, A>> & T.State(A, R, r)),
    ~(pair => index => fold_step(~A, ~R, ~r, pair, index)),
    T.range_between(0, U32.min(length, actual)),
    start(~A, ~R, ~r, slots, control)))

def drive(~A: Data, ~R: Type, ~r: T.Reducer<A, R>,
  vec: VecMaybe<A>, control: T.Control<T.State(A, R, r)>) ->
  T.Control<T.State(A, R, r)>:
  match vec:
    case VecMaybe{length, capacity, depth, slots}:
      drive_sized(~A, ~R, ~r, length,
        Array.size(Maybe<&2, A>, slots), control)

def VecMaybe.source(~A: Data, vec: VecMaybe<A>) -> T.Source<A, VecMaybe<A>,
  (R => r => v => c => drive(~A, ~R, ~r, v, c))>:
  T.Source{vec}
