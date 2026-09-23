// Resolve only a template instance already checked by Bend. def_inst keys
// its ~ arguments by source syntax; checked terms may have extra Ann nodes,
// so use Bend's conversion equality only as a bounded fallback. Ambiguous,
// missing, or large tables refuse specialization.
const STATIC_TEMPLATE_SCAN_LIMIT = 64;
const STATIC_TEMPLATE_TERM_LIMIT = 16384;
function static_template_term_comparable(book: Book, term: HTerm): boolean {
  const lowered = Bend.term_lower(term);
  const text = Bend.term_key(lowered);
  if (text.length > STATIC_TEMPLATE_TERM_LIMIT) return false;
  let fuel = 8192;
  const safe = (value: unknown): boolean => {
    if (--fuel < 0) return false;
    if (Array.isArray(value)) return value.every(safe);
    if (value === null || typeof value !== "object") return true;
    const node = value as Record<string, unknown>;
    if (node.$ === "Ref" && typeof node.k === "string") {
      const def = book.tlds[node.k];
      if (def?.$ === "Def" && (def.u || def.i || def.b)) return false;
    }
    return Object.entries(node).every(([key, child]) =>
      key === "s" || safe(child));
  };
  return safe(lowered);
}

function static_template_instance(book: Book, generic: Bend.Name,
  args: HTerm[]): Bend.Name | null {
  const def = book.tlds[generic];
  const table = book.tmps[generic];
  if (def?.$ !== "Def" || def.x !== args.length || table === undefined) {
    return null;
  }
  const exact_key = args.map((a) => Bend.term_key(Bend.term_lower(a))).join("\n");
  const checked = (name: Bend.Name | undefined): Bend.Name | null => {
    const inst = name === undefined ? undefined : book.tlds[name];
    return inst?.$ === "Def" && inst.x === 0
      && inst.e !== undefined && inst.v !== null ? name as Bend.Name : null;
  };
  const exact = checked(table[exact_key]);
  if (exact !== null) return exact;
  if (!args.every((arg) => static_template_term_comparable(book, arg))) {
    return null;
  }

  const entries = Object.entries(table);
  if (entries.length > STATIC_TEMPLATE_SCAN_LIMIT) return null;
  let found: Bend.Name | null = null;
  for (const [key, name] of entries) {
    const keys = key.split("\n");
    if (keys.length !== args.length) continue;
    let equal = true;
    for (let i = 0; i < keys.length; i++) {
      let expected: HTerm;
      try {
        expected = Bend.term_higher(JSON.parse(keys[i]) as Bend.LTerm);
      } catch {
        equal = false;
        break;
      }
      if (!static_template_term_comparable(book, expected)) {
        equal = false;
        break;
      }
      try {
        if (!Bend.term_compare("EQ", book, args[i], expected)) {
          equal = false;
          break;
        }
      } catch {
        equal = false;
        break;
      }
    }
    if (equal) {
      if (found !== null && found !== name) return null;
      found = name;
    }
  }
  return checked(found ?? undefined);
}

// Checked applications keep type annotations between curried arguments.
// Flatten those annotations for template lookup without changing the term
// that the ordinary evaluator sees.
const STATIC_SPINE_LIMIT = 2048;
function static_unapply(term: HTerm): [HTerm, HTerm[]] | null {
  const args: HTerm[] = [];
  let cur = term;
  for (let fuel = STATIC_SPINE_LIMIT; fuel > 0; fuel--) {
    const x = Bend.term_force(cur);
    if (x.$ === "Ann") {
      cur = x.x;
    } else if (x.$ === "Rwt") {
      cur = x.f;
    } else if (x.$ === "App") {
      args.push(x.x);
      cur = x.f;
    } else {
      args.reverse();
      return [cur, args];
    }
  }
  return null;
}

// Resolve a statically constructed function before lowering its application.
// This is deliberately bounded and call-by-value: a projection must not erase
// evaluation of another field. Foreign calls, unsafe defs, forks and dynamic
// values stop evaluation; failure leaves the original expression intact.
function static_fun(book: Book, t: HTerm): HTerm | null {
  const spine = static_unapply(t);
  if (spine === null) return null;
  const [raw_head, args] = spine;
  const head = Bend.term_strip(raw_head);
  const argc = args.length;
  const def = head.$ === "Ref" ? book.tlds[head.k] : undefined;
  if (head.$ !== "Lam" && (def?.$ !== "Def" || argc < def.n)) return null;
  let fuel = 2048;
  const values = new Map<Bend.Name, HTerm>();
  const fail = {};
  const run = (tm: HTerm): HTerm => {
    if (--fuel < 0) throw fail;
    // A generic Def.e is checked under opaque template parameters, not at
    // the arguments of this call. Resolve to an existing checked instance
    // before evaluating any part of the generic application.
    const spine = static_unapply(Bend.term_force(tm));
    if (spine === null) throw fail;
    const [raw_head, raw_args] = spine;
    const head = Bend.term_strip(raw_head);
    if (head.$ === "Ref") {
      const generic = book.tlds[head.k];
      if (generic?.$ === "Def" && generic.x > 0) {
        if (raw_args.length < generic.x) throw fail;
        const instance = static_template_instance(book, head.k,
          raw_args.slice(0, generic.x));
        if (instance === null) throw fail;
        let resolved: HTerm = Bend.Ref(instance);
        for (const arg of raw_args.slice(generic.x)) {
          resolved = Bend.App(resolved, arg);
        }
        return run(resolved);
      }
    }
    const x = Bend.term_force(tm);
    switch (x.$) {
      case "Ann": return Bend.Ann(run(x.x), x.T, x.s);
      case "Ref": {
        const d = book.tlds[x.k];
        if (x.b || d?.$ !== "Def" || d.u || d.i || !d.e || d.x > 0
          || (d.b && OPERATIONS[eff_name(x.k)] !== undefined)) {
          if (d?.$ === "ADT") return x;
          throw fail;
        }
        const body = d.e;
        return memo(values, x.k, () => run(Bend.term_higher(body)));
      }
      case "App": {
        const f = Bend.term_strip(run(x.f));
        const a = run(x.x);
        if (f.$ === "Lam") return run(f.f(a));
        if (f.$ === "Mat") {
          const c = Bend.term_strip(a);
          if (c.$ !== "Ctr") throw fail;
          let arm: HTerm = f;
          while (Bend.term_strip(arm).$ === "Mat") {
            const m = Bend.term_strip(arm) as Of<"Mat">;
            if (m.k === c.k) {
              return run(c.x.reduce((h, v) => Bend.App(h, v), m.h));
            }
            arm = m.m;
          }
          throw fail;
        }
        throw fail;
      }
      case "Ctr": return Bend.Ctr(x.k, x.x.map(run), x.s);
      case "Let": {
        if (x.v.length !== 1) throw fail;
        return run(x.f(x.v.map(run)));
      }
      case "Rwt": return run(x.f);
      case "Lam": case "Mat": case "Efq": case "Typ": case "All":
      case "ADT": case "Qua": case "Qnt": case "Eql": case "Rfl":
        return x;
      default: throw fail;
    }
  };
  try {
    const out = run(t);
    return Bend.term_strip(out).$ === "Lam" ? out : null;
  } catch (e) {
    if (e !== fail) throw e;
    return null;
  }
}

// Keep annotations and bind a dynamic argument once when eliminating a
// static callback. Re-run on its body so nested callback records disappear.
function specialize(book: Book, tm: HTerm, budget = { left: 256 }): HTerm {
  const x = Bend.term_force(tm);
  switch (x.$) {
    case "Ann": return Bend.Ann(specialize(book, x.x, budget), x.T, x.s);
    case "Lam": return Bend.Lam(x.k, x.i,
      (a: HTerm) => specialize(book, x.f(a), budget), x.s, x.q);
    case "Mat": return Bend.Mat(x.k, specialize(book, x.h, budget),
      specialize(book, x.m, budget), x.s);
    case "Let": return Bend.Let(x.k, x.i, x.v.map((v) => specialize(book, v, budget)),
      (as: HTerm[]) => specialize(book, x.f(as), budget), x.s, x.q);
    case "Ctr": return term_const(x) ? x
      : Bend.Ctr(x.k, x.x.map((v) => specialize(book, v, budget)), x.s);
    case "Rwt": return specialize(book, x.f, budget);
    case "App": {
      const f = specialize(book, x.f, budget);
      const a = specialize(book, x.x, budget);
      const held = Bend.term_strip(f);
      if (held.$ === "Let") {
        const T = ty_ann(f);
        return Bend.Let(held.k, held.i, held.v, (as: HTerm[]) => {
          const b = held.f(as);
          return specialize(book, Bend.App(T === null ? b : Bend.Ann(b, T), a), budget);
        }, held.s, held.q);
      }
      // A bare named function stays a call. Only computed function heads
      // need specialization; this does not inline every ordinary call.
      if (Bend.term_strip(f).$ !== "App"
        && Bend.term_strip(f).$ !== "Lam") return Bend.App(f, a, x.s);
      const v = budget.left > 0 ? static_fun(book, f) : null;
      const lam = v === null ? null : Bend.term_strip(v);
      if (lam?.$ !== "Lam") return Bend.App(f, a, x.s);
      const ty = ty_all(book, ty_ann(f));
      if (ty === null) return Bend.App(f, a, x.s);
      budget.left--;
      if (!quant_live(ty.q) || term_const(a)
        || Bend.term_strip(a).$ === "Var") {
        return specialize(book, lam.f(a), budget);
      }
      return Bend.Let([lam.k], [0], [Bend.Ann(a, ty.A)],
        (as: HTerm[]) => specialize(book, lam.f(as[0]), budget), x.s, [ty.q]);
    }
    default: return x;
  }
}
