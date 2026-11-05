import test from 'node:test';
import assert from 'node:assert/strict';

import {
  calculateBundleQuantity,
  createBundleSubscriptionFields,
  formatBundleDescription,
  isBundleSubscriptionItem,
  parseBundleDetail
} from './bundleLineItems.js';

test('parses a legacy multi-line bundle description', () => {
  const parsed = parseBundleDetail(
    'WAHRMS HR + Payroll  + Biometric  Integration\nDuration: 12 Months\nNo Of onboardings: 250\nUnit Price: 25'
  );

  assert.equal(parsed.baseDescription, 'WAHRMS HR + Payroll  + Biometric  Integration');
  assert.equal(parsed.durationMonths, 12);
  assert.equal(parsed.onboardingCount, 250);
  assert.equal(parsed.unitPrice, 25);
});

test('parses a legacy single-line bundle description', () => {
  const parsed = parseBundleDetail(
    'WAHRMS HR + ATM Subscription Duration: 12 Months No Of onboardings: 250 Unit Price: 25'
  );

  assert.equal(parsed.baseDescription, 'WAHRMS HR + ATM Subscription');
  assert.equal(parsed.durationMonths, 12);
  assert.equal(parsed.onboardingCount, 250);
  assert.equal(parsed.unitPrice, 25);
});

test('formats all bundle detail lines, using an em dash for empty values', () => {
  assert.equal(
    formatBundleDescription({
      baseDescription: 'WAHRMS HR + ATM Subscription',
      durationMonths: '12',
      onboardingCount: '250',
      unitPrice: '45'
    }),
    'WAHRMS HR + ATM Subscription\nDuration: 12 Months\nNo. of Onboardings: 250\nUnit Price: ₹45'
  );

  assert.equal(
    formatBundleDescription({
      baseDescription: 'WAHRMS HR + ATM Subscription',
      durationMonths: '',
      onboardingCount: '',
      unitPrice: ''
    }),
    'WAHRMS HR + ATM Subscription\nDuration: —\nNo. of Onboardings: —\nUnit Price: —'
  );

  assert.equal(
    formatBundleDescription({
      baseDescription: 'WAHRMS HR + ATM Subscription',
      durationMonths: '12',
      onboardingCount: '',
      unitPrice: '45'
    }),
    'WAHRMS HR + ATM Subscription\nDuration: 12 Months\nNo. of Onboardings: —\nUnit Price: ₹45'
  );
});

test('calculates quantity as duration multiplied by onboarding count', () => {
  assert.equal(calculateBundleQuantity('12', '250'), 3000);
  assert.equal(calculateBundleQuantity(12, 250), 3000);
  assert.equal(calculateBundleQuantity('', '250'), null);
  assert.equal(calculateBundleQuantity('12', ''), null);
  assert.equal(calculateBundleQuantity('12.5', '250'), null);
  assert.equal(calculateBundleQuantity('0', '250'), null);
  assert.equal(calculateBundleQuantity('-12', '250'), null);
});

test('new package fields discard arbitrary legacy defaults but keep the package rate', () => {
  const fields = createBundleSubscriptionFields({
    item_code: 'HR_ATM_SUB',
    name: 'WAHRMS HR + Attendance Subscription',
    description: 'WAHRMS HR + Payroll  + Biometric  Integration\nDuration: 12 Months\nNo Of onboardings: 250\nUnit Price: 25',
    rate: 45
  });

  assert.equal(fields.durationMonths, '');
  assert.equal(fields.onboardingCount, '');
  assert.equal(fields.rate, 45);
  assert.equal(fields.qty, 0);
  assert.equal(
    fields.description,
    'WAHRMS HR + Attendance Subscription\nDuration: —\nNo. of Onboardings: —\nUnit Price: ₹45'
  );
  assert.match(fields.description, /Duration: —/);
  assert.match(fields.description, /No\. of Onboardings: —/);
});

test('identifies subscription modules without treating hardware as subscription', () => {
  assert.equal(isBundleSubscriptionItem({ isBundleItem: true, itemCode: 'HR_ATM_SUB', description: 'Subscription' }), true);
  assert.equal(isBundleSubscriptionItem({ isBundleItem: true, name: 'WAHRMS Complete Suite Subscription' }), true);
  assert.equal(isBundleSubscriptionItem({ isBundleItem: true, itemCode: 'BIO_INTEGRATION', name: 'Biometric Integration' }), false);
});
