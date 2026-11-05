import test from 'node:test';
import assert from 'node:assert/strict';

import {
  ADDON_BILLING_UNITS,
  ADDON_PRICING_TYPES,
  ADDON_PRODUCTS,
  ONE_TIME_ADDONS,
  PER_EMPLOYEE_ADDONS,
  createAddonLineItem,
  findAddonLineIndex,
  getAddonByCode,
  isAddonLineItem
} from './addonProducts.js';

const EXPECTED = [
  { code: 'live_location_tracking', name: 'Live Location Tracking', rate: 60, hsn: '998314', pricingType: 'per_employee', billingUnit: 'employee' },
  { code: 'shift_roster', name: 'Shift Roster', rate: 15, hsn: '998314', pricingType: 'per_employee', billingUnit: 'employee' },
  { code: 'live_expense_trip', name: 'Live Expense Trip', rate: 50, hsn: '998314', pricingType: 'per_employee', billingUnit: 'employee' },
  { code: 'device_trust', name: 'Device Trust', rate: 10, hsn: '998314', pricingType: 'per_employee', billingUnit: 'employee' },
  { code: 'biometric_device_setup', name: 'Biometric Device Setup', rate: 4999, hsn: '998315', pricingType: 'one_time', billingUnit: 'device' }
];

test('central catalogue contains the five add-on products with exact pricing', () => {
  assert.equal(ADDON_PRODUCTS.length, 5);
  assert.deepEqual(
    ADDON_PRODUCTS.map(({ code, name, rate, hsn, pricingType, billingUnit }) => ({
      code, name, rate, hsn, pricingType, billingUnit
    })),
    EXPECTED
  );
  assert.equal(ADDON_PRODUCTS.every((addon) => addon.gstRate === 0.18), true);
});

test('recurring and one-time add-ons stay separated', () => {
  assert.equal(PER_EMPLOYEE_ADDONS.length, 4);
  assert.equal(ONE_TIME_ADDONS.length, 1);
  assert.equal(ONE_TIME_ADDONS[0].code, 'biometric_device_setup');
  assert.equal(PER_EMPLOYEE_ADDONS.every((addon) => addon.pricingType === ADDON_PRICING_TYPES.PER_EMPLOYEE), true);
  assert.equal(ONE_TIME_ADDONS.every((addon) => addon.pricingType === ADDON_PRICING_TYPES.ONE_TIME), true);
  assert.equal(PER_EMPLOYEE_ADDONS.every((addon) => addon.billingUnit === ADDON_BILLING_UNITS.EMPLOYEE), true);
  assert.equal(ONE_TIME_ADDONS[0].billingUnit, ADDON_BILLING_UNITS.DEVICE);
});

test('lookup handles codes case-insensitively and rejects unknown products', () => {
  assert.equal(getAddonByCode('SHIFT_ROSTER')?.name, 'Shift Roster');
  assert.equal(getAddonByCode('  device_trust  ')?.rate, 10);
  assert.equal(getAddonByCode('unknown_addon'), null);
  assert.equal(getAddonByCode(''), null);
});

test('line item keeps the product title only and copies the catalogue price', () => {
  const addon = getAddonByCode('live_location_tracking');
  const item = createAddonLineItem(addon, { id: 'line-1', qty: 25 });

  assert.equal(item.id, 'line-1');
  assert.equal(item.name, 'Live Location Tracking');
  assert.equal(item.description, 'Live Location Tracking');
  assert.equal(item.description.includes('\n'), false);
  assert.equal(item.hsn, '998314');
  assert.equal(item.qty, 25);
  assert.equal(item.rate, 60);
  assert.equal(item.gstRate, 0.18);
  assert.equal(item.pricingType, 'per_employee');
  assert.equal(item.billingUnit, 'employee');
  assert.equal(item.isAddon, true);
  assert.equal(item.is_addon, true);
  assert.equal(item.isBundleItem, false);
  assert.equal(item.isBundleDetail, false);
});

test('one-time setup line uses device quantity and a one-time rate', () => {
  const item = createAddonLineItem('biometric_device_setup', { id: 'line-2', qty: 3 });
  assert.equal(item.description, 'Biometric Device Setup');
  assert.equal(item.qty, 3);
  assert.equal(item.rate, 4999);
  assert.equal(item.hsn, '998315');
  assert.equal(item.pricingType, 'one_time');
  assert.equal(item.billingUnit, 'device');
});

test('quantity defaults safely when blank or invalid', () => {
  assert.equal(createAddonLineItem('shift_roster').qty, 1);
  assert.equal(createAddonLineItem('shift_roster', { qty: 0 }).qty, 1);
  assert.equal(createAddonLineItem('shift_roster', { qty: -4 }).qty, 1);
  assert.equal(createAddonLineItem('shift_roster', { qty: '12' }).qty, 12);
});

test('selected add-ons are found by stable code without matching ordinary lines', () => {
  const roster = createAddonLineItem('shift_roster', { id: 'line-1' });
  const location = createAddonLineItem('live_location_tracking', { id: 'line-2' });
  const items = [
    { id: 'line-0', description: 'Manual consulting', isAddon: false },
    roster,
    location
  ];

  assert.equal(findAddonLineIndex(items, 'shift_roster'), 1);
  assert.equal(findAddonLineIndex(items, 'SHIFT_ROSTER'), 1);
  assert.equal(findAddonLineIndex(items, 'device_trust'), -1);
  assert.equal(isAddonLineItem(items[0]), false);
  assert.equal(isAddonLineItem(roster), true);
});
