import Base
import ../transduce_core.bend as T

# These statements use the actual library constructors rather than a List
# model. They cover a single step of map/filter with the total U32 reducer.
law map_step:
  for ~f: U32 -> U32
  for +state: U32
  for +x: U32
  {T.step(U32, U32,
      T.map(~U32, ~U32, ~U32, ~f, ~T.sum()), state, x) ==
    T.step(U32, U32, T.sum(), state, f(x)) : T.Control<Empty, U32>}

def map_step(f, state, x):
  {==}

law filter_true_step:
  for +state: U32
  for +x: U32
  {T.step(U32, U32,
      T.filter(~U32, ~U32, ~(x => True{}), ~T.sum()), state, x) ==
    T.step(U32, U32, T.sum(), state, x) : T.Control<Empty, U32>}

def filter_true_step(state, x):
  {==}

law filter_false_step:
  for +state: U32
  for +x: U32
  {T.step(U32, U32,
      T.filter(~U32, ~U32, ~(x => False{}), ~T.sum()), state, x) ==
    T.Continue{state} : T.Control<Empty, U32>}

def filter_false_step(state, x):
  {==}

def main() -> {T.step(U32, U32,
  T.map(~U32, ~U32, ~U32, ~U32.inc, ~T.sum()), 0, 1) ==
  T.Continue{2} : T.Control<Empty, U32>}:
  map_step(~U32.inc, 0, 1)
