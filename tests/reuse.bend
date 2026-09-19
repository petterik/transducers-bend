import Base
import ../transduce.bend as T

def above(threshold: U32, x: U32) -> Bool:
  U32.is_gt(x, threshold)

# One declaration, different consumers and result types.
def pipeline(~R: Type, ~down: T.Reducer<U32, R>) -> T.Reducer<U32, R>:
  T.map(~U32, ~U32, ~R, ~(x => (x + 1 : U32)),
    ~T.filter(~U32, ~R, ~U32, ~above,
      ~T.take(~U32, ~R, ~down)))

def prepend(xs: List<U32>, x: U32) -> List<U32>:
  x <> xs

def reverse_collector() -> T.Reducer<U32, List<U32>>:
  T.reducing(~U32, ~List<U32>, ~List<U32>, ~prepend, ~(xs => xs))

def main() -> IO(Unit):
  do IO<Unit>:
    IO.print(U32.show(T.transduce(~T.over_list(~U32, ~U32, ~pipeline(~U32, ~T.sum())), (2, (2n, 0)), [1, 2, 3, 4, 5])))
    IO.print(List.show(~&1, ~U32, ~U32.show,
      T.transduce(~T.over_list(~U32, ~List<U32>, ~pipeline(~List<U32>, ~reverse_collector())), (2, (2n, [])), [1, 2, 3, 4, 5])))
    IO.print(U32.show(T.transduce(~T.over_list(~U32, ~U32, ~T.identity(~U32, ~U32, ~T.sum())), 10, [1, 2])))
#|7
#|[4, 3]
#|13
