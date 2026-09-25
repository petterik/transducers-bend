import Base
import ./explicit_reducer_types.bend as E
import ./composable_xf_probe.bend as C
import ../../transduce.bend as T

# A user-defined stage with an owned runtime setting. The static code for the
# corresponding closed reducer is T.map_with, not a compiler builtin.
def add(offset: U32, x: U32) -> U32:
  (offset + x : U32)

def wrap(-S: Type, offset: U32, control: T.Control<S>) ->
  T.Control<T.Configured<U32, S>>:
  match control:
    case T.Continue{state}:
      T.Continue{T.Configured{offset, state}}
    case T.Stop{state}:
      T.Stop{T.Configured{offset, state}}

def begin(-Cfg: Type, -S: Type, start: Cfg -> T.Control<S>,
  config: U32 & Cfg) -> T.Control<T.Configured<U32, S>>:
  (offset, inner) = config
  wrap(S, offset, start(inner))

def advance(-S: Type, step: S -> U32 -> T.Control<S>,
  state: T.Configured<U32, S>, x: U32) ->
  T.Control<T.Configured<U32, S>>:
  match state:
    case T.Configured{+config, inner}:
      wrap(S, config, step(inner, add(config, x)))

def end(-R: Type, -S: Type, done: S -> R,
  state: T.Configured<U32, S>) -> R:
  match state:
    case T.Configured{config, inner}:
      done(inner)

def code(-R: Type, -Cfg: Type, -S: Type,
  down: E.R2<U32, R, Cfg, S>) ->
  E.R2<U32, R, U32 & Cfg, T.Configured<U32, S>>:
  match down:
    case E.R2{start, step, done}:
      E.R2{config => begin(Cfg, S, start, config),
        state => x => advance(S, step, state, x),
        state => end(R, S, done, state)}

def shifted(offset: U32) -> C.Xf<(K => U32 & K),
  (K => T.Configured<U32, K>), code>:
  C.Xf{K => config => (offset, config)}
