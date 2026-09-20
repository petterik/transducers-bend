import Base
import ../../../transduce.bend as T

def to_u32(x: Char) -> U32:
  Char.to_u32(x)

def above(t: U32, x: U32) -> Bool:
  U32.is_gt(x, t)

def pipeline() -> T.Reducer<Char, U32>:
  T.map(~Char, ~U32, ~U32, ~to_u32,
    ~T.filter(~U32, ~U32, ~U32, ~above,
      ~T.take(~U32, ~U32, ~T.sum())))

def run(+xs: String, n: Nat) -> U32:
  T.transduce(~T.over_string(~U32, ~pipeline()), (96, (n, 0)), xs)

def main() -> IO(Unit):
  IO.print(U32.show(run("", 0n)) ++ ":" ++
    U32.show(run("abcd", 2n)) ++ ":" ++
    U32.show(run("abcd", 32n)))
