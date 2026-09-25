import Base
import ./no_stop_total_probe.bend as P
import ./branch_control_ablation.bend as Tree

def main() -> U32 & U32 & U32 & U32 & U32 & U32 & U32 & U32 & U32 & U32:
  (P.choose_array(0n, Array.new(U32, 10n, 1)),
   P.choose_array(1n, Array.new(U32, 10n, 1)),
   P.choose_array(2n, Array.new(U32, 10n, 1)),
   P.choose_array(3n, Array.new(U32, 10n, 1)),
   P.choose_array(4n, Array.new(U32, 10n, 1)),
   P.choose_tree(0n, Tree.build(10n, 1)),
   P.choose_tree(1n, Tree.build(10n, 1)),
   P.choose_tree(2n, Tree.build(10n, 1)),
   P.choose_tree(3n, Tree.build(10n, 1)),
   P.choose_tree(4n, Tree.build(10n, 1)))
#|(2048, 2048, 2048, 2048, 2048, 1573376, 1573376, 1573376, 1573376, 1573376)
