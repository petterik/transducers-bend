import Base
import ../../transduce.bend as T

# Fixture-only prototype. This intentionally supports U32 only so Array.new's
# initializer is concrete and padded cells have a harmless zero value.
type ArrayChunk is Type:
  ArrayChunk{items: Array<U32>, len: Nat}

type ArrayPartitioning<-S: Type> is Type:
  ArrayPartitioning{size: Nat, depth: Nat, len: Nat,
    items: Maybe<Array<U32>>, inner: T.Control<S>}

def array_partition_emit_after(~R: Type, ~down: T.Reducer<ArrayChunk, R>,
  size: Nat, depth: Nat,
  c: T.Control<T.State(ArrayChunk, R, down)>) ->
  T.Control<ArrayPartitioning<T.State(ArrayChunk, R, down)>>:
  match c:
    case T.Stop{s}:
      T.Stop{ArrayPartitioning{size, depth, 0n, None{}, T.Stop{s}}}
    case T.Continue{s}:
      T.Continue{ArrayPartitioning{size, depth, 0n, None{}, T.Continue{s}}}

def array_partition_emit(~R: Type, ~down: T.Reducer<ArrayChunk, R>,
  size: Nat, depth: Nat, items: Array<U32>, +len: Nat,
  inner: T.State(ArrayChunk, R, down)) ->
  T.Control<ArrayPartitioning<T.State(ArrayChunk, R, down)>>:
  array_partition_emit_after(~R, ~down, size, depth,
    T.step(ArrayChunk, R, down, inner, ArrayChunk{items, len}))

def array_partition_put_after(~R: Type, ~down: T.Reducer<ArrayChunk, R>,
  size: Nat, depth: Nat, len: Nat, inner: T.State(ArrayChunk, R, down),
  next: Array<U32>, next_len: Nat, full: Bool) ->
  T.Control<ArrayPartitioning<T.State(ArrayChunk, R, down)>>:
  match full:
    case True{}:
      array_partition_emit(~R, ~down, size, depth, next, next_len, inner)
    case False{}:
      T.Continue{ArrayPartitioning{size, depth, next_len, Some{next},
        T.Continue{inner}}}

def array_partition_put(~R: Type, ~down: T.Reducer<ArrayChunk, R>,
  +size: Nat, +depth: Nat, +len: Nat,
  inner: T.State(ArrayChunk, R, down),
  items: Array<U32>, x: U32) ->
  T.Control<ArrayPartitioning<T.State(ArrayChunk, R, down)>>:
  next = Array.set(U32, items, U32.from_nat(len), x)
  next_len = Nat.add(len, 1n)
  array_partition_put_after(~R, ~down, size, depth, len, inner, next,
    next_len, Nat.is_eq(Nat.add(len, 1n), size))

def array_partition_start_control(~R: Type, ~down: T.Reducer<ArrayChunk, R>,
  size: Nat, depth: Nat, inner: T.Control<T.State(ArrayChunk, R, down)>) ->
  T.Control<ArrayPartitioning<T.State(ArrayChunk, R, down)>>:
  match size inner:
    case 0n T.Stop{s}:
      T.Stop{ArrayPartitioning{0n, 0n, 0n, None{}, T.Stop{s}}}
    case 0n T.Continue{s}:
      T.Stop{ArrayPartitioning{0n, depth, 0n, None{}, T.Continue{s}}}
    case 1n+p T.Stop{s}:
      T.Stop{ArrayPartitioning{1n+p, depth, 0n, None{}, T.Stop{s}}}
    case 1n+p T.Continue{s}:
      T.Continue{ArrayPartitioning{1n+p, depth, 0n, None{}, T.Continue{s}}}

def array_partition_start(~R: Type, ~down: T.Reducer<ArrayChunk, R>,
  config: Nat & (Nat & T.Config(ArrayChunk, R, down))) ->
  T.Control<ArrayPartitioning<T.State(ArrayChunk, R, down)>>:
  (size, depth_config) = config
  (depth, inner_config) = depth_config
  array_partition_start_control(~R, ~down, size, depth,
    T.start(ArrayChunk, R, down, inner_config))

def array_partition_step_continue(~R: Type,
  ~down: T.Reducer<ArrayChunk, R>, size: Nat, +depth: Nat, len: Nat,
  items: Maybe<Array<U32>>, inner: T.State(ArrayChunk, R, down), x: U32) ->
  T.Control<ArrayPartitioning<T.State(ArrayChunk, R, down)>>:
  match items:
    case None{}:
      empty = Array.new(U32, depth, 0)
      array_partition_put(~R, ~down, size, depth, len, inner, empty, x)
    case Some{array}:
      array_partition_put(~R, ~down, size, depth, len, inner, array, x)

def array_partition_step(~R: Type, ~down: T.Reducer<ArrayChunk, R>,
  state: ArrayPartitioning<T.State(ArrayChunk, R, down)>, x: U32) ->
  T.Control<ArrayPartitioning<T.State(ArrayChunk, R, down)>>:
  match state:
    case ArrayPartitioning{size, depth, len, items, T.Stop{s}}:
      T.Stop{ArrayPartitioning{size, depth, len, items, T.Stop{s}}}
    case ArrayPartitioning{size, depth, len, items, T.Continue{s}}:
      array_partition_step_continue(~R, ~down, size, depth, len, items, s, x)

def array_partition_finish_continue(~R: Type,
  ~down: T.Reducer<ArrayChunk, R>, size: Nat, depth: Nat, len: Nat,
  items: Maybe<Array<U32>>, inner: T.State(ArrayChunk, R, down)) -> R:
  match items:
    case None{}:
      T.finish(ArrayChunk, R, down, inner)
    case Some{array}:
      T.finish_control(~ArrayChunk, ~R, ~down,
        T.step(ArrayChunk, R, down, inner, ArrayChunk{array, len}))

def array_partition_finish(~R: Type, ~down: T.Reducer<ArrayChunk, R>,
  state: ArrayPartitioning<T.State(ArrayChunk, R, down)>) -> R:
  match state:
    case ArrayPartitioning{size, depth, len, items, T.Stop{s}}:
      T.finish(ArrayChunk, R, down, s)
    case ArrayPartitioning{size, depth, len, items, T.Continue{s}}:
      array_partition_finish_continue(~R, ~down, size, depth, len, items, s)

def partition_array(~R: Type, ~down: T.Reducer<ArrayChunk, R>) -> T.Reducer<U32, R>:
  T.Reducer{Nat & (Nat & T.Config(ArrayChunk, R, down)),
    ArrayPartitioning<T.State(ArrayChunk, R, down)>,
    c => array_partition_start(~R, ~down, c),
    s => x => array_partition_step(~R, ~down, s, x),
    s => array_partition_finish(~R, ~down, s)}

type ArrayItem is Type:
  ArrayItem{rest: Array<U32>, value: U32}

def array_item_after_get(result: Array<U32> & U32) -> ArrayItem:
  (next, x) = result
  ArrayItem{next, x}

type ReaderPhase is Type:
  ReadArray{index: Nat, rev: List<U32>, items: Array<U32>}
  ReadValue{index: Nat, rev: List<U32>, item: ArrayItem}

def reader_values(phase: ReaderPhase) -> List<U32>:
  match phase:
    case ReadArray{index, rev, items}:
      List.reverse(&1, U32, rev)
    case ReadValue{index, rev, item}:
      List.reverse(&1, U32, rev)

def chunk_values_loop(fuel: Nat, left: Nat, phase: ReaderPhase) -> List<U32>:
  match fuel left phase:
    case 0n left phase:
      reader_values(phase)
    case 1n+q 0n phase:
      reader_values(phase)
    case 1n+q 1n+p ReadArray{+index, rev, items}:
      chunk_values_loop(q, 1n+p,
        ReadValue{index, rev,
          array_item_after_get(Array.get(U32, items, U32.from_nat(index)))})
    case 1n+q 1n+p ReadValue{index, rev, ArrayItem{next, value}}:
      chunk_values_loop(q, p,
        ReadArray{Nat.add(index, 1n), value <> rev, next})

def chunk_values(chunk: ArrayChunk) -> List<U32>:
  match chunk:
    case ArrayChunk{items, +len}:
      chunk_values_loop(Nat.mul(len, 2n), len, ReadArray{0n, [], items})

def show_values(xs: List<U32>) -> String:
  List.show(~&1, ~U32, ~U32.show, xs)

def show_groups(xs: List<List<U32>>) -> String:
  List.show(~&1, ~List<U32>, ~show_values, xs)

def numbers(n: Nat, acc: List<U32>) -> List<U32>:
  match n:
    case 0n:
      acc
    case 1n++p:
      numbers(p, U32.from_nat(p) <> acc)

def direct_partition_loop(xs: List<U32>, +size: Nat, left: Nat,
  items: List<U32>, groups: List<List<U32>>) -> List<List<U32>>:
  match xs left:
    case xs 0n:
      List.reverse(&1, List<U32>, groups)
    case Nil{} 1n+p:
      match items:
        case Nil{}:
          List.reverse(&1, List<U32>, groups)
        case h <> t:
          List.reverse(&1, List<U32>,
            List.reverse(&1, U32, items) <> groups)
    case h <> t 1n+p:
      match p:
        case 0n:
          direct_partition_loop(t, size, size, [],
            List.reverse(&1, U32, h <> items) <> groups)
        case 1n+q:
          direct_partition_loop(t, size, 1n+q, h <> items, groups)

def direct_partition(xs: List<U32>, size: Nat) -> List<List<U32>>:
  match size:
    case 0n:
      []
    case 1n++p:
      direct_partition_loop(xs, 1n+p, 1n+p, [], [])

type Trace is Type:
  Trace{starts: Nat, steps: Nat, finishes: Nat, groups: List<List<U32>>}

def trace_start(u: Unit) -> T.Control<Trace>:
  T.Continue{Trace{1n, 0n, 0n, []}}

def trace_step(state: Trace, chunk: ArrayChunk) -> T.Control<Trace>:
  match state:
    case Trace{starts, steps, finishes, groups}:
      T.Continue{Trace{starts, Nat.add(steps, 1n), finishes,
        chunk_values(chunk) <> groups}}

def trace_stop_step(state: Trace, chunk: ArrayChunk) -> T.Control<Trace>:
  match state:
    case Trace{starts, steps, finishes, groups}:
      T.Stop{Trace{starts, Nat.add(steps, 1n), finishes,
        chunk_values(chunk) <> groups}}

def trace_initial_stop(u: Unit) -> T.Control<Trace>:
  T.Stop{Trace{1n, 0n, 0n, []}}

def trace_finish(state: Trace) -> Trace:
  match state:
    case Trace{starts, steps, finishes, groups}:
      Trace{starts, steps, Nat.add(finishes, 1n),
        List.reverse(&1, List<U32>, groups)}

def trace_reducer() -> T.Reducer<ArrayChunk, Trace>:
  T.Reducer{Unit, Trace, trace_start, trace_step, trace_finish}

def trace_stop_reducer() -> T.Reducer<ArrayChunk, Trace>:
  T.Reducer{Unit, Trace, trace_start, trace_stop_step, trace_finish}

def trace_initial_stop_reducer() -> T.Reducer<ArrayChunk, Trace>:
  T.Reducer{Unit, Trace, trace_initial_stop, trace_step, trace_finish}

def array_groups_start(u: Unit) -> T.Control<List<List<U32>>>:
  T.Continue{[]}

def array_groups_step(groups: List<List<U32>>, chunk: ArrayChunk) ->
  T.Control<List<List<U32>>>:
  T.Continue{chunk_values(chunk) <> groups}

def array_groups_finish(groups: List<List<U32>>) -> List<List<U32>>:
  List.reverse(&1, List<U32>, groups)

def array_groups_reducer() -> T.Reducer<ArrayChunk, List<List<U32>>>:
  T.Reducer{Unit, List<List<U32>>, array_groups_start, array_groups_step,
    array_groups_finish}

def array_groups(size: Nat, depth: Nat, xs: List<U32>) -> List<List<U32>>:
  T.transduce(~T.over_list(~U32, ~List<List<U32>>,
    ~partition_array(~List<List<U32>>, ~array_groups_reducer())),
    (size, (depth, Unit{})), xs)

def list_groups(size: Nat, xs: List<U32>) -> List<List<U32>>:
  T.transduce(~T.over_list(~U32, ~List<List<U32>>,
    ~T.partition_all(~U32, ~List<List<U32>>,
      ~T.into_list(~List<U32>))), (size, Unit{}), xs)

def array_trace(~down: T.Reducer<ArrayChunk, Trace>, size: Nat, depth: Nat,
  inner_config: T.Config(ArrayChunk, Trace, down), xs: List<U32>) -> Trace:
  T.transduce(~T.over_list(~U32, ~Trace,
    ~partition_array(~Trace, ~down)), (size, (depth, inner_config)), xs)

def eq_values(xs: List<U32>, ys: List<U32>) -> Bool:
  match xs ys:
    case Nil{} Nil{}:
      True{}
    case x <> xt y <> yt:
      Bool.and(U32.is_eq(x, y), eq_values(xt, yt))
    case _ _:
      False{}

def eq_groups(xs: List<List<U32>>, ys: List<List<U32>>) -> Bool:
  match xs ys:
    case Nil{} Nil{}:
      True{}
    case x <> xt y <> yt:
      Bool.and(eq_values(x, y), eq_groups(xt, yt))
    case _ _:
      False{}

type ProbeCase is Data:
  ProbeCase{width: Nat, depth: Nat, count: Nat}

def same_both(expected_list: List<List<U32>>,
  expected_array: List<List<U32>>, from_list: List<List<U32>>,
  from_array: List<List<U32>>) -> Bool:
  Bool.and(eq_groups(from_list, expected_list),
    eq_groups(from_array, expected_array))

def case_ok(test: ProbeCase) -> Bool:
  match test:
    case ProbeCase{+width, +depth, +count}:
      same_both(direct_partition(numbers(count, []), width),
        direct_partition(numbers(count, []), width),
        list_groups(width, numbers(count, [])),
        array_groups(width, depth, numbers(count, [])))

def cases_ok(cases: List<ProbeCase>) -> List<Bool>:
  match cases:
    case Nil{}:
      []
    case test <> rest:
      case_ok(test) <> cases_ok(rest)

def trace_ok(trace: Trace, starts: Nat, steps: Nat, finishes: Nat,
  groups: List<List<U32>>) -> Bool:
  match trace:
    case Trace{got_starts, got_steps, got_finishes, got_groups}:
      Bool.and(Nat.is_eq(got_starts, starts),
        Bool.and(Nat.is_eq(got_steps, steps),
          Bool.and(Nat.is_eq(got_finishes, finishes),
            eq_groups(got_groups, groups))))

def lifecycle_checks() -> List<Bool>:
  partial = array_trace(~trace_reducer(), 3n, 2n, Unit{}, numbers(2n, []))
  zero = array_trace(~trace_reducer(), 0n, 0n, Unit{}, numbers(5n, []))
  initial = array_trace(~trace_initial_stop_reducer(), 2n, 1n, Unit{},
    numbers(5n, []))
  stop_full = array_trace(~trace_stop_reducer(), 2n, 1n, Unit{},
    numbers(5n, []))
  stop_partial = array_trace(~trace_stop_reducer(), 3n, 2n, Unit{}, numbers(2n, []))
  [trace_ok(partial, 1n, 1n, 1n, [[0, 1]]),
   trace_ok(zero, 1n, 0n, 1n, []),
   trace_ok(initial, 1n, 0n, 1n, []),
   trace_ok(stop_full, 1n, 1n, 1n, [[0, 1]]),
   trace_ok(stop_partial, 1n, 1n, 1n, [[0, 1]])]

def main() -> List<Bool>:
  List.append(&1, Bool, cases_ok([ProbeCase{1n, 0n, 0n},
      ProbeCase{1n, 0n, 1n},
      ProbeCase{1n, 0n, 2n}, ProbeCase{1n, 0n, 3n}, ProbeCase{1n, 0n, 5n},
      ProbeCase{2n, 1n, 0n}, ProbeCase{2n, 1n, 1n},
      ProbeCase{2n, 1n, 2n}, ProbeCase{2n, 1n, 3n}, ProbeCase{2n, 1n, 5n},
      ProbeCase{3n, 2n, 0n}, ProbeCase{3n, 2n, 2n},
      ProbeCase{3n, 2n, 3n}, ProbeCase{3n, 2n, 4n}, ProbeCase{3n, 2n, 7n},
      ProbeCase{8n, 3n, 0n}, ProbeCase{8n, 3n, 7n},
      ProbeCase{8n, 3n, 8n}, ProbeCase{8n, 3n, 9n},
      ProbeCase{8n, 3n, 17n}]), lifecycle_checks())
