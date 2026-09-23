import Base
import ../../transduce.bend as T
import ./semantic_probe.bend as P

def sum_list(xs: List<U32>, +total: U32) -> U32:
  match xs:
    case Nil{}:
      total
    case x <> rest:
      sum_list(rest, (total + x : U32))

def add_list_chunk(total: U32, xs: List<U32>) -> U32:
  (total + sum_list(xs, 0) : U32)

def list_fold(width: Nat, budget: Nat, xs: List<U32>) -> U32:
  T.transduce(~T.over_list(~U32, ~U32,
    ~T.partition_all(~U32, ~U32,
      ~T.take(~List<U32>, ~U32,
        ~T.reducing(~List<U32>, ~U32, ~U32, ~add_list_chunk, ~(s => s))))),
    (width, (budget, 0)), xs)

def add_array_chunk(total: U32, chunk: P.ArrayChunk) -> U32:
  (total + P.array_chunk_sum(chunk) : U32)

def array_fold(width: Nat, depth: Nat, budget: Nat, xs: List<U32>) -> U32:
  T.transduce(~T.over_list(~U32, ~U32,
    ~P.partition_array(~U32,
      ~T.take(~P.ArrayChunk, ~U32,
        ~T.reducing(~P.ArrayChunk, ~U32, ~U32, ~add_array_chunk, ~(s => s))))),
    (width, (depth, (budget, 0))), xs)

def direct_fold_loop(xs: List<U32>, +width: Nat, budget: Nat,
  left: Nat, +group_total: U32, +total: U32) -> U32:
  match xs budget left:
    case xs 0n left:
      total
    case xs budget 0n:
      total
    case Nil{} budget left:
      total
    case h <> t 1n+b 1n+p:
      match p:
        case 0n:
          direct_fold_loop(t, width, b, width, 0,
            (total + group_total + h : U32))
        case 1n+q:
          direct_fold_loop(t, width, 1n+b, 1n+q,
            (group_total + h : U32), total)

def direct_fold(+width: Nat, budget: Nat, xs: List<U32>) -> U32:
  direct_fold_loop(xs, width, budget, width, 0, 0)

def same_three(a: U32, b: U32, +direct: U32) -> Bool:
  Bool.and(U32.is_eq(a, direct), U32.is_eq(b, direct))

def probe_case(+width: Nat, depth: Nat, +budget: Nat) -> Bool:
  same_three(list_fold(width, budget, P.numbers(96n, [])),
    array_fold(width, depth, budget, P.numbers(96n, [])),
    direct_fold(width, budget, P.numbers(96n, [])))

def main() -> List<Bool>:
  [probe_case(1n, 0n, 96n), probe_case(2n, 1n, 48n),
   probe_case(3n, 2n, 32n), probe_case(8n, 3n, 12n),
   probe_case(1n, 0n, 2n), probe_case(2n, 1n, 2n),
   probe_case(3n, 2n, 2n), probe_case(8n, 3n, 2n)]
