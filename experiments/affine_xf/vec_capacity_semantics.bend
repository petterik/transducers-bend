import Base
import ./vec_capacity.bend as Capacity
import ./vec_data_probe.bend as MaybeVec
import ./vec_data_fill_probe.bend as FillVec

def main() -> Maybe<Nat> & Maybe<Nat> & Maybe<Nat> & Maybe<Nat> &
  Maybe<Nat> & Maybe<Nat> & Maybe<Nat> & Maybe<Nat> & Maybe<Nat> &
  Maybe<MaybeVec.VecData<U32>> & Maybe<FillVec.VecFill<String>>:
  (Capacity.depth_for_items(0), Capacity.depth_for_items(1),
   Capacity.depth_for_items(2), Capacity.depth_for_items(3),
   Capacity.depth_for_items(4), Capacity.depth_for_items(5),
   Capacity.depth_for_items(8388608),
   Capacity.depth_for_items(8388609),
   Capacity.depth_for_items(4294967295),
   MaybeVec.reserve_items(~U32, 3),
   FillVec.reserve_items(~String, 3, "x"))
