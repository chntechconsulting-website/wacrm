const PAID_ALIASES = new Set([
  'PAID',
  'PAYMENT_RECEIVED',
  'RECEIVED',
  'SUCCESS',
  'SUCCEEDED',
  'CONFIRMED',
  'COMPLETED',
  'SETTLED'
]);

const PARTIAL_ALIASES = new Set([
  'PARTIALLY_PAID',
  'PARTIAL',
  'PARTIAL_PAYMENT',
  'PART_PAYMENT',
  'PARTLY_PAID'
]);

const REJECTED_ALIASES = new Set(['REJECTED', 'DECLINED', 'FAILED']);

const CANCELLED_ALIASES = new Set(['CANCELLED', 'CANCELED', 'VOID']);

const normalizeLabel = (value) =>
  String(value || '')
    .trim()
    .toUpperCase()
    .replace(/[-\s]+/g, '_');

export function normalizePaymentStatus(value) {
  const status = normalizeLabel(value);
  if (PAID_ALIASES.has(status)) return 'PAID';
  if (PARTIAL_ALIASES.has(status)) return 'PARTIALLY_PAID';
  return 'PAYMENT_PENDING';
}

export function normalizeFinanceHandoffStatus(value) {
  const status = normalizeLabel(value);
  if (PAID_ALIASES.has(status)) return 'PAID';
  if (REJECTED_ALIASES.has(status)) return 'REJECTED';
  if (CANCELLED_ALIASES.has(status)) return 'CANCELLED';
  return 'PAYMENT_PENDING';
}
