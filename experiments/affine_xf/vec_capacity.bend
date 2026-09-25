import Base

# Array.new with a nontrivial shared filler reports ERR_RFCS at depth 24.
# A generic Data Vec cannot tell which fillers are trivial, so this probe
# conservatively accepts capacities through 2^23 elements.
def checked_depth(+depth: Nat, allowed: Bool) -> Maybe<Nat>:
  match allowed:
    case True{}:
      Some{depth}
    case False{}:
      None{}

def depth_for_many(requested: U32) -> Maybe<Nat>:
  +depth = Nat.add(U32.log2(U32.sub(requested, 1)), 1n)
  checked_depth(depth, Nat.is_le(depth, 23n))

def depth_for_if(requested: U32, small: Bool) -> Maybe<Nat>:
  match small:
    case True{}:
      Some{0n}
    case False{}:
      depth_for_many(requested)

def depth_for_items(+requested: U32) -> Maybe<Nat>:
  depth_for_if(requested, U32.is_le(requested, 1))
