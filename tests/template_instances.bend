import Base

# The compiler book contains separate checked instances for these closed ~
# arguments. Keep different values and callbacks from sharing an instance.
def add_by(~by: U32, x: U32) -> U32:
  (x + by : U32)

def invoke(~f: U32 -> U32, x: U32) -> U32:
  f(x)

def add_one(x: U32) -> U32:
  (x + 1 : U32)

def add_ten(x: U32) -> U32:
  (x + 10 : U32)

def main() -> List<U32>:
  [add_by(~(1 : U32), 41), add_by(~(2 : U32), 40),
   invoke(~add_one, 41), invoke(~add_ten, 32)]
#|[42, 42, 42, 42]
