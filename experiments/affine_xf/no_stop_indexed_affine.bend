import Base
import ./no_stop_indexed_probe.bend as P

def main() -> Array<U32>:
  P.affine_array(Array.new(U32, 3n, 9))
