import Base

type Plan is Data:
  Id{}
  Add{}
  Both{first: Plan, second: Plan}

# Erasing the plan removes runtime dispatch, but ordinary computation then
# cannot inspect it to choose which stage to execute.
def interpret(-plan: Plan, x: U32) -> U32:
  match plan x:
    case Id{} x:
      x
    case Add{} x:
      (x + 1 : U32)
    case Both{first, second} x:
      interpret(second, interpret(first, x))

def main() -> U32:
  interpret(Both{Add{}, Add{}}, 1)
