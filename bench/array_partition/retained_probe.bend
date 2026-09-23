import Base
import ../../transduce.bend as T
import ./semantic_probe.bend as P

type RetainedStats is Type:
  RetainedStats{groups: Nat, total: U32}

def list_groups_stats(groups: List<List<U32>>, +count: Nat,
  +total: U32) -> RetainedStats:
  match groups:
    case Nil{}:
      RetainedStats{count, total}
    case group <> rest:
      list_groups_stats(rest, Nat.add(count, 1n),
        (total + P.sum_values_loop(group, 0) : U32))

def array_groups_stats(groups: List<P.ArrayChunk>, +count: Nat,
  +total: U32) -> RetainedStats:
  match groups:
    case Nil{}:
      RetainedStats{count, total}
    case group <> rest:
      array_groups_stats(rest, Nat.add(count, 1n),
        (total + P.array_chunk_sum(group) : U32))

def list_retain(width: Nat, xs: List<U32>) -> RetainedStats:
  groups = T.transduce(~T.over_list(~U32, ~List<List<U32>>,
    ~T.partition_all(~U32, ~List<List<U32>>,
      ~T.into_list(~List<U32>))), (width, Unit{}), xs)
  list_groups_stats(groups, 0n, 0)

def array_retain(width: Nat, depth: Nat, xs: List<U32>) -> RetainedStats:
  groups = T.transduce(~T.over_list(~U32, ~List<P.ArrayChunk>,
    ~P.partition_array(~List<P.ArrayChunk>, ~T.into_list(~P.ArrayChunk))),
    (width, (depth, Unit{})), xs)
  array_groups_stats(groups, 0n, 0)

def stats_match(stats: RetainedStats, expected_groups: Nat,
  expected_total: U32) -> Bool:
  match stats:
    case RetainedStats{groups, total}:
      Bool.and(Nat.is_eq(groups, expected_groups),
        U32.is_eq(total, expected_total))

def case_ok(+width: Nat, +depth: Nat, +expected_groups: Nat) -> Bool:
  +expected_total = P.sum_values_loop(P.numbers(97n, []), 0)
  Bool.and(
    stats_match(list_retain(width, P.numbers(97n, [])), expected_groups,
      expected_total),
    stats_match(array_retain(width, depth, P.numbers(97n, [])),
      expected_groups, expected_total))

def main() -> List<Bool>:
  [case_ok(1n, 0n, 97n), case_ok(2n, 1n, 49n),
   case_ok(3n, 2n, 33n), case_ok(8n, 3n, 13n)]
