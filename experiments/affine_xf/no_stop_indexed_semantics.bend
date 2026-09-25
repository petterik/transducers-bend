import Base
import ./no_stop_indexed_probe.bend as P
import ./branch_control_ablation.bend as Tree

def main() -> List<U32>:
  [P.total_array(Array.new(U32, 3n, 1)),
   P.budget_array(Array.new(U32, 3n, 1), 0),
   P.budget_array(Array.new(U32, 3n, 1), 3),
   P.initial_halt_array(Array.new(U32, 3n, 1)),
   P.total_tree(Tree.build(3n, 1)),
   P.budget_tree(Tree.build(3n, 1), 0),
   P.budget_tree(Tree.build(3n, 1), 3),
   P.nested_cat_array(Array.new(U32, 3n, 1), 0),
   P.nested_cat_array(Array.new(U32, 3n, 1), 3),
   P.nested_cat_array(Array.new(U32, 3n, 1), 16)]
