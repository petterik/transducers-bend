import Base
import ./bullet_cathedral.bend as B

# Keep the original simulation and transducer renderer, but stream successive
# frames instead of replaying from frame zero for each image. A fresh shield
# wave enters every 240 frames while the absolute bullet clock keeps moving.
def new_wave_if(reset: Bool, world: B.Damage) -> B.Damage:
  match reset:
    case True{}: B.initial()
    case False{}: world

def new_wave(+frame: U32, world: B.Damage) -> B.Damage:
  new_wave_if(U32.is_eq(U32.mod(frame, 240), 0), world)

def rgb_bytes_go(pixels: List<&1, U32>, acc: List<&2, U32>) ->
  List<&2, U32>:
  match pixels:
    case Nil{}: List.reverse(&2, U32, acc)
    case +color <> rest:
      rgb_bytes_go(rest,
        U32.and(color, 255) <>
        U32.and(U32.shrn(color, 8n), 255) <>
        U32.shrn(color, 16n) <> acc)

def rgb_bytes(pixels: Array<U32>) -> List<&2, U32>:
  rgb_bytes_go(Array.to_list(~U32, pixels), [])

def wrote(pair: File & Result<&1, &1, U32 & String, Unit>) -> IO(File):
  (file, result) = pair
  do IO<File>:
    IO.pass(Unit, result)
    return file

def frames(left: Nat, +frame: U32, held: B.Held, file: File) -> IO(Unit):
  match left held:
    case 0n B.Held{world, pixels}: File.close(file)
    case 1n+p B.Held{world, pixels}:
      do IO<Unit>:
        pair : File & Result<&1, &1, U32 & String, Unit> <-
          File.write_bytes(file, rgb_bytes(pixels))
        file : File <- wrote(pair)
        frames(p, U32.inc(frame), B.render_copy(
          B.step(U32.inc(frame), new_wave(U32.inc(frame), world)),
          U32.inc(frame)), file)

def run_args(args: List<String>) -> IO(Unit):
  match args:
    case path <> count <> rest:
      do IO<Unit>:
        file : File <- IO.try(File, File.open(path, "w"))
        frames(U32.to_nat(B.parsed_u32(U32.read(count))), 0,
          B.render_copy(B.step(0, B.initial()), 0), file)
    case _: IO.print("expected FIFO path and frame count")

def main() -> IO(Unit):
  do IO<Unit>:
    args : List<String> <- IO.args()
    run_args(args)
