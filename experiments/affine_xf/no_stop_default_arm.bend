import Base
import ./no_stop_indexed_probe.bend as P

def get(flow: P.Flow<Empty, U32>) -> U32:
  match flow:
    case P.Ready{value}: value
    case _: 99

def get_other(flow: P.Flow<Empty, U32>) -> U32:
  match flow:
    case P.Halted{permit, value}: 99
    case _: 1

def main() -> U32:
  (get(P.Ready{42}) + get_other(P.Ready{0}) : U32)
