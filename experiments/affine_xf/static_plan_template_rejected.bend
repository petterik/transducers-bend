import Base

type Plan is Data:
  Id{}
  Add{}
  Both{first: Plan, second: Plan}

# A template can receive closed syntax, but this direct attempt to interpret
# a matched recursive plan inside the template is rejected by the checker.
def interpret(~plan: Plan, x: U32) -> U32:
  match plan x:
    case Id{} x:
      x
    case Add{} x:
      (x + 1 : U32)
    case Both{first, second} x:
      interpret(~second, interpret(~first, x))

def main() -> U32:
  interpret(~Both{Add{}, Add{}}, 1)
