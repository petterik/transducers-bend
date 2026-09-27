import Base

type WalkPair is Data:
  WalkPair{left: U32, right: U32}

def always_ready(state: U32) -> ArrayWalkCheck<U32>:
  ArrayWalkReady{state}

def add_pair(acc: U32, value: WalkPair) -> U32:
  match value:
    case WalkPair{left, right}:
      U32.add(acc, U32.add(left, right))

def pair_sum() -> U32:
  Array.walk(~WalkPair, ~U32, ~add_pair, ~always_ready,
    Array.new(WalkPair, 2n, WalkPair{1, 2}), 0)

def add_string(acc: U32, value: String) -> U32:
  U32.add(acc, U32.from_nat(String.length(value)))

def string_sum() -> U32:
  Array.walk(~String, ~U32, ~add_string, ~always_ready,
    Array.new(String, 2n, "abc"), 0)

type Shared is Type:
  Shared{writer: Array<U32>, count: U32, sum: U32}

def shared_ready(state: Shared) -> ArrayWalkCheck<Shared>:
  ArrayWalkReady{state}

def shared_step(state: Shared, value: U32) -> Shared:
  match state:
    case Shared{writer, +count, sum}:
      Shared{Array.set(U32, writer, U32.inc(count), 7),
        U32.inc(count), U32.add(sum, value)}

def shared_result(state: Shared) -> U32:
  match state:
    case Shared{writer, count, sum}: sum

def shared_run(pair: Array<U32> & Array<U32>) -> U32:
  (reader, writer) = pair
  shared_result(Array.walk(~U32, ~Shared, ~shared_step, ~shared_ready,
    reader, Shared{writer, 0, 0}))

def shared_sum() -> U32:
  shared_run(Array.fork(U32, Array.new(U32, 2n, 1)))

def main() -> U32 & U32 & U32:
  (pair_sum(), string_sum(), shared_sum())
#|(12, 12, 22)
