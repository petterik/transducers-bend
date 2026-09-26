import Base

# Output-only bridge for a packed U32 framebuffer. Simulation and pixel
# computation stay in Bend; the C effect packs RGB bytes for the FIFO.
def write_frame(file: File, pixels: Array<U32>, count: U32) ->
  IO(File & Result<&1, &1, U32 & String, Unit>):
  import "./bullet_cathedral_rgb.c"
