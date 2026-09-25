import Base
import ./xf.bend as V
import ./transduce_core.bend as T
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

# Fast path when the caller already proved index < vec.length. As with
# Array.get, an out-of-range index wraps within physical Array capacity.
def get_unchecked_after(~A: Data, length: U32, capacity: U32,
  depth: Nat, filler: A, result: Array<A> & A) -> Vec<A> & A:
  (slots, value) = result
  (Vec{length, capacity, depth, filler, slots}, value)

def get_unchecked(~A: Data, vec: Vec<A>, index: U32) -> Vec<A> & A:
  match vec:
    case Vec{length, capacity, depth, filler, slots}:
      get_unchecked_after(~A, length, capacity, depth, filler,
        Array.get(A, slots, index))

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

# Caller must prove index < vec.length. Returns the displaced value.
def set_unchecked_after(~A: Data, length: U32, capacity: U32,
  depth: Nat, filler: A, result: Array<A> & A) -> Vec<A> & A:
  (slots, old) = result
  (Vec{length, capacity, depth, filler, slots}, old)

def set_unchecked(~A: Data, vec: Vec<A>, index: U32, value: A) ->
  Vec<A> & A:
  match vec:
    case Vec{length, capacity, depth, filler, slots}:
      set_unchecked_after(~A, length, capacity, depth, filler,
        Array.swap(A, slots, index, value))

def step(~A: Data, vec: Vec<A>, value: A) -> T.Control<Empty, Vec<A>>:
  T.Continue{push(~A, vec, value)}

def reducer(~A: Data) -> T.Reducer<A, Vec<A>>:
  T.Reducer{Empty, Vec<A>, Vec<A>, vec => T.Continue{vec},
    vec => value => step(~A, vec, value), vec => vec}

def rf(~A: Data) -> V.Rf<A, Vec<A>, reducer(~A), Vec<A>>:
  V.Rf{vec => vec}

def Vec.destination(~A: Data, vec: Vec<A>) ->
  V.Destination<A, Vec<A>, reducer(~A)>:
  V.Destination{vec, rf(~A)}

def source_vec_checked(~A: Data, ~K: Data, ~S: Type,
  checked: T.Checked<K, S>, slots: Array<A>) ->
  T.Checked<K, (Array<A> & S)>:
  match checked:
    case T.Ready{s}:
      T.Ready{(slots, s)}
    case T.Halted{permit, s}:
      T.Halted{permit, (slots, s)}

def source_vec_inspect(~A: Data, ~K: Data, ~S: Type,
  ~inspect: S -> T.Checked<K, S>, pair: Array<A> & S) ->
  T.Checked<K, (Array<A> & S)>:
  (slots, s) = pair
  source_vec_checked(~A, ~K, ~S, inspect(s), slots)

def source_vec_after_get(~A: Data, ~S: Type,
  ~advance: S -> A -> S, s: S, got: Array<A> & A) -> Array<A> & S:
  (slots, x) = got
  (slots, advance(s, x))

def source_vec_step(~A: Data, ~S: Type,
  ~advance: S -> A -> S, pair: Array<A> & S,
  index: U32) -> Array<A> & S:
  (slots, s) = pair
  source_vec_after_get(~A, ~S, ~advance, s, Array.get(A, slots, index))

def source_vec_finish(~A: Data, ~S: Type, pair: Array<A> & S) -> S:
  (slots, s) = pair
  s

def source_vec_sized(~A: Data, ~K: Data, ~S: Type,
  ~advance: S -> A -> S, ~inspect: S -> T.Checked<K, S>,
  length: U32, sized: Array<A> & U32, s: S) -> S:
  (slots, actual) = sized
  source_vec_finish(~A, ~S, T.source_range(
    ~K, ~(Array<A> & S),
    ~(pair => index => source_vec_step(~A, ~S, ~advance, pair, index)),
    ~(pair => source_vec_inspect(~A, ~K, ~S, ~inspect, pair)),
    T.range_between(0, U32.min(length, actual)), (slots, s)))

def source_vec(~A: Data, ~K: Data, ~S: Type,
  ~advance: S -> A -> S, ~inspect: S -> T.Checked<K, S>,
  vec: Vec<A>, s: S) -> S:
  match vec:
    case Vec{length, capacity, depth, filler, slots}:
      source_vec_sized(~A, ~K, ~S, ~advance, ~inspect,
        length, Array.size(A, slots), s)

def Vec.source(~A: Data, vec: Vec<A>) -> T.Source<A, Vec<A>,
  (K => S => advance => inspect => v => s =>
    source_vec(~A, ~K, ~S, ~advance, ~inspect, v, s))>:
  T.Source{vec}

def Vec.adapter(~A: Data) -> T.SourceAdapter<A, Vec<A>,
  (K => S => advance => inspect => v => s =>
    source_vec(~A, ~K, ~S, ~advance, ~inspect, v, s))>:
  T.SourceAdapter{}
