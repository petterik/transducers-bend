---
created_at: 2026-09-20T22:35:00+02:00
status: current
---

# Configured composition checkpoint

The existing API fixture remains the successful baseline: one type-changing
`keep` declaration is reused with `count` and `into_list` over range, list, and
the independent tree source. The reducer description is static and the
consumer configuration is fresh on every call. That closes the semantic part
of the configured API work, but callers still construct the reducer's dependent
configuration explicitly when a pipeline contains `filter`, `take`, or other
configured stages.

## Target call shape

The desired shape is a pipeline-specific settings value whose fields describe
the public choices, while the pipeline hides its internal nested configuration:

```text
settings = PipelineSettings{threshold, limit}
pipeline_config(settings, downstream_config)
transduce(over_list(pipeline), pipeline_config, source)
```

The settings record must remain ordinary runtime data. The downstream
configuration must remain separate from the fresh reducer state, so a single
description can run with a scalar consumer and a collection consumer.

## What the language currently permits

The direct nested pipeline works and is the current public form:

```bend
def pipeline(~R: Type, ~down: T.Reducer<Nat, R>) -> T.Reducer<U32, R>:
  T.filter(~U32, ~R, ~U32, ~above,
    ~T.keep(~U32, ~Nat, ~R, ~to_nat,
      ~T.take(~Nat, ~R, ~down)))
```

The first generic composition attempt used a transformation value:

```bend
def comp(~A: Type, ~B: Type, ~C: Type, ~R: Type,
  ~outer: T.Reducer<B, R> -> T.Reducer<A, R>,
  ~inner: T.Reducer<C, R> -> T.Reducer<B, R>,
  ~down: T.Reducer<C, R>) -> T.Reducer<A, R>:
  outer(inner(down))
```

Passing a lambda that calls `T.map` or `T.cat_maybe` fails before lowering:

```text
a template applied to closed ~ arguments (a def parameter is not comptime)
```

The lambda's downstream parameter is a runtime binder, so it cannot be passed
as the closed `~down` argument required by the existing reducer templates. A
runtime stage object or a compiler registry would hide this boundary, but would
give up the static composition property that makes the current library fast.

A second probe packaged `threshold`, `limit`, and a downstream configuration in
a `Data` record and returned `U32 & (Nat & R)`. Ordinary functions returning that
pair type work when their fields are supplied directly. When a function first
matches a runtime settings record and its result is supplied as a transducer
configuration, the current checker rejects the dependent pair at the call site
with an `expected Nat / observed U32` mismatch. The sibling compiler produces
the same diagnostic. This is a type-elaboration boundary, not evidence that a
runtime record should be added without a proof of its dependent field order.

## Decision

Keep the reducer protocol and explicit tuple configuration while the compiler
work focuses on static facts and local representation. Do not add a generic
`comp` interpreter, a closed list of named stages, or a second production
implementation of every adapter. An application may define a concrete settings
record and a wrapper when its downstream configuration is known; that wrapper
must be tested with both scalar and collection consumers before it becomes a
library recommendation.

The next API work is therefore a small language/library experiment, not a
performance claim:

1. Define a concrete pipeline settings record and a reducer wrapper whose
   configuration type is a named constructor rather than a dependent pair.
2. Prove start, step, finish, fresh state, and stopping for `count`, `into_list`,
   and a scalar consumer.
3. Repeat the extension parity matrix and inspect generated JS/native code.
4. Only then decide whether Bend needs better dependent-record construction or
   a higher-rank static transformation parameter.

Until that experiment passes, result-type and configuration repetition are an
explicit language limitation recorded in
[`ERGONOMICS.md`](../foundation/ERGONOMICS.md), rather than an optimizer
workaround or a reason to change the reducer semantics.
