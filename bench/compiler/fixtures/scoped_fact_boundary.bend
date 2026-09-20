import Base

# The two callers share one typed loop and one layout. Only the first enters
# with the state shape used by the proved fast transition; the second is a
# valid exceptional state that must use the generic behavior.
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

def spin(+x: U32, +n: Nat, c: Envelope) -> Envelope:
  match n c:
    case n Finished{memory}:
      Finished{memory}
    case 0n Ready{memory}:
      Ready{memory}
    case 1n+p Ready{memory}:
      spin(x, p, route(x, memory, U32.is_gt(x, 0)))

def safe(+x: U32) -> Envelope:
  spin(x, 8n, Ready{Memory{Open{4294967295}, 2n, 17}})

def exceptional(+x: U32) -> Envelope:
  spin(x, 8n, Finished{Memory{Closed{13}, 0n, 91}})

def main() -> List<Envelope>:
  List.append(&1, Envelope,
    List.map(~U32, ~Envelope, ~(x => safe(x)), [0, 1, 2]),
    List.map(~U32, ~Envelope, ~(x => exceptional(x)), [0, 1, 2]))
#|[Ready{Memory{Open{4294967295}, 2n, 17}}, Finished{Memory{Open{1}, 0n, 17}}, Finished{Memory{Open{3}, 0n, 17}}, Finished{Memory{Closed{13}, 0n, 91}}, Finished{Memory{Closed{13}, 0n, 91}}, Finished{Memory{Closed{13}, 0n, 91}}]
