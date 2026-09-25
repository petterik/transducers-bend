import Base
import ./transduce_core.bend as T

# Stages own runtime settings; their reducing code is a closed type-level
# recipe. The recipe carries its stop permit inside the resulting reducer.
type Xf<-A: Type, -B: Type,
  -P: @-R: Type -> @-down: T.Reducer<B, R> ->
    T.Reducer<A, R>> is Type:
  Xf{configure: @-R: Type -> @-down: T.Reducer<B, R> ->
    T.Config(B, R, down) -> T.Config(A, R, P(R, down))}

type Rf<-B: Type, -R: Type, -Q: T.Reducer<B, R>, -Init: Type> is Type:
  Rf{prepare: Init -> T.Config(B, R, Q)}

def sum_rf() -> Rf<U32, U32, T.sum(), U32>:
  Rf{initial => initial}

def count_nat_rf() -> Rf<Nat, Nat, T.count(~Nat), Unit>:
  Rf{initial => initial}

def map(~A: Type, ~B: Type, ~f: A -> B) -> Xf<A, B,
  (R => down => T.map(~A, ~B, ~R, ~f, ~down))>:
  Xf{R => down => config => config}

def map_indexed(~A: Type, ~B: Type, ~f: Nat -> A -> B) -> Xf<A, B,
  (R => down => T.map_indexed(~A, ~B, ~R, ~f, ~down))>:
  Xf{R => down => config => config}

def map_with(~A: Type, ~B: Type, ~C: Data,
  ~f: C -> A -> B, setting: C) -> Xf<A, B,
  (R => down => T.map_with(~A, ~B, ~R, ~C, ~f, ~down))>:
  Xf{R => down => config => (setting, config)}

def filter(~A: Data, ~predicate: A -> Bool) -> Xf<A, A,
  (R => down => T.filter(~A, ~R, ~predicate, ~down))>:
  Xf{R => down => config => config}

def remove(~A: Data, ~predicate: A -> Bool) -> Xf<A, A,
  (R => down => T.filter(~A, ~R,
    ~(x => Bool.not(predicate(x))), ~down))>:
  Xf{R => down => config => config}

# Adjacent duplicates only. The caller provides equality for Data values.
def dedupe(~A: Data, ~equal: A -> A -> Bool) -> Xf<A, A,
  (R => down => T.dedupe(~A, ~R, ~equal, ~down))>:
  Xf{R => down => config => config}

# Separator is copied between values, so it and the input type must be Data.
def interpose(~A: Data, separator: A) -> Xf<A, A,
  (R => down => T.interpose(~A, ~R, ~down))>:
  Xf{R => down => config => (separator, config)}

def keep(~A: Type, ~B: Type, ~f: A -> Maybe<B>) -> Xf<A, B,
  (R => down => T.keep(~A, ~B, ~R, ~f, ~down))>:
  Xf{R => down => config => config}

def keep_indexed(~A: Type, ~B: Type,
  ~f: Nat -> A -> Maybe<B>) -> Xf<A, B,
  (R => down => T.keep_indexed(~A, ~B, ~R, ~f, ~down))>:
  Xf{R => down => config => config}

# Drives each returned reducible fragment directly. If f first constructs a
# List or Array, that fragment's allocation still occurs.
def mapcat(~A: Type, ~B: Type, ~X: Type,
  ~Drive: @-K: Data -> @-S: Type -> @-advance: (S -> B -> S) ->
    @-inspect: (S -> T.Checked<K, S>) -> X -> S -> S,
  ~f: A -> X) -> Xf<A, B,
    (R => down => T.mapcat(~A, ~B, ~X, ~Drive, ~R, ~f, ~down))>:
  Xf{R => down => config => config}

# Lower-level explicit-drive form, useful when no owner adapter is available.
def cat_drive(~B: Type, ~X: Type,
  ~Drive: @-K: Data -> @-S: Type -> @-advance: (S -> B -> S) ->
    @-inspect: (S -> T.Checked<K, S>) -> X -> S -> S) -> Xf<X, B,
    (R => down => T.cat_source(~B, ~X, ~Drive, ~R, ~down))>:
  Xf{R => down => config => config}

# The adapter names a collection's static drive. It has no fragment value and
# disappears when the stage is configured. Compose map(f) with cat(adapter)
# to avoid spelling the drive at the call site.
def cat(~B: Type, ~X: Type,
  ~Drive: @-K: Data -> @-S: Type -> @-advance: (S -> B -> S) ->
    @-inspect: (S -> T.Checked<K, S>) -> X -> S -> S,
  adapter: T.SourceAdapter<B, X, Drive>) -> Xf<X, B,
    (R => down => T.cat_source(~B, ~X, ~Drive, ~R, ~down))>:
  Xf{R => down => config => config}

def take(~A: Type, n: Nat) -> Xf<A, A,
  (R => down => T.take(~A, ~R, ~down))>:
  Xf{R => down => config => (n, config)}

def drop(~A: Type, n: Nat) -> Xf<A, A,
  (R => down => T.drop(~A, ~R, ~down))>:
  Xf{R => down => config => (n, config)}

# Emits positions 0, n, 2n, ... . Zero emits nothing and still traverses;
# take(0) instead when the source should stop before producing any item.
def take_nth(~A: Type, n: Nat) -> Xf<A, A,
  (R => down => T.take_nth(~A, ~R, ~down))>:
  Xf{R => down => config => (n, config)}

def take_while(~A: Data, ~predicate: A -> Bool) -> Xf<A, A,
  (R => down => T.take_while(~A, ~R, ~predicate, ~down))>:
  Xf{R => down => config => config}

def drop_while(~A: Data, ~predicate: A -> Bool) -> Xf<A, A,
  (R => down => T.drop_while(~A, ~R, ~predicate, ~down))>:
  Xf{R => down => config => config}

# Produces ordered List chunks. Buffer and chunk construction cost remains,
# including when a downstream consumer immediately reduces each chunk.
def partition_all(~A: Type, width: Nat) -> Xf<A, List<A>,
  (R => down => T.partition_all(~A, ~R, ~down))>:
  Xf{R => down => config => (width, config)}

def compose(~A: Type, ~B: Type, ~C: Type,
  ~Outer: @-R: Type -> @-down: T.Reducer<B, R> -> T.Reducer<A, R>,
  ~Inner: @-R: Type -> @-down: T.Reducer<C, R> -> T.Reducer<B, R>,
  xf: Xf<A, B, Outer>, xg: Xf<B, C, Inner>) ->
  Xf<A, C, (R => down => Outer(R, Inner(R, down)))>:
  match xf xg:
    case Xf{configureF} Xf{configureG}:
      Xf{R => down => config =>
        configureF(R, Inner(R, down), configureG(R, down, config))}

def comp2(~A: Type, ~B: Type, ~C: Type,
  ~P: @-R: Type -> @-down: T.Reducer<B, R> -> T.Reducer<A, R>,
  ~Q: @-R: Type -> @-down: T.Reducer<C, R> -> T.Reducer<B, R>,
  a: Xf<A, B, P>, b: Xf<B, C, Q>) ->
  Xf<A, C, (R => down => P(R, Q(R, down)))>:
  compose(~A, ~B, ~C, ~P, ~Q, a, b)

def comp3(~A: Type, ~B: Type, ~C: Type, ~D: Type,
  ~P: @-R: Type -> @-down: T.Reducer<B, R> -> T.Reducer<A, R>,
  ~Q: @-R: Type -> @-down: T.Reducer<C, R> -> T.Reducer<B, R>,
  ~S: @-R: Type -> @-down: T.Reducer<D, R> -> T.Reducer<C, R>,
  a: Xf<A, B, P>, b: Xf<B, C, Q>, c: Xf<C, D, S>) ->
  Xf<A, D, (R => down => P(R, Q(R, S(R, down))))>:
  comp2(~A, ~B, ~D, ~P, ~(R => down => Q(R, S(R, down))),
    a, comp2(~B, ~C, ~D, ~Q, ~S, b, c))

def comp4(~A: Type, ~B: Type, ~C: Type, ~D: Type, ~E: Type,
  ~P: @-R: Type -> @-down: T.Reducer<B, R> -> T.Reducer<A, R>,
  ~Q: @-R: Type -> @-down: T.Reducer<C, R> -> T.Reducer<B, R>,
  ~S: @-R: Type -> @-down: T.Reducer<D, R> -> T.Reducer<C, R>,
  ~U: @-R: Type -> @-down: T.Reducer<E, R> -> T.Reducer<D, R>,
  a: Xf<A, B, P>, b: Xf<B, C, Q>,
  c: Xf<C, D, S>, d: Xf<D, E, U>) ->
  Xf<A, E, (R => down => P(R, Q(R, S(R, U(R, down)))))>:
  comp2(~A, ~B, ~E, ~P,
    ~(R => down => Q(R, S(R, U(R, down)))),
    a, comp3(~B, ~C, ~D, ~E, ~Q, ~S, ~U, b, c, d))

def comp5(~A: Type, ~B: Type, ~C: Type, ~D: Type, ~E: Type, ~F: Type,
  ~P: @-R: Type -> @-down: T.Reducer<B, R> -> T.Reducer<A, R>,
  ~Q: @-R: Type -> @-down: T.Reducer<C, R> -> T.Reducer<B, R>,
  ~S: @-R: Type -> @-down: T.Reducer<D, R> -> T.Reducer<C, R>,
  ~U: @-R: Type -> @-down: T.Reducer<E, R> -> T.Reducer<D, R>,
  ~W: @-R: Type -> @-down: T.Reducer<F, R> -> T.Reducer<E, R>,
  a: Xf<A, B, P>, b: Xf<B, C, Q>,
  c: Xf<C, D, S>, d: Xf<D, E, U>, e: Xf<E, F, W>) ->
  Xf<A, F, (R => down => P(R, Q(R, S(R, U(R, W(R, down))))))>:
  comp2(~A, ~B, ~F, ~P,
    ~(R => down => Q(R, S(R, U(R, W(R, down))))),
    a, comp4(~B, ~C, ~D, ~E, ~F, ~Q, ~S, ~U, ~W, b, c, d, e))

def list_prepend(~A: Type) -> T.Reducer<A, List<A>>:
  T.Reducer{Empty, List<A>, List<A>,
    xs => T.Continue{xs},
    xs => x => T.Continue{x <> xs},
    xs => xs}

def list_prepend_rf(~A: Type) ->
  Rf<A, List<A>, list_prepend(~A), List<A>>:
  Rf{xs => xs}

type Destination<-B: Type, -D: Type,
  -Q: T.Reducer<B, D>> is Type:
  Destination{value: D, consumer: Rf<B, D, Q, D>}

def Destination.allow_companion() -> Unit:
  Unit{}

def List.destination(~A: Type, xs: List<A>) ->
  Destination<A, List<A>, list_prepend(~A)>:
  Destination{xs, list_prepend_rf(~A)}

def transduce_from(~A: Type, ~B: Type,
  ~P: @-R: Type -> @-down: T.Reducer<B, R> -> T.Reducer<A, R>,
  ~R: Type, ~Q: T.Reducer<B, R>, ~Init: Type,
  ~X: Type,
  ~Drive: @-K: Data -> @-S: Type -> @-advance: (S -> A -> S) ->
    @-inspect: (S -> T.Checked<K, S>) -> X -> S -> S,
  xf: Xf<A, B, P>, rf: Rf<B, R, Q, Init>,
  initial: Init, source: T.Source<A, X, Drive>) -> R:
  match xf rf source:
    case Xf{configure} Rf{prepare} T.Source{input}:
      config = configure(R, Q, prepare(initial))
      T.finish_control(~A, ~R, ~P(R, Q),
        Drive(T.Permit(A, R, P(R, Q)),
          (T.Control<T.Permit(A, R, P(R, Q)), T.State(A, R, P(R, Q))>),
          (control => x => T.step_control(~A, ~R, ~P(R, Q), control, x)),
          (control => T.inspect_control(~T.Permit(A, R, P(R, Q)),
            ~T.State(A, R, P(R, Q)), control)),
          input, T.start(A, R, P(R, Q), config)))

def transduce(~A: Type, ~B: Type,
  ~P: @-R: Type -> @-down: T.Reducer<B, R> -> T.Reducer<A, R>,
  ~R: Type, ~Q: T.Reducer<B, R>, ~Init: Type,
  ~X: Type,
  ~Drive: @-K: Data -> @-S: Type -> @-advance: (S -> A -> S) ->
    @-inspect: (S -> T.Checked<K, S>) -> X -> S -> S,
  xf: Xf<A, B, P>, rf: Rf<B, R, Q, Init>,
  initial: Init, source: T.Source<A, X, Drive>) -> R:
  transduce_from(~A, ~B, ~P, ~R, ~Q, ~Init, ~X, ~Drive,
    xf, rf, initial, source)

def into_from(~A: Type, ~B: Type,
  ~P: @-R: Type -> @-down: T.Reducer<B, R> -> T.Reducer<A, R>,
  ~D: Type, ~Q: T.Reducer<B, D>, ~X: Type,
  ~Drive: @-K: Data -> @-S: Type -> @-advance: (S -> A -> S) ->
    @-inspect: (S -> T.Checked<K, S>) -> X -> S -> S,
  destination: Destination<B, D, Q>, xf: Xf<A, B, P>,
  source: T.Source<A, X, Drive>) -> D:
  match destination:
    case Destination{value, consumer}:
      transduce_from(~A, ~B, ~P, ~D, ~Q, ~D, ~X, ~Drive,
        xf, consumer, value, source)

def into(~A: Type, ~B: Type,
  ~P: @-R: Type -> @-down: T.Reducer<B, R> -> T.Reducer<A, R>,
  ~D: Type, ~Q: T.Reducer<B, D>, ~X: Type,
  ~Drive: @-K: Data -> @-S: Type -> @-advance: (S -> A -> S) ->
    @-inspect: (S -> T.Checked<K, S>) -> X -> S -> S,
  destination: Destination<B, D, Q>, xf: Xf<A, B, P>,
  source: T.Source<A, X, Drive>) -> D:
  into_from(~A, ~B, ~P, ~D, ~Q, ~X, ~Drive,
    destination, xf, source)
