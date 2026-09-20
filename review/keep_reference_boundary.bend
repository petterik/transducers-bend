import Base
import ../transduce.bend as T

def build(+n: Nat, xs: List<U32>) -> List<U32>:
  match n:
    case 0n:
      xs
    case 1n+p:
      build(p, U32.from_nat(p) <> xs)

def is_zero(x: U32) -> Bool:
  U32.is_zero(x)

def maybe_keep_bool(z: Bool) -> Maybe<U32>:
  match z:
    case True{}:
      None{}
    case False{}:
      Some{1}

def maybe_keep(x: U32) -> Maybe<U32>:
  maybe_keep_bool(is_zero(x))

def keep_pipeline() -> T.Reducer<U32, U32>:
  T.keep(~U32, ~U32, ~U32, ~maybe_keep,
    ~T.take(~U32, ~U32, ~T.sum()))

def keep_direct_step(xs: List<U32>, m: Maybe<U32>, +left: Nat,
  acc: U32) -> U32:
  match xs m left:
    case Nil{} None{} 0n:
      acc
    case Nil{} Some{value} 0n:
      (acc + value : U32)
    case Nil{} None{} 1n+p:
      acc
    case Nil{} Some{value} 1n+p:
      (acc + value : U32)
    case h <> t None{} 0n:
      acc
    case h <> t Some{value} 0n:
      (acc + value : U32)
    case h <> t None{} 1n+p:
      keep_direct_step(t, maybe_keep(h), 1n+p, acc)
    case h <> t Some{value} 1n+p:
      keep_direct_step(t, maybe_keep(h), p, (acc + value : U32))

def keep_direct(xs: List<U32>, +left: Nat, acc: U32) -> U32:
  match xs left:
    case xs 0n:
      acc
    case Nil{} 1n+p:
      acc
    case h <> t 1n+p:
      keep_direct_step(t, maybe_keep(h), p, acc)

def main() -> IO(Unit):
  do IO<Unit>:
    IO.print(U32.show(keep_direct(build(5n, []), 1n, 0)))
    IO.print(U32.show(T.transduce(~T.over_list(~U32, ~U32, ~keep_pipeline()), (1n, 0), build(5n, []))))
#|0
#|1
