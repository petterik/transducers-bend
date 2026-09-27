import Base

type WalkTrace is Data:
  WalkTrace{steps: U32, checks: U32, sum: U32, limit: U32}

def values() -> Array<U32>:
  a = Array.set(U32, [0 : U32*4n], 0, 1)
  b = Array.set(U32, a, 1, 2)
  c = Array.set(U32, b, 2, 3)
  Array.set(U32, c, 3, 4)

def step(trace: WalkTrace, x: U32) -> WalkTrace:
  match trace:
    case WalkTrace{steps, checks, sum, limit}:
      WalkTrace{U32.inc(steps), checks, U32.add(sum, x), limit}

def choose(keep: Bool, trace: WalkTrace) -> ArrayWalkCheck<WalkTrace>:
  match keep:
    case True{}: ArrayWalkReady{trace}
    case False{}: ArrayWalkHalted{trace}

def inspect(trace: WalkTrace) -> ArrayWalkCheck<WalkTrace>:
  match trace:
    case WalkTrace{+steps, checks, sum, +limit}:
      choose(U32.is_lt(steps, limit),
        WalkTrace{steps, U32.inc(checks), sum, limit})

def result(trace: WalkTrace) -> U32 & U32 & U32:
  match trace:
    case WalkTrace{steps, checks, sum, limit}: (steps, checks, sum)

def trace_sum(trace: WalkTrace) -> U32:
  match trace:
    case WalkTrace{steps, checks, sum, limit}: sum

def run(limit: U32) -> U32 & U32 & U32:
  result(Array.walk(~U32, ~WalkTrace, ~step, ~inspect,
    values(), WalkTrace{0, 0, 0, limit}))

def one() -> U32:
  trace_sum(Array.walk(~U32, ~WalkTrace, ~step, ~inspect,
    Array.new(U32, 0n, 9), WalkTrace{0, 0, 0, 8}))

# Direct calls to the helper with an invalid span must retain Array.get's
# wraparound behavior rather than using the bounded native fast path.
def invalid_span() -> U32 & U32 & U32:
  result(Array.walk.loop(~U32, ~WalkTrace, ~step, ~inspect, 2n, 5,
    Array.walk.attach(~U32, ~WalkTrace,
      inspect(WalkTrace{0, 0, 0, 8}), values())))

def invalid_tail_span() -> U32:
  trace_sum(Array.walk.loop(~U32, ~WalkTrace, ~step, ~inspect, 2n, 3,
    Array.walk.attach(~U32, ~WalkTrace,
      inspect(WalkTrace{0, 0, 0, 8}), values())))

def main() -> (U32 & U32 & U32) & (U32 & U32 & U32) &
  (U32 & U32 & U32) & (U32 & U32 & U32) & (U32 & U32 & U32) &
  (U32 & U32 & U32) & U32 & U32:
  (run(0), run(1), run(3), run(4), run(8), invalid_span(),
    invalid_tail_span(), one())
#|((0, 1, 0), (1, 2, 1), (3, 4, 6), (4, 5, 10), (4, 5, 10), (2, 3, 5), 5, 9)
