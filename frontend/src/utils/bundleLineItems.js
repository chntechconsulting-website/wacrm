/**
 * Helpers for WAHRMS bundle subscription line items.
 *
 * The editor keeps three independent values (duration, onboarding count and
 * unit price) and rebuilds the human readable description used by previews,
 * PDFs and saved documents. `rate` remains the authoritative unit price.
 */

const DETAIL_LABEL_PATTERN = /(?:\bDuration\s*:|\bNo\.?\s*Of\s*Onboardings?\s*:|\bUnit\s*Price\s*:|\bPrice\s*per\s*user\s*:)/i;
const DETAIL_LINE_PATTERN = /^\s*(?:Duration\b|No\.?\s*Of\s*Onboardings?\b|Unit\s*Price\b|Price\s*per\s*user\b)/i;

const DURATION_PATTERN = /Duration\s*:?\s*(\d+(?:\.\d+)?)/i;
const ONBOARDING_PATTERN = /No\.?\s*Of\s*Onboardings?\s*:?\s*(\d+(?:\.\d+)?)/i;
const UNIT_PRICE_PATTERN = /(?:Unit\s*Price|Price\s*per\s*user)\s*:?\s*(?:₹|Rs\.?|INR)?\s*(\d+(?:\.\d+)?)/i;

export function toPositiveInteger(value) {
  if (value === null || value === undefined || value === '') return null;
  const number = Number(value);
  if (!Number.isFinite(number) || number <= 0 || !Number.isInteger(number)) return null;
  return number;
}

export function toNonNegativeNumber(value) {
  if (value === null || value === undefined || value === '') return null;
  const number = Number(value);
  if (!Number.isFinite(number) || number < 0) return null;
  return number;
}

/**
 * Split a saved bundle description into its base text and structured values.
 * Legacy descriptions that only contain the composite text are supported.
 */
export function parseBundleDetail(rawDescription) {
  const description = String(rawDescription || '').trim();
  if (!description) {
    return {
      baseDescription: '',
      durationMonths: null,
      onboardingCount: null,
      unitPrice: null
    };
  }

  const durationMatch = description.match(DURATION_PATTERN);
  const onboardingMatch = description.match(ONBOARDING_PATTERN);
  const unitPriceMatch = description.match(UNIT_PRICE_PATTERN);

  const firstDetailIndex = description.search(DETAIL_LABEL_PATTERN);
  const baseSource = firstDetailIndex > 0 ? description.slice(0, firstDetailIndex) : (firstDetailIndex === 0 ? '' : description);
  const baseDescription = baseSource
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line && !DETAIL_LINE_PATTERN.test(line))
    .join('\n')
    .trim();

  return {
    baseDescription,
    durationMonths: durationMatch ? toPositiveInteger(durationMatch[1]) : null,
    onboardingCount: onboardingMatch ? toPositiveInteger(onboardingMatch[1]) : null,
    unitPrice: unitPriceMatch ? toNonNegativeNumber(unitPriceMatch[1]) : null
  };
}

function formatAmount(value) {
  return new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 }).format(value);
}

/**
 * Build the text-only bundle detail block used by the preview and PDF.
 * All three lines are always present; empty or invalid values use an em dash
 * so the document never silently drops a bundle detail.
 */
export function formatBundleDescription({
  baseDescription = '',
  durationMonths = '',
  onboardingCount = '',
  unitPrice = ''
} = {}) {
  const lines = [];
  const base = String(baseDescription || '').trim();
  if (base) lines.push(base);

  const duration = toPositiveInteger(durationMonths);
  lines.push(`Duration: ${duration !== null ? `${duration} Months` : '—'}`);

  const onboardings = toPositiveInteger(onboardingCount);
  lines.push(`No. of Onboardings: ${onboardings !== null ? onboardings : '—'}`);

  const price = toNonNegativeNumber(unitPrice);
  lines.push(`Unit Price: ${price !== null ? `₹${formatAmount(price)}` : '—'}`);

  return lines.join('\n');
}

/**
 * Single source of truth for the automatic quantity rule.
 * Returns null when either input is empty or invalid.
 */
export function calculateBundleQuantity(durationMonths, onboardingCount) {
  const duration = toPositiveInteger(durationMonths);
  const onboardings = toPositiveInteger(onboardingCount);
  if (duration === null || onboardings === null) return null;
  return duration * onboardings;
}

/**
 * Subscription modules use the three structured inputs; hardware/services
 * included in the same package keep the normal description editor.
 */
export function isBundleSubscriptionItem(item = {}) {
  if (item.isBundleDetail === true) return true;
  if (!item.isBundleItem && !item.bundleId) return false;

  const itemCode = String(item.itemCode || item.item_code || '').toUpperCase();
  if (itemCode.endsWith('_SUB')) return true;

  const itemName = String(item.name || '').toLowerCase();
  if (itemName.includes('subscription')) return true;

  return DETAIL_LABEL_PATTERN.test(String(item.description || ''));
}

/**
 * Build the structured fields for a subscription module loaded from the
 * bundle master. Arbitrary values embedded in the old master description are
 * intentionally discarded; only the real package rate is carried forward.
 */
export function createBundleSubscriptionFields(item = {}) {
  const parsed = parseBundleDetail(item.description || item.name || '');
  const baseDescription = String(item.name || '').trim()
    || parsed.baseDescription
    || String(item.description || '').trim();
  const rate = toNonNegativeNumber(item.rate);

  return {
    baseDescription,
    durationMonths: '',
    onboardingCount: '',
    rate: rate === null ? 0 : rate,
    qty: 0,
    description: formatBundleDescription({
      baseDescription,
      durationMonths: '',
      onboardingCount: '',
      unitPrice: rate
    })
  };
}
