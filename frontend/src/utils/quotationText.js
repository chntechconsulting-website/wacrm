/**
 * Lightweight quotation text helpers.
 *
 * This module intentionally has no imports. It is used by the WAQuote list
 * page so the page does not have to pull in the pdfmake bundle just to split
 * an item description into display lines.
 */

export function splitDescriptionIntoLines(rawDescription) {
  if (!rawDescription) return ['—'];

  // Normalize and mend any accidental linebreaks inside key labels
  const rawStr = String(rawDescription)
    .replace(/No\.?\s*Of\s*[\r\n]+\s*Onboardings?/gi, 'No. of Onboardings')
    .replace(/Unit\s*[\r\n]+\s*Price/gi, 'Unit Price')
    .trim();

  // Split on existing linebreaks first
  const rawLines = rawStr.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);

  const finalLines = [];
  // Match whole labels so the word "Onboardings" inside "No. of Onboardings"
  // is consumed together with its label. Each label stays with its value.
  const labelPattern = /\b(?:WaPayroll|Duration|No\.?\s*Of\s+onboardings?|onboardings?|Unit\s*Price|Price\s*per\s*user|Plan(?=\s*:)|SIM\s*Card|FACE\+FINGER)\b\s*:?/gi;

  for (const line of rawLines) {
    const normalized = line.replace(/\s+/g, ' ').trim();
    const matches = [...normalized.matchAll(labelPattern)];
    if (matches.length === 0) {
      finalLines.push(line);
      continue;
    }

    const base = normalized.slice(0, matches[0].index).trim();
    if (base) finalLines.push(base);

    matches.forEach((match, index) => {
      const start = match.index;
      const end = index + 1 < matches.length ? matches[index + 1].index : normalized.length;
      const segment = normalized.slice(start, end).trim();
      if (segment) finalLines.push(segment);
    });
  }

  return finalLines.length > 0 ? finalLines : ['—'];
}
