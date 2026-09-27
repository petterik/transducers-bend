import Base

def four() -> Array<U32>:
  Array.fill(~U32, ~U32.inc, Array.new(U32, 2n, 0))

def malformed() -> Array<U32>:
  Array.fill.loop(~U32, ~U32.inc, 2n, 3, Array.new(U32, 2n, 0))

def single() -> Array<U32>:
  Array.fill(~U32, ~U32.inc, Array.new(U32, 0n, 0))

def prefix(count: U32) -> List<U32>:
  Array.to_list(~U32, Array.fill.prefix(~U32, ~U32.inc,
    count, Array.new(U32, 2n, 0)))

def word(i: U32) -> String:
  Bool.pick(String, U32.is_eq(i, 0), "a", "b")

def shared(pair: Array<U32> & Array<U32>) -> List<U32> & List<U32>:
  (left, right) = pair
  (Array.to_list(~U32, Array.fill(~U32, ~U32.inc, left)),
    Array.to_list(~U32, right))

def main() -> List<U32> & List<U32> & List<U32> & List<String> &
  (List<U32> & List<U32>) & List<U32> & List<U32> & List<U32>:
  (Array.to_list(~U32, four()),
   Array.to_list(~U32, malformed()),
   Array.to_list(~U32, single()),
   Array.to_list(~String, Array.fill(~String, ~word,
     Array.new(String, 1n, "z"))),
   shared(Array.clone(U32, Array.new(U32, 1n, 0))),
   prefix(0), prefix(2), prefix(9))
#|([1, 2, 3, 4], [5, 0, 0, 4], [1], ["a", "b"], ([1, 2], [0, 0]), [0, 0, 0, 0], [1, 2, 0, 0], [1, 2, 3, 4])
