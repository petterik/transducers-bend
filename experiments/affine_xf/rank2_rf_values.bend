import Base
import ./rank2_static_typed.bend as S
import ./rank2_sources.bend as Sources
import ./custom_shift.bend as Shift
import ../../transduce.bend as T

# A consumer value also carries checked static reducer code in its type.
# Its live field consumes the caller's initial value and produces the
# configuration the reducer requires. No runtime reducer record is needed.
type Rf<-B: Type, -R: Type, -Q: T.Reducer<B, R>, -Init: Type> is Type:
  Rf{prepare: Init -> T.Config(B, R, Q)}

def sum_rf() -> Rf<U32, U32, T.sum(), U32>:
  Rf{initial => initial}

def count_nat_rf() -> Rf<Nat, Nat, T.count(~Nat), Unit>:
  Rf{initial => initial}

# A stage owns its runtime settings; its reducer recipe is checked, closed
# code in the result type. The leading type parameters remain explicit because
# today's omitted-template inference uses ordinary value arguments only.
def map(~A: Type, ~B: Type, ~f: A -> B) -> S.Xf<A, B,
  (R => down => T.map(~A, ~B, ~R, ~f, ~down))>:
  S.Xf{R => down => config => config}

def map_with(~A: Type, ~B: Type, ~C: Data, ~f: C -> A -> B,
  setting: C) -> S.Xf<A, B,
  (R => down => T.map_with(~A, ~B, ~R, ~C, ~f, ~down))>:
  S.Xf{R => down => config => (setting, config)}

def take(~A: Type, n: Nat) -> S.Xf<A, A,
  (R => down => T.take(~A, ~R, ~down))>:
  S.Xf{R => down => config => (n, config)}

def mapcat(~A: Type, ~B: Type, ~f: A -> List<B>) -> S.Xf<A, B,
  (R => down => T.mapcat(~A, ~B, ~R, ~f, ~down))>:
  S.Xf{R => down => config => config}

def keep(~A: Type, ~B: Type, ~f: A -> Maybe<B>) -> S.Xf<A, B,
  (R => down => T.keep(~A, ~B, ~R, ~f, ~down))>:
  S.Xf{R => down => config => config}

def filter(~A: Data, ~predicate: A -> Bool) -> S.Xf<A, A,
  (R => down => T.filter(~A, ~R, ~Unit,
    ~(unused => x => predicate(x)), ~down))>:
  S.Xf{R => down => config => (Unit{}, config)}

def remove(~A: Data, ~predicate: A -> Bool) -> S.Xf<A, A,
  (R => down => T.filter(~A, ~R, ~Unit,
    ~(unused => x => Bool.not(predicate(x))), ~down))>:
  S.Xf{R => down => config => (Unit{}, config)}

def shifted(offset: U32) -> S.Xf<U32, U32,
  (R => down => T.map_with(~U32, ~U32, ~R, ~U32,
    ~Shift.add, ~down))>:
  map_with(~U32, ~U32, ~U32, ~Shift.add, offset)

def taking_u32(n: Nat) -> S.Xf<U32, U32,
  (R => down => T.take(~U32, ~R, ~down))>:
  take(~U32, n)

# Inferred static indices make composition look like an ordinary value call.
def compose(~A: Type, ~B: Type, ~C: Type,
  ~Outer: @-R: Type -> @-down: T.Reducer<B, R> -> T.Reducer<A, R>,
  ~Inner: @-R: Type -> @-down: T.Reducer<C, R> -> T.Reducer<B, R>,
  xf: S.Xf<A, B, Outer>, xg: S.Xf<B, C, Inner>) ->
  S.Xf<A, C, (R => down => Outer(R, Inner(R, down)))>:
  match xf xg:
    case S.Xf{configureF} S.Xf{configureG}:
      S.Xf{R => down => config =>
        configureF(R, Inner(R, down), configureG(R, down, config))}

# Fixed arities preserve each stage's distinct input, output, and closed
# provider type. They elaborate to the same binary composition, in source
# order, without constructing a runtime collection of stages.
def comp2(~A: Type, ~B: Type, ~C: Type,
  ~P: @-R: Type -> @-down: T.Reducer<B, R> -> T.Reducer<A, R>,
  ~Q: @-R: Type -> @-down: T.Reducer<C, R> -> T.Reducer<B, R>,
  a: S.Xf<A, B, P>, b: S.Xf<B, C, Q>) ->
  S.Xf<A, C, (R => down => P(R, Q(R, down)))>:
  compose(~A, ~B, ~C, ~P, ~Q, a, b)

def comp3(~A: Type, ~B: Type, ~C: Type, ~D: Type,
  ~P: @-R: Type -> @-down: T.Reducer<B, R> -> T.Reducer<A, R>,
  ~Q: @-R: Type -> @-down: T.Reducer<C, R> -> T.Reducer<B, R>,
  ~S: @-R: Type -> @-down: T.Reducer<D, R> -> T.Reducer<C, R>,
  a: S.Xf<A, B, P>, b: S.Xf<B, C, Q>, c: S.Xf<C, D, S>) ->
  S.Xf<A, D, (R => down => P(R, Q(R, S(R, down))))>:
  comp2(~A, ~B, ~D, ~P, ~(R => down => Q(R, S(R, down))),
    a, comp2(~B, ~C, ~D, ~Q, ~S, b, c))

def comp4(~A: Type, ~B: Type, ~C: Type, ~D: Type, ~E: Type,
  ~P: @-R: Type -> @-down: T.Reducer<B, R> -> T.Reducer<A, R>,
  ~Q: @-R: Type -> @-down: T.Reducer<C, R> -> T.Reducer<B, R>,
  ~S: @-R: Type -> @-down: T.Reducer<D, R> -> T.Reducer<C, R>,
  ~U: @-R: Type -> @-down: T.Reducer<E, R> -> T.Reducer<D, R>,
  a: S.Xf<A, B, P>, b: S.Xf<B, C, Q>,
  c: S.Xf<C, D, S>, d: S.Xf<D, E, U>) ->
  S.Xf<A, E, (R => down => P(R, Q(R, S(R, U(R, down)))))>:
  comp2(~A, ~B, ~E, ~P,
    ~(R => down => Q(R, S(R, U(R, down)))),
    a, comp3(~B, ~C, ~D, ~E, ~Q, ~S, ~U, b, c, d))

def comp5(~A: Type, ~B: Type, ~C: Type, ~D: Type, ~E: Type, ~F: Type,
  ~P: @-R: Type -> @-down: T.Reducer<B, R> -> T.Reducer<A, R>,
  ~Q: @-R: Type -> @-down: T.Reducer<C, R> -> T.Reducer<B, R>,
  ~S: @-R: Type -> @-down: T.Reducer<D, R> -> T.Reducer<C, R>,
  ~U: @-R: Type -> @-down: T.Reducer<E, R> -> T.Reducer<D, R>,
  ~W: @-R: Type -> @-down: T.Reducer<F, R> -> T.Reducer<E, R>,
  a: S.Xf<A, B, P>, b: S.Xf<B, C, Q>,
  c: S.Xf<C, D, S>, d: S.Xf<D, E, U>, e: S.Xf<E, F, W>) ->
  S.Xf<A, F, (R => down => P(R, Q(R, S(R, U(R, W(R, down))))))>:
  comp2(~A, ~B, ~F, ~P,
    ~(R => down => Q(R, S(R, U(R, W(R, down))))),
    a, comp4(~B, ~C, ~D, ~E, ~F, ~Q, ~S, ~U, ~W, b, c, d, e))

# Prepending is the List destination's insertion semantics. Unlike
# T.into_list it accepts an existing List and does not reverse at completion.
def list_prepend(~A: Type) -> T.Reducer<A, List<A>>:
  T.Reducer{List<A>, List<A>, xs => T.Continue{xs},
    xs => x => T.Continue{x <> xs}, xs => xs}

def list_prepend_rf(~A: Type) -> Rf<A, List<A>, list_prepend(~A), List<A>>:
  Rf{xs => xs}

# A destination selects its insertion reducer while owning an existing value.
type Destination<-B: Type, -D: Type, -Q: T.Reducer<B, D>> is Type:
  Destination{value: D, consumer: Rf<B, D, Q, D>}

def transduce_from(~A: Type, ~B: Type,
  ~P: @-Result: Type -> @-consumer: T.Reducer<B, Result> ->
    T.Reducer<A, Result>,
  ~R: Type, ~Q: T.Reducer<B, R>, ~Init: Type,
  ~X: Type,
  ~Drive: @-Result: Type -> @-recipe: T.Reducer<A, Result> ->
    X -> T.Control<T.State(A, Result, recipe)> ->
      T.Control<T.State(A, Result, recipe)>,
  xf: S.Xf<A, B, P>, rf: Rf<B, R, Q, Init>,
  initial: Init, source: Sources.Source<A, X, Drive>) -> R:
  match xf rf source:
    case S.Xf{configure} Rf{prepare} Sources.Source{input}:
      config = configure(R, Q, prepare(initial))
      T.finish_control(~A, ~R, ~P(R, Q),
        Drive(R, P(R, Q), input,
          T.start(A, R, P(R, Q), config)))

def transduce(~A: Type, ~B: Type,
  ~P: @-Result: Type -> @-consumer: T.Reducer<B, Result> ->
    T.Reducer<A, Result>,
  ~R: Type, ~Q: T.Reducer<B, R>, ~Init: Type,
  xf: S.Xf<A, B, P>, rf: Rf<B, R, Q, Init>,
  initial: Init, xs: List<A>) -> R:
  transduce_from(~A, ~B, ~P, ~R, ~Q, ~Init,
    ~List<A>, ~(Result => recipe => ys => c =>
      T.reduce_list_static(~A, ~Result, ~recipe, ys, c)),
    xf, rf, initial, Sources.list_source(~A, xs))

def into_from(~A: Type, ~B: Type,
  ~P: @-Result: Type -> @-consumer: T.Reducer<B, Result> ->
    T.Reducer<A, Result>,
  ~D: Type, ~Q: T.Reducer<B, D>, ~X: Type,
  ~Drive: @-Result: Type -> @-recipe: T.Reducer<A, Result> ->
    X -> T.Control<T.State(A, Result, recipe)> ->
      T.Control<T.State(A, Result, recipe)>,
  dest: Destination<B, D, Q>, xf: S.Xf<A, B, P>,
  source: Sources.Source<A, X, Drive>) -> D:
  match dest:
    case Destination{value, consumer}:
      transduce_from(~A, ~B, ~P, ~D, ~Q, ~D, ~X, ~Drive,
        xf, consumer, value, source)

def into(~A: Type, ~B: Type,
  ~P: @-Result: Type -> @-consumer: T.Reducer<B, Result> ->
    T.Reducer<A, Result>,
  dest: List<B>, xf: S.Xf<A, B, P>, xs: List<A>) -> List<B>:
  into_from(~A, ~B, ~P, ~List<B>, ~list_prepend(~B), ~List<A>,
    ~(Result => recipe => ys => c =>
      T.reduce_list_static(~A, ~Result, ~recipe, ys, c)),
    Destination{dest, list_prepend_rf(~B)},
    xf, Sources.list_source(~A, xs))

def main() -> U32:
  xf_sum = S.compose(U32, U32, U32,
    (R => down => T.map_with(~U32, ~U32, ~R, ~U32,
      ~Shift.add, ~down)),
    (R => down => T.take(~U32, ~R, ~down)),
    shifted(1), taking_u32(2n))
  sum = transduce(~U32, ~U32,
    ~(R => down => T.map_with(~U32, ~U32, ~R, ~U32,
      ~Shift.add, ~T.take(~U32, ~R, ~down))),
    ~U32, ~T.sum(), ~U32,
    xf_sum, sum_rf(), 0, [1, 2, 3])
  xf_count = S.compose(U32, Nat, Nat,
    (R => down => T.map(~U32, ~Nat, ~R, ~U32.to_nat, ~down)),
    (R => down => T.take(~Nat, ~R, ~down)),
    S.mapped(), S.taking(2n))
  count = transduce(~U32, ~Nat,
    ~(R => down => T.map(~U32, ~Nat, ~R, ~U32.to_nat,
      ~T.take(~Nat, ~R, ~down))),
    ~Nat, ~T.count(~Nat), ~Unit,
    xf_count, count_nat_rf(), Unit{}, [1, 2, 3])
  (sum + U32.from_nat(count) : U32)
#|7
