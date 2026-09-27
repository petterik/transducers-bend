import Base

def ready(state: U32) -> ArrayWalkCheck<U32>:
  ArrayWalkReady{state}

def add(state: U32, value: U32) -> U32:
  U32.add(state, value)

def folded() -> U32:
  Array.walk(~U32, ~U32, ~add, ~ready,
    Array.new(U32, 10n, 1), 0)

def combined() -> U32:
  a b = folded!() folded!()
  U32.add(a, b)

def main() -> IO(Unit):
  IO.print(U32.show(combined()))
#|2048
