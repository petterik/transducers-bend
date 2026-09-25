import Base
import ../../transduce_core.bend as T

type PairSource is Type:
  PairSource{first: U32, second: U32}

def example() -> PairSource:
  PairSource{3, 4}

def source_after_first(~K: Data, ~S: Type, ~advance: S -> U32 -> S,
  second: U32, checked: T.Checked<K, S>) -> S:
  match checked:
    case T.Halted{permit, s}:
      s
    case T.Ready{s}:
      advance(s, second)

def source_pair_checked(~K: Data, ~S: Type, ~advance: S -> U32 -> S,
  ~inspect: S -> T.Checked<K, S>, pair: PairSource,
  checked: T.Checked<K, S>) -> S:
  match pair checked:
    case PairSource{first, second} T.Halted{permit, s}:
      s
    case PairSource{first, second} T.Ready{s}:
      source_after_first(~K, ~S, ~advance, second,
        inspect(advance(s, first)))

def source_pair(~K: Data, ~S: Type, ~advance: S -> U32 -> S,
  ~inspect: S -> T.Checked<K, S>, pair: PairSource, s: S) -> S:
  source_pair_checked(~K, ~S, ~advance, ~inspect, pair, inspect(s))

def PairSource.source(source: PairSource) ->
  T.Source<U32, PairSource, (K => S => advance => inspect => v => s =>
    source_pair(~K, ~S, ~advance, ~inspect, v, s))>:
  T.Source{source}
