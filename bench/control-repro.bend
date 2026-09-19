# Standalone scalar reduction: no transducer library, templates, or callbacks.
import Base

type State is Type:
  State{left: Nat, sum: U32}

type Control is Type:
  Continue{state: State}
  Stop{state: State}

def mix(+x: U32) -> U32:
  (U32.xor(U32.mul(x, 1664525), U32.shrn(x, 13n)) + 1013904223 : U32)

def mapped(+x: U32) -> U32:
  (U32.xor(x, U32.shrn(x, 13n)) + 1 : U32)

def predicate(threshold: U32, x: U32) -> Bool:
  U32.is_gt(mix(mix(mix(x))), threshold)

def feed(yes: Bool, left: Nat, sum: U32, x: U32) -> State:
  match yes left:
    case False{} n:
      State{n, sum}
    case True{} 0n:
      State{0n, sum}
    case True{} 1n+p:
      State{p, (sum + x : U32)}

def step(threshold: U32, state: State, +x: U32) -> State:
  match state:
    case State{left, sum}:
      feed(predicate(threshold, x), left, sum, x)

def direct(n: Nat, +x: U32, state: State, +threshold: U32) -> U32:
  match n state:
    case n State{0n, sum}:
      sum
    case 0n State{left, sum}:
      sum
    case 1n+p State{1n+k, sum}:
      direct(p, (x + 1 : U32), step(threshold, State{1n+k, sum}, mapped(x)), threshold)

# Explicitly represent the stop decision after every accepted value.
def control(state: State) -> Control:
  match state:
    case State{0n, sum}:
      Stop{State{0n, sum}}
    case State{1n+p, sum}:
      Continue{State{1n+p, sum}}

def tagged_step(threshold: U32, state: State, +x: U32) -> Control:
  control(step(threshold, state, x))

def tagged(n: Nat, +x: U32, c: Control, +threshold: U32) -> U32:
  match n c:
    case n Stop{State{left, sum}}:
      sum
    case 0n Continue{State{left, sum}}:
      sum
    case 1n+p Continue{s}:
      tagged(p, (x + 1 : U32), tagged_step(threshold, s, mapped(x)), threshold)

# Restate the reachable invariant: Continue always has a positive count.
def guarded(n: Nat, +x: U32, c: Control, +threshold: U32) -> U32:
  match n c:
    case n Stop{State{left, sum}}:
      sum
    case 0n Continue{State{left, sum}}:
      sum
    case 1n+p Continue{State{0n, sum}}:
      sum
    case 1n+p Continue{State{1n+k, sum}}:
      guarded(p, (x + 1 : U32), tagged_step(threshold, State{1n+k, sum}, mapped(x)), threshold)

# Same reachable states, but normalize control only in the accepted arm.
def split_feed(yes: Bool, left: Nat, sum: U32, x: U32) -> Control:
  match yes left:
    case False{} n:
      Continue{State{n, sum}}
    case True{} 0n:
      Stop{State{0n, sum}}
    case True{} 1n+p:
      control(State{p, (sum + x : U32)})

def split_step(threshold: U32, state: State, +x: U32) -> Control:
  match state:
    case State{left, sum}:
      split_feed(predicate(threshold, x), left, sum, x)

def split(n: Nat, +x: U32, c: Control, +threshold: U32) -> U32:
  match n c:
    case n Stop{State{left, sum}}:
      sum
    case 0n Continue{State{left, sum}}:
      sum
    case 1n+p Continue{s}:
      split(p, (x + 1 : U32), split_step(threshold, s, mapped(x)), threshold)
