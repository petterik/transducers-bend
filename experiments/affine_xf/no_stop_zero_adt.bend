import Base

# The backend experiment must recognize any empty datatype, not a name.
type Never is Type:

type Choice is Type:
  A{x: U32}
  B{impossible: Never, y: U32}

def get(x: Choice) -> U32:
  match x:
    case A{value}: value
    case B{impossible, value}:
      match impossible:

def main() -> U32:
  get(A{42})
