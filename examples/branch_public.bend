import Base
import ../transduce_core.bend as T

# An independent affine collection. Its owner supplies the public source
# companion, so clients can pass Branch values directly to Xf.transduce.
type Branch is Type:
  Tip{value: U32}
  Fork{left: Branch, right: Branch}

def build(depth: Nat, +seed: U32) -> Branch:
  match depth:
    case 0n:
      Tip{seed}
    case 1n++p:
      Fork{build(p, (seed * 2 : U32)),
        build(p, ((seed * 2 : U32) + 1 : U32))}

def direct(xs: Branch, acc: U32) -> U32:
  match xs:
    case Tip{x}:
      (acc + U32.inc(x) : U32)
    case Fork{left, right}:
      direct(right, direct(left, acc))

def drive_loop(~K: Data, ~S: Type,
  ~advance: S -> U32 -> S, ~inspect: S -> T.Checked<K, S>,
  xs: Branch, checked: T.Checked<K, S>) -> S:
  match xs checked:
    case Tip{x} T.Halted{permit, state}: state
    case Tip{x} T.Ready{state}: advance(state, x)
    case Fork{left, right} T.Halted{permit, state}: state
    case Fork{left, right} T.Ready{state}:
      drive_loop(~K, ~S, ~advance, ~inspect, right,
        inspect(drive_loop(~K, ~S, ~advance, ~inspect,
          left, T.Ready{state})))

def drive(~K: Data, ~S: Type,
  ~advance: S -> U32 -> S, ~inspect: S -> T.Checked<K, S>,
  xs: Branch, state: S) -> S:
  drive_loop(~K, ~S, ~advance, ~inspect, xs, inspect(state))

def Branch.source(xs: Branch) -> T.Source<U32, Branch,
  (K => S => advance => inspect => tree => state =>
    drive(~K, ~S, ~advance, ~inspect, tree, state))>:
  T.Source{xs}
