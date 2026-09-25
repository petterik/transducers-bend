import Base
import ./xf.bend as V
import ./transduce.bend as T
import ./vec_capacity.bend as Capacity

# Ordered, growable collection of Data values. All public operations assume
# values came from empty/with_capacity and subsequent Vec operations. Bend
# currently exposes data constructors across modules, so callers must not
# fabricate Vec records with inconsistent length, capacity, depth, or slots.
#
# The caller-provided filler permits flat Array allocation without an
# optional-value tag. Only the prefix [0, length) is logically initialized;
# the filler is never returned as a collected element.
type Vec<-A: Data> is Type:
  Vec{length: U32, capacity: U32, depth: Nat,
    filler: A, slots: Array<A>}

def empty(~A: Data, +filler: A) -> Vec<A>:
  Vec{0, 1, 0n, filler, Array.new(A, 0n, filler)}

def reserve_after_size(~A: Data, filler: A, depth: Nat,
  result: Array<A> & U32) -> Vec<A>:
  (slots, capacity) = result
  Vec{0, capacity, depth, filler, slots}

def reserve_depth(~A: Data, +depth: Nat, +filler: A) -> Vec<A>:
  reserve_after_size(~A, filler, depth,
    Array.size(A, Array.new(A, depth, filler)))

def reserve_items_at(~A: Data, +filler: A,
  choice: Maybe<Nat>) -> Maybe<Vec<A>>:
  match choice:
    case None{}:
      None{}
    case Some{depth}:
      Some{reserve_depth(~A, depth, filler)}

# None means the request exceeds the conservative 2^23-element initial
# capacity limit. Dynamic growth follows Bend Array's runtime limits.
def with_capacity(~A: Data, requested: U32, filler: A) ->
  Maybe<Vec<A>>:
  reserve_items_at(~A, filler, Capacity.depth_for_items(requested))

def grow(~A: Data, slots: Array<A>, depth: Nat, filler: A) -> Array<A>:
  ANode{slots, Array.new(A, depth, filler)}

def push_space(~A: Data, +length: U32, +capacity: U32, +depth: Nat,
  +filler: A, slots: Array<A>, value: A, has_space: Bool) -> Vec<A>:
  match has_space:
    case True{}:
      Vec{U32.add(length, 1), capacity, depth, filler,
        Array.set(A, slots, length, value)}
    case False{}:
      Vec{U32.add(length, 1), U32.add(capacity, capacity),
        Nat.add(depth, 1n), filler,
        Array.set(A, grow(~A, slots, depth, filler), length, value)}

def push(~A: Data, vec: Vec<A>, value: A) -> Vec<A>:
  match vec:
    case Vec{+length, +capacity, depth, +filler, slots}:
      push_space(~A, length, capacity, depth, filler, slots, value,
        U32.is_lt(length, capacity))

def get_after(~A: Data, length: U32, capacity: U32, depth: Nat,
  filler: A, result: Array<A> & A) -> Vec<A> & Maybe<&2, A>:
  (slots, value) = result
  (Vec{length, capacity, depth, filler, slots}, Some{value})

def get_if(~A: Data, length: U32, capacity: U32, depth: Nat,
  filler: A, slots: Array<A>, index: U32, valid: Bool) ->
  Vec<A> & Maybe<&2, A>:
  match valid:
    case True{}:
      get_after(~A, length, capacity, depth, filler,
        Array.get(A, slots, index))
    case False{}:
      (Vec{length, capacity, depth, filler, slots}, None{})

def get_sized(~A: Data, +length: U32, capacity: U32, depth: Nat,
  filler: A, result: Array<A> & U32, +index: U32) ->
  Vec<A> & Maybe<&2, A>:
  (slots, actual) = result
  get_if(~A, length, capacity, depth, filler, slots, index,
    Bool.and(U32.is_lt(index, length), U32.is_lt(index, actual)))

def get(~A: Data, vec: Vec<A>, +index: U32) ->
  Vec<A> & Maybe<&2, A>:
  match vec:
    case Vec{+length, capacity, depth, filler, slots}:
      get_sized(~A, length, capacity, depth, filler,
        Array.size(A, slots), index)

type UpdateResult<-A: Data> is Type:
  Updated{vec: Vec<A>, old: A}
  Invalid{vec: Vec<A>, value: A}

def set_after(~A: Data, length: U32, capacity: U32, depth: Nat,
  filler: A, result: Array<A> & A) -> UpdateResult<A>:
  (slots, old) = result
  Updated{Vec{length, capacity, depth, filler, slots}, old}

def set_if(~A: Data, length: U32, capacity: U32, depth: Nat,
  filler: A, slots: Array<A>, index: U32, value: A,
  valid: Bool) -> UpdateResult<A>:
  match valid:
    case True{}:
      set_after(~A, length, capacity, depth, filler,
        Array.swap(A, slots, index, value))
    case False{}:
      Invalid{Vec{length, capacity, depth, filler, slots}, value}

def set_sized(~A: Data, +length: U32, capacity: U32, depth: Nat,
  filler: A, result: Array<A> & U32, +index: U32, value: A) ->
  UpdateResult<A>:
  (slots, actual) = result
  set_if(~A, length, capacity, depth, filler, slots, index, value,
    Bool.and(U32.is_lt(index, length), U32.is_lt(index, actual)))

def set(~A: Data, vec: Vec<A>, +index: U32, value: A) ->
  UpdateResult<A>:
  match vec:
    case Vec{+length, capacity, depth, filler, slots}:
      set_sized(~A, length, capacity, depth, filler,
        Array.size(A, slots), index, value)

def step(~A: Data, vec: Vec<A>, value: A) -> T.Control<Vec<A>>:
  T.Continue{push(~A, vec, value)}

def reducer(~A: Data) -> T.Reducer<A, Vec<A>>:
  T.Reducer{Vec<A>, Vec<A>, vec => T.Continue{vec},
    vec => value => step(~A, vec, value), vec => vec}

def rf(~A: Data) -> V.Rf<A, Vec<A>, reducer(~A), Vec<A>>:
  V.Rf{vec => vec}

def Vec.destination(~A: Data, vec: Vec<A>) ->
  V.Destination<A, Vec<A>, reducer(~A)>:
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

def drive_sized(~A: Data, ~R: Type, ~r: T.Reducer<A, R>,
  length: U32, result: Array<A> & U32,
  control: T.Control<T.State(A, R, r)>) ->
  T.Control<T.State(A, R, r)>:
  (slots, actual) = result
  finish(~A, ~R, ~r, T.reduce_range(
    ~(Array<A> & T.State(A, R, r)),
    ~(pair => index => fold_step(~A, ~R, ~r, pair, index)),
    T.range_between(0, U32.min(length, actual)),
    start(~A, ~R, ~r, slots, control)))

def drive(~A: Data, ~R: Type, ~r: T.Reducer<A, R>,
  vec: Vec<A>, control: T.Control<T.State(A, R, r)>) ->
  T.Control<T.State(A, R, r)>:
  match vec:
    case Vec{length, capacity, depth, filler, slots}:
      drive_sized(~A, ~R, ~r, length, Array.size(A, slots), control)

def Vec.source(~A: Data, vec: Vec<A>) -> T.Source<A, Vec<A>,
  (R => r => v => c => drive(~A, ~R, ~r, v, c))>:
  T.Source{vec}
