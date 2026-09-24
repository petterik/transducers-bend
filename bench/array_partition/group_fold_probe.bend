import Base
import ../../transduce.bend as T
import ./fold_probe.bend as F
import ./semantic_probe.bend as P

# Bench-only alternative to materializing List chunks. The inner fold is
# explicit: each source value updates group state, and the completed group
# summary is sent to the ordinary downstream reducer. This is not a replacement
# for partition_all, which must still return observable chunks.
type GroupFolding<-S: Type, -D: Type> is Type:
  GroupFolding{size: Nat, left: Nat, used: Bool,
    group: Maybe<S>, inner: T.Control<D>}

def group_fold_start_after(~S: Type, ~D: Type, ~start: Unit -> S,
  size: Nat, inner: T.Control<D>) -> T.Control<GroupFolding<S, D>>:
  match size inner:
    case 0n T.Stop{s}:
      T.Stop{GroupFolding{0n, 0n, False{}, None{}, T.Stop{s}}}
    case 0n T.Continue{s}:
      T.Stop{GroupFolding{0n, 0n, False{}, None{}, T.Continue{s}}}
    case 1n++p T.Stop{s}:
      T.Stop{GroupFolding{1n+p, 1n+p, False{}, None{}, T.Stop{s}}}
    case 1n++p T.Continue{s}:
      T.Continue{GroupFolding{1n+p, 1n+p, False{},
        Some{start(Unit{})}, T.Continue{s}}}

def group_fold_start(~B: Type, ~R: Type, ~S: Type,
  ~start: Unit -> S, ~down: T.Reducer<B, R>,
  config: Nat & T.Config(B, R, down)) -> T.Control<GroupFolding<S, T.State(B, R, down)>>:
  (size, inner_config) = config
  group_fold_start_after(~S, ~T.State(B, R, down), ~start, size,
    T.start(B, R, down, inner_config))

def group_fold_emit_after(~S: Type, ~D: Type, ~start: Unit -> S,
  +size: Nat, c: T.Control<D>) ->
  T.Control<GroupFolding<S, D>>:
  match c:
    case T.Stop{s}:
      T.Stop{GroupFolding{size, size, False{}, None{}, T.Stop{s}}}
    case T.Continue{s}:
      T.Continue{GroupFolding{size, size, False{},
        Some{start(Unit{})}, T.Continue{s}}}

def group_fold_emit(~B: Type, ~R: Type, ~S: Type,
  ~start: Unit -> S, ~finish: S -> B,
  ~down: T.Reducer<B, R>, size: Nat,
  inner: T.State(B, R, down), next: B) ->
  T.Control<GroupFolding<S, T.State(B, R, down)>>:
  group_fold_emit_after(~S, ~T.State(B, R, down), ~start, size,
    T.step(B, R, down, inner, next))

def group_fold_step_nonzero(~A: Type, ~B: Type, ~R: Type, ~S: Type,
  ~start: Unit -> S, ~advance: S -> A -> S, ~finish: S -> B,
  ~down: T.Reducer<B, R>, size: Nat, p: Nat, used: Bool,
  group: Maybe<S>, inner: T.State(B, R, down), x: A) ->
  T.Control<GroupFolding<S, T.State(B, R, down)>>:
  match p:
    case 0n:
      match group:
        case None{}:
          T.Stop{GroupFolding{size, 1n, used, None{}, T.Continue{inner}}}
        case Some{value}:
          next = advance(value, x)
          group_fold_emit(~B, ~R, ~S, ~start, ~finish, ~down, size,
            inner, finish(next))
    case 1n+q:
      match group:
        case None{}:
          T.Stop{GroupFolding{size, 1n+q, used, None{}, T.Continue{inner}}}
        case Some{value}:
          next = advance(value, x)
          T.Continue{GroupFolding{size, 1n+q, True{}, Some{next},
            T.Continue{inner}}}

def group_fold_step_active(~A: Type, ~B: Type, ~R: Type, ~S: Type,
  ~start: Unit -> S, ~advance: S -> A -> S, ~finish: S -> B,
  ~down: T.Reducer<B, R>, size: Nat, left: Nat, used: Bool, group: Maybe<S>,
  inner: T.State(B, R, down), x: A) ->
  T.Control<GroupFolding<S, T.State(B, R, down)>>:
  match left:
    case 0n:
      T.Stop{GroupFolding{size, left, used, group, T.Continue{inner}}}
    case 1n+p:
      group_fold_step_nonzero(~A, ~B, ~R, ~S, ~start, ~advance, ~finish,
        ~down, size, p, used, group, inner, x)

def group_fold_step(~A: Type, ~B: Type, ~R: Type, ~S: Type,
  ~start: Unit -> S, ~advance: S -> A -> S, ~finish: S -> B,
  ~down: T.Reducer<B, R>, state: GroupFolding<S, T.State(B, R, down)>, x: A) ->
  T.Control<GroupFolding<S, T.State(B, R, down)>>:
  match state:
    case GroupFolding{size, left, used, group, T.Stop{s}}:
      T.Stop{GroupFolding{size, left, used, group, T.Stop{s}}}
    case GroupFolding{size, left, used, group, T.Continue{s}}:
      group_fold_step_active(~A, ~B, ~R, ~S, ~start, ~advance, ~finish,
        ~down, size, left, used, group, s, x)

def group_fold_finish_active(~B: Type, ~R: Type, ~S: Type,
  ~finish: S -> B, ~down: T.Reducer<B, R>, used: Bool, group: Maybe<S>,
  inner: T.State(B, R, down)) -> R:
  match used group:
    case False{} None{}:
      T.finish(B, R, down, inner)
    case True{} Some{value}:
      T.finish_control(~B, ~R, ~down,
        T.step(B, R, down, inner, finish(value)))
    case False{} Some{value}:
      T.finish(B, R, down, inner)
    case True{} None{}:
      T.finish(B, R, down, inner)

def group_fold_finish(~B: Type, ~R: Type, ~S: Type,
  ~finish: S -> B, ~down: T.Reducer<B, R>,
  state: GroupFolding<S, T.State(B, R, down)>) -> R:
  match state:
    case GroupFolding{size, left, used, group, T.Stop{s}}:
      T.finish(B, R, down, s)
    case GroupFolding{size, left, used, group, T.Continue{s}}:
      group_fold_finish_active(~B, ~R, ~S, ~finish, ~down, used, group, s)

def group_fold(~A: Type, ~B: Type, ~R: Type, ~S: Type,
  ~start: Unit -> S, ~advance: S -> A -> S, ~finish: S -> B,
  ~down: T.Reducer<B, R>) -> T.Reducer<A, R>:
  T.Reducer{Nat & T.Config(B, R, down),
    GroupFolding<S, T.State(B, R, down)>,
    c => group_fold_start(~B, ~R, ~S, ~start, ~down, c),
    s => x => group_fold_step(~A, ~B, ~R, ~S, ~start, ~advance, ~finish,
      ~down, s, x),
    s => group_fold_finish(~B, ~R, ~S, ~finish, ~down, s)}

def sum_start(unit: Unit) -> U32:
  0

def sum_advance(total: U32, x: U32) -> U32:
  (total + x : U32)

def sum_finish(total: U32) -> U32:
  total

def add_group_sum(total: U32, group: U32) -> U32:
  (total + group : U32)

def list_group_sum(width: Nat, budget: Nat, xs: List<U32>) -> U32:
  T.transduce(~T.over_list(~U32, ~U32,
    ~group_fold(~U32, ~U32, ~U32, ~U32, ~sum_start, ~sum_advance,
      ~sum_finish,
      ~T.take(~U32, ~U32,
        ~T.reducing(~U32, ~U32, ~U32, ~add_group_sum, ~(s => s))))),
    (width, (budget, 0)), xs)

type HashState is Type:
  HashState{hash: U32, multiplier: U32}

type HashSegment is Data:
  HashSegment{hash: U32, multiplier: U32}

def hash_start(unit: Unit) -> HashState:
  HashState{0, 1}

def hash_advance(state: HashState, x: U32) -> HashState:
  match state:
    case HashState{hash, multiplier}:
      HashState{((hash * 33 : U32) + x + 1 : U32),
        (multiplier * 33 : U32)}

def hash_finish(state: HashState) -> HashSegment:
  match state:
    case HashState{hash, multiplier}:
      HashSegment{hash, multiplier}

def hash_segment(total: U32, segment: HashSegment) -> U32:
  match segment:
    case HashSegment{hash, multiplier}:
      (((total * multiplier : U32) + hash : U32))

def list_group_hash(width: Nat, budget: Nat, xs: List<U32>) -> U32:
  T.transduce(~T.over_list(~U32, ~U32,
    ~group_fold(~U32, ~HashSegment, ~U32, ~HashState, ~hash_start,
      ~hash_advance, ~hash_finish,
      ~T.take(~HashSegment, ~U32,
        ~T.reducing(~HashSegment, ~U32, ~U32, ~hash_segment, ~(s => s))))),
    (width, (budget, 0)), xs)

def range_group_sum(width: Nat, budget: Nat, end: U32) -> U32:
  T.transduce(~T.over_range(~U32,
    ~group_fold(~U32, ~U32, ~U32, ~U32, ~sum_start, ~sum_advance,
      ~sum_finish,
      ~T.take(~U32, ~U32,
        ~T.reducing(~U32, ~U32, ~U32, ~add_group_sum, ~(s => s))))),
    (width, (budget, 0)), T.range(end))

def range_adapter_probe() -> List<Bool>:
  [U32.is_eq(range_group_sum(3n, 4n, 10), 45),
   U32.is_eq(range_group_sum(3n, 2n, 10), 15),
   U32.is_eq(range_group_sum(3n, 4n, 0), 0)]

def list_adapter_probe() -> List<Bool>:
  [U32.is_eq(list_group_sum(3n, 4n, P.numbers(10n, [])),
      F.list_fold(3n, 4n, P.numbers(10n, []))),
   U32.is_eq(list_group_sum(3n, 2n, P.numbers(10n, [])),
      F.list_fold(3n, 2n, P.numbers(10n, []))),
   U32.is_eq(list_group_sum(3n, 4n, P.numbers(0n, [])),
      F.list_fold(3n, 4n, P.numbers(0n, []))),
   U32.is_eq(list_group_sum(3n, 0n, P.numbers(10n, [])),
      F.list_fold(3n, 0n, P.numbers(10n, []))),
   U32.is_eq(list_group_sum(0n, 4n, P.numbers(10n, [])),
      F.list_fold(0n, 4n, P.numbers(10n, []))),
   U32.is_eq(list_group_sum(1n, 4n, P.numbers(10n, [])),
      F.list_fold(1n, 4n, P.numbers(10n, []))),
   U32.is_eq(list_group_hash(3n, 4n, P.numbers(10n, [])),
      F.list_hash_fold(3n, 4n, P.numbers(10n, []))),
   U32.is_eq(list_group_hash(3n, 2n, P.numbers(10n, [])),
      F.list_hash_fold(3n, 2n, P.numbers(10n, []))),
   U32.is_eq(list_group_hash(3n, 4n, P.numbers(0n, [])),
      F.list_hash_fold(3n, 4n, P.numbers(0n, []))),
   U32.is_eq(list_group_hash(1n, 4n, P.numbers(10n, [])),
      F.list_hash_fold(1n, 4n, P.numbers(10n, [])))]

def append_probes(xs: List<Bool>, ys: List<Bool>) -> List<Bool>:
  match xs:
    case Nil{}:
      ys
    case x <> rest:
      x <> append_probes(rest, ys)

def main() -> List<Bool>:
  append_probes(list_adapter_probe(), range_adapter_probe())
