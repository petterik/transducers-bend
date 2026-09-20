import Base
import ../transduce.bend as T
import ../examples/tree.bend as Tree

# A concrete wrapper keeps the public settings named while leaving the
# downstream configuration separate and typed by the selected consumer.
type PipelineSettings is Data:
  PipelineSettings{threshold: U32, limit: Nat, width: Nat}

type PipelineConfig<-D: Type> is Type:
  PipelineConfig{settings: PipelineSettings, consumer: D}

def above(threshold: U32, x: U32) -> Bool:
  U32.is_gt(x, threshold)

def to_nat(x: U32) -> Maybe<Nat>:
  Some{U32.to_nat(x)}

def internal(~R: Type, ~down: T.Reducer<List<Nat>, R>) -> T.Reducer<U32, R>:
  T.filter(~U32, ~R, ~U32, ~above,
    ~T.keep(~U32, ~Nat, ~R, ~to_nat,
      ~T.take(~Nat, ~R,
        ~T.partition_all(~Nat, ~R, ~down))))

def start_config(~R: Type, ~down: T.Reducer<List<Nat>, R>,
  config: PipelineConfig<T.Config(List<Nat>, R, down)>) ->
  T.Control<T.State(U32, R, internal(~R, ~down))>:
  match config:
    case PipelineConfig{PipelineSettings{threshold, limit, width}, consumer}:
      T.start(U32, R, internal(~R, ~down),
        (threshold, (limit, (width, consumer))))

def pipeline(~R: Type, ~down: T.Reducer<List<Nat>, R>) -> T.Reducer<U32, R>:
  T.Reducer{PipelineConfig<T.Config(List<Nat>, R, down)>,
    T.State(U32, R, internal(~R, ~down)),
    c => start_config(~R, ~down, c),
    s => x => T.step(U32, R, internal(~R, ~down), s, x),
    s => T.finish(U32, R, internal(~R, ~down), s)}

def unit_config(threshold: U32, limit: Nat, width: Nat) -> PipelineConfig<Unit>:
  PipelineConfig{PipelineSettings{threshold, limit, width}, Unit{}}

def u32_config(threshold: U32, limit: Nat, width: Nat,
  consumer: U32) -> PipelineConfig<U32>:
  PipelineConfig{PipelineSettings{threshold, limit, width}, consumer}

def initial_stop() -> T.Reducer<List<Nat>, Nat>:
  T.Reducer{Unit, Nat, u => T.Stop{0n}, s => group => T.Stop{s}, s => s}

def sum_group(xs: List<Nat>, +total: U32) -> U32:
  match xs:
    case Nil{}:
      total
    case h <> t:
      sum_group(t, (total + U32.from_nat(h) : U32))

def sum_groups() -> T.Reducer<List<Nat>, U32>:
  T.Reducer{U32, U32, s => T.Continue{s},
    s => group => T.Continue{sum_group(group, s)}, s => s}

def show_groups(groups: List<List<Nat>>) -> String:
  List.show(~&1, ~List<Nat>, ~(xs => List.show(~&1, ~Nat, ~Nat.show, xs)), groups)

def main() -> IO(Unit):
  do IO<Unit>:
    # Count and ordered collection use the same named pipeline settings.
    IO.print(Nat.show(T.transduce(
      ~T.over_list(~U32, ~Nat,
        ~pipeline(~Nat, ~T.count(~List<Nat>))),
      unit_config(1, 4n, 3n), [1, 2, 3, 4, 5])))
    IO.print(show_groups(T.transduce(
      ~T.over_list(~U32, ~List<List<Nat>>,
        ~pipeline(~List<List<Nat>>, ~T.into_list(~List<Nat>))),
      unit_config(1, 4n, 3n), [1, 2, 3, 4, 5])))
    # The U32 initial value proves that consumer configuration is not forced
    # to Unit and remains separate from the named pipeline settings.
    IO.print(U32.show(T.transduce(
      ~T.over_list(~U32, ~U32, ~pipeline(~U32, ~sum_groups())),
      u32_config(1, 4n, 3n, 0), [1, 2, 3, 4, 5])))
    # Range and tree adapters see the same declaration and settings.
    IO.print(Nat.show(T.transduce(
      ~T.over_range(~Nat,
        ~pipeline(~Nat, ~T.count(~List<Nat>))),
      unit_config(1, 4n, 2n), T.range_between(1, 6))))
    IO.print(Nat.show(T.transduce(
      ~Tree.over_tree(~U32, ~Nat,
        ~pipeline(~Nat, ~T.count(~List<Nat>))),
      unit_config(1, 4n, 2n),
      Tree.Branch{Tree.Leaf{1}, Tree.Branch{Tree.Leaf{2}, Tree.Leaf{3}}})))
    # A downstream initial Stop prevents source steps, and repeated runs are
    # fresh because the wrapper stores no mutable state outside the reducer.
    IO.print(Nat.show(T.transduce(
      ~T.over_list(~U32, ~Nat,
        ~pipeline(~Nat, ~initial_stop())),
      unit_config(1, 4n, 2n), [1, 2, 3])))
    IO.print(List.show(~&1, ~Nat, ~Nat.show, [
      T.transduce(~T.over_list(~U32, ~Nat,
        ~pipeline(~Nat, ~T.count(~List<Nat>))),
        unit_config(1, 4n, 2n), [1, 2, 3, 4, 5]),
      T.transduce(~T.over_list(~U32, ~Nat,
        ~pipeline(~Nat, ~T.count(~List<Nat>))),
        unit_config(1, 4n, 2n), [1, 2, 3, 4, 5])]))
#|2
#|[[2, 3, 4], [5]]
#|14
#|2
#|1
#|0
#|[2, 2]
