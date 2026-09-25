// Experimental, name-independent inference for explicit ~?AUTO placeholders.
// It only solves leading template arguments that appear structurally in
// checked runtime-argument types. No arbitrary unification or runtime value
// evaluation is attempted.
function infer_template_autos(book: Book, lhs: LHS, tm: Extract<HTerm, { $: "Ref" }>,
  def: Def, sp: HTerm[], ctx: Ctx, d: number): HTerm[] {
  const xs = sp.slice(0, def.x);
  const autos = xs.map((a, i) => a.$ === "Hol" && a.k === "AUTO" ? i : -1)
    .filter((i) => i >= 0);
  if (autos.length === 0) return xs;
  if (sp.length <= def.x) {
    throw Err(book, ctx, "a runtime argument whose type determines ~?AUTO", tm, tm.s, lhs.def);
  }
  let T = def.T;
  const marks = new Map<number, HTerm>();
  for (let i = 0; i < def.x; i++) {
    const h = tele_head(book, T, ctx, lhs.def, tm.s);
    const a = autos.includes(i) ? Hol("__AUTO_" + i, tm.s) : xs[i];
    if (autos.includes(i)) marks.set(i, a);
    T = h.B(a);
  }
  const found = new Map<number, HTerm>();
  let fuel = 512;
  const unify = (want: HTerm, got: HTerm): boolean => {
    if (--fuel < 0) return false;
    const w = term_strip(term_wnf(book, want));
    const g = term_strip(term_wnf(book, got));
    if (w.$ === "Hol" && w.k.startsWith("__AUTO_")) {
      const i = Number(w.k.slice(7));
      // Match the internal node itself, not a forgeable user-written hole.
      if (w !== marks.get(i)) return false;
      const prior = found.get(i);
      if (prior !== undefined) return term_compare("EQ", book, prior, g, d);
      found.set(i, g);
      return true;
    }
    if (w.$ === "ADT" && g.$ === "ADT"
      && w.k === g.k && w.x.length === g.x.length) {
      return w.x.every((a, i) => unify(a, g.x[i]));
    }
    return term_compare("EQ", book, w, g, d);
  };
  let last: HTerm = tm;
  for (let j = def.x; j < sp.length && found.size < autos.length; j++) {
    const h = tele_head(book, T, ctx, lhs.def, tm.s);
    const actual = term_infer(book, lhs, sp[j], Lone(), ctx, d).ty;
    last = actual;
    if (!unify(h.A, actual)) {
      throw Err(book, ctx, "~?AUTO solved by a unique structural type match", actual, tm.s, lhs.def);
    }
    T = h.B(sp[j]);
  }
  if (autos.some((i) => !found.has(i))) {
    throw Err(book, ctx, "~?AUTO solved by a unique structural type match", last, tm.s, lhs.def);
  }
  for (const i of autos) xs[i] = found.get(i)!;
  return xs;
}
