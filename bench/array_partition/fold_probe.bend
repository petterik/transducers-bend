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

# Handwritten control with the same materialized, ordered List chunks as
# partition_all. This isolates reducer/composition overhead from chunk storage
# and traversal costs.
def materialized_fold_loop(xs: List<U32>, +width: Nat, budget: Nat,
  left: Nat, items: List<U32>, +total: U32) -> U32:
  match xs budget left:
    case xs 0n left:
      total
    case Nil{} budget left:
      (total + sum_list(List.reverse(&1, U32, items), 0) : U32)
    case h <> t 1n+b 0n:
      total
    case h <> t 1n+b 1n:
      next_items : List<U32> = h <> items
      chunk_sum = sum_list(List.reverse(&1, U32, next_items), 0)
      materialized_fold_loop(t, width, b, width, [],
        (total + chunk_sum : U32))
    case h <> t 1n+b 1n+1n+q:
      materialized_fold_loop(t, width, 1n+b, 1n+q, h <> items, total)

def materialized_fold(+width: Nat, budget: Nat, xs: List<U32>) -> U32:
  materialized_fold_loop(xs, width, budget, width, [], 0)

# Order-sensitive consumer used as a second timed workload. It rolls each
# emitted group's values into one hash in encounter order.
def hash_values(xs: List<U32>, +hash: U32) -> U32:
  match xs:
    case Nil{}:
      hash
    case x <> rest:
      hash_values(rest, (((hash * 33 : U32) + x + 1 : U32)))

def hash_list_chunk(total: U32, xs: List<U32>) -> U32:
  hash_values(xs, total)

def list_hash_fold(width: Nat, budget: Nat, xs: List<U32>) -> U32:
  T.transduce(~T.over_list(~U32, ~U32,
    ~T.partition_all(~U32, ~U32,
      ~T.take(~List<U32>, ~U32,
        ~T.reducing(~List<U32>, ~U32, ~U32,
          ~hash_list_chunk, ~(s => s))))),
    (width, (budget, 0)), xs)

def materialized_hash_loop(xs: List<U32>, +width: Nat, budget: Nat,
  left: Nat, items: List<U32>, +total: U32) -> U32:
  match xs budget left items:
    case xs 0n left items:
      total
    case Nil{} budget left items:
      hash_values(List.reverse(&1, U32, items), total)
    case h <> t 1n+b 0n items:
      total
    case h <> t 1n+b 1n items:
      next_items : List<U32> = h <> items
      next_total = hash_values(List.reverse(&1, U32, next_items), total)
      materialized_hash_loop(t, width, b, width, [], next_total)
    case +h <> t 1n+b 1n+1n+q items:
      materialized_hash_loop(t, width, 1n+b, 1n+q, h <> items, total)

def materialized_hash_fold(+width: Nat, budget: Nat, xs: List<U32>) -> U32:
  materialized_hash_loop(xs, width, budget, width, [], 0)

def direct_hash_loop(xs: List<U32>, +width: Nat, budget: Nat,
  left: Nat, +total: U32) -> U32:
  match xs budget left:
    case xs 0n left:
      total
    case Nil{} budget left:
      total
    case h <> t 1n+b 0n:
      total
    case h <> t 1n+b 1n:
      direct_hash_loop(t, width, b, width,
        (((total * 33 : U32) + h + 1 : U32)))
    case h <> t 1n+b 1n+1n+q:
      direct_hash_loop(t, width, 1n+b, 1n+q,
        (((total * 33 : U32) + h + 1 : U32)))

def direct_hash_fold(+width: Nat, budget: Nat, xs: List<U32>) -> U32:
  direct_hash_loop(xs, width, budget, width, 0)

def same_three(a: U32, b: U32, +c: U32) -> Bool:
  Bool.and(U32.is_eq(a, c), U32.is_eq(b, c))

def order_probe_case(+width: Nat, +budget: Nat, +input_items: Nat) -> Bool:
  same_three(list_hash_fold(width, budget, P.numbers(input_items, [])),
    materialized_hash_fold(width, budget, P.numbers(input_items, [])),
    direct_hash_fold(width, budget, P.numbers(input_items, [])))

def add_array_chunk(total: U32, chunk: P.ArrayChunk) -> U32:
  (total + P.array_chunk_sum(chunk) : U32)

def add_array_chunk_two_phase(total: U32, chunk: P.ArrayChunk) -> U32:
  (total + P.array_chunk_sum_two_phase(chunk) : U32)

def array_fold(width: Nat, depth: Nat, budget: Nat, xs: List<U32>) -> U32:
  T.transduce(~T.over_list(~U32, ~U32,
    ~P.partition_array(~U32,
      ~T.take(~P.ArrayChunk, ~U32,
        ~T.reducing(~P.ArrayChunk, ~U32, ~U32, ~add_array_chunk, ~(s => s))))),
    (width, (depth, (budget, 0))), xs)

def array_fold_two_phase(width: Nat, depth: Nat, budget: Nat,
  xs: List<U32>) -> U32:
  T.transduce(~T.over_list(~U32, ~U32,
    ~P.partition_array(~U32,
      ~T.take(~P.ArrayChunk, ~U32,
        ~T.reducing(~P.ArrayChunk, ~U32, ~U32,
          ~add_array_chunk_two_phase, ~(s => s))))),
    (width, (depth, (budget, 0))), xs)

def direct_fold_loop(xs: List<U32>, +width: Nat, budget: Nat,
  left: Nat, +group_total: U32, +total: U32) -> U32:
  match xs budget left:
    case xs 0n left:
      total
    case xs budget 0n:
      total
    case Nil{} budget left:
      (total + group_total : U32)
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

def same_five(a: U32, b: U32, c: U32, d: U32, +direct: U32) -> Bool:
  Bool.and(U32.is_eq(a, direct),
    Bool.and(U32.is_eq(b, direct),
      Bool.and(U32.is_eq(c, direct), U32.is_eq(d, direct))))

def probe_case(+width: Nat, +depth: Nat, +budget: Nat,
  +input_items: Nat) -> Bool:
  same_five(list_fold(width, budget, P.numbers(input_items, [])),
    array_fold_two_phase(width, depth, budget, P.numbers(input_items, [])),
    array_fold(width, depth, budget, P.numbers(input_items, [])),
    materialized_fold(width, budget, P.numbers(input_items, [])),
    direct_fold(width, budget, P.numbers(input_items, [])))

def main() -> List<Bool>:
  [probe_case(1n, 0n, 96n, 96n), probe_case(2n, 1n, 48n, 96n),
   probe_case(3n, 2n, 32n, 96n), probe_case(8n, 3n, 12n, 96n),
   probe_case(1n, 0n, 2n, 96n), probe_case(2n, 1n, 2n, 96n),
   probe_case(3n, 2n, 2n, 96n), probe_case(8n, 3n, 2n, 96n),
   probe_case(2n, 1n, 49n, 97n), probe_case(3n, 2n, 34n, 101n),
   probe_case(8n, 3n, 13n, 97n),
   order_probe_case(3n, 32n, 96n), order_probe_case(3n, 2n, 96n),
   order_probe_case(3n, 34n, 101n), order_probe_case(8n, 12n, 96n),
   order_probe_case(8n, 2n, 96n), order_probe_case(8n, 13n, 97n)]
