import Base
import ../transduce.bend as T

def accept(f: Unit -> U32) -> Bool:
  True{}

def add(acc: U32, f: Unit -> U32) -> U32:
  (acc + f(Unit{}) : U32)

def bad() -> T.Reducer<(Unit -> U32), U32>:
  T.filter(~(Unit -> U32), ~U32, ~Unit, ~(u => f => accept(f)),
    ~T.reducing(~(Unit -> U32), ~U32, ~U32, ~add, ~(s => s)))

def main() -> U32:
  T.transduce(~T.over_list(~(Unit -> U32), ~U32, ~bad()), (Unit{}, 0), [u => 1])
#|Error:
#|- expected : Data
#|- observed : Type
#|Context:
#|- A         : Data
#|- R         : Type
#|- C         : Data
#|- predicate : @_:Unit -> @_:(@_:Unit -> U32) -> Bool
#|- down      : ../transduce.Reducer<@_:Unit -> U32, U32>
#|- state     : ../transduce.Configured<Unit, U32>
#|Location: ../transduce.filter_step~0
#|10 | def bad() -> T.Reducer<(Unit -> U32), U32>:
#|11>|   T.filter(~(Unit -> U32), ~U32, ~Unit, ~(u => f => accept(f)),
#|12 |     ~T.reducing(~(Unit -> U32), ~U32, ~U32, ~add, ~(s => s)))
#|exit 1
