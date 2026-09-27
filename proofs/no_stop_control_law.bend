import Base
import ../transduce_core.bend as T

# This uses the actual Control<Empty, S> type of a total reducer.
def drive(~step: U32 -> U32 -> U32,
  xs: List<U32>, control: T.Control<Empty, U32>) ->
  T.Control<Empty, U32>:
  match xs control:
    case Nil{} control: control
    case h <> t T.Continue{state}:
      drive(~step, t, T.Continue{step(state, h)})
    case h <> t T.Stop{permit, state}:
      match permit:

def total(~step: U32 -> U32 -> U32,
  xs: List<U32>, state: U32) -> U32:
  match xs:
    case Nil{}: state
    case h <> t: total(~step, t, step(state, h))

law no_stop_agrees:
  for ~step: U32 -> U32 -> U32
  for xs: List<U32>
  for +state: U32
  {drive(~step, xs, T.Continue{state}) ==
    T.Continue{total(~step, xs, state)} : T.Control<Empty, U32>}

def no_stop_agrees(step, xs, state):
  match xs:
    case Nil{}: {==}
    case h <> t: no_stop_agrees(~step, t, step(state, h))

def main() -> {drive(~U32.add, [1, 2, 3], T.Continue{0}) ==
  T.Continue{total(~U32.add, [1, 2, 3], 0)} : T.Control<Empty, U32>}:
  no_stop_agrees(~U32.add, [1, 2, 3], 0)
