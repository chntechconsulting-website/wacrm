/**
 * Helpers for WAHRMS bundle subscription line items.
 *
 * The editor keeps three independent values (duration, onboarding count and
 * unit price) and rebuilds the human readable description used by previews,
 * PDFs and saved documents. `rate` remains the authoritative unit price.
 */

import {
  getDefaultPlanCode,
  getPlanByCode,
  normalizeBundlePlans,
  normalizePlanName,
  planCodeFromName
} from './billingPackages.js';

const DETAIL_LABEL_PATTERN = /(?:\bDuration\s*:|\bNo\.?\s*Of\s*Onboardings?\s*:|\bUnit\s*Price\s*:|\bPrice\s*per\s*user\s*:|\bPlan\s*:)/i;
const DETAIL_LINE_PATTERN = /^\s*(?:Duration\b|No\.?\s*Of\s*Onboardings?\b|Unit\s*Price\b|Price\s*per\s*user\b|Plan\b)/i;

const DURATION_PATTERN = /Duration\s*:?\s*(\d+(?:\.\d+)?)/i;
const ONBOARDING_PATTERN = /No\.?\s*Of\s*Onboardings?\s*:?\s*(\d+(?:\.\d+)?)/i;
const UNIT_PRICE_PATTERN = /(?:Unit\s*Price|Price\s*per\s*user)\s*:?\s*(?:₹|Rs\.?|INR)?\s*(\d+(?:\.\d+)?)/i;
const PLAN_PATTERN = /(?:^|\n)\s*Plan\s*:?\s*([^\n]+)/i;

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
      unitPrice: null,
      planName: ''
    };
  }

  const durationMatch = description.match(DURATION_PATTERN);
  const onboardingMatch = description.match(ONBOARDING_PATTERN);
  const unitPriceMatch = description.match(UNIT_PRICE_PATTERN);
  const planMatch = description.match(PLAN_PATTERN);

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
    unitPrice: unitPriceMatch ? toNonNegativeNumber(unitPriceMatch[1]) : null,
    planName: planMatch ? normalizePlanName(planMatch[1]) : ''
  };
}

function formatAmount(value) {
  return new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 }).format(value);
}

/**
 * Build the text-only bundle detail block used by the preview and PDF.
 * All three bundle detail lines are always present; empty or invalid values
 * use an em dash. The plan line is included when a plan is known.
 */
export function formatBundleDescription({
  baseDescription = '',
  planName = '',
  durationMonths = '',
  onboardingCount = '',
  unitPrice = ''
} = {}) {
  const lines = [];
  const base = String(baseDescription || '').trim();
  if (base) lines.push(base);

  const plan = normalizePlanName(planName);
  if (plan) lines.push(`Plan: ${plan}`);

  const duration = toPositiveInteger(durationMonths);
  lines.push(`Duration: ${duration !== null ? `${duration} Months` : '—'}`);

  const onboardings = toPositiveInteger(onboardingCount);
  lines.push(`No. of Onboardings: ${onboardings !== null ? onboardings : '—'}`);

  const price = toNonNegativeNumber(unitPrice);
  lines.push(`Unit Price: ${price !== null ? `Rs. ${formatAmount(price)}` : '—'}`);

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
 * intentionally discarded; only the selected plan rate is carried forward.
 */
export function createBundleSubscriptionFields(item = {}, planCode = '', bundlePlans = []) {
  const parsed = parseBundleDetail(item.description || item.name || '');
  const baseDescription = String(item.name || '').trim()
    || parsed.baseDescription
    || String(item.description || '').trim();

  const itemPlans = normalizeBundlePlans(item.plans);
  const plans = itemPlans.length > 0 ? itemPlans : normalizeBundlePlans(bundlePlans);
  const requestedPlanCode = planCode || item.planCode || item.plan_code || '';
  const resolvedPlan = getPlanByCode(plans, requestedPlanCode);
  const resolvedPlanCode = resolvedPlan?.code
    || String(requestedPlanCode || '').toLowerCase()
    || getDefaultPlanCode(plans);
  const isCustom = Boolean(resolvedPlan?.isCustom) || resolvedPlanCode === 'custom';
  const fallbackRate = toNonNegativeNumber(item.rate);

  const rate = resolvedPlan
    ? (resolvedPlan.isCustom ? '' : resolvedPlan.rate)
    : (fallbackRate === null ? '' : fallbackRate);
  const planName = normalizePlanName(
    resolvedPlan?.name || item.planName || item.plan_name || parsed.planName || ''
  );

  return {
    baseDescription,
    planCode: resolvedPlanCode,
    planName,
    planRate: isCustom ? null : (resolvedPlan?.rate ?? (fallbackRate === null ? null : fallbackRate)),
    isCustomPlan: isCustom,
    durationMonths: '',
    onboardingCount: '',
    rate,
    qty: 0,
    description: formatBundleDescription({
      baseDescription,
      planName,
      durationMonths: '',
      onboardingCount: '',
      unitPrice: rate
    })
  };
}

/**
 * Restore the selected plan code from saved line items. Newer documents save
 * planCode/planName; legacy documents may only carry a Plan: line.
 */
export function getPlanCodeFromItems(items = []) {
  if (!Array.isArray(items)) return '';

  for (const item of items) {
    const directCode = item.planCode || item.plan_code;
    if (directCode) return String(directCode).toLowerCase();

    const directName = item.planName || item.plan_name;
    if (directName) {
      const code = planCodeFromName(directName);
      if (code) return code;
    }

    const parsed = parseBundleDetail(item.description || '');
    const parsedCode = planCodeFromName(parsed.planName);
    if (parsedCode) return parsedCode;
  }

  return '';
}

/**
 * Custom plan rates are negotiated, never inherited from Pro or Business.
 * Blank, zero and non-numeric rates block document issuance.
 */
export function validateBundlePlanLines(lineItems = []) {
  if (!Array.isArray(lineItems)) return '';

  for (const item of lineItems) {
    if (!item?.isBundleDetail) continue;

    const planCode = String(
      item.planCode || planCodeFromName(item.planName) || ''
    ).toLowerCase();
    if (planCode !== 'custom') continue;

    const rate = toNonNegativeNumber(item.rate);
    if (rate === null || rate <= 0) {
      return 'Enter a negotiated per-employee rate greater than zero for the Custom plan before issuing this document.';
    }
  }

  return '';
}
