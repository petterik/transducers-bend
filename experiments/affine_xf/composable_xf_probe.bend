import Base
import ./explicit_reducer_types.bend as E
import ../../transduce.bend as T

# Reducer code is ordinary here; matching it consumes the record and moves
# each callback into exactly one callback of the new reducer.
def map_code(-R: Type, -C: Type, -S: Type,
  down: E.R2<U32, R, C, S>) -> E.R2<U32, R, C, S>:
  match down:
    case E.R2{start, advance, done}:
      E.R2{start, s => x => advance(s, E.plus_one(x)), done}

def take_control(-S: Type, n: Nat, c: T.Control<S>) ->
  T.Control<T.Taking<S>>:
  match n c:
    case 0n T.Continue{s}:
      T.Stop{T.Taking{0n, T.Continue{s}}}
    case 0n T.Stop{s}:
      T.Stop{T.Taking{0n, T.Stop{s}}}
    case 1n+p T.Continue{s}:
      T.Continue{T.Taking{1n+p, T.Continue{s}}}
    case 1n+p T.Stop{s}:
      T.Stop{T.Taking{1n+p, T.Stop{s}}}

def take_start(-C: Type, -S: Type, start: C -> T.Control<S>,
  config: Nat & C) -> T.Control<T.Taking<S>>:
  (limit, c) = config
  take_control(S, limit, start(c))

def take_step(-S: Type, advance: S -> U32 -> T.Control<S>,
  state: T.Taking<S>, x: U32) -> T.Control<T.Taking<S>>:
  match state:
    case T.Taking{0n, inner}:
      T.Stop{T.Taking{0n, inner}}
    case T.Taking{1n+p, T.Stop{s}}:
      T.Stop{T.Taking{1n+p, T.Stop{s}}}
    case T.Taking{1n+p, T.Continue{s}}:
      take_control(S, p, advance(s, x))

def take_done(-R: Type, -S: Type, done: S -> R,
  state: T.Taking<S>) -> R:
  match state:
    case T.Taking{left, T.Stop{s}}:
      done(s)
    case T.Taking{left, T.Continue{s}}:
      done(s)

def take_code(-R: Type, -C: Type, -S: Type,
  down: E.R2<U32, R, C, S>) ->
  E.R2<U32, R, Nat & C, T.Taking<S>>:
  match down:
    case E.R2{start, advance, done}:
      E.R2{cfg => take_start(C, S, start, cfg),
        state => x => take_step(S, advance, state, x),
        state => take_done(R, S, done, state)}

type Xf<-CF: Type -> Type, -SF: Type -> Type,
  -code: @-R: Type -> @-C: Type -> @-S: Type ->
    E.R2<U32, R, C, S> -> E.R2<U32, R, CF(C), SF(S)>> is Type:
  Xf{configure: @-C: Type -> C -> CF(C)}

def mapped() -> Xf<(C => C), (S => S), map_code>:
  Xf{C => c => c}

def taking(n: Nat) -> Xf<(C => Nat & C),
  (S => T.Taking<S>), take_code>:
  Xf{C => c => (n, c)}

def compose(
  ~CF: Type -> Type, ~SF: Type -> Type,
  ~codeF: @-R: Type -> @-C: Type -> @-S: Type ->
    E.R2<U32, R, C, S> -> E.R2<U32, R, CF(C), SF(S)>,
  ~CG: Type -> Type, ~SG: Type -> Type,
  ~codeG: @-R: Type -> @-C: Type -> @-S: Type ->
    E.R2<U32, R, C, S> -> E.R2<U32, R, CG(C), SG(S)>,
  xfF: Xf<CF, SF, codeF>, xfG: Xf<CG, SG, codeG>) ->
  Xf<(C => CF(CG(C))), (S => SF(SG(S))),
    (R => C => S => down =>
      codeF(R, CG(C), SG(S), codeG(R, C, S, down)))>:
  match xfF xfG:
    case Xf{cfgF} Xf{cfgG}:
      Xf{C => c => cfgF(CG(C), cfgG(C, c))}

def configure(
  -CF: Type -> Type, -SF: Type -> Type,
  -code: @-R: Type -> @-C: Type -> @-S: Type ->
    E.R2<U32, R, C, S> -> E.R2<U32, R, CF(C), SF(S)>,
  -C: Type, xf: Xf<CF, SF, code>, initial: C) -> CF(C):
  match xf:
    case Xf{f}:
      f(C, initial)

def fold2(~R: Type, ~C: Type, ~S: Type, ~r: E.R2<U32, R, C, S>,
  xs: List<U32>, control: T.Control<S>) -> T.Control<S>:
  match xs control:
    case Nil{} c:
      c
    case h <> t T.Stop{s}:
      T.Stop{s}
    case h <> t T.Continue{s}:
      fold2(~R, ~C, ~S, ~r, t,
        E.step2(~U32, ~R, ~C, ~S, r)(s, h))

def finish2(~R: Type, ~C: Type, ~S: Type, ~r: E.R2<U32, R, C, S>,
  control: T.Control<S>) -> R:
  match control:
    case T.Stop{s}:
      E.done2(~U32, ~R, ~C, ~S, r)(s)
    case T.Continue{s}:
      E.done2(~U32, ~R, ~C, ~S, r)(s)

def run_recipe(~R: Type, ~C: Type, ~S: Type,
  ~r: E.R2<U32, R, C, S>, config: C, xs: List<U32>) -> R:
  finish2(~R, ~C, ~S, ~r,
    fold2(~R, ~C, ~S, ~r, xs,
      E.start2(~U32, ~R, ~C, ~S, r)(config)))

def run(
  ~R: Type, ~C: Type, ~S: Type,
  ~CF: Type -> Type, ~SF: Type -> Type,
  ~code: @-R: Type -> @-C: Type -> @-S: Type ->
    E.R2<U32, R, C, S> -> E.R2<U32, R, CF(C), SF(S)>,
  ~down: E.R2<U32, R, C, S>,
  xf: Xf<CF, SF, code>, config: C, xs: List<U32>) -> R:
  match xf:
    case Xf{configure}:
      finish2(~R, ~CF(C), ~SF(S), ~code(R, C, S, down),
        fold2(~R, ~CF(C), ~SF(S), ~code(R, C, S, down), xs,
          E.start2(~U32, ~R, ~CF(C), ~SF(S),
            code(R, C, S, down))(configure(C, config))))

def main() -> U32:
  xf = compose(
    ~(C => C), ~(S => S), ~map_code,
    ~(C => Nat & C), ~(S => T.Taking<S>), ~take_code,
    mapped(), taking(2n))
  run(~U32, ~U32, ~U32,
    ~(C => Nat & C), ~(S => T.Taking<S>),
    ~(R => C => S => down =>
      map_code(R, Nat & C, T.Taking<S>, take_code(R, C, S, down))),
    ~E.sum2(), xf, 0, [1, 2, 3])
#|5
