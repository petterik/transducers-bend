import Base
import ../xf.bend as X

def numbers() -> List<U32>:
  [1, 2, 3]

def empty() -> List<U32>:
  []

def singleton() -> List<U32>:
  [4]

def empty_pairs() -> List<(U32 & U32)>:
  []

def pair_sum(pair: U32 & U32) -> U32:
  (a, b) = pair
  U32.add(a, b)

def pairs() -> List<(U32 & U32)>:
  X.into(empty_pairs(), X.window2(~U32), numbers())

def summed() -> U32:
  X.transduce(X.comp2(X.window2(~U32),
    X.map(~(U32 & U32), ~U32, ~pair_sum)), X.sum_rf(), 0,
    numbers())

def main() -> List<(U32 & U32)> & List<(U32 & U32)> &
  List<(U32 & U32)> & List<(U32 & U32)> & U32:
  (pairs(),
   X.into(empty_pairs(), X.window2(~U32), empty()),
   X.into(empty_pairs(), X.window2(~U32), singleton()),
   X.into(empty_pairs(),
     X.comp2(X.window2(~U32), X.take(~(U32 & U32), 1n)),
     numbers()), summed())
#|([(2, 3), (1, 2)], [], [], [(1, 2)], 8)
