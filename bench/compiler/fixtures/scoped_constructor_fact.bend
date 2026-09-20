import Base

type FactPair is Type:
  FactPair{left: U32, right: U32}

def select_pair(p: FactPair, flag: Bool) -> U32:
  match p:
    case FactPair{left, right}:
      match flag:
        case False{}:
          left
        case True{}:
          zero = U32.from_nat(List.length(&1, Unit, [Unit{}]))
          (left + right + zero : U32)

def select_dynamic(p: FactPair, flag: Bool) -> U32:
  match p:
    case FactPair{left, right}:
      match flag:
        case False{}:
          left
        case True{}:
          zero = U32.from_nat(List.length(&1, Unit, [Unit{}]))
          (left + right + zero : U32)

def has_arg(xs: List<String>) -> Bool:
  match xs:
    case Nil{}:
      False{}
    case h <> t:
      True{}

def consume_value(flag: Bool) -> U32:
  select_pair(FactPair{1, 2}, flag)

def consume_dynamic_value(n: U32, flag: Bool) -> U32:
  select_dynamic(FactPair{n, 2}, flag)

def consume_dynamic(flag: Bool, xs: List<String>) -> IO(Unit):
  n = U32.from_nat(List.length(&1, String, xs))
  IO.bind(Unit, Unit, IO.print(U32.show(consume_value(flag))),
    u => IO.print(U32.show(consume_dynamic_value(n, False{}))))

def consume_args(xs: List<String>) -> IO(Unit):
  IO.bind(List<String>, Unit, IO.args(),
    ys => consume_dynamic(has_arg(xs), ys))

def main() -> IO(Unit):
  IO.bind(List<String>, Unit, IO.args(), consume_args)
#|4
#|1
