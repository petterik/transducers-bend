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
          (value + 1 : U32)
    case Right{value}:
      match flag:
        case False{}:
          (value + 100 : U32)
        case True{}:
          (value + 200 : U32)

def has_arg(xs: List<String>) -> Bool:
  match xs:
    case Nil{}:
      False{}
    case h <> t:
      True{}

def left_value(+flag: Bool) -> U32:
  (choose_left(Left{5}, flag) + choose_left(Right{7}, flag) : U32)

def main() -> IO(Unit):
  IO.bind(List<String>, Unit, IO.args(),
    xs => IO.print(U32.show(left_value(has_arg(xs)))))
# With one argument: 213. With no arguments: 112.
