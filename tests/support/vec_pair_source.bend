import Base
import ../../transduce.bend as T

type PairSource is Type:
  PairSource{first: U32, second: U32}

def example() -> PairSource:
  PairSource{3, 4}

def source_after_first(~S: Type, ~advance: S -> U32 -> S,
  second: U32, checked: T.Checked<S>) -> S:
  match checked:
    case T.Halted{s}:
      s
    case T.Ready{s}:
      advance(s, second)

def source_pair_checked(~S: Type, ~advance: S -> U32 -> S,
  ~inspect: S -> T.Checked<S>, pair: PairSource,
  checked: T.Checked<S>) -> S:
  match pair checked:
    case PairSource{first, second} T.Halted{s}:
      s
    case PairSource{first, second} T.Ready{s}:
      source_after_first(~S, ~advance, second,
        inspect(advance(s, first)))

def source_pair(~S: Type, ~advance: S -> U32 -> S,
  ~inspect: S -> T.Checked<S>, pair: PairSource, s: S) -> S:
  source_pair_checked(~S, ~advance, ~inspect, pair, inspect(s))

def PairSource.source(source: PairSource) ->
  T.Source<U32, PairSource, (S => advance => inspect => v => s =>
    source_pair(~S, ~advance, ~inspect, v, s))>:
  T.Source{source}
