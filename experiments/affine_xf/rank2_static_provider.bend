import Base
import ./custom_shift.bend as Shift
import ../../transduce.bend as T

# This library combinator has no cases for either stage. Each stage supplies
# a closed provider lambda; the compiler specializes their composition.
def compose_provider(~R: Type,
  ~outer: T.Reducer<U32, R> -> T.Reducer<U32, R>,
  ~inner: T.Reducer<U32, R> -> T.Reducer<U32, R>,
  ~down: T.Reducer<U32, R>) -> T.Reducer<U32, R>:
  outer(inner(down))

# The provider is erased static code. The value owns only runtime settings.
# Its configure function is polymorphic in the consumer and returns exactly
# the configuration type required by the provider-transformed reducer.
type Xf<-P: @-R: Type -> @-down: T.Reducer<U32, R> ->
  T.Reducer<U32, R>> is Type:
  Xf{configure: @-R: Type -> @-down: T.Reducer<U32, R> ->
    T.Config(U32, R, down) -> T.Config(U32, R, P(R, down))}

def run(~P: @-R: Type -> @-down: T.Reducer<U32, R> ->
    T.Reducer<U32, R>,
  ~R: Type, ~down: T.Reducer<U32, R>,
  xf: Xf<P>, initial: T.Config(U32, R, down), xs: List<U32>) -> R:
  match xf:
    case Xf{configure}:
      config = configure(R, down, initial)
      T.transduce(~T.over_list(~U32, ~R, ~P(R, down)), config, xs)

def run_range(~P: @-R: Type -> @-down: T.Reducer<U32, R> ->
    T.Reducer<U32, R>,
  ~R: Type, ~down: T.Reducer<U32, R>,
  xf: Xf<P>, initial: T.Config(U32, R, down), source: T.Range) -> R:
  match xf:
    case Xf{configure}:
      config = configure(R, down, initial)
      T.transduce(~T.over_range(~R, ~P(R, down)), config, source)

def shift_take(n: Nat, offset: U32) -> Xf<
  (R => down => compose_provider(~R,
    ~(d => T.map_with(~U32, ~U32, ~R, ~U32, ~Shift.add, ~d)),
    ~(d => T.take(~U32, ~R, ~d)), ~down))>:
  Xf{R => down => config => (offset, (n, config))}

def main() -> U32:
  sum = run(~(R => down => compose_provider(~R,
      ~(d => T.map_with(~U32, ~U32, ~R, ~U32, ~Shift.add, ~d)),
      ~(d => T.take(~U32, ~R, ~d)), ~down)),
    ~U32, ~T.sum(), shift_take(2n, 1), 0, [1, 2, 3])
  count = run(~(R => down => compose_provider(~R,
      ~(d => T.map_with(~U32, ~U32, ~R, ~U32, ~Shift.add, ~d)),
      ~(d => T.take(~U32, ~R, ~d)), ~down)),
    ~Nat, ~T.count(~U32), shift_take(2n, 1), Unit{}, [1, 2, 3])
  ranged = run_range(~(R => down => compose_provider(~R,
      ~(d => T.map_with(~U32, ~U32, ~R, ~U32, ~Shift.add, ~d)),
      ~(d => T.take(~U32, ~R, ~d)), ~down)),
    ~U32, ~T.sum(), shift_take(2n, 1), 0, T.range_between(1, 4))
  (sum + U32.from_nat(count) + ranged : U32)
#|12
