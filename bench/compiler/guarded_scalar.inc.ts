// Experimental typed scalar-region analysis, appended to isolated comp.ts only.
// No source/helper names or generated-C parsing participate in recognition.
type GX = {
  op: string;
  a: GX[];
  n?: number;
  id?: number;
  size?: number;
};
type GV = {
  xs: GX[];
  lay: Lay;
};
type GP = [GX, boolean][];
type GR = {
  pc: GP;
  v: GV;
};
const GN = 281474976710655;
const gx = (op: string, ...a: GX[]): GX => {
  const size = 1 + a.reduce((n, x) => n + (x.size ?? 1), 0);
  if (size > 256)
    throw new GReject("expression size");
  return { op, a, size };
};
const gn = (n: number): GX => ({ op: "lit", a: [], n });
const gkey = (x: GX): string => JSON.stringify(x, (k, v) => k === "size" ? undefined : v);
const geq = (a: GX, b: GX): boolean => gkey(a) === gkey(b);
class GReject extends Error {
}
function guarded_scalar(fl: File, ck: Call, ers: HTerm[], name: string, original: string): string | null {
  const sig = sig_def(fl, ck.k);
  if ([...sig.lays, sig.ret].some(l => l.ks.includes("box"))
    || sig.ret.ks.length > 8 || sig.lays.reduce((n, l) => n + l.ks.length, 0) > 12)
    return null;
  let fuel = 3000, leaves = 0, serial = 0;
  const budget = () => { if (--fuel < 0)
    throw new GReject("budget"); };
  const bounds: [number, number][] = [];
  const selectors: GX[] = [];
  const input = (l: Lay): GV => {
    const xs = l.ks.map(k => {
      const id = serial++;
      bounds[id] = [0, k === "w64" ? GN : 4294967295];
      return { op: "var", a: [], id } as GX;
    });
    const tags = (s: Lay, at: number) => {
      if (!s.arms)
        return;
      if (s.arms.length > 1) {
        bounds[xs[at].id!] = [0, s.arms.length - 1];
        if (s.arms.length === 2 && s.arms.every(a => a.fs.length === 0))
          selectors.push(xs[at]);
      }
      // Overlapping sum payloads may have different types/ranges: never infer
      // a payload tag bound unless every arm has the identical field layout.
      if (s.arms.every(a => JSON.stringify(a.fs) === JSON.stringify(s.arms![0].fs)))
        s.arms[0].fs.forEach(f => tags(f.lay, at + f.at));
    };
    tags(l, 0);
    return { xs, lay: l };
  };
  const args = sig.lays.map(input);
  if (!selectors.length)
    return null;
  const affine = (x: GX): [number, number] | null => x.op === "var" ? [x.id!, 0]
    : x.op === "offset" && x.a[1].op === "lit" ? (() => {
      const b = affine(x.a[0]);
      return b && [b[0], b[1] + x.a[1].n!] as [number, number];
    })() : null;
  const range = (x: GX, pc: GP): [number, number] => {
    if (x.op === "lit")
      return [x.n!, x.n!];
    const af = affine(x);
    if (!af)
      return [0, x.op === "eq" ? 1 : x.op === "add32" ? 4294967295 : GN];
    let [lo, hi] = bounds[af[0]];
    for (const [c, yes] of pc) {
      if (c.op !== "eq" || c.a[1].op !== "lit")
        continue;
      const b = affine(c.a[0]);
      if (!b || b[0] !== af[0])
        continue;
      const n = c.a[1].n! - b[1];
      if (yes) {
        lo = Math.max(lo, n);
        hi = Math.min(hi, n);
      }
      else {
        if (lo === n)
          lo++;
        if (hi === n)
          hi--;
      }
    }
    return [lo + af[1], hi + af[1]];
  };
  const simp = (x: GX, pc: GP): GX => {
    budget();
    const known = pc.find(([c]) => geq(c, x));
    if (known)
      return gn(+known[1]);
    if (x.op === "var" || x.op === "offset") {
      const [lo, hi] = range(x, pc);
      if (lo === hi)
        return gn(lo);
    }
    if (x.op === "lit" || x.op === "var")
      return x;
    const a = x.a.map(y => simp(y, pc));
    if (x.op === "offset") {
      if (a[0].op === "lit")
        return gn(a[0].n! + a[1].n!);
      if (a[1].n === 0)
        return a[0];
      if (a[0].op === "offset")
        return simp(gx("offset", a[0].a[0], gn(a[0].a[1].n! + a[1].n!)), pc);
    }
    if (x.op === "eq") {
      if (geq(a[0], a[1]))
        return gn(1);
      const [l, h] = range(a[0], pc), [m, n] = range(a[1], pc);
      if (h < m || n < l)
        return gn(0);
      if (l === h && m === n)
        return gn(+(l === m));
    }
    if (x.op === "ite") {
      if (a[0].op === "lit")
        return a[a[0].n ? 1 : 2];
      if (geq(a[1], a[2]))
        return a[1];
      if (a[1].n === 1 && a[2].n === 0)
        return a[0];
    }
    return { ...x, a };
  };
  const offset = (x: GX, n: number, pc: GP): GX => {
    const [lo, hi] = range(x, pc);
    if (lo + n < 0 || hi + n > GN)
      throw new GReject("checked Nat");
    return simp(gx("offset", x, gn(n)), pc);
  };
  const cast = (v: GV, l: Lay): GV => {
    if (!lay_eq(v.lay, l))
      throw new GReject("layout conversion");
    return v;
  };
  const visit = (t: HTerm, ty0: HTerm | null, es: HTerm[], vs: GV[], env: Map<Probe, GV>, pc: GP, stack: string[]): GR[] => {
    budget();
    if (stack.length > 16)
      throw new GReject("depth");
    const [x, ty] = ty_peel(t, ty0);
    if (x.$ === "Lam") {
      const all = ty_all(fl.book, ty);
      if (!all)
        throw new GReject("untyped lambda");
      if (!quant_live(all.q)) {
        const e = es[0];
        if (!e)
          throw new GReject("erasure");
        return visit(x.f(e), all.B(e), es.slice(1), vs, env, pc, stack);
      }
      if (!vs.length)
        throw new GReject("closure");
      const o = term_open(x), ne = new Map(env);
      ne.set(o.ps[0], cast(vs[0], lay_of(fl.book, all.A)));
      return visit(o.b, all.B(DUMMY), es, vs.slice(1), ne, pc, stack);
    }
    if (x.$ === "Mat") {
      if (!vs.length)
        throw new GReject("match closure");
      const all = ty_all(fl.book, ty);
      if (!all)
        throw new GReject("match type");
      const adt = mat_adt(fl.book, all.A), l = lay_of(fl.book, all.A), s = cast(vs[0], l);
      if (l.ks.includes("box") || adt.k === "U32" || adt.k === "F32")
        throw new GReject("match representation");
      const { arms, end } = mat_arms(x);
      if (Bend.term_strip(end).$ !== "Efq")
        throw new GReject("open match");
      const walk = (i: number, facts: GP): GR[] => {
        if (i >= arms.length)
          throw new GReject("nonexhaustive");
        const [k, h] = arms[i];
        let fields: GV[], cond: GX;
        if (adt.k === "Nat") {
          if (k !== "Zero" && k !== "Succ")
            throw new GReject("Nat arm");
          cond = gx("eq", s.xs[0], gn(0));
          if (k === "Succ")
            cond = gx("eq", cond, gn(0));
          fields = [];
        }
        else {
          const arm = lay_arm(l, k);
          cond = l.arms!.length === 1 ? gn(1) : gx("eq", s.xs[0], gn(l.arms!.indexOf(arm)));
          fields = arm.fs.map(f => ({ xs: s.xs.slice(f.at, f.at + f.lay.ks.length), lay: f.lay }));
        }
        const c = simp(cond, facts), result: GR[] = [];
        if (c.n !== 0) {
          const p: GP = c.n === 1 ? facts : [...facts, [cond, true]];
          if (adt.k === "Nat" && k === "Succ")
            fields = [{ xs: [offset(s.xs[0], -1, p)], lay: l }];
          result.push(...visit(h, null, es, [...fields, ...vs.slice(1)], new Map(env), p, stack));
        }
        if (c.n !== 1) {
          // A final exhaustive arm is reached with its tag known. Nat Succ
          // uses the complement of the preceding Zero test, never a guess.
          result.push(...walk(i + 1, [...facts, [cond, false]]));
        }
        return result;
      };
      return walk(0, pc);
    }
    if (vs.length)
      throw new GReject("eta/overapplication");
    if (x.$ === "Var") {
      const v = env.get(probe_of(x));
      if (!v)
        throw new GReject("scope");
      return [{ pc, v }];
    }
    const each = (ts: HTerm[], done: (vs: GV[], pc: GP) => GR[], i = 0, out: GV[] = [], facts = pc): GR[] => i === ts.length ? done(out, facts) : visit(ts[i], null, [], [], env, facts, stack).flatMap(r => each(ts, done, i + 1, [...out, r.v], r.pc));
    if (x.$ === "Let") {
      if (x.k.length !== 1)
        throw new GReject("fork");
      const o = term_open(x);
      return each(x.v, (vals, p) => { const ne = new Map(env); ne.set(o.ps[0], vals[0]); return visit(o.b, null, es, [], ne, p, stack); });
    }
    if (x.$ === "Ctr") {
      const [adt, u] = ctr_adt(fl, x, ty), l = lay_of(fl.book, adt);
      if (l.ks.includes("box") || adt.k === "F32")
        throw new GReject("constructor");
      if (u !== null)
        return [{ pc, v: { xs: [gn(Number(u))], lay: l } }];
      return each(ctr_flds(fl.book, x.k, x.x), (vals, p) => {
        let xs = l.ks.map(() => gn(0));
        if (adt.k === "Nat")
          xs = [vals.length ? offset(vals[0].xs[0], 1, p) : gn(0)];
        else {
          const arm = lay_arm(l, x.k);
          if (l.arms!.length > 1)
            xs[0] = gn(l.arms!.indexOf(arm));
          vals.forEach((v, j) => cast(v, arm.fs[j].lay).xs.forEach((e, n) => xs[arm.fs[j].at + n] = e));
        }
        if (++leaves > 256)
          throw new GReject("leaves");
        return [{ pc: p, v: { xs, lay: l } }];
      });
    }
    if (x.$ === "App" || x.$ === "Ref") {
      const m = term_spine(fl, x);
      if (m.t.$ !== "Ref")
        throw new GReject("indirect call");
      const k = m.t.k, op = eff_name(k), intr = intr_of(fl, k);
      if (intr) {
        // Semantic intrinsic identity, not its generated spelling. This first
        // region admits wrapping addition only; all other operations bail out.
        if (op !== "u32_add")
          throw new GReject("intrinsic " + op);
        return each(m.args, (v, p) => [{ pc: p, v: { xs: [gx("add32", v[0].xs[0], v[1].xs[0])], lay: W32 } }]);
      }
      const d = m.tld;
      if (!m.call || m.call.bang || !d || d.$ !== "Def" || !d.h || def_foreign(d)
        || stack.includes(k) || !flat_of(k))
        throw new GReject("opaque/recursive call");
      const ds = tele_unbind(fl.book, d.T).doms;
      const er = m.all.filter((_, i) => i < d.n && !quant_live(ds[i][0]));
      return each(m.args, (v, p) => visit(d.h!, d.T, er, v, new Map(), p, [...stack, k]));
    }
    throw new GReject("term " + x.$);
  };
  try {
    const d = fl.book.tlds[ck.k] as Def;
    const rows = visit(d.h!, d.T, ers, args, new Map(), [], [ck.k]);
    if (rows.length < 3 || rows.length > 32)
      return null;
    // Independent budget for bounded simplification/search.
    fuel = 60000;
    const tests: GX[] = [];
    rows.forEach(r => r.pc.forEach(([x]) => {
      if (x.op === "eq" && x.a[0].op === "var" && x.a[1].op === "lit" && !tests.some(t => geq(t, x)))
        tests.push(x);
    }));
    if (tests.length > 8)
      return null;
    const invariants = sig.ret.ks.map((_, j) => {
      const ins = args.flatMap(v => v.xs);
      return ins.find(x => rows.every(r => geq(simp(r.v.xs[j], r.pc), simp(x, r.pc))));
    });
    const build = (rs: GR[], j: number, pc: GP): GX => {
      budget();
      if (!rs.length)
        throw new GReject("empty join");
      const vals = rs.map(r => simp(r.v.xs[j], pc));
      for (const v of vals)
        if (rs.every(r => geq(simp(r.v.xs[j], [...r.pc, ...pc]), simp(v, [...r.pc, ...pc]))))
          return v;
      const c = rs.flatMap(r => r.pc.map(([x]) => x)).find(x => simp(x, pc).op !== "lit");
      if (!c)
        throw new GReject("join");
      const part = (yes: boolean) => rs.filter(r => simp(c, r.pc).n !== +!yes);
      return simp(gx("ite", c, build(part(true), j, [...pc, [c, true]]), build(part(false), j, [...pc, [c, false]])), pc);
    };
    // Re-check totality after joining paths: proving a decrement in its
    // original branch does not license evaluating it in a wider region.
    const total = (x: GX, pc: GP): boolean => {
      budget();
      if (x.op === "offset") {
        const [lo, hi] = range(x, pc);
        return lo >= 0 && hi <= GN && lo <= hi && total(x.a[0], pc);
      }
      if (x.op === "ite")
        return total(x.a[0], pc)
          && total(x.a[1], [...pc, [x.a[0], true]])
          && total(x.a[2], [...pc, [x.a[0], false]]);
      return x.a.every(a => total(a, pc));
    };
    const render = (x: GX): string => x.op === "lit" ? `${x.n}ull` : x.op === "var" ? `r${x.id}`
      : x.op === "offset" ? `(${render(x.a[0])} ${x.a[1].n! < 0 ? "-" : "+"} ${Math.abs(x.a[1].n!)}ull)`
        : x.op === "eq" ? `(${render(x.a[0])} == ${render(x.a[1])})`
          : x.op === "add32" ? `(u32)(${render(x.a[0])} + ${render(x.a[1])})`
            : x.op === "ite" ? `(${render(x.a[0])} ? ${render(x.a[1])} : ${render(x.a[2])})`
              : (() => { throw new GReject("render"); })();
    for (const selector of selectors) {
      const guards = tests.filter(x => !geq(x.a[0], selector));
      // Exactly two state tests bounds outlining and code growth. No hint that
      // their fallback is rare is inferred from a datatype or field name.
      for (let a = 0; a < guards.length; a++)
        for (let b = a + 1; b < guards.length; b++)
          for (let bits = 0; bits < 4; bits++) {
            const pc: GP = [[guards[a], !!(bits & 1)], [guards[b], !!(bits & 2)]];
            const rs = rows.filter(r => pc.every(([c, y]) => simp(c, r.pc).n !== +!y));
            if (rs.length < 2 || rs.length === rows.length)
              continue;
            let outputs = sig.ret.ks.map((_, j) => build(rs, j, pc));
            // Recover a Boolean result from a computed scalar result, by checking
            // equality in every original path under the proposed guard.
            for (let j = 0; j < outputs.length; j++)
              if (sig.ret.ks[j] === "w32")
                for (let k = 0; k < outputs.length; k++)
                  if (sig.ret.ks[k] === "w64" && rs.every(r => {
                    const p = [...r.pc, ...pc];
                    return geq(simp(r.v.xs[j], p), simp(gx("eq", r.v.xs[k], gn(0)), p));
                  }))
                    outputs[j] = { op: "outzero", a: [], id: k };
            outputs = outputs.map((x, j) => invariants[j] ?? x);
            const selected = (x: GX): boolean => x.op !== "ite" ? x.a.every(selected)
              : x.a[0].op === "eq" && geq(x.a[0].a[0], selector) && x.a[0].a[1].op === "lit"
                && x.a.slice(1).every(y => !JSON.stringify(y).includes('"ite"'));
            if (!outputs.every(selected) || !outputs.every(x => total(x, pc)) || !outputs.some(x => x.op === "outzero")
              || outputs.filter(x => x.op === "ite").length < 2)
              continue;
            const guard = pc.map(([x, y]) => `${y ? "" : "!"}${render(x)}`).join(" && ");
            const decl = sig.lays.flatMap(l => l.ks).map((k, i) => `, ${lay_c(k)} r${i}`).join("");
            const slow = name + "_guarded_fallback";
            const saved = original.replace(new RegExp(`^(INLINE|FAR) Term ${name}\\(`), `static __attribute__((noinline, cold)) Term ${slow}(`);
            const lines = [`/* guarded_scalar: typed region; ${rows.length} paths; expression-derived invariants */`,
              saved, `INLINE Term ${name}(Env e, THR Term* o${decl}) {`,
              `  if (!(${guard})) {`,
              `    if (!${slow}(e, o${bounds.map((_, i) => `, r${i}`).join("")})) return 0;`,
              ...invariants.flatMap((x, j) => x ? [`    o[${j}] = ${render(x)};`] : []),
              "    return 1;", "  }"];
            outputs.forEach((x, j) => { if (x.op !== "outzero")
              lines.push(`  Term g${j} = ${render(x)};`); });
            outputs.forEach((x, j) => lines.push(`  o[${j}] = ${x.op === "outzero" ? `(g${x.id} == 0)` : `g${j}`};`));
            lines.push("  return 1;", "}");
            // Host-only experiment: device sees exactly the original helper.
            return ["#if !defined(__METAL_VERSION__) && !defined(__CUDACC__) && !defined(__CUDACC_RTC__)", ...lines, "#else", original, "#endif"].join("\n");
          }
    }
  }
  catch (e) {
    if (!(e instanceof GReject))
      throw e;
    if (process.env.BEND_GUARDED_TRACE)
      console.error(`guarded reject ${ck.k}: ${e.message}`);
  }
  return null;
}
