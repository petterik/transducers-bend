# Test-only buffering and completion-emitting adapters exercise the public
# protocol. They are not public partitioning operators.
import Base
import ../transduce.bend as T

def digits(s: U32, x: U32) -> T.Control<U32>:
  T.Continue{((s * 10 : U32) + x : U32)}

def collector() -> T.Reducer<U32, U32>:
  T.Reducer{U32, U32, s => T.Continue{s}, digits, s => (s + 1000 : U32)}

type Buffer<-S: Type> is Type:
  Buffer{pending: Maybe<U32>, inner: T.Control<S>}

def wrap(~S: Type, pending: Maybe<U32>, c: T.Control<S>) -> T.Control<Buffer<S>>:
  match c:
    case T.Continue{s}:
      T.Continue{Buffer{pending, T.Continue{s}}}
    case T.Stop{s}:
      T.Stop{Buffer{pending, T.Stop{s}}}

def advance(~down: T.Reducer<U32, U32>, state: Buffer<T.State(U32, U32, down)>, x: U32) -> T.Control<Buffer<T.State(U32, U32, down)>>:
  match state:
    case Buffer{pending, T.Stop{s}}:
      T.Stop{Buffer{pending, T.Stop{s}}}
    case Buffer{None{}, T.Continue{s}}:
      T.Continue{Buffer{Some{x}, T.Continue{s}}}
    case Buffer{Some{p}, T.Continue{s}}:
      wrap(~T.State(U32, U32, down), None{}, T.step(U32, U32, down, s, (p + x : U32)))

def flush(~down: T.Reducer<U32, U32>, state: Buffer<T.State(U32, U32, down)>) -> U32:
  match state:
    case Buffer{pending, T.Stop{s}}:
      T.finish(U32, U32, down, s)
    case Buffer{None{}, T.Continue{s}}:
      T.finish(U32, U32, down, s)
    case Buffer{Some{p}, T.Continue{s}}:
      T.finish_control(~U32, ~U32, ~down, T.step(U32, U32, down, s, p))

def pair(~down: T.Reducer<U32, U32>) -> T.Reducer<U32, U32>:
  T.Reducer{T.Config(U32, U32, down), Buffer<T.State(U32, U32, down)>,
    c => wrap(~T.State(U32, U32, down), None{}, T.start(U32, U32, down, c)),
    s => x => advance(~down, s, x), s => flush(~down, s)}

# Completion may itself produce more than one value. Each emission checks
# downstream control before the next, including a Stop from its first emit.
def send(~down: T.Reducer<U32, U32>, c: T.Control<T.State(U32, U32, down)>, x: U32) -> T.Control<T.State(U32, U32, down)>:
  match c:
    case T.Stop{s}:
      T.Stop{s}
    case T.Continue{s}:
      T.step(U32, U32, down, s, x)

def ending_start(~S: Type, c: T.Control<S>) -> T.Control<T.Control<S>>:
  match c:
    case T.Continue{s}:
      T.Continue{T.Continue{s}}
    case T.Stop{s}:
      T.Stop{T.Stop{s}}

def ending(~down: T.Reducer<U32, U32>) -> T.Reducer<U32, U32>:
  T.Reducer{T.Config(U32, U32, down), T.Control<T.State(U32, U32, down)>,
    c => ending_start(~T.State(U32, U32, down), T.start(U32, U32, down, c)),
    s => x => T.Continue{s},
    s => T.finish_control(~U32, ~U32, ~down, send(~down, send(~down, s, 1), 2))}

def main() -> List<U32>:
  [T.transduce(~U32, ~U32, ~T.take(~U32, ~U32, ~pair(~collector())), (3n, 0), [1, 2, 3, 4, 5]),
   T.transduce(~U32, ~U32, ~pair(~T.take(~U32, ~U32, ~collector())), (1n, 0), [1, 2, 3, 4, 5]),
   T.transduce(~U32, ~U32, ~pair(~collector()), 0, []),
   T.transduce(~U32, ~U32, ~pair(~T.take(~U32, ~U32, ~collector())), (0n, 0), [1, 2, 3]),
   T.transduce(~U32, ~U32, ~pair(~pair(~collector())), 0, [1, 2, 3]),
   T.transduce(~U32, ~U32, ~ending(~T.take(~U32, ~U32, ~collector())), (1n, 0), []),
   T.transduce(~U32, ~U32, ~ending(~T.take(~U32, ~U32, ~collector())), (0n, 0), [])]
#|[1033, 1003, 1000, 1000, 1006, 1001, 1000]
