import Base
import ../xf.bend as Xf
import ../vec_maybe.bend as Vec

type Label is Data:
  Label{text: String}

def label(s: String) -> Label:
  Label{s}

def label_size(x: Label) -> U32:
  match x:
    case Label{text}:
      U32.from_nat(String.length(text))

def names() -> List<String>:
  ["a", "bb", "ccc"]

def labels() -> U32:
  vec = Xf.into(Vec.empty(~Label),
    Xf.map(~String, ~Label, ~label), names())
  Xf.transduce(Xf.map(~Label, ~U32, ~label_size),
    Xf.sum_rf(), 0, vec)

def nums() -> List<U32>:
  [1, 2, 3]

def empty_u32() -> List<U32>:
  []

def order() -> List<U32>:
  vec = Xf.into(Vec.empty(~U32),
    Xf.map(~U32, ~U32, ~(x => x)), nums())
  Xf.into(empty_u32(), Xf.map(~U32, ~U32, ~(x => x)), vec)

def after_get(result: Vec.VecMaybe<U32> & Maybe<&2, U32>) ->
  Maybe<&2, U32>:
  (vec, found) = result
  found

def after_set(result: Vec.UpdateResult<U32>) ->
  Maybe<&2, U32> & Maybe<&2, U32>:
  match result:
    case Vec.Updated{vec, old}:
      (old, after_get(Vec.get(~U32, vec, 1)))
    case Vec.Invalid{vec, value}:
      (None{}, after_get(Vec.get(~U32, vec, 1)))

def indexed() -> Maybe<&2, U32> & Maybe<&2, U32>:
  vec = Vec.push(~U32, Vec.push(~U32, Vec.empty(~U32), 1), 2)
  after_set(Vec.set(~U32, vec, 1, 20))

def too_large(choice: Maybe<Vec.VecMaybe<U32>>) -> Bool:
  match choice:
    case None{}:
      True{}
    case Some{vec}:
      False{}

def main() -> U32 & List<U32> & (Maybe<&2, U32> & Maybe<&2, U32>) & Bool:
  (labels(), order(), indexed(),
   too_large(Vec.with_capacity(~U32, 8388609)))
#|(6, [3, 2, 1], (Some{2}, Some{20}), True{})
