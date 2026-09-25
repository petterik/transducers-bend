import Base
import ./rank2_rf_values.bend as V
import ./rank2_companion_api.bend as Auto
import ../../transduce.bend as T

# An owned, ordered builder. Empty slots are constructible without T: Data.
type Vec<-A: Type> is Type:
  Vec{length: U32, capacity: U32, depth: Nat, slots: Array<Maybe<A>>}

def empty_slots(~A: Type, depth: Nat) -> Array<Maybe<A>>:
  match depth:
    case 0n:
      ALeaf{None{}}
    case 1n+ +p:
      ANode{empty_slots(~A, p), empty_slots(~A, p)}

def empty(~A: Type) -> Vec<A>:
  Vec{0, 1, 0n, ALeaf{None{}}}

def grow_slots(~A: Type, slots: Array<Maybe<A>>, depth: Nat) ->
  Array<Maybe<A>>:
  ANode{slots, empty_slots(~A, depth)}

def push_space(~A: Type, +length: U32, +capacity: U32, +depth: Nat,
  slots: Array<Maybe<A>>, value: A, has_space: Bool) -> Vec<A>:
  match has_space:
    case True{}:
      Vec{U32.add(length, 1), capacity, depth,
        Array.set(Maybe<A>, slots, length, Some{value})}
    case False{}:
      Vec{U32.add(length, 1), U32.add(capacity, capacity),
        Nat.add(depth, 1n),
        Array.set(Maybe<A>, grow_slots(~A, slots, depth), length,
          Some{value})}

def push(~A: Type, vec: Vec<A>, value: A) -> Vec<A>:
  match vec:
    case Vec{+length, +capacity, depth, slots}:
      push_space(~A, length, capacity, depth, slots, value,
        U32.is_lt(length, capacity))

def vec_step(~A: Type, vec: Vec<A>, value: A) -> T.Control<Vec<A>>:
  T.Continue{push(~A, vec, value)}

def vec_reducer(~A: Type) -> T.Reducer<A, Vec<A>>:
  T.Reducer{Vec<A>, Vec<A>, vec => T.Continue{vec},
    vec => value => vec_step(~A, vec, value), vec => vec}

def vec_rf(~A: Type) -> V.Rf<A, Vec<A>, vec_reducer(~A), Vec<A>>:
  V.Rf{vec => vec}

def Vec.destination(~A: Type, vec: Vec<A>) ->
  V.Destination<A, Vec<A>, vec_reducer(~A)>:
  V.Destination{vec, vec_rf(~A)}

def vec_start(~A: Type, ~R: Type, ~r: T.Reducer<A, R>,
  slots: Array<Maybe<A>>, control: T.Control<T.State(A, R, r)>) ->
  T.Control<(Array<Maybe<A>> & T.State(A, R, r))>:
  match control:
    case T.Stop{state}:
      T.Stop{(slots, state)}
    case T.Continue{state}:
      T.Continue{(slots, state)}

def vec_done(~A: Type, ~R: Type, ~r: T.Reducer<A, R>,
  control: T.Control<(Array<Maybe<A>> & T.State(A, R, r))>) ->
  T.Control<T.State(A, R, r)>:
  match control:
    case T.Stop{(slots, state)}:
      T.Stop{state}
    case T.Continue{(slots, state)}:
      T.Continue{state}

def vec_step_done(~A: Type, ~R: Type, ~r: T.Reducer<A, R>,
  slots: Array<Maybe<A>>, control: T.Control<T.State(A, R, r)>) ->
  T.Control<(Array<Maybe<A>> & T.State(A, R, r))>:
  match control:
    case T.Stop{state}:
      T.Stop{(slots, state)}
    case T.Continue{state}:
      T.Continue{(slots, state)}

def vec_after_swap(~A: Type, ~R: Type, ~r: T.Reducer<A, R>,
  state: T.State(A, R, r), result: Array<Maybe<A>> & Maybe<A>) ->
  T.Control<(Array<Maybe<A>> & T.State(A, R, r))>:
  (slots, item) = result
  match item:
    case None{}:
      T.Continue{(slots, state)}
    case Some{value}:
      vec_step_done(~A, ~R, ~r, slots, T.step(A, R, r, state, value))

def vec_fold_step(~A: Type, ~R: Type, ~r: T.Reducer<A, R>,
  pair: Array<Maybe<A>> & T.State(A, R, r), index: U32) ->
  T.Control<(Array<Maybe<A>> & T.State(A, R, r))>:
  (slots, state) = pair
  vec_after_swap(~A, ~R, ~r, state,
    Array.swap(Maybe<A>, slots, index, None{}))

def drive_vec(~A: Type, ~R: Type, ~r: T.Reducer<A, R>,
  vec: Vec<A>, control: T.Control<T.State(A, R, r)>) ->
  T.Control<T.State(A, R, r)>:
  match vec:
    case Vec{length, capacity, depth, slots}:
      vec_done(~A, ~R, ~r,
        T.reduce_range(~(Array<Maybe<A>> & T.State(A, R, r)),
          ~(pair => index => vec_fold_step(~A, ~R, ~r, pair, index)),
          T.range_between(0, length),
          vec_start(~A, ~R, ~r, slots, control)))

def Vec.source(~A: Type, vec: Vec<A>) -> T.Source<A, Vec<A>,
  (R => r => v => c => drive_vec(~A, ~R, ~r, v, c))>:
  T.Source{vec}

type ReplaceResult<-A: Type> is Type:
  Replaced{vec: Vec<A>, old: Maybe<A>}
  OutOfBounds{vec: Vec<A>, value: A}

def replace_after_swap(~A: Type, length: U32, capacity: U32, depth: Nat,
  result: Array<Maybe<A>> & Maybe<A>) -> ReplaceResult<A>:
  (next, old) = result
  Replaced{Vec{length, capacity, depth, next}, old}

def replace_if(~A: Type, length: U32, capacity: U32, depth: Nat,
  slots: Array<Maybe<A>>, index: U32, value: A, valid: Bool) ->
  ReplaceResult<A>:
  match valid:
    case True{}:
      replace_after_swap(~A, length, capacity, depth,
        Array.swap(Maybe<A>, slots, index, Some{value}))
    case False{}:
      OutOfBounds{Vec{length, capacity, depth, slots}, value}

def replace(~A: Type, vec: Vec<A>, +index: U32, value: A) ->
  ReplaceResult<A>:
  match vec:
    case Vec{+length, capacity, depth, slots}:
      replace_if(~A, length, capacity, depth, slots, index, value,
        U32.is_lt(index, length))

def get_after_swap(~A: Data, +index: U32,
  result: Array<Maybe<A>> & Maybe<A>) ->
  Array<Maybe<A>> & Maybe<A>:
  (slots, previous) = result
  match previous:
    case None{}:
      (slots, None{})
    case Some{+value}:
      (Array.set(Maybe<A>, slots, index, Some{value}), Some{value})

def get_after(~A: Data, length: U32, capacity: U32, depth: Nat,
  result: Array<Maybe<A>> & Maybe<A>) -> Vec<A> & Maybe<A>:
  (slots, value) = result
  (Vec{length, capacity, depth, slots}, value)

def get_valid(~A: Data, length: U32, capacity: U32, depth: Nat,
  slots: Array<Maybe<A>>, +index: U32, valid: Bool) ->
  Vec<A> & Maybe<A>:
  match valid:
    case True{}:
      get_after(~A, length, capacity, depth,
        get_after_swap(~A, index,
          Array.swap(Maybe<A>, slots, index, None{})))
    case False{}:
      (Vec{length, capacity, depth, slots}, None{})

def get(~A: Data, vec: Vec<A>, +index: U32) -> Vec<A> & Maybe<A>:
  match vec:
    case Vec{+length, capacity, depth, slots}:
      get_valid(~A, length, capacity, depth, slots, index,
        U32.is_lt(index, length))

def example_after_replace(result: ReplaceResult<U32>) ->
  U32 & U32 & List<Maybe<U32>>:
  match result:
    case Replaced{Vec{length, capacity, depth, slots}, old}:
      (length, capacity, Array.to_list.go(~Maybe<U32>, slots, []))
    case OutOfBounds{Vec{length, capacity, depth, slots}, value}:
      (length, capacity, Array.to_list.go(~Maybe<U32>, slots, []))

def collection_example(xs: List<U32>, output: List<U32>) -> List<U32>:
  dest = empty(~U32)
  vec = Auto.into(dest, V.shifted(1), xs)
  Auto.into(output, V.shifted(0), vec)

type Token is Type:
  Token{value: U32}

def token_value(token: Token) -> U32:
  match token:
    case Token{value}:
      value

def affine_example() -> U32:
  v = push(~Token, push(~Token, push(~Token, empty(~Token),
    Token{1}), Token{2}), Token{3})
  Auto.transduce(V.map(~Token, ~U32, ~token_value), V.sum_rf(), 0, v)

def lookup_finish(first: Maybe<U32>, result: Vec<U32> & Maybe<U32>) ->
  Maybe<U32> & Maybe<U32>:
  (rest, second) = result
  (first, second)

def lookup_next(result: Vec<U32> & Maybe<U32>) ->
  Maybe<U32> & Maybe<U32>:
  (vec, first) = result
  lookup_finish(first, get(~U32, vec, 7))

def lookup_example() -> Maybe<U32> & Maybe<U32>:
  vec = push(~U32, push(~U32, empty(~U32), 5), 8)
  lookup_next(get(~U32, vec, 1))

def take_example(n: Nat) -> U32:
  vec = push(~U32, push(~U32, push(~U32, empty(~U32), 1), 2), 3)
  Auto.transduce(V.taking_u32(n), V.sum_rf(), 0, vec)

def main() -> (U32 & U32 & List<Maybe<U32>>) & List<U32> & U32 &
  (Maybe<U32> & Maybe<U32>) & U32 & U32:
  v = push(~U32, push(~U32, push(~U32, empty(~U32), 1), 2), 3)
  (example_after_replace(replace(~U32, v, 1, 20)),
    collection_example([1, 2, 3], [99]), affine_example(),
    lookup_example(), take_example(2n), take_example(0n))
#|((3, 4, [Some{1}, Some{20}, Some{3}, None{}]), [4, 3, 2, 99], 6, (Some{8}, None{}), 3, 0)
