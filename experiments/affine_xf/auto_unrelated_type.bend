import Base

# The candidate must infer through an arbitrary user-defined type constructor,
# not recognize the transducer library's Xf by name.
type Tagged<-A: Type> is Type:
  Tagged{value: A}

def pack(x: U32) -> Tagged<U32>:
  Tagged{x}

def unpack(~A: Type, tagged: Tagged<A>) -> A:
  match tagged:
    case Tagged{value}:
      value

def main() -> U32:
  tagged = pack(7)
  unpack(~?AUTO, tagged)
#|7
