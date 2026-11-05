import test from 'node:test';
import assert from 'node:assert/strict';

import {
  WAHRMS_PACKAGE_CATALOG,
  WAHRMS_PACKAGE_CODES,
  getBundlePlans,
  getDefaultPlanCode,
  getPlanByCode,
  normalizeBundlePlans
} from './billingPackages.js';
import {
  createBundleSubscriptionFields,
  formatBundleDescription,
  getPlanCodeFromItems,
  validateBundlePlanLines
} from './bundleLineItems.js';

const EXPECTED_PACKAGES = {
  hr_atm: {
    name: 'HR + ATM',
    plans: { pro: 40, business: 55, custom: null },
    features: [
      'Core HR & Employee Directory',
      'Attendance & Time Tracking',
      'Leave & Holiday Management',
      'Biometric Device Integration'
    ]
  },
  hr_payroll: {
    name: 'HR + Payroll',
    plans: { pro: 45, business: 60, custom: null },
    features: [
      'Core HR & Employee Profiles',
      'Statutory Payroll Engine',
      'PF, ESI, PT & TDS Filings',
      'One-Click Payslips & Direct Bank Advice'
    ]
  },
  hr_atm_payroll: {
    name: 'HR + ATM + Payroll',
    plans: { pro: 50, business: 70, custom: null },
    features: [
      'Core HR & Lifecycle Management',
      'Biometric Attendance Sync',
      'Statutory Payroll & Compliance Engine',
      'One-Click Payslips & Direct Bank Advice'
    ]
  },
  bio_payroll: {
    name: 'Biometric + Payroll',
    plans: { pro: 45, business: 60, custom: null },
    features: [
      'Biometric Device Integration',
      'Attendance Management',
      'Payroll Processing',
      'PF, ESI & Statutory Compliance',
      'Payslip Generation'
    ]
  }
};

test('catalogue exposes exactly the four WA HRMS packages in display order', () => {
  assert.deepEqual(WAHRMS_PACKAGE_CODES, ['hr_atm', 'hr_payroll', 'hr_atm_payroll', 'bio_payroll']);
  assert.equal(new Set(WAHRMS_PACKAGE_CODES).size, 4);
  assert.equal(WAHRMS_PACKAGE_CATALOG.length, 4);
});

test('every package keeps its exact feature list and name', () => {
  for (const [code, expected] of Object.entries(EXPECTED_PACKAGES)) {
    const pkg = WAHRMS_PACKAGE_CATALOG.find((entry) => entry.bundleCode === code);
    assert.ok(pkg, `missing package ${code}`);
    assert.equal(pkg.name, expected.name);
    assert.deepEqual(pkg.features, expected.features);
  }
});

test('all 12 package/plan combinations resolve the expected per-employee rate', () => {
  for (const [code, expected] of Object.entries(EXPECTED_PACKAGES)) {
    const pkg = WAHRMS_PACKAGE_CATALOG.find((entry) => entry.bundleCode === code);
    const plans = getBundlePlans(pkg);
    assert.equal(plans.length, 3);
    assert.deepEqual(plans.map((plan) => plan.code), ['pro', 'business', 'custom']);

    for (const [planCode, expectedRate] of Object.entries(expected.plans)) {
      const plan = getPlanByCode(plans, planCode);
      assert.ok(plan, `${code}/${planCode} plan missing`);
      assert.equal(plan.rate, expectedRate, `${code}/${planCode} catalogue rate`);

      const item = pkg.items.find((line) => String(line.item_code).endsWith('_SUB'));
      const fields = createBundleSubscriptionFields(item, planCode);
      assert.equal(fields.planCode, planCode);
      assert.equal(fields.planName, plan.name);
      if (planCode === 'custom') {
        assert.equal(fields.rate, '', `${code}/custom line rate must stay blank`);
        assert.equal(fields.isCustomPlan, true);
        assert.match(fields.description, /Unit Price: —/);
      } else {
        assert.equal(fields.rate, expectedRate, `${code}/${planCode} line rate`);
        assert.equal(fields.isCustomPlan, false);
        assert.match(fields.description, new RegExp(`Unit Price: Rs\\. ${expectedRate}`));
      }
      assert.match(fields.description, new RegExp(`Plan: ${plan.name}`));
    }
  }
});

test('default plan is Pro and custom never inherits Pro or Business pricing', () => {
  const plans = getBundlePlans(WAHRMS_PACKAGE_CATALOG[0]);
  assert.equal(getDefaultPlanCode(plans), 'pro');
  assert.equal(getPlanByCode(plans, 'custom').rate, null);

  const custom = createBundleSubscriptionFields(
    WAHRMS_PACKAGE_CATALOG[0].items[0],
    'custom'
  );
  assert.equal(custom.rate, '');
  assert.equal(custom.planRate, null);
  assert.equal(custom.isCustomPlan, true);
  assert.ok(!custom.description.includes('₹40'));
  assert.ok(!custom.description.includes('₹55'));
});

test('normalizes plans from legacy API shapes', () => {
  const plans = normalizeBundlePlans([
    { planCode: 'pro', planName: 'Pro', planRate: 40 },
    { code: 'business', name: 'Business', rate: '55' },
    { code: 'custom', isCustom: true, rate: 99 }
  ]);

  assert.deepEqual(plans, [
    { code: 'pro', name: 'Pro', rate: 40, isCustom: false },
    { code: 'business', name: 'Business', rate: 55, isCustom: false },
    { code: 'custom', name: 'Custom', rate: null, isCustom: true }
  ]);
});

test('saved documents restore plan code from fields or a Plan line', () => {
  assert.equal(getPlanCodeFromItems([{ planCode: 'business' }]), 'business');
  assert.equal(getPlanCodeFromItems([{ planName: 'Custom' }]), 'custom');
  assert.equal(
    getPlanCodeFromItems([
      { description: 'WAHRMS HR + ATM Subscription\nPlan: Business\nDuration: 12 Months' }
    ]),
    'business'
  );
  assert.equal(getPlanCodeFromItems([{ description: 'WAHRMS HR + ATM Subscription' }]), '');
});

test('custom plan rate is validated before issuance', () => {
  assert.match(
    validateBundlePlanLines([{ isBundleDetail: true, planCode: 'custom', rate: 0 }]),
    /negotiated per-employee rate/
  );
  assert.match(
    validateBundlePlanLines([{ isBundleDetail: true, planCode: 'custom', rate: '' }]),
    /negotiated per-employee rate/
  );
  assert.equal(
    validateBundlePlanLines([{ isBundleDetail: true, planCode: 'custom', rate: 72.5 }]),
    ''
  );
  assert.equal(
    validateBundlePlanLines([{ isBundleDetail: true, planCode: 'pro', rate: 0 }]),
    ''
  );
});

test('formatted plan text parses back into the same plan', () => {
  const description = formatBundleDescription({
    baseDescription: 'WAHRMS Biometric + Payroll Subscription',
    planName: 'Business',
    durationMonths: 12,
    onboardingCount: 250,
    unitPrice: 60
  });

  assert.match(description, /Plan: Business/);
  assert.match(description, /Duration: 12 Months/);
  assert.match(description, /No\. of Onboardings: 250/);
  assert.match(description, /Unit Price: Rs\. 60/);
  assert.equal(getPlanCodeFromItems([{ description }]), 'business');
});
