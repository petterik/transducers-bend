// Pack Bend's flat U32 array into RGB24 once, then use the usual async IO
// worker. This is an output bridge, not part of the renderer.
static void bullet_rgb_call(IoWork* w) {
  int fd = (int)w->hand;
  ssize_t n = 0;
  for (uint64_t at = 0; n >= 0 && at < w->size; at += (uint64_t)n) {
    n = write(fd, w->data + at, w->size - at);
    if (n == 0) {
      errno = EIO;
      n = -1;
    }
  }
  io_sys_end(w, n);
}

static Term bullet_rgb_pack(Env e, IoWork* w) {
  Term r = w->code != 0 ? io_fail(e, w->code, NULL)
    : io_done(e, term_pak(CID(Unit), 0));
  free(w->data);
  return io_tup(e, io_hand(w->hand), r);
}

Term write_frame_run(Env e, Term* f, IoWork* w) {
  Term pixels = f[1];
  u32 count = (u32)f[2];
  w->hand = (intptr_t)io_hand_v(f[0]);
  w->code = 0;
  if (term_tag(pixels) != TAG_BUF || (u64)count > (1ull << blk_cls(pixels))) {
    w->data = NULL;
    w->size = 0;
    w->code = EINVAL;
    blk_free(e, pixels);
    return bullet_rgb_pack(e, w);
  }
  w->size = (u64)count * 3;
  w->data = io_mem(malloc(w->size));
  Loc loc = blk_loc(e.mem, pixels);
  for (u32 i = 0; i < count; i += 1) {
    u32 color = (u32)blk_read(e.mem, false, loc, i);
    w->data[3ull * i] = (u8)(color >> 16);
    w->data[3ull * i + 1] = (u8)(color >> 8);
    w->data[3ull * i + 2] = (u8)color;
  }
  blk_free(e, pixels);
  return io_work(w, bullet_rgb_call, bullet_rgb_pack);
}

static void __attribute__((constructor)) write_frame_use(void) {
  io_eff(CID(write_frame), write_frame_run, 0);
}
