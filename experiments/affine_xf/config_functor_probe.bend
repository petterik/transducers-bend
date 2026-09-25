import Base

type Xf<-Cmap: Type -> Type> is Type:
  Xf{configure: @-C: Type -> C -> Cmap(C)}

def identity() -> Xf<(C => C)>:
  Xf{C => c => c}

def taking(n: Nat) -> Xf<(C => Nat & C)>:
  Xf{C => c => (n, c)}

def compose(~F: Type -> Type, ~G: Type -> Type,
  outer: Xf<F>, inner: Xf<G>) -> Xf<(C => F(G(C)))>:
  match outer inner:
    case Xf{f} Xf{g}:
      Xf{C => c => f(G(C), g(C, c))}

def apply(~Cmap: Type -> Type, xf: Xf<Cmap>, x: U32) -> Cmap(U32):
  match xf:
    case Xf{configure}:
      configure(U32, x)

def sum_pair(p: Nat & U32) -> U32:
  (left, value) = p
  (U32.from_nat(left) + value : U32)

def main() -> U32:
  sum_pair(apply(~(C => Nat & C),
    compose(~(C => Nat & C), ~(C => C), taking(3n), identity()), 7))
#|10
