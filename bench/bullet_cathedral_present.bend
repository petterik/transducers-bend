import Base

# Present a finished 1920x1080 CPU framebuffer in a native Window. The
# returned Bool is False after the close button or Escape key is pressed.
def present(window: Window, pixels: Array<U32>) -> IO(Window & Bool):
  import "./bullet_cathedral_present.c"
