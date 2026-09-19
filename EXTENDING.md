# Adding a reducible source

A source owns its traversal. The library owns reducer initialization and completion. Sources are selected explicitly at compile time; data, bounds, and reducer configuration remain runtime values. There is no registry, closed source enum, or requirement to edit `transduce.bend`.

## Implement a stopping fold

The convention is:

```python
def reduce(~A: Type, ~S: Type, ~advance: S -> A -> T.Control<S>,
  source: YourType<A>, control: T.Control<S>) -> T.Control<S>:
  # Traverse source in the documented order.
```

`advance` is closed template code, not a repeatedly called affine runtime closure. `S` and `A` may both be affine. The fold must:

1. Return initially stopped control without calling advance.
2. Feed elements in its documented order, once each, until exhaustion or Stop.
3. Return the exact owned state from advance, preserving Stop. Never call advance after Stop.
4. On empty/exhausted input, return the current control unchanged.
5. Neither initialize nor complete the reducer. Never drop an intermediate state and replace it with a fresh one.
6. Terminate using a decreasing structural input or a justified finite budget. Do not precompute a list or its length merely to fit a generic loop.

Unused owned source data may still require cleanup after Stop. The pure-source contract does not define resource-owning IO cleanup or resumable remainders. Parallel traversal needs additional ordering, combination, and stopping semantics.

## Bind it to a reducer

Here is the actual binding adapter from [examples/tree.bend](examples/tree.bend):

```python
def over_tree(~A: Type, ~R: Type, ~r: T.Reducer<A, R>) -> T.Reduction:
  T.reducible(~Tree<A>, ~A, ~R, ~(u => r),
    ~(xs => c => reduce(~A, ~T.State(A, R, r),
      ~(s => x => T.step(A, R, r, s, x)), xs, c)))
```

The first argument describes the source input type, followed by its element and result types. `~(u => r)` delays the closed reducer description; it is compile-time code, not a reusable runtime closure. The final argument supplies the bound fold. `reducible` installs initialization and completion around that fold. Use this helper instead of constructing a `Reduction` record directly.

The delay avoids repeatedly evaluating the same reducer description at nested binding boundaries in the fork's bounded specialization pass. Internally, type metadata is delayed too. These are representation details encapsulated by the adapter; callers supply their pipeline only once:

```python
import Base
import ./transduce.bend as T
import ./examples/tree.bend as Tree

def main() -> U32:
  T.transduce(~Tree.over_tree(~U32, ~U32, ~T.sum()),
    0, Tree.Branch{Tree.Leaf{1}, Tree.Leaf{2}})
# 3
```

Built-in bindings follow exactly this pattern: `over_list`, `over_range`, and `over_string`. For a non-generic source, fix its element type inside the adapter. Strings use Char, ranges use U32. The `Reduction` description supplies the configuration/input/output types, so callers do not repeat them as separate arguments to `transduce`.

This is explicit static dispatch, not automatic trait resolution. Runtime selection between different source representations needs a user-defined wrapper and its own fold, or a branch selecting the appropriate call. No new language or compiler change is required for an extension.

## Run the conformance checks

[tests/support/source_contract.bend](tests/support/source_contract.bend) provides a reusable test helper. Supply your fold specialized to its `Trace` state, a fresh source yielding `[1,2,3]`, and a fresh empty source. It checks initial Stop, stopping after one/two elements, encounter order, full exhaustion, and empty input with either control state. A step after a step-generated Stop produces a sentinel failure. See [tests/source_contract.bend](tests/source_contract.bend) for all four source implementations using the same suite.

Also test your representation's particular obligations: affine inputs/state, numeric boundaries, traversal order, and cleanup expectations. [tests/extensions.bend](tests/extensions.bend) exercises the external tree with affine function values. [tests/lifecycle.bend](tests/lifecycle.bend) checks initialization/completion across list, range, string, and tree; JS instrumentation observes 12 starts, 8 steps, and 12 finishes.

Run `python3 tests/run.py` from the repository root. The runner uses the sibling fork at `../bend/bend2/main.ts` and checks JS plus native CPU. Representative library and extension fixtures assert that generated JS contains neither Reducer nor Reduction records. This is a code-generation check, not a universal guarantee: large expressions or unsupported callback shapes can exceed specialization's limits. In custom `Reducer` constructors, explicit forwarding lambdas around pattern-matching callbacks let the current pass resolve callable heads; the lifecycle fixture demonstrates this form.

The contract is a documented obligation, not a proof imposed by the type of an arbitrary third-party fold. [LAWS.md](LAWS.md) distinguishes executable evidence from outstanding formal proofs.
