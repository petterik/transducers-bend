---
created_at: 2026-09-19T22:09:39+02:00
status: foundation
---

# Deferred transduce ergonomics

September 19 scope: Clojure illustrates clarity, not required syntax. The target
is immediate `transduce` with statically known operations. Arbitrary runtime
captures, eduction, lazy sequence production and a generic `conj` interface are
not goals. Fusion takes priority; see [the strategy](../archive/20260919-FUSION.md).

## What should become simpler

Users should specify the transformation order, operation arguments, consumer and
source. They should not repeatedly specify the final result type at every stage
or manually reconstruct internal configuration tuples.

A transformation should be describable independently of the final reducer, even
if its representation remains a closed template rather than a runtime value.
Named reusable definitions are sufficient; first-class runtime pipeline objects
and dynamic stage selection are not requirements.

## Candidate approach to test later

1. Package input/output type information with a static transformation description.
   The current Reduction description already demonstrates deriving types from
   one description; investigate the same principle for transformations.
2. Provide static composition that checks adjacent element types and derives
   the full reducer lifecycle once a consumer is supplied. Hide the consumer's
   result type inside that application where Bend permits it.
3. Keep closed callback code separate from ordinary runtime settings. If settings
   remain necessary, offer named configuration construction or a typed package
   so the caller does not maintain a positional nested tuple. This does not
   require arbitrary closure capture. Literal static settings can be simpler.
4. Keep source selection explicit if necessary. A small amount of honest explicit
   source/type syntax is preferable to a new trait system solely for this library.
5. Keep every description static enough to disappear under specialization. Do
   not trade the established fusion path for an unmeasured runtime builder.

These are representation candidates, not verified Bend signatures. A minimal
prototype must establish what can be derived library-side before requesting
language changes. General inference is not a dependency; targeted implicit type
arguments could remove remaining repetition later if the language supports them.

## Acceptance example

Express a closed map, closed filter and take count as one composition, and apply
it with two different consumers without restating its stages or their result
types. Include a type-changing map and a runtime count to distinguish actual
genericity from a U32-only convenience wrapper. Confirm fresh state per execution,
correct stage order and stopping, and unchanged generated hot-loop behavior.

This does not require retaining a source or input elements between executions.
Counter state and the consumer accumulator remain compatible with the scope.
Element-buffering additions and borrowed-source API design can be considered
separately if a concrete need arises. Existing public consumers need not be
removed merely because no new generic collection interface is planned.
