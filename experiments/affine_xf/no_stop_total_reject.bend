import Base
import ../../transduce.bend as T
import ./no_stop_total_probe.bend as P
import ./branch_control_ablation.bend as Tree

# A step that can stop does not have the total step type.
def main() -> U32:
  P.fold_tree_total(~U32, ~(s => x => T.Stop{s}), Tree.build(4n, 1), 0)
