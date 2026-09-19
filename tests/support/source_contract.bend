# Reusable conformance checks for source-owned folds. Supply a fresh [1,2,3]
# source and an empty source; adapt element values to U32 in advance if needed.
import Base
import ../../transduce.bend as T

type Trace is Type:
  Trace{left: Nat, calls: U32, digits: U32}

def wrap(left: Nat, calls: U32, digits: U32) -> T.Control<Trace>:
  match left:
    case 0n:
      T.Stop{Trace{0n, calls, digits}}
    case 1n+p:
      T.Continue{Trace{1n+p, calls, digits}}

def advance(state: Trace, x: U32) -> T.Control<Trace>:
  match state:
    case Trace{0n, calls, digits}:
      T.Stop{Trace{0n, 999, 999}}
    case Trace{1n+p, calls, digits}:
      wrap(p, (calls + 1 : U32), ((digits * 10 : U32) + x : U32))

def char_advance(state: Trace, x: Char) -> T.Control<Trace>:
  advance(state, (Char.to_u32(x) - 48 : U32))

def result(c: T.Control<Trace>) -> List<U32>:
  match c:
    case T.Stop{Trace{left, calls, digits}}:
      [1, calls, digits]
    case T.Continue{Trace{left, calls, digits}}:
      [0, calls, digits]

def cases(~X: Type, ~fold: X -> T.Control<Trace> -> T.Control<Trace>,
  ~make: Unit -> X, ~empty: Unit -> X) -> List<List<U32>>:
  [result(fold(make(Unit{}), T.Stop{Trace{9n, 0, 0}})),
   result(fold(make(Unit{}), T.Continue{Trace{1n, 0, 0}})),
   result(fold(make(Unit{}), T.Continue{Trace{2n, 0, 0}})),
   result(fold(make(Unit{}), T.Continue{Trace{9n, 0, 0}})),
   result(fold(empty(Unit{}), T.Continue{Trace{9n, 0, 0}})),
   result(fold(empty(Unit{}), T.Stop{Trace{9n, 0, 0}}))]
