import Base
import ../xf.bend as X
import ./support/vec_pair_source.bend as Pair

def numbers() -> List<U32>:
  [1, 2, 3, 4]

def short() -> List<U32>:
  [1, 2]

def empty() -> List<U32>:
  []

def empty_triples() -> List<(U32 & U32 & U32)>:
  []

def triple_sum(triple: U32 & U32 & U32) -> U32:
  (a, b, c) = triple
  U32.add(a, U32.add(b, c))

def triples() -> List<(U32 & U32 & U32)>:
  X.into(empty_triples(), X.windows3(~U32), numbers())

def summed() -> U32:
  X.transduce(X.comp2(X.windows3(~U32),
    X.map(~(U32 & U32 & U32), ~U32, ~triple_sum)),
    X.sum_rf(), 0, numbers())

def main() -> List<(U32 & U32 & U32)> &
  List<(U32 & U32 & U32)> & List<(U32 & U32 & U32)> &
  List<(U32 & U32 & U32)> & List<(U32 & U32 & U32)> & U32:
  (triples(),
   X.into(empty_triples(), X.windows3(~U32), short()),
   X.into(empty_triples(), X.windows3(~U32), empty()),
   X.into(empty_triples(),
     X.comp2(X.windows3(~U32), X.take(~(U32 & U32 & U32), 1n)),
     numbers()),
   X.into(empty_triples(), X.windows3(~U32), Pair.example()),
   summed())
#|([(2, 3, 4), (1, 2, 3)], [], [], [(1, 2, 3)], [], 15)
