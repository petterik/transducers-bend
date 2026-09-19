// Experimental native-emitter pass. Deliberately accepts a tiny C grammar,
// not arbitrary C expressions. Unknown syntax means leave the match alone.
// Inputs must already be materialized, unboxed integer words.
export function scalarSelect(
  arms: string[][], inputs: Set<string>, outputs: string[], condition: string,
): string[] | null {
  if (arms.length !== 2 || outputs.length === 0 || outputs.length > 8
    || outputs.some(x => inputs.has(x))) return null;
  const parse = (lines: string[]) => {
    if (lines.length > 32) return null;
    const env = new Map([...inputs].map(x => [x, x]));
    const result = new Map<string, string>();
    const expand = (s: string): string | null => {
      if (s.length > 2048) return null;
      const tokens = s.match(/U32_BIN|[A-Za-z_]\w*|0x[0-9a-f]+(?:ull)?|\d+(?:ull)?|==|!=|<=|>=|[(),+*\-&|^<>]/gi);
      if (!tokens || tokens.join('') !== s.replace(/\s/g, '')) return null;
      let at = 0;
      const expr = (): string | null => {
        const t = tokens[at++];
        if (t === 'U32_BIN') {
          if (tokens[at++] !== '(') return null;
          const a = expr();
          if (a === null || tokens[at++] !== ',') return null;
          const op = tokens[at++];
          if (!['+', '-', '*', '&', '|', '^', '==', '!=', '<', '<=', '>', '>='].includes(op)
            || tokens[at++] !== ',') return null;
          const b = expr();
          if (b === null || tokens[at++] !== ')') return null;
          return `U32_BIN(${a}, ${op}, ${b})`;
        }
        if (/^(?:0x[0-9a-f]+|\d+)(?:ull)?$/i.test(t ?? '')) {
          return BigInt(t.replace(/ull$/i, '')) <= 0xffffffffffffffffn ? t : null;
        }
        return env.get(t) ?? null;
      };
      const value = expr();
      return at === tokens.length && value !== null && value.length <= 2048 ? value : null;
    };
    for (const raw of lines) {
      const line = raw.trim();
      const m = /^(?:(u32|u64|Term) )?([A-Za-z_]\w*) = (.*);$/.exec(line);
      if (!m) return null;
      const [, decl, name, rhs] = m;
      if (decl ? env.has(name) || outputs.includes(name) : !outputs.includes(name)) return null;
      const value = expand(rhs);
      if (value === null || result.has(name)) return null;
      // u32 temporaries truncate; Term and u64 preserve the whole word.
      const bound = decl === 'u32' ? `U32_BIN(${value}, +, 0)` : value;
      env.set(name, bound);
      if (!decl) result.set(name, bound);
    }
    return result.size === outputs.length ? result : null;
  };
  const a = parse(arms[0]), b = parse(arms[1]);
  if (!a || !b) return null;
  return outputs.map(x => `${x} = (${condition}) ? (${a.get(x)}) : (${b.get(x)});`);
}
