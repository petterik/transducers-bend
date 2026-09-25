import Base
import ./local_rf_alias.bend as P

# A local closure that captures a runtime value is not closed template code.
def run(k: U32) -> U32:
  rf : U32 -> U32 -> U32 = a => b => (a + b + k : U32)
  P.fold(~rf, [1, 2, 3], 0)

def main() -> U32:
  run(4)
