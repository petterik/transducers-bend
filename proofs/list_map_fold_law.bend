import Base

# A source-level law for the pure List fragment of the transducer contract.
# It models map followed by a left fold, not the native compiler/runtime.
def mapped(~f: U32 -> U32, xs: List<U32>) -> List<U32>:
  match xs:
    case Nil{}: []
    case h <> t: f(h) <> mapped(~f, t)

def folded(~step: U32 -> U32 -> U32,
  xs: List<U32>, state: U32) -> U32:
  match xs:
    case Nil{}: state
    case h <> t: folded(~step, t, step(state, h))

def fused(~f: U32 -> U32, ~step: U32 -> U32 -> U32,
  xs: List<U32>, state: U32) -> U32:
  match xs:
    case Nil{}: state
    case h <> t: fused(~f, ~step, t, step(state, f(h)))

law map_fold:
  for ~f: U32 -> U32
  for ~step: U32 -> U32 -> U32
  for xs: List<U32>
  for +state: U32
  {folded(~step, mapped(~f, xs), state) ==
    fused(~f, ~step, xs, state) : U32}

def map_fold(f, step, xs, state):
  match xs:
    case Nil{}: {==}
    case h <> t: map_fold(~f, ~step, t, step(state, f(h)))

law map_compose:
  for ~f: U32 -> U32
  for ~g: U32 -> U32
  for xs: List<U32>
  {mapped(~g, mapped(~f, xs)) ==
    mapped(~(x => g(f(x))), xs) : List<U32>}

def map_compose(f, g, xs):
  match xs:
    case Nil{}: {==}
    case h <> t:
      %map_compose(~f, ~g, t) :
        {g(f(h)) <> mapped(~g, mapped(~f, t)) ==
          g(f(h)) <> _ : List<U32>}
      {==}

def main() -> {folded(~U32.add, mapped(~U32.inc, [1, 2, 3]), 0) ==
  fused(~U32.inc, ~U32.add, [1, 2, 3], 0) : U32}:
  map_fold(~U32.inc, ~U32.add, [1, 2, 3], 0)
