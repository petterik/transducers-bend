import Base
import ../../transduce.bend as T

# A small record makes one-to-many mapping natural without copying an affine
# scalar. Each source record expands to four lanes, then the pipeline keeps,
# normalizes, and reduces those lanes.
type Quad is Data:
  Quad{a: U32, b: U32, c: U32, d: U32}

def leaf(seed: U32) -> Quad:
  Quad{seed, 1664525, 1013904223, 2654435761}

# Build the same balanced source shape that over_array traverses. The right
# subtree starts after the left subtree, so the leaves are in seed order.
def build(+depth: Nat, +seed: U32) -> Array<Quad>:
  match depth:
    case 0n:
      ALeaf{leaf(seed)}
    case 1n+p:
      left right = build(p, seed) build(p, U32.add(seed, U32.shln(1, p)))
      ANode{left, right}

def pair(x: Quad) -> List<U32>:
  match x:
    case Quad{a, b, c, d}:
      [a, b, c, d]

def keep(x: U32) -> Bool:
  U32.is_ne(U32.and(x, 3), 0)

def keep_with(_config: U32, x: U32) -> Bool:
  keep(x)

def work(n: Nat, +x: U32) -> U32:
  match n:
    case 0n:
      x
    case 1n+p:
      work(p,
        U32.xor(U32.add(U32.mul(x, 1664525), 1013904223),
          U32.shrn(x, 13n)))

def normalize(x: U32) -> U32:
  work(NORMALIZE_ROUNDSn, U32.xor(x, 2654435761))

def expand(xs: List<Quad>) -> List<U32>:
  match xs:
    case Nil{}:
      []
    case h <> t:
      List.append(&1, U32, pair(h), expand(t))

def filter_owned_put(+h: U32, r: List<&2, U32>, keep_value: Bool) -> List<&2, U32>:
  match keep_value:
    case False{}:
      r
    case True{}:
      h <> r

def filter_owned(xs: List<U32>) -> List<&2, U32>:
  match xs:
    case Nil{}:
      []
    case +h <> t:
      filter_owned_put(h, filter_owned(t), keep(h))

# Core Bend materialization baseline: convert the balanced array to a list,
# flatten the four-lane records, map with Base.List.map, filter, and fold. The
# small owned filter adapter is the same predicate/retention operation as
# Base.List.filter; it is required because Base.List.map returns the affine
# list kind while Base.List.filter consumes the shared list kind in this fork.
def staged(xs: Array<Quad>) -> U32:
  lanes = expand(Array.to_list(~Quad, xs))
  mapped = List.map(~U32, ~U32, ~normalize, lanes)
  kept = filter_owned(mapped)
  List.foldl(~&2, ~U32, ~U32, ~U32.add, kept, 0)

def transduced(xs: Array<Quad>) -> U32:
  T.transduce(~T.over_array(~Quad, ~U32,
    ~T.map(~Quad, ~List<U32>, ~U32, ~pair,
      ~T.cat(~U32, ~U32,
        ~T.map(~U32, ~U32, ~U32, ~normalize,
          ~T.filter(~U32, ~U32, ~U32, ~keep_with, ~T.sum()))))), (0, 0), xs)

def feed_keep(k: Bool, +acc: U32, +x: U32) -> U32:
  match k:
    case False{}:
      acc
    case True{}:
      U32.add(acc, x)

def feed(+acc: U32, +x: U32) -> U32:
  +y = normalize(x)
  feed_keep(keep(y), acc, y)

def direct_quad(x: Quad, +acc: U32) -> U32:
  match x:
    case Quad{a, b, c, d}:
      acc = feed(acc, a)
      acc = feed(acc, b)
      acc = feed(acc, c)
      feed(acc, d)

# User-authored fused Bend comparator. It traverses the same balanced source
# directly and performs the complete map/filter/reduce in one loop-shaped
# function, without any reducer description or materialized list.
def direct_array(xs: Array<Quad>, +acc: U32) -> U32:
  match xs:
    case ALeaf{x}:
      direct_quad(x, acc)
    case ANode{left, right}:
      direct_array(right, direct_array(left, acc))

def direct(xs: Array<Quad>) -> U32:
  direct_array(xs, 0)
