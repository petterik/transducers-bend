import Base
import ../transduce.bend as T

def above(threshold: U32, x: U32) -> Bool:
  U32.is_gt(x, threshold)

def filter_take() -> T.Reducer<U32, U32>:
  T.filter(~U32, ~U32, ~U32, ~above, ~T.take(~U32, ~U32, ~T.sum()))

def take_filter() -> T.Reducer<U32, U32>:
  T.take(~U32, ~U32, ~T.filter(~U32, ~U32, ~U32, ~above, ~T.sum()))

def twice_take() -> T.Reducer<U32, U32>:
  T.take(~U32, ~U32, ~T.take(~U32, ~U32, ~T.sum()))

def limited_step(s: U32, x: U32) -> T.Control<U32>:
  T.Stop{(s + x : U32)}

def limited() -> T.Reducer<U32, U32>:
  T.Reducer{U32, U32, s => T.Continue{s}, limited_step, s => s}

def stopped() -> T.Reducer<U32, U32>:
  T.Reducer{U32, U32, s => T.Stop{s}, limited_step, s => s}

def main() -> List<U32>:
  [T.transduce(~T.over_list(~U32, ~U32, ~filter_take()), (2, (2n, 0)), [1, 2, 3, 4]),
   T.transduce(~T.over_list(~U32, ~U32, ~take_filter()), (2n, (2, 0)), [1, 2, 3, 4]),
   T.transduce(~T.over_list(~U32, ~U32, ~twice_take()), (4n, (2n, 0)), [1, 2, 3, 4]),
   T.transduce(~T.over_list(~U32, ~U32, ~twice_take()), (1n, (4n, 0)), [1, 2, 3, 4]),
   T.transduce(~T.over_list(~U32, ~U32, ~twice_take()), (4n, (0n, 0)), [1, 2, 3, 4]),
   T.transduce(~T.over_list(~U32, ~U32, ~limited()), 10, [1, 2, 3]),
   T.transduce(~T.over_list(~U32, ~U32, ~stopped()), 10, [1, 2, 3]),
   T.transduce(~T.over_list(~U32, ~U32, ~T.take(~U32, ~U32, ~limited())), (9n, 0), [1, 2, 3]),
   T.transduce(~T.over_list(~U32, ~U32, ~T.sum()), 0, [1, 2, 3]),
   T.transduce(~T.over_list(~U32, ~U32, ~T.sum()), 0, [1, 2, 3])]
#|[7, 0, 3, 1, 0, 11, 10, 1, 6, 6]
