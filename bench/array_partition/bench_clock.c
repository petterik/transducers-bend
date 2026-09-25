Term now_us_run(Env e, Term* f, IoWork* w) {
  return (Term)(io_tick() / 1000ull);
}

static void __attribute__((constructor)) now_us_use(void) {
  io_eff(CID(now_us), now_us_run, 0);
}
