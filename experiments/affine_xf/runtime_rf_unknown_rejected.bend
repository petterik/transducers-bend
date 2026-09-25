import Base
import ./local_rf_alias.bend as P

# A genuine runtime parameter has no local closed value to specialize.
def run(rf: U32 -> U32 -> U32) -> U32:
  P.fold(~rf, [1, 2, 3], 0)

def main() -> U32:
  run(U32.add)
