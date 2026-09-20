import Base

type Choice is Type:
  Left{value: U32}
  Right{value: U32}

def choose_left(p: Choice, flag: Bool) -> U32:
  match p:
    case Left{value}:
      match flag:
        case False{}:
          value
        case True{}:
          one = U32.from_nat(List.length(&1, Unit, [Unit{}]))
          (value + one : U32)
    case Right{value}:
      (value + 100 : U32)

def has_arg(xs: List<String>) -> Bool:
  match xs:
    case Nil{}:
      False{}
    case h <> t:
      True{}

def left_value(flag: Bool) -> U32:
  choose_left(Left{5}, flag)

def main() -> IO(Unit):
  IO.bind(List<String>, Unit, IO.args(),
    xs => IO.print(U32.show(left_value(has_arg(xs)))))
#|6
