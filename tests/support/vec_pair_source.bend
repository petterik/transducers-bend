import Base
import ../../transduce.bend as T

type PairSource is Type:
  PairSource{first: U32, second: U32}

def example() -> PairSource:
  PairSource{3, 4}

def after_first(~R: Type, ~r: T.Reducer<U32, R>,
  second: U32, control: T.Control<T.State(U32, R, r)>) ->
  T.Control<T.State(U32, R, r)>:
  match control:
    case T.Stop{state}:
      T.Stop{state}
    case T.Continue{state}:
      T.step(U32, R, r, state, second)

def drive_started(~R: Type, ~r: T.Reducer<U32, R>,
  first: U32, second: U32,
  control: T.Control<T.State(U32, R, r)>) ->
  T.Control<T.State(U32, R, r)>:
  match control:
    case T.Stop{state}:
      T.Stop{state}
    case T.Continue{state}:
      after_first(~R, ~r, second, T.step(U32, R, r, state, first))

def drive(~R: Type, ~r: T.Reducer<U32, R>,
  source: PairSource, control: T.Control<T.State(U32, R, r)>) ->
  T.Control<T.State(U32, R, r)>:
  match source:
    case PairSource{first, second}:
      drive_started(~R, ~r, first, second, control)

def PairSource.source(source: PairSource) ->
  T.Source<U32, PairSource, (R => r => v => c => drive(~R, ~r, v, c))>:
  T.Source{source}
