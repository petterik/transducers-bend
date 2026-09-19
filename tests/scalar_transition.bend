# Full-state equivalence for the benchmark-only scalar specialization.
import Base
import ../transduce.bend as T
import ../bench/scalar_prototype.bend as P

def same_inner(a: T.Control<U32>, b: T.Control<U32>) -> Bool:
  match a b:
    case T.Continue{x} T.Continue{y}:
      U32.is_eq(x, y)
    case T.Stop{x} T.Stop{y}:
      U32.is_eq(x, y)
    case T.Continue{x} T.Stop{y}:
      False{}
    case T.Stop{x} T.Continue{y}:
      False{}

def same_state(a: T.Configured<U32, T.Taking<U32>>, b: T.Configured<U32, T.Taking<U32>>) -> Bool:
  match a b:
    case T.Configured{at, T.Taking{an, ac}} T.Configured{bt, T.Taking{bn, bc}}:
      Bool.and(U32.is_eq(at, bt), Bool.and(Nat.is_eq(an, bn), same_inner(ac, bc)))

def same(a: T.Control<T.Configured<U32, T.Taking<U32>>>, b: T.Control<T.Configured<U32, T.Taking<U32>>>) -> Bool:
  match a b:
    case T.Continue{x} T.Continue{y}:
      same_state(x, y)
    case T.Stop{x} T.Stop{y}:
      same_state(x, y)
    case T.Continue{x} T.Stop{y}:
      False{}
    case T.Stop{x} T.Continue{y}:
      False{}

def inner(stopped: Bool, sum: U32) -> T.Control<U32>:
  match stopped:
    case True{}:
      T.Stop{sum}
    case False{}:
      T.Continue{sum}

def max_nat() -> Nat:
  Nat.add(Nat.mul(4294967295n, 65536n), 65535n)

def check(+n: Nat, +threshold: U32, +sum: U32, +x: U32, +stopped: Bool) -> Bool:
  same(P.scalar_step(T.Configured{threshold, T.Taking{n, inner(stopped, sum)}}, x),
    T.step(U32, U32, P.base_pipeline(), T.Configured{threshold, T.Taking{n, inner(stopped, sum)}}, x))

def main() -> List<Bool>:
  [check(0n, 0, 0, 0, False{}),
   check(0n, 0, 0, 0, True{}),
   check(0n, 0, 0, 1, False{}),
   check(0n, 0, 0, 1, True{}),
   check(0n, 0, 0, 4294967295, False{}),
   check(0n, 0, 0, 4294967295, True{}),
   check(0n, 0, 4294967295, 0, False{}),
   check(0n, 0, 4294967295, 0, True{}),
   check(0n, 0, 4294967295, 1, False{}),
   check(0n, 0, 4294967295, 1, True{}),
   check(0n, 0, 4294967295, 4294967295, False{}),
   check(0n, 0, 4294967295, 4294967295, True{}),
   check(0n, 1, 0, 0, False{}),
   check(0n, 1, 0, 0, True{}),
   check(0n, 1, 0, 1, False{}),
   check(0n, 1, 0, 1, True{}),
   check(0n, 1, 0, 4294967295, False{}),
   check(0n, 1, 0, 4294967295, True{}),
   check(0n, 1, 4294967295, 0, False{}),
   check(0n, 1, 4294967295, 0, True{}),
   check(0n, 1, 4294967295, 1, False{}),
   check(0n, 1, 4294967295, 1, True{}),
   check(0n, 1, 4294967295, 4294967295, False{}),
   check(0n, 1, 4294967295, 4294967295, True{}),
   check(0n, 4294967295, 0, 0, False{}),
   check(0n, 4294967295, 0, 0, True{}),
   check(0n, 4294967295, 0, 1, False{}),
   check(0n, 4294967295, 0, 1, True{}),
   check(0n, 4294967295, 0, 4294967295, False{}),
   check(0n, 4294967295, 0, 4294967295, True{}),
   check(0n, 4294967295, 4294967295, 0, False{}),
   check(0n, 4294967295, 4294967295, 0, True{}),
   check(0n, 4294967295, 4294967295, 1, False{}),
   check(0n, 4294967295, 4294967295, 1, True{}),
   check(0n, 4294967295, 4294967295, 4294967295, False{}),
   check(0n, 4294967295, 4294967295, 4294967295, True{}),
   check(1n, 0, 0, 0, False{}),
   check(1n, 0, 0, 0, True{}),
   check(1n, 0, 0, 1, False{}),
   check(1n, 0, 0, 1, True{}),
   check(1n, 0, 0, 4294967295, False{}),
   check(1n, 0, 0, 4294967295, True{}),
   check(1n, 0, 4294967295, 0, False{}),
   check(1n, 0, 4294967295, 0, True{}),
   check(1n, 0, 4294967295, 1, False{}),
   check(1n, 0, 4294967295, 1, True{}),
   check(1n, 0, 4294967295, 4294967295, False{}),
   check(1n, 0, 4294967295, 4294967295, True{}),
   check(1n, 1, 0, 0, False{}),
   check(1n, 1, 0, 0, True{}),
   check(1n, 1, 0, 1, False{}),
   check(1n, 1, 0, 1, True{}),
   check(1n, 1, 0, 4294967295, False{}),
   check(1n, 1, 0, 4294967295, True{}),
   check(1n, 1, 4294967295, 0, False{}),
   check(1n, 1, 4294967295, 0, True{}),
   check(1n, 1, 4294967295, 1, False{}),
   check(1n, 1, 4294967295, 1, True{}),
   check(1n, 1, 4294967295, 4294967295, False{}),
   check(1n, 1, 4294967295, 4294967295, True{}),
   check(1n, 4294967295, 0, 0, False{}),
   check(1n, 4294967295, 0, 0, True{}),
   check(1n, 4294967295, 0, 1, False{}),
   check(1n, 4294967295, 0, 1, True{}),
   check(1n, 4294967295, 0, 4294967295, False{}),
   check(1n, 4294967295, 0, 4294967295, True{}),
   check(1n, 4294967295, 4294967295, 0, False{}),
   check(1n, 4294967295, 4294967295, 0, True{}),
   check(1n, 4294967295, 4294967295, 1, False{}),
   check(1n, 4294967295, 4294967295, 1, True{}),
   check(1n, 4294967295, 4294967295, 4294967295, False{}),
   check(1n, 4294967295, 4294967295, 4294967295, True{}),
   check(2n, 0, 0, 0, False{}),
   check(2n, 0, 0, 0, True{}),
   check(2n, 0, 0, 1, False{}),
   check(2n, 0, 0, 1, True{}),
   check(2n, 0, 0, 4294967295, False{}),
   check(2n, 0, 0, 4294967295, True{}),
   check(2n, 0, 4294967295, 0, False{}),
   check(2n, 0, 4294967295, 0, True{}),
   check(2n, 0, 4294967295, 1, False{}),
   check(2n, 0, 4294967295, 1, True{}),
   check(2n, 0, 4294967295, 4294967295, False{}),
   check(2n, 0, 4294967295, 4294967295, True{}),
   check(2n, 1, 0, 0, False{}),
   check(2n, 1, 0, 0, True{}),
   check(2n, 1, 0, 1, False{}),
   check(2n, 1, 0, 1, True{}),
   check(2n, 1, 0, 4294967295, False{}),
   check(2n, 1, 0, 4294967295, True{}),
   check(2n, 1, 4294967295, 0, False{}),
   check(2n, 1, 4294967295, 0, True{}),
   check(2n, 1, 4294967295, 1, False{}),
   check(2n, 1, 4294967295, 1, True{}),
   check(2n, 1, 4294967295, 4294967295, False{}),
   check(2n, 1, 4294967295, 4294967295, True{}),
   check(2n, 4294967295, 0, 0, False{}),
   check(2n, 4294967295, 0, 0, True{}),
   check(2n, 4294967295, 0, 1, False{}),
   check(2n, 4294967295, 0, 1, True{}),
   check(2n, 4294967295, 0, 4294967295, False{}),
   check(2n, 4294967295, 0, 4294967295, True{}),
   check(2n, 4294967295, 4294967295, 0, False{}),
   check(2n, 4294967295, 4294967295, 0, True{}),
   check(2n, 4294967295, 4294967295, 1, False{}),
   check(2n, 4294967295, 4294967295, 1, True{}),
   check(2n, 4294967295, 4294967295, 4294967295, False{}),
   check(2n, 4294967295, 4294967295, 4294967295, True{}),
   check(max_nat(), 0, 0, 0, False{}),
   check(max_nat(), 0, 0, 0, True{}),
   check(max_nat(), 0, 0, 1, False{}),
   check(max_nat(), 0, 0, 1, True{}),
   check(max_nat(), 0, 0, 4294967295, False{}),
   check(max_nat(), 0, 0, 4294967295, True{}),
   check(max_nat(), 0, 4294967295, 0, False{}),
   check(max_nat(), 0, 4294967295, 0, True{}),
   check(max_nat(), 0, 4294967295, 1, False{}),
   check(max_nat(), 0, 4294967295, 1, True{}),
   check(max_nat(), 0, 4294967295, 4294967295, False{}),
   check(max_nat(), 0, 4294967295, 4294967295, True{}),
   check(max_nat(), 1, 0, 0, False{}),
   check(max_nat(), 1, 0, 0, True{}),
   check(max_nat(), 1, 0, 1, False{}),
   check(max_nat(), 1, 0, 1, True{}),
   check(max_nat(), 1, 0, 4294967295, False{}),
   check(max_nat(), 1, 0, 4294967295, True{}),
   check(max_nat(), 1, 4294967295, 0, False{}),
   check(max_nat(), 1, 4294967295, 0, True{}),
   check(max_nat(), 1, 4294967295, 1, False{}),
   check(max_nat(), 1, 4294967295, 1, True{}),
   check(max_nat(), 1, 4294967295, 4294967295, False{}),
   check(max_nat(), 1, 4294967295, 4294967295, True{}),
   check(max_nat(), 4294967295, 0, 0, False{}),
   check(max_nat(), 4294967295, 0, 0, True{}),
   check(max_nat(), 4294967295, 0, 1, False{}),
   check(max_nat(), 4294967295, 0, 1, True{}),
   check(max_nat(), 4294967295, 0, 4294967295, False{}),
   check(max_nat(), 4294967295, 0, 4294967295, True{}),
   check(max_nat(), 4294967295, 4294967295, 0, False{}),
   check(max_nat(), 4294967295, 4294967295, 0, True{}),
   check(max_nat(), 4294967295, 4294967295, 1, False{}),
   check(max_nat(), 4294967295, 4294967295, 1, True{}),
   check(max_nat(), 4294967295, 4294967295, 4294967295, False{}),
   check(max_nat(), 4294967295, 4294967295, 4294967295, True{})]
#|[True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}, True{}]
