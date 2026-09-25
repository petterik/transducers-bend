---
created_at: 2026-09-20T22:35:00+02:00
status: current
---

# Configured composition checkpoint

The concrete named-settings experiment now passes. A pipeline can expose one
runtime settings value while keeping the selected consumer's configuration
separate and typed. The fixture is
[`tests/configured_pipeline.bend`](../../tests/configured_pipeline.bend).

## The public shape

The experiment declares the settings once:

```bend
type PipelineSettings is Data:
  PipelineSettings{threshold: U32, limit: Nat, width: Nat}

type PipelineConfig<-D: Type> is Type:
  PipelineConfig{settings: PipelineSettings, consumer: D}
```

The wrapper's reducer configuration is `PipelineConfig<D>`, where `D` is the
selected downstream configuration type. At initialization it matches the
named settings and translates them into the private tuple expected by the
existing stages:

```text
PipelineConfig{settings, consumer}
  -> (threshold, (limit, (width, consumer)))
```

The concrete pipeline is configured filter → type-changing keep → take →
partition. Step and finish delegate to that already-declared reducer. The
translation happens once at start; settings are not interpreted on every
element.

The same pipeline declaration is exercised with:

- a count consumer, which returns the number of groups;
- an ordered group collector, which observes the partial final group;
- a `U32` sum consumer whose initial value is a non-`Unit` configuration;
- the built-in List and range sources and the independent tree source;
- an initial downstream `Stop`; and
- two consecutive runs with fresh reducer state.

The contained facts compiler and the unchanged sibling compiler both produce
the same seven-line result:

```text
2
[[2, 3, 4], [5]]
14
2
1
0
[2, 2]
```

This resolves the feasibility question: a concrete application wrapper can
hide the nested configuration without changing reducer semantics or requiring
a runtime stage registry.

## What remains deliberately open

This is a feasibility pattern, not a new generic library abstraction. The
wrapper still names the internal stage order and writes the one-time tuple
translation by hand. A generic `comp` interpreter, runtime stage registry, or
compiler list of named stages would sacrifice the static composition property
that currently enables fusion, so none is introduced from this experiment.

The named wrapper also remains a more difficult compiler shape than a closed
pipeline: generated JS for the fixture still contains reducer records. The
fixture is therefore a semantic API checkpoint, not a performance or
allocation claim. Before recommending this pattern broadly, measure it with
the paired parity harness and decide whether the compiler should learn a
specific initialization-boundary fact or Bend needs richer static composition.

The earlier generic-composition and dependent-pair probes remain useful
language-limit cases. Passing a concrete wrapper does not prove that Bend can
derive the wrapper automatically. The next design decision is whether the
repeated handwritten builder justifies a small static configuration-builder
feature; it should be driven by a second real pipeline and retained generated
code evidence.
