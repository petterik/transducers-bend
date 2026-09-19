import Base
import ../transduce.bend as T

def inc(x: U32) -> U32:
  (x + 1 : U32)

def above(t: U32, x: U32) -> Bool:
  U32.is_gt(x, t)

def pipeline(~R: Type, ~down: T.Reducer<U32, R>) -> T.Reducer<U32, R>:
  T.map(~U32, ~U32, ~R, ~inc,
    ~T.filter(~U32, ~R, ~U32, ~above, ~T.take(~U32, ~R, ~down)))

def stopped() -> T.Reducer<U32, U32>:
  T.Reducer{Unit, U32, u => T.Stop{10}, s => x => T.Continue{99}, s => (s + 1000 : U32)}

def one() -> T.Reducer<U32, U32>:
  T.Reducer{Unit, U32, u => T.Continue{10}, s => x => T.Stop{(s + x : U32)}, s => (s + 1000 : U32)}

def add_closure(acc: U32, f: Unit -> U32) -> U32:
  (acc + f(Unit{}) : U32)

def closures() -> T.Reducer<U32, List<(Unit -> U32)>>:
  T.map(~U32, ~(Unit -> U32), ~List<(Unit -> U32)>, ~(x => u => x), ~T.into_list(~(Unit -> U32)))

def main() -> IO(Unit):
  do IO<Unit>:
    IO.print(U32.show(T.transduce(~T.over_range(~U32, ~pipeline(~U32, ~T.sum())), (2, (2n, 0)), T.range_between(1, 6))))
    IO.print(List.show(~&1, ~U32, ~U32.show,
      T.transduce(~T.over_range(~List<U32>, ~pipeline(~List<U32>, ~T.into_list(~U32))), (2, (2n, Unit{})), T.range_between(1, 6))))
    IO.print(Nat.show(T.transduce(~T.over_range(~Nat, ~pipeline(~Nat, ~T.count(~U32))), (2, (2n, Unit{})), T.range_between(1, 6))))
    IO.print(List.show(~&1, ~U32, ~U32.show,
      T.transduce(~T.over_list(~U32, ~List<U32>, ~pipeline(~List<U32>, ~T.into_list(~U32))), (2, (2n, Unit{})), [1, 2, 3, 4, 5])))
    IO.print(List.show(~&1, ~U32, ~U32.show,
      T.transduce(~T.over_range(~List<U32>, ~T.into_list(~U32)), Unit{}, T.range_between(4294967293, 4294967295))))
    IO.print(Nat.show(T.transduce(~T.over_range(~Nat, ~T.count(~U32)), Unit{}, T.range_between(4294967295, 4294967295))))
    IO.print(Nat.show(T.transduce(~T.over_range(~Nat, ~T.count(~U32)), Unit{}, T.range_between(4294967295, 0))))
    IO.print(Nat.show(T.transduce(~T.over_range(~Nat, ~T.count(~U32)), Unit{}, T.range_between(0, 0))))
    IO.print(Nat.show(T.transduce(~T.over_range(~Nat, ~T.count(~U32)), Unit{}, T.range_between(3, 1))))
    IO.print(U32.show(T.transduce(~T.over_range(~U32, ~pipeline(~U32, ~T.sum())), (0, (0n, 17)), T.range_between(0, 4294967295))))
    IO.print(U32.show(T.transduce(~T.over_range(~U32, ~pipeline(~U32, ~T.sum())), (0, (1n, 0)), T.range_between(0, 4294967295))))
    IO.print(U32.show(T.transduce(~T.over_range(~U32, ~stopped()), Unit{}, T.range_between(0, 4294967295))))
    IO.print(U32.show(T.transduce(~T.over_range(~U32, ~one()), Unit{}, T.range_between(7, 4294967295))))
    IO.print(U32.show(T.transduce(~T.over_range(~U32, ~one()), Unit{}, T.range_between(7, 7))))
    IO.print(U32.show(List.foldl(~&1, ~(Unit -> U32), ~U32, ~add_closure,
      T.transduce(~T.over_range(~List<(Unit -> U32)>, ~closures()), Unit{}, T.range_between(1, 4)), 0)))
    IO.print(U32.show(List.foldl(~&1, ~(Unit -> U32), ~U32, ~add_closure,
      T.transduce(~T.over_list(~U32, ~List<(Unit -> U32)>, ~closures()), Unit{}, [4, 5]), 0)))
    IO.print(Nat.show(T.transduce(~T.over_list(~(Unit -> U32), ~Nat, ~T.count(~(Unit -> U32))), Unit{}, [u => 1, u => 2])))
#|7
#|[3, 4]
#|2
#|[3, 4]
#|[4294967293, 4294967294]
#|0
#|0
#|0
#|0
#|17
#|1
#|1010
#|1017
#|1010
#|6
#|9
#|2
