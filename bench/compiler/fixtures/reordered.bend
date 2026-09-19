import Base

# Deliberately different names, field order, parameter order and inner tags.
type Cell is Type:
  Closed{value: U32}
  Open{value: U32}
type Memory is Type:
  Memory{cell: Cell, quota: Nat, cookie: U32}
type Envelope is Type:
  Ready{memory: Memory}
  Finished{memory: Memory}

def package(n: Nat, sum: U32, cookie: U32) -> Envelope:
  match n:
    case 0n:
      Finished{Memory{Open{sum}, 0n, cookie}}
    case 1n+p:
      Ready{Memory{Open{sum}, 1n+p, cookie}}

def advance(memory: Memory, x: U32) -> Envelope:
  match memory:
    case Memory{Closed{sum}, n, cookie}:
      Finished{Memory{Closed{sum}, n, cookie}}
    case Memory{Open{sum}, 0n, cookie}:
      Finished{Memory{Open{sum}, 0n, cookie}}
    case Memory{Open{sum}, 1n+p, cookie}:
      package(p, (sum + x : U32), cookie)

def route(x: U32, memory: Memory, permit: Bool) -> Envelope:
  match permit:
    case False{}:
      Ready{memory}
    case True{}:
      advance(memory, x)

def exercise(+x: U32) -> Envelope:
  route(x, Memory{Open{4294967295}, 2n, 17}, U32.is_gt(x, 0))
def main() -> List<Envelope>:
  List.map(~U32, ~Envelope, ~(x => exercise(x)), [0, 1, 2])
#|[Ready{Memory{Open{4294967295}, 2n, 17}}, Ready{Memory{Open{0}, 1n, 17}}, Ready{Memory{Open{1}, 1n, 17}}]
