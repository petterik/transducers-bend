# Bounded exhaustive checks, not proofs. All five coordinates range over 0..4.
import Base
import ../transduce.bend as T

def same(xs: List<U32>, ys: List<U32>) -> Bool:
  match xs ys:
    case Nil{} Nil{}:
      True{}
    case Nil{} h <> t:
      False{}
    case h <> t Nil{}:
      False{}
    case x <> xt y <> yt:
      Bool.and(U32.is_eq(x, y), same(xt, yt))

# Independent reference: construct [0, end), then drop begin elements.
def ascending(+n: Nat, acc: List<U32>) -> List<U32>:
  match n:
    case 0n:
      acc
    case 1n+p:
      ascending(p, U32.from_nat(p) <> acc)

def reference(begin: Nat, end: Nat) -> List<U32>:
  List.drop(&1, U32, ascending(end, []), begin)

def above(t: U32, x: U32) -> Bool:
  U32.is_gt(x, t)

def inc(x: U32) -> U32:
  (x + 1 : U32)

def twice(x: U32) -> U32:
  (x * 2 : U32)

def pipeline(~R: Type, ~down: T.Reducer<U32, R>) -> T.Reducer<U32, R>:
  T.map(~U32, ~U32, ~R, ~inc,
    ~T.filter(~U32, ~R, ~U32, ~above, ~T.take(~U32, ~R, ~down)))

def ordered(+begin: Nat, +end: Nat, +threshold: U32, +n: Nat) -> Bool:
  same(
    T.transduce(~T.over_range(~List<U32>, ~pipeline(~List<U32>, ~T.into_list(~U32))), (threshold, (n, Unit{})), T.range_between(U32.from_nat(begin), U32.from_nat(end))),
    T.transduce(~T.over_list(~U32, ~List<U32>, ~pipeline(~List<U32>, ~T.into_list(~U32))), (threshold, (n, Unit{})), reference(begin, end)))

def scalar(+begin: Nat, +end: Nat, +threshold: U32, +n: Nat) -> Bool:
  U32.is_eq(
    T.transduce(~T.over_range(~U32, ~pipeline(~U32, ~T.sum())), (threshold, (n, 0)), T.range_between(U32.from_nat(begin), U32.from_nat(end))),
    T.transduce(~T.over_list(~U32, ~U32, ~pipeline(~U32, ~T.sum())), (threshold, (n, 0)), reference(begin, end)))

def counted(+begin: Nat, +end: Nat, +threshold: U32, +n: Nat) -> Bool:
  Nat.is_eq(
    T.transduce(~T.over_range(~Nat, ~pipeline(~Nat, ~T.count(~U32))), (threshold, (n, Unit{})), T.range_between(U32.from_nat(begin), U32.from_nat(end))),
    List.length(&1, U32,
      T.transduce(~T.over_list(~U32, ~List<U32>, ~pipeline(~List<U32>, ~T.into_list(~U32))), (threshold, (n, Unit{})), reference(begin, end))))

def identity_law(+begin: Nat, +end: Nat) -> Bool:
  same(T.transduce(~T.over_range(~List<U32>, ~T.identity(~U32, ~List<U32>, ~T.into_list(~U32))), Unit{}, T.range_between(U32.from_nat(begin), U32.from_nat(end))), reference(begin, end))

def map_law(+begin: Nat, +end: Nat) -> Bool:
  same(
    T.transduce(~T.over_range(~List<U32>, ~T.map(~U32, ~U32, ~List<U32>, ~inc,
        ~T.map(~U32, ~U32, ~List<U32>, ~twice, ~T.into_list(~U32)))), Unit{}, T.range_between(U32.from_nat(begin), U32.from_nat(end))),
    T.transduce(~T.over_range(~List<U32>, ~T.map(~U32, ~U32, ~List<U32>, ~(x => twice(inc(x))), ~T.into_list(~U32))), Unit{}, T.range_between(U32.from_nat(begin), U32.from_nat(end))))

def take_law(+begin: Nat, +end: Nat, +n: Nat, +m: Nat) -> Bool:
  same(
    T.transduce(~T.over_range(~List<U32>, ~T.take(~U32, ~List<U32>, ~T.take(~U32, ~List<U32>, ~T.into_list(~U32)))), (n, (m, Unit{})), T.range_between(U32.from_nat(begin), U32.from_nat(end))),
    T.transduce(~T.over_range(~List<U32>, ~T.take(~U32, ~List<U32>, ~T.into_list(~U32))), (Nat.min(n, m), Unit{}), T.range_between(U32.from_nat(begin), U32.from_nat(end))))

def failure(ok: Bool) -> Nat:
  match ok:
    case True{}:
      0n
    case False{}:
      1n

def check(+begin: Nat, +end: Nat, +threshold: Nat, +n: Nat, +m: Nat) -> Nat:
  Nat.add(failure(ordered(begin, end, U32.from_nat(threshold), n)),
  Nat.add(failure(scalar(begin, end, U32.from_nat(threshold), n)),
  Nat.add(failure(counted(begin, end, U32.from_nat(threshold), n)),
  Nat.add(failure(identity_law(begin, end)),
  Nat.add(failure(map_law(begin, end)), failure(take_law(begin, end, n, m)))))))

# Enumerate a base-five tuple. This executes 3125 cases and 18750 checks.
def sweep(+fuel: Nat, acc: Nat) -> Nat:
  match fuel:
    case 0n:
      acc
    case 1n+p:
      sweep(p, Nat.add(acc, check(Nat.div(p, 625n), Nat.mod(Nat.div(p, 125n), 5n),
        Nat.mod(Nat.div(p, 25n), 5n), Nat.mod(Nat.div(p, 5n), 5n), Nat.mod(p, 5n))))

def main() -> Nat:
  sweep(3125n, 0n)
#|0n
