export const MAX_REFERENCE_ASSETS = 10;

export interface MentionParseResult {
  indexes: number[];
  invalid: number[];
}

export interface MentionQuery {
  start: number;
  end: number;
  query: string;
}

export function parseReferenceMentions(prompt: string, assetCount: number): MentionParseResult {
  const indexes = new Set<number>();
  const invalid = new Set<number>();

  for (const match of prompt.matchAll(/@(\d{1,2})(?!\d)/g)) {
    const index = Number(match[1]);
    if (index >= 1 && index <= assetCount && index <= MAX_REFERENCE_ASSETS) {
      indexes.add(index);
    } else {
      invalid.add(index);
    }
  }

  for (const match of prompt.matchAll(/@\[已删除(\d{1,2})\]/g)) {
    invalid.add(Number(match[1]));
  }

  return {
    indexes: [...indexes].sort((left, right) => left - right),
    invalid: [...invalid].sort((left, right) => left - right),
  };
}

export function referencesForPrompt<T>(
  prompt: string,
  assets: T[],
): { assets: T[]; invalid: number[] } {
  const parsed = parseReferenceMentions(prompt, assets.length);
  return {
    assets: parsed.indexes.length
      ? assets.filter((_, index) => parsed.indexes.includes(index + 1))
      : assets,
    invalid: parsed.invalid,
  };
}

export function rewriteMentionsAfterRemoval(prompt: string, removedIndex: number): string {
  return prompt.replace(/@(\d{1,2})(?!\d)/g, (token, rawIndex: string) => {
    const index = Number(rawIndex);
    if (index === removedIndex) return `@[已删除${removedIndex}]`;
    return index > removedIndex ? `@${index - 1}` : token;
  });
}

export function mentionQueryAtCursor(value: string, cursor: number): MentionQuery | null {
  const safeCursor = Math.max(0, Math.min(cursor, value.length));
  const beforeCursor = value.slice(0, safeCursor);
  const match = /@(\d{0,2})$/.exec(beforeCursor);
  if (!match) return null;
  return {
    start: safeCursor - match[0].length,
    end: safeCursor,
    query: match[1],
  };
}

export function replaceMentionQuery(
  value: string,
  cursor: number,
  index: number,
): { value: string; cursor: number } {
  const query = mentionQueryAtCursor(value, cursor);
  if (!query) return { value, cursor };
  const inserted = `@${index} `;
  return {
    value: value.slice(0, query.start) + inserted + value.slice(query.end),
    cursor: query.start + inserted.length,
  };
}
