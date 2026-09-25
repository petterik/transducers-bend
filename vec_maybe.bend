import Base
import ./xf.bend as V
import ./transduce_core.bend as T
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

def step(~A: Data, vec: VecMaybe<A>, value: A) -> T.Control<Empty, VecMaybe<A>>:
  T.Continue{push(~A, vec, value)}

def reducer(~A: Data) -> T.Reducer<A, VecMaybe<A>>:
  T.Reducer{Empty, VecMaybe<A>, VecMaybe<A>, vec => T.Continue{vec},
    vec => value => step(~A, vec, value), vec => vec}

def rf(~A: Data) -> V.Rf<A, VecMaybe<A>, reducer(~A), VecMaybe<A>>:
  V.Rf{vec => vec}

def VecMaybe.destination(~A: Data, vec: VecMaybe<A>) ->
  V.Destination<A, VecMaybe<A>, reducer(~A)>:
  V.Destination{vec, rf(~A)}

def source_vec_checked(~A: Data, ~K: Data, ~S: Type,
  checked: T.Checked<K, S>, slots: Array<Maybe<&2, A>>) ->
  T.Checked<K, (Array<Maybe<&2, A>> & S)>:
  match checked:
    case T.Ready{s}:
      T.Ready{(slots, s)}
    case T.Halted{permit, s}:
      T.Halted{permit, (slots, s)}

def source_vec_inspect(~A: Data, ~K: Data, ~S: Type,
  ~inspect: S -> T.Checked<K, S>, pair: Array<Maybe<&2, A>> & S) ->
  T.Checked<K, (Array<Maybe<&2, A>> & S)>:
  (slots, s) = pair
  source_vec_checked(~A, ~K, ~S, inspect(s), slots)

def source_vec_after_get(~A: Data, ~S: Type,
  ~advance: S -> A -> S, s: S,
  got: Array<Maybe<&2, A>> & Maybe<&2, A>) ->
  Array<Maybe<&2, A>> & S:
  (slots, item) = got
  match item:
    case None{}:
      (slots, s)
    case Some{x}:
      (slots, advance(s, x))

def source_vec_step(~A: Data, ~S: Type,
  ~advance: S -> A -> S, pair: Array<Maybe<&2, A>> & S,
  index: U32) -> Array<Maybe<&2, A>> & S:
  (slots, s) = pair
  source_vec_after_get(~A, ~S, ~advance, s,
    Array.swap(Maybe<&2, A>, slots, index, None{}))

def source_vec_finish(~A: Data, ~S: Type,
  pair: Array<Maybe<&2, A>> & S) -> S:
  (slots, s) = pair
  s

def source_vec_sized(~A: Data, ~K: Data, ~S: Type,
  ~advance: S -> A -> S, ~inspect: S -> T.Checked<K, S>,
  length: U32, sized: Array<Maybe<&2, A>> & U32, s: S) -> S:
  (slots, actual) = sized
  source_vec_finish(~A, ~S, T.source_range(
    ~K, ~(Array<Maybe<&2, A>> & S),
    ~(pair => index => source_vec_step(~A, ~S, ~advance, pair, index)),
    ~(pair => source_vec_inspect(~A, ~K, ~S, ~inspect, pair)),
    T.range_between(0, U32.min(length, actual)), (slots, s)))

def source_vec(~A: Data, ~K: Data, ~S: Type,
  ~advance: S -> A -> S, ~inspect: S -> T.Checked<K, S>,
  vec: VecMaybe<A>, s: S) -> S:
  match vec:
    case VecMaybe{length, capacity, depth, slots}:
      source_vec_sized(~A, ~K, ~S, ~advance, ~inspect,
        length, Array.size(Maybe<&2, A>, slots), s)

def VecMaybe.source(~A: Data, vec: VecMaybe<A>) -> T.Source<A, VecMaybe<A>,
  (K => S => advance => inspect => v => s =>
    source_vec(~A, ~K, ~S, ~advance, ~inspect, v, s))>:
  T.Source{vec}
