import Base
import ../../transduce.bend as T

# The rank-2 provider representation generalized across input/output types.
type Xf<-A: Type, -B: Type,
  -P: @-R: Type -> @-down: T.Reducer<B, R> ->
    T.Reducer<A, R>> is Type:
  Xf{configure: @-R: Type -> @-down: T.Reducer<B, R> ->
    T.Config(B, R, down) -> T.Config(A, R, P(R, down))}

def mapped() -> Xf<U32, Nat,
  (R => down => T.map(~U32, ~Nat, ~R, ~U32.to_nat, ~down))>:
  Xf{R => down => config => config}

def taking(n: Nat) -> Xf<Nat, Nat,
  (R => down => T.take(~Nat, ~R, ~down))>:
  Xf{R => down => config => (n, config)}

def compose(
  -A: Type, -B: Type, -C: Type,
  -Outer: @-R: Type -> @-down: T.Reducer<B, R> -> T.Reducer<A, R>,
  -Inner: @-R: Type -> @-down: T.Reducer<C, R> -> T.Reducer<B, R>,
  xf: Xf<A, B, Outer>, xg: Xf<B, C, Inner>) ->
  Xf<A, C, (R => down => Outer(R, Inner(R, down)))>:
  match xf xg:
    case Xf{configureF} Xf{configureG}:
      Xf{R => down => config =>
        configureF(R, Inner(R, down), configureG(R, down, config))}

def run(~A: Type, ~B: Type,
  ~P: @-R: Type -> @-down: T.Reducer<B, R> -> T.Reducer<A, R>,
  ~R: Type, ~down: T.Reducer<B, R>,
  xf: Xf<A, B, P>, initial: T.Config(B, R, down),
  xs: List<A>) -> R:
  match xf:
    case Xf{configure}:
      config = configure(R, down, initial)
      T.transduce(~T.over_list(~A, ~R, ~P(R, down)), config, xs)

def main() -> Nat:
  xf = compose(U32, Nat, Nat,
    (R => down => T.map(~U32, ~Nat, ~R, ~U32.to_nat, ~down)),
    (R => down => T.take(~Nat, ~R, ~down)),
    mapped(), taking(2n))
  run(~U32, ~Nat,
    ~(R => down => T.map(~U32, ~Nat, ~R, ~U32.to_nat,
      ~T.take(~Nat, ~R, ~down))),
    ~Nat, ~T.count(~Nat), xf, Unit{}, [1, 2, 3])
#|2n
