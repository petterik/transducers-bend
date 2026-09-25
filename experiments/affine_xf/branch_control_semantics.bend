import Base
import ./branch_control_ablation.bend as B

def main() -> U32 & U32 & U32 & U32 & U32:
  (B.choose(0n, B.build(10n, 1), 17),
   B.choose(1n, B.build(10n, 1), 17),
   B.choose(2n, B.build(10n, 1), 17),
   B.choose(3n, B.build(10n, 1), 17),
   B.choose(4n, B.build(10n, 1), 17))
#|(1573376, 1573376, 17561, 17561, 0)
