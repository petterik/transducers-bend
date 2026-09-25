// Isolated experiment: a nominal value may convert to a nominal expected type
// through one method owned by its defining type. The method name is derived
// from the expected type's simple name, not from a collection registry.
function companion_marked(book: Book, expected: HTerm): boolean {
  const e = term_strip(term_wnf(book, expected));
  if (e.$ !== "ADT") return false;
  const marker = book.tlds[e.k + ".allow_companion"];
  if (marker?.$ !== "Def" || marker.n !== 0 || marker.x !== 0
    || marker.v === null) return false;
  const marker_result = term_strip(term_wnf(book, marker.T));
  if (marker_result.$ !== "ADT" || marker_result.k !== "Unit"
    || marker_result.x.length !== 0) return false;
  return true;
}

function companion_method(book: Book, actual: HTerm, expected: HTerm): Name | null {
  const a = term_strip(term_wnf(book, actual));
  const e = term_strip(term_wnf(book, expected));
  if (a.$ !== "ADT" || e.$ !== "ADT" || a.k === e.k
    || !companion_marked(book, e)) return null;
  const simple = e.k.slice(e.k.lastIndexOf(".") + 1);
  if (simple.length === 0) return null;
  const suffix = simple[0].toLowerCase() + simple.slice(1);
  const own = a.k + "." + suffix;
  const own_def = book.tlds[own];
  if (own_def?.$ === "Def" && own_def.v !== null) return own;
  // Base cannot import the protocol library. For a Base-owned nominal type,
  // let that protocol's own module define its one canonical adapter instead.
  if (book.tlds[a.k]?.b !== true) return null;
  const target_module = e.k.slice(0, e.k.lastIndexOf("."));
  const extension = target_module + "." + a.k + "." + suffix;
  const extension_def = book.tlds[extension];
  return extension_def?.$ === "Def" && extension_def.v !== null ? extension : null;
}

function companion_call(book: Book, method: Name, arg: HTerm): HTerm {
  const def = book.tlds[method] as Def;
  let out: HTerm = Ref(method, arg.s);
  for (let i = 0; i < def.x; i++) out = App(out, Hol("AUTO", arg.s), arg.s);
  return App(out, arg, arg.s);
}
