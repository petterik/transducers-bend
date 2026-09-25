import Base
import ./vec_data_probe.bend as Vec
import ./vec_data_fill_probe.bend as Fill
import ./rank2_companion_api.bend as Auto
import ./rank2_rf_values.bend as V

def string_size(s: String) -> U32:
  U32.from_nat(String.length(s))

def empty_u32() -> List<U32>:
  []

def collect_maybe(xs: List<String>) -> List<U32>:
  vec = Auto.into(Vec.reserve(~String, 2n),
    V.map(~String, ~String, ~(s => s)), xs)
  Auto.into(empty_u32(), V.map(~String, ~U32, ~string_size), vec)

def collect_fill(xs: List<String>) -> List<U32>:
  vec = Auto.into(Fill.reserve(~String, 2n, ""),
    V.map(~String, ~String, ~(s => s)), xs)
  Auto.into(empty_u32(), V.map(~String, ~U32, ~string_size), vec)

def main() -> List<U32> & List<U32>:
  (collect_maybe(["a", "bb", "ccc"]),
   collect_fill(["a", "bb", "ccc"]))
#|([3, 2, 1], [3, 2, 1])
