import Base
import ./companion_boundary_owner.bend as O

def plain(x: U32) -> U32:
  (x + 1 : U32)

def main() -> U32 & U32 & U32:
  (O.chain(~O.read, O.Raw{7}),
   O.direct(O.Raw{9}),
   plain(10))
#|(7, 9, 11)
