import Base
import ../transduce.bend as T

# The benchmark runner replaces transform and the main expression per case.
def work(n: Nat, +x: U32) -> U32:
  match n:
    case 0n:
      x
    case 1n+p:
      work(p, (U32.xor(U32.mul(x, 1664525), U32.shrn(x, 13n)) + 1013904223 : U32))

def transform(x: U32) -> U32:
  (x + 1 : U32)

def above(threshold: U32, x: U32) -> Bool:
  U32.is_gt(x, threshold)

def pipeline() -> T.Reducer<U32, U32>:
  T.map(~U32, ~U32, ~U32, ~transform,
    ~T.filter(~U32, ~U32, ~U32, ~above,
      ~T.take(~U32, ~U32, ~T.sum())))

def build(n: Nat, xs: List<U32>) -> List<U32>:
  match n:
    case 0n:
      xs
    case 1n+p:
      build(p, 1 <> xs)

def mapped(xs: List<U32>) -> List<&2, U32>:
  match xs:
    case Nil{}:
      Nil{}
    case h <> t:
      transform(h) <> mapped(t)

def staged(xs: List<U32>, n: Nat) -> U32:
  List.foldl(~&2, ~U32, ~U32, ~U32.add,
    List.take(&2, U32, List.filter(~U32, ~(x => U32.is_gt(x, 1)), mapped(xs)), n), 0)

type Running is Type:
  Running{remaining: Nat, acc: U32}

def next(keep: Bool, n: Nat, acc: U32, x: U32) -> Running:
  match keep n:
    case False{} n:
      Running{n, acc}
    case True{} 0n:
      Running{0n, acc}
    case True{} 1n+p:
      Running{p, (acc + x : U32)}

def feed(n: Nat, acc: U32, +x: U32) -> Running:
  next(U32.is_gt(x, 1), n, acc, x)

def direct(xs: List<U32>, state: Running) -> U32:
  match xs state:
    case _ Running{0n, acc}:
      acc
    case Nil{} Running{n, acc}:
      acc
    case h <> t Running{1n+p, acc}:
      direct(t, feed(1n+p, acc, transform(h)))

def main() -> U32:
  T.transduce(~U32, ~U32, ~pipeline(), (1, (100000n, 0)), build(100000n, []))
#|200000
