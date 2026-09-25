import Base

# Can a closed template argument act as a recursively interpretable,
# extensible stage plan, including nested arguments from a match?
type Plan is Data:
  Id{}
  Add{}
  Both{first: Plan, second: Plan}

def interpret(plan: Plan, x: U32) -> U32:
  match plan x:
    case Id{} x:
      x
    case Add{} x:
      (x + 1 : U32)
    case Both{first, second} x:
      interpret(second, interpret(first, x))

def main() -> U32:
  interpret(Both{Add{}, Add{}}, 1)
#|3
