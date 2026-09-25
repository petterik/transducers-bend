import Base
import ./explicit_reducer_types.bend as E
import ../../transduce.bend as T

def collect2() -> E.R2<U32, List<U32>, List<U32>, List<U32>>:
  E.R2{xs => T.Continue{xs}, xs => x => T.Continue{x <> xs}, xs => xs}

def main() -> List<U32>:
  xf : E.Xf<U32, U32, E.plus_one> = E.Xf{2n}
  E.run(~U32, ~U32, ~List<U32>, ~List<U32>, ~List<U32>,
    ~E.plus_one, ~collect2(), xf, [9], [1, 2, 3])
