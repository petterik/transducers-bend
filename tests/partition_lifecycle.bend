import Base
import ../transduce.bend as T

type Trace is Type:
  Trace{starts: Nat, steps: Nat, finishes: Nat, groups: List<List<U32>>}

def trace_start(u: Unit) -> T.Control<Trace>:
  T.Continue{Trace{1n, 0n, 0n, []}}

def trace_step(state: Trace, group: List<U32>) -> T.Control<Trace>:
  match state:
    case Trace{starts, steps, finishes, groups}:
      T.Continue{Trace{starts, 1n+steps, finishes, group <> groups}}

def trace_finish(state: Trace) -> Trace:
  match state:
    case Trace{starts, steps, finishes, groups}:
      Trace{starts, steps, 1n+finishes, groups}

def trace_reducer() -> T.Reducer<List<U32>, Trace>:
  T.Reducer{Unit, Trace, trace_start, trace_step, trace_finish}

def stop_start(u: Unit) -> T.Control<Trace>:
  T.Stop{Trace{1n, 0n, 0n, []}}

def stop_after_start(u: Unit) -> T.Control<Trace>:
  T.Continue{Trace{1n, 0n, 0n, []}}

def stop_step(state: Trace, group: List<U32>) -> T.Control<Trace>:
  match state:
    case Trace{starts, steps, finishes, groups}:
      T.Stop{Trace{starts, 1n+steps, finishes, group <> groups}}

def stop_reducer() -> T.Reducer<List<U32>, Trace>:
  T.Reducer{Unit, Trace, stop_after_start, stop_step, trace_finish}

def initial_stop_reducer() -> T.Reducer<List<U32>, Trace>:
  T.Reducer{Unit, Trace, stop_start, stop_step, trace_finish}

type AffineTrace is Type:
  AffineTrace{starts: Nat, steps: Nat, finishes: Nat, sum: U32}

def affine_sum(xs: List<(Unit -> U32)>, +total: U32) -> U32:
  match xs:
    case Nil{}:
      total
    case f <> rest:
      affine_sum(rest, (total + f(Unit{}) : U32))

def affine_start(u: Unit) -> T.Control<AffineTrace>:
  T.Continue{AffineTrace{1n, 0n, 0n, 0}}

def affine_step(state: AffineTrace, group: List<(Unit -> U32)>) -> T.Control<AffineTrace>:
  match state:
    case AffineTrace{starts, steps, finishes, sum}:
      T.Continue{AffineTrace{starts, 1n+steps, finishes, affine_sum(group, sum)}}

def affine_stop_step(state: AffineTrace, group: List<(Unit -> U32)>) -> T.Control<AffineTrace>:
  match state:
    case AffineTrace{starts, steps, finishes, sum}:
      T.Stop{AffineTrace{starts, 1n+steps, finishes, affine_sum(group, sum)}}

def affine_finish(state: AffineTrace) -> AffineTrace:
  match state:
    case AffineTrace{starts, steps, finishes, sum}:
      AffineTrace{starts, steps, 1n+finishes, sum}

def affine_reducer() -> T.Reducer<List<(Unit -> U32)>, AffineTrace>:
  T.Reducer{Unit, AffineTrace, affine_start, affine_step, affine_finish}

def affine_stop_reducer() -> T.Reducer<List<(Unit -> U32)>, AffineTrace>:
  T.Reducer{Unit, AffineTrace, affine_start, affine_stop_step, affine_finish}

def show_affine(state: AffineTrace) -> String:
  match state:
    case AffineTrace{starts, steps, finishes, sum}:
      Nat.show(starts) ++ ":" ++ Nat.show(steps) ++ ":" ++
        Nat.show(finishes) ++ ":" ++ U32.show(sum)

def affine_full() -> AffineTrace:
  T.transduce(~T.over_list(~(Unit -> U32), ~AffineTrace,
    ~T.partition_all(~(Unit -> U32), ~AffineTrace, ~affine_reducer())),
    (2n, Unit{}), [u => 1, u => 2, u => 3])

def affine_stop() -> AffineTrace:
  T.transduce(~T.over_list(~(Unit -> U32), ~AffineTrace,
    ~T.partition_all(~(Unit -> U32), ~AffineTrace, ~affine_stop_reducer())),
    (2n, Unit{}), [u => 1, u => 2, u => 3, u => 4])

def show_groups(groups: List<List<U32>>) -> String:
  List.show(~&1, ~List<U32>, ~(xs => List.show(~&1, ~U32, ~U32.show, xs)), groups)

def show_trace(state: Trace) -> String:
  match state:
    case Trace{starts, steps, finishes, groups}:
      Nat.show(starts) ++ ":" ++ Nat.show(steps) ++ ":" ++
        Nat.show(finishes) ++ ":" ++ show_groups(List.reverse(&1, List<U32>, groups))

def full() -> Trace:
  T.transduce(~T.over_list(~U32, ~Trace,
    ~T.partition_all(~U32, ~Trace, ~trace_reducer())),
    (2n, Unit{}), [1, 2, 3, 4, 5])

def partial() -> Trace:
  T.transduce(~T.over_list(~U32, ~Trace,
    ~T.partition_all(~U32, ~Trace, ~trace_reducer())),
    (3n, Unit{}), [1, 2])

def initial_stop() -> Trace:
  T.transduce(~T.over_list(~U32, ~Trace,
    ~T.partition_all(~U32, ~Trace, ~initial_stop_reducer())),
    (2n, Unit{}), [1, 2, 3])

def stop_full() -> Trace:
  T.transduce(~T.over_list(~U32, ~Trace,
    ~T.partition_all(~U32, ~Trace, ~stop_reducer())),
    (2n, Unit{}), [1, 2, 3, 4])

def stop_partial() -> Trace:
  T.transduce(~T.over_list(~U32, ~Trace,
    ~T.partition_all(~U32, ~Trace, ~stop_reducer())),
    (3n, Unit{}), [1, 2])

def nested() -> List<List<List<U32>>>:
  T.transduce(~T.over_list(~U32, ~List<List<List<U32>>>,
    ~T.partition_all(~U32, ~List<List<List<U32>>>,
      ~T.partition_all(~List<U32>, ~List<List<List<U32>>>,
        ~T.into_list(~List<List<U32>>)))),
    (2n, (2n, Unit{})), [1, 2, 3, 4, 5])

def main() -> List<String>:
  [show_trace(full()), show_trace(partial()), show_trace(initial_stop()),
   show_trace(stop_full()), show_trace(stop_partial()),
   List.show(~&1, ~String, ~(x => x),
     List.map(~List<List<U32>>, ~String, ~show_groups, nested())),
   show_trace(full()), show_affine(affine_full()), show_affine(affine_stop())]
#|["1:3:1:[[1, 2], [3, 4], [5]]", "1:1:1:[[1, 2]]", "1:0:1:[]", "1:1:1:[[1, 2]]", "1:1:1:[[1, 2]]", "[[[1, 2], [3, 4]], [[5]]]", "1:3:1:[[1, 2], [3, 4], [5]]", "1:2:1:6", "1:1:1:3"]
