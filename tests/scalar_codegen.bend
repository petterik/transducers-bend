import Base

type TwoWords is Type:
  TwoWords{first: U32, second: U32}

def choose(yes: Bool, +x: U32, +y: U32) -> TwoWords:
  match yes:
    case True{}:
      TwoWords{(x + y : U32), (x * y : U32)}
    case False{}:
      TwoWords{x, y}

# Speculating the True branch for max Nat would incorrectly fail-stop.
def checked(yes: Bool, n: Nat) -> Nat:
  match yes:
    case True{}:
      1n+n
    case False{}:
      n

def max_nat() -> Nat:
  Nat.add(Nat.mul(4294967295n, 65536n), 65535n)

type CheckedWords is Type:
  CheckedWords{first: TwoWords, second: TwoWords, last: Nat, dynamic: List<TwoWords>, guarded: List<Nat>}

def choose_word(+x: U32) -> TwoWords:
  choose(U32.is_gt(x, 1), x, 2)

def checked_word(+n: Nat) -> Nat:
  checked(Nat.is_eq(n, 0n), n)

def main() -> CheckedWords:
  CheckedWords{choose(True{}, 4294967295, 2), choose(False{}, 7, 9), checked(False{}, max_nat()),
    List.map(~U32, ~TwoWords, ~(x => choose_word(x)), [0, 4294967295, 5]),
    List.map(~Nat, ~Nat, ~(n => checked_word(n)), [max_nat(), 0n])}
#|CheckedWords{TwoWords{1, 4294967294}, TwoWords{7, 9}, 281474976710655n, [TwoWords{0, 2}, TwoWords{1, 4294967294}, TwoWords{7, 10}], [281474976710655n, 1n]}
