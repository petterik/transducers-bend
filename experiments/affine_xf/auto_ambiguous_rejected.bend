import Base

def unrelated(~A: Type, xs: List<U32>) -> U32:
  0

def items() -> List<U32>:
  [1, 2, 3]

def main() -> U32:
  unrelated(~?AUTO, items())
