import Base

type Never is Data:

type Choice<-K: Data> is Type:
  Value{item: U32}
  Halted{permit: K, item: U32}

type Boxed<-K: Data> is Type:
  Leaf{choice: Choice<K>}
  Fork{left: Boxed<K>, right: Boxed<K>}

def generic(-K: Data, choice: Choice<K>) -> U32:
  match choice:
    case Value{item}: item
    case Halted{permit, item}: (item + 100 : U32)

def with_default(choice: Choice<Never>) -> U32:
  match choice:
    case Value{item}: item
    case _: 999

def opposite_default(choice: Choice<Never>) -> U32:
  match choice:
    case Halted{permit, item}: item
    case _: 7

def array_sum(xs: Array<Choice<Never>>) -> U32:
  match xs:
    case ALeaf{x}: generic(Never, x)
    case ANode{left, right}:
      (array_sum(left) + array_sum(right) : U32)

def boxed_sum(xs: Boxed<Never>) -> U32:
  match xs:
    case Leaf{choice}: generic(Never, choice)
    case Fork{left, right}:
      (boxed_sum(left) + boxed_sum(right) : U32)

def main() -> List<U32>:
  [generic(Never, Value{3}),
   generic(Unit, Halted{Unit{}, 5}),
   with_default(Value{11}),
   opposite_default(Value{23}),
   array_sum(ANode{ALeaf{Value{2}}, ALeaf{Value{4}}}),
   boxed_sum(Fork{Leaf{Value{6}}, Leaf{Value{8}}})]
#|[3, 105, 11, 7, 6, 14]
