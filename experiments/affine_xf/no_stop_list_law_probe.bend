import Base
import ../../transduce.bend as T

def stopping(~step: U32 -> U32 -> U32, xs: List<U32>, c: T.Control<U32>) -> T.Control<U32>:
  match xs c:
    case Nil{} c:
      c
    case h <> t T.Stop{s}:
      T.Stop{s}
    case h <> t T.Continue{s}:
      stopping(~step, t, T.Continue{step(s, h)})

def total(~step: U32 -> U32 -> U32, xs: List<U32>, state: U32) -> U32:
  match xs:
    case Nil{}:
      state
    case h <> t:
      total(~step, t, step(state, h))

law agree:
  for ~step: U32 -> U32 -> U32
  for xs: List<U32>
  for +state: U32
  {stopping(~step, xs, T.Continue{state}) == T.Continue{total(~step, xs, state)} : T.Control<U32>}

def agree(step, xs, state):
  match xs:
    case Nil{}:
      {==}
    case h <> t:
      agree(~step, t, step(state, h))

def main() -> {stopping(~U32.add, [1, 2, 3], T.Continue{0}) ==
  T.Continue{total(~U32.add, [1, 2, 3], 0)} : T.Control<U32>}:
  agree(~U32.add, [1, 2, 3], 0)
