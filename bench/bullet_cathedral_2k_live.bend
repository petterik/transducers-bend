import Base
import ./bullet_cathedral_2k_frames.bend as B
import ./bullet_cathedral_rgb.bend as RGB

# Advance one simulation tick and render one 1920x1080 image per write.
# Restart the shield wave every 240 frames so a long run keeps changing.
def new_wave_if(reset: Bool, world: B.Damage) -> B.Damage:
  match reset:
    case True{}: B.initial()
    case False{}: world

def new_wave(+frame: U32, world: B.Damage) -> B.Damage:
  new_wave_if(U32.is_eq(U32.mod(frame, 240), 0), world)

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
          RGB.write_frame(file, pixels, 2073600)
        file : File <- wrote(pair)
        frames(p, U32.inc(frame),
          B.step_render(U32.inc(frame),
            new_wave(U32.inc(frame), world)), file)

def run_args(args: List<String>) -> IO(Unit):
  match args:
    case path <> count <> rest:
      do IO<Unit>:
        file : File <- IO.try(File, File.open(path, "w"))
        frames(U32.to_nat(B.parsed_u32(U32.read(count))), 0,
          B.step_render(0, B.initial()), file)
    case _: IO.print("expected FIFO path and frame count")

def main() -> IO(Unit):
  do IO<Unit>:
    args : List<String> <- IO.args()
    run_args(args)
