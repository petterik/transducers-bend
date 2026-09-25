---
created_at: 2026-09-25T21:55:00+02:00
status: validated-locally
---

# Public transducer versus ordinary Bend List code

The release comparison must include the Bend code a user is likely to write:
`List.foldl(add, List.map(inc, xs), 0)`. The older map benchmark used the
explicit reducer API, so it cannot establish the current public API's cost.
[This fixture](../../bench/public_list_map_fold.bend) runs three equivalent
owned `List<U32>` computations: a handwritten fused fold, public
`X.transduce(X.map(inc), X.sum_rf(), 0, xs)`, and `Base.List.map` followed by
`Base.List.foldl`. All use `U32.inc` and `U32.add`; all return the same checked
sum. The input is built from a runtime size before the microsecond clock starts.

On this machine, 36 interleaved native runs per size, one Bend thread, GPU off,
and Clang `-O3` produced these medians:

| List length | Direct fused µs | Public transduce µs | List.map + foldl µs | Public/direct paired median |
| ---: | ---: | ---: | ---: | ---: |
| 4,096 | 4 | 4 | 16 | 1.00× |
| 65,536 | 65.5 | 69.5 | 235.5 | 1.02× |
| 262,144 | 440.5 | 447.5 | 1107.5 | 1.00× |

The generated C's timed `heap_alloc` call counts were nine for both direct and
public transduce at every size. `List.map + foldl` made one additional call per
input item (4,105, 65,545, and 262,153 respectively) to build the intermediate
mapped list. These counts are calls to Bend's native allocation helper, not
bytes or peak live memory. The checksum and allocation results establish fusion
for this simple map/fold pipeline. The timing is consistent with direct speed in
paired runs; it is not a promise of parity for every source or pipeline.

Timing noise is material: at length 262,144, individual direct runs ranged
174–556 µs and public runs 191–544 µs. The median of the per-session ratios
was 1.00× even though separate medians differ. Do not infer a stable 1–6%
public cost from these numbers. The independent Array no-stop comparison and
the Branch layout ablation give the broader fused-path evidence; see the
[integration report](20260925-NO-STOP-PUBLIC-INTEGRATION.md) and
[Branch reassessment](20260925-BRANCH-LAYOUT-REASSESSMENT.md).

This comparison does not cover retained output or buffered transformations.
`partition_all` creates ordered chunks, and a List-producing `mapcat` callback
creates its fragment before reduction. Their allocation costs need to be
documented on those transducers rather than hidden behind the scalar result.

Reproduce with `python3 bench/public_list_map_fold.py --sessions 36 --output
/tmp/public-list-map-fold.json` from the library root. The checked-in
[raw samples](../../bench/public-list-map-fold-20260925.json) include every
microsecond observation, checksum, paired ratio, allocation count, compiler
commit, and machine description. The fixture uses the `codex/transducer-no-stop`
compiler fork at `1b4f641b`.

To verify the release setup, I made fresh local clones of both repositories as
siblings, checked out the compiler branch at `1b4f641b`, and ran
`python3 tests/run.py`, `python3 tests/public_differential.py`, and
`bun experiments/affine_xf/check_no_stop_cache.ts` from the library clone.
They passed 47/47 JS/native fixtures, both 44-case differential suites, and
the separate-book constructor-cache check. This validates clean-checkout use
of the pinned branch; it does not establish compatibility with upstream Bend
or other compiler revisions.
