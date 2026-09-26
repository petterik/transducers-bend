import Base
import ./bullet_cathedral_2k_frames.bend as B
import ./bullet_cathedral_present.bend as P

# Bend computes each frame into its flat Array<U32>. A native effect presents
# that finished array, then the next simulation tick starts immediately.
def new_wave_if(reset: Bool, world: B.Damage) -> B.Damage:
  match reset:
    case True{}: B.initial()
    case False{}: world

def new_wave(+frame: U32, world: B.Damage) -> B.Damage:
  new_wave_if(U32.is_eq(U32.mod(frame, 240), 0), world)

def finish(window: Window, +frame: U32, elapsed: Nat) -> IO(Unit):
  do IO<Unit>:
    IO.print("Presented " ++ U32.show(U32.inc(frame)) ++
      " frames in " ++ Nat.show(Nat.div(elapsed, 1000n)) ++ " seconds")
    Window.close(window)

@unsafe def frames(+frame: U32, held: B.Held, window: Window,
  +start: Nat, +sample_time: Nat, +sample_count: U32,
  +duration: Nat) -> IO(Unit):
  match held:
    case B.Held{world, pixels}:
      do IO<Unit>:
        result : Window & Bool <- P.present(window, pixels)
        after_present(result, frame, world, start, sample_time,
          sample_count, duration)

def next_frame(+frame: U32, world: B.Damage, window: Window,
  start: Nat, sample_time: Nat, sample_count: U32,
  duration: Nat) -> IO(Unit):
  frames(U32.inc(frame),
    B.step_render(U32.inc(frame), new_wave(U32.inc(frame), world)),
    window, start, sample_time, sample_count, duration)

def show_fps(+frame: U32, world: B.Damage, window: Window,
  start: Nat, now: Nat, duration: Nat, +fps: Nat) -> IO(Unit):
  do IO<Unit>:
    window : Window <- Window.set_title(window,
      "Bullet Cathedral | " ++ Nat.show(fps) ++ " FPS | frame " ++
      U32.show(U32.inc(frame)))
    IO.print("frame " ++ U32.show(U32.inc(frame)) ++ ": " ++
      Nat.show(fps) ++ " FPS")
    next_frame(frame, world, window, start, now, 0, duration)

def report_if(report: Bool, +frame: U32, world: B.Damage,
  window: Window, start: Nat, sample_time: Nat,
  +sample_count: U32, +now: Nat, duration: Nat) -> IO(Unit):
  match report:
    case True{}:
      show_fps(frame, world, window, start, now, duration,
        Nat.div(Nat.mul(U32.to_nat(sample_count), 1000n),
          Nat.max(1n, Nat.sub(now, sample_time))))
    case False{}:
      next_frame(frame, world, window, start, sample_time,
        sample_count, duration)

def stop_if(stop: Bool, +frame: U32, world: B.Damage,
  window: Window, +start: Nat, +sample_time: Nat,
  +sample_count: U32, +now: Nat, duration: Nat) -> IO(Unit):
  match stop:
    case True{}: finish(window, frame, Nat.sub(now, start))
    case False{}:
      report_if(Nat.is_ge(Nat.sub(now, sample_time), 1000n),
        frame, world, window, start, sample_time,
        U32.inc(sample_count), now, duration)

def continue_if(open: Bool, +frame: U32, world: B.Damage,
  window: Window, +start: Nat, +sample_time: Nat,
  +sample_count: U32, +now: Nat, +duration: Nat) -> IO(Unit):
  stop_if(Bool.or(Bool.not(open),
    Nat.is_ge(Nat.sub(now, start), duration)), frame, world,
    window, start, sample_time, sample_count, now, duration)

def after_present(pair: Window & Bool, frame: U32, world: B.Damage,
  start: Nat, sample_time: Nat, sample_count: U32,
  duration: Nat) -> IO(Unit):
  (window, open) = pair
  do IO<Unit>:
    now : Nat <- IO.now()
    continue_if(open, frame, world, window, start, sample_time,
      sample_count, now, duration)

def start_frames(window: Window, +start: Nat, duration: Nat) -> IO(Unit):
  frames(0, B.step_render(0, B.initial()), window,
    start, start, 0, duration)

def run(duration: Nat, +width: U32) -> IO(Unit):
  do IO<Unit>:
    window : Window <- IO.try(Window, Window.open(
      "Bullet Cathedral | CPU transducers", width,
      U32.div(U32.mul(width, 9), 16)))
    start : Nat <- IO.now()
    start_frames(window, start, duration)

def run_args(args: List<String>) -> IO(Unit):
  match args:
    case duration <> width <> rest:
      run(U32.to_nat(B.parsed_u32(U32.read(duration))),
        B.parsed_u32(U32.read(width)))
    case _: run(1800000n, 1280)

def main() -> IO(Unit):
  do IO<Unit>:
    args : List<String> <- IO.args()
    run_args(args)
