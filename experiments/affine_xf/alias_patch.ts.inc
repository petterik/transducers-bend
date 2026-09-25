  // Experimental: a local alias of closed static code may be used as a
  // template argument. The candidate checks the resolved expression in the
  // empty context as usual; an unresolved runtime parameter is still refused.
  // Only substitute inert values. A let-bound call may diverge (for example
  // through @unsafe), so erasing its evaluation would change source semantics.
  const inert_alias = (arg: HTerm, fuel = 128): boolean => {
    if (fuel === 0) return false;
    switch (arg.$) {
      case "Ann": return inert_alias(arg.x, fuel - 1);
      case "Var": return arg.v !== undefined && inert_alias(arg.v, fuel - 1);
      case "Ref": case "Lam": case "Lit": return true;
      case "Ctr": return arg.x.every((field) => inert_alias(field, fuel - 1));
      default: return false;
    }
  };
  let alias_fuel = 512;
  const resolve_alias = (arg: HTerm): HTerm => {
    if (--alias_fuel < 0) return arg;
    switch (arg.$) {
      case "Var": return arg.v !== undefined && inert_alias(arg.v)
        ? resolve_alias(arg.v) : arg;
      case "Ann": return Ann(resolve_alias(arg.x), arg.T, arg.s);
      case "App": return App(resolve_alias(arg.f), resolve_alias(arg.x), arg.s);
      case "Lam": return Lam(arg.k, arg.i, (x: HTerm) =>
        resolve_alias(arg.f(x)), arg.s, arg.q);
      case "Ctr": return Ctr(arg.k, arg.x.map(resolve_alias), arg.s);
      default: return arg;
    }
  };
  const xs = sp.slice(0, def.x).map((arg) => resolve_alias(arg));
