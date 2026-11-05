/**
 * Central catalogue for quotation add-on products.
 *
 * Add-on prices are intentionally kept in this single module. Quotation line
 * items copy the rate from here when they are added, then store the copied
 * rate with the saved document so historical quotations are never repriced.
 */

export const ADDON_PRICING_TYPES = Object.freeze({
  PER_EMPLOYEE: 'per_employee',
  ONE_TIME: 'one_time'
});

export const ADDON_BILLING_UNITS = Object.freeze({
  EMPLOYEE: 'employee',
  DEVICE: 'device'
});

export const ADDON_PRODUCTS = Object.freeze([
  {
    code: 'live_location_tracking',
    name: 'Live Location Tracking',
    hsn: '998314',
    rate: 60,
    gstRate: 0.18,
    pricingType: ADDON_PRICING_TYPES.PER_EMPLOYEE,
    billingUnit: ADDON_BILLING_UNITS.EMPLOYEE
  },
  {
    code: 'shift_roster',
    name: 'Shift Roster',
    hsn: '998314',
    rate: 15,
    gstRate: 0.18,
    pricingType: ADDON_PRICING_TYPES.PER_EMPLOYEE,
    billingUnit: ADDON_BILLING_UNITS.EMPLOYEE
  },
  {
    code: 'live_expense_trip',
    name: 'Live Expense Trip',
    hsn: '998314',
    rate: 50,
    gstRate: 0.18,
    pricingType: ADDON_PRICING_TYPES.PER_EMPLOYEE,
    billingUnit: ADDON_BILLING_UNITS.EMPLOYEE
  },
  {
    code: 'device_trust',
    name: 'Device Trust',
    hsn: '998314',
    rate: 10,
    gstRate: 0.18,
    pricingType: ADDON_PRICING_TYPES.PER_EMPLOYEE,
    billingUnit: ADDON_BILLING_UNITS.EMPLOYEE
  },
  {
    code: 'biometric_device_setup',
    name: 'Biometric Device Setup',
    hsn: '998315',
    rate: 4999,
    gstRate: 0.18,
    pricingType: ADDON_PRICING_TYPES.ONE_TIME,
    billingUnit: ADDON_BILLING_UNITS.DEVICE
  }
]);

export const PER_EMPLOYEE_ADDONS = ADDON_PRODUCTS.filter(
  (addon) => addon.pricingType === ADDON_PRICING_TYPES.PER_EMPLOYEE
);

export const ONE_TIME_ADDONS = ADDON_PRODUCTS.filter(
  (addon) => addon.pricingType === ADDON_PRICING_TYPES.ONE_TIME
);

export function getAddonByCode(code) {
  const normalized = String(code || '').trim().toLowerCase();
  if (!normalized) return null;
  return ADDON_PRODUCTS.find((addon) => addon.code === normalized) || null;
}

export function isAddonLineItem(item = {}) {
  return Boolean(item.isAddon || item.is_addon || item.addonCode || item.addon_code);
}

/**
 * Find an add-on line by its stable product code. Used to make selection
 * idempotent and to remove an add-on when its card is clicked again.
 */
export function findAddonLineIndex(items = [], addonCode = '') {
  if (!Array.isArray(items)) return -1;
  const normalized = String(addonCode || '').toLowerCase();
  if (!normalized) return -1;
  return items.findIndex((item) => {
    if (!isAddonLineItem(item)) return false;
    return String(item.addonCode || item.addon_code || '').toLowerCase() === normalized;
  });
}

/**
 * Build a normal quotation line item from the central add-on catalogue.
 * The description is deliberately just the product title, so quotation
 * previews and PDFs never inherit marketing copy or feature bullets.
 */
export function createAddonLineItem(addonOrCode, options = {}) {
  const addon = typeof addonOrCode === 'string'
    ? getAddonByCode(addonOrCode)
    : addonOrCode;
  if (!addon) return null;

  const numericQty = Number(options.qty);
  const qty = Number.isFinite(numericQty) && numericQty > 0 ? Math.floor(numericQty) : 1;

  return {
    id: options.id ?? `addon-${addon.code}-${Date.now()}`,
    isBundleItem: false,
    isBundleDetail: false,
    bundleId: null,
    itemCode: addon.code.toUpperCase(),
    addonCode: addon.code,
    isAddon: true,
    is_addon: true,
    name: addon.name,
    description: addon.name,
    hsn: addon.hsn,
    qty,
    rate: Number(addon.rate),
    gstRate: Number(addon.gstRate),
    discount: 0,
    pricingType: addon.pricingType,
    billingUnit: addon.billingUnit,
    quantityMode: 'manual'
  };
}
