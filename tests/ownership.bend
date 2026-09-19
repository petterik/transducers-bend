import Base
import ../transduce.bend as T

def append_flag(acc: List<Bool>, x: Bool) -> List<Bool>:
  x <> acc

def flags() -> T.Reducer<U32, List<Bool>>:
  T.map(~U32, ~Bool, ~List<Bool>, ~U32.is_even,
    ~T.reducing(~Bool, ~List<Bool>, ~List<Bool>, ~append_flag, ~(s => s)))

def add_closure(acc: U32, f: Unit -> U32) -> U32:
  (acc + f(Unit{}) : U32)

def closures() -> T.Reducer<U32, U32>:
  T.map(~U32, ~(Unit -> U32), ~U32, ~(x => u => x),
    ~T.reducing(~(Unit -> U32), ~U32, ~U32, ~add_closure, ~(s => s)))

def runtime_map() -> T.Reducer<U32, U32>:
  T.map_with(~U32, ~U32, ~U32, ~U32, ~U32.add, ~T.sum())

def main() -> IO(Unit):
  do IO<Unit>:
    IO.print(List.show(~&1, ~Bool, ~Bool.show, T.transduce(~U32, ~List<Bool>, ~flags(), [], [1, 2, 3])))
    IO.print(U32.show(T.transduce(~U32, ~U32, ~closures(), 0, [1, 2, 3])))
    IO.print(U32.show(T.transduce(~U32, ~U32, ~runtime_map(), (10, 0), [1, 2])))
    IO.print(U32.show(T.transduce(~U32, ~U32, ~T.sum(), 10, [1, 2])))
#|[False, True, False]
#|6
#|23
#|13
