/**
 * Central catalogue for WA! HRMS subscription packages and their plans.
 *
 * All subscription prices are per employee, per month. The backend bundle
 * master mirrors this catalogue; this module is the offline fallback and the
 * single frontend source for package/plan pricing.
 */

export const BILLING_PLANS = [
  { code: 'pro', name: 'Pro', isCustom: false },
  { code: 'business', name: 'Business', isCustom: false },
  { code: 'custom', name: 'Custom', isCustom: true }
];

function buildPlans(proRate, businessRate) {
  return [
    { code: 'pro', name: 'Pro', rate: proRate, isCustom: false },
    { code: 'business', name: 'Business', rate: businessRate, isCustom: false },
    { code: 'custom', name: 'Custom', rate: null, isCustom: true }
  ];
}

export const WAHRMS_PACKAGE_CATALOG = [
  {
    bundleCode: 'hr_atm',
    category: 'WAHRMS',
    name: 'HR + ATM',
    tagline: 'Core HR with attendance & time.',
    description: 'Integrated employee directory, leave management, and real-time biometric attendance capture.',
    badge: null,
    sortOrder: 1,
    features: [
      'Core HR & Employee Directory',
      'Attendance & Time Tracking',
      'Leave & Holiday Management',
      'Biometric Device Integration'
    ],
    items: [
      {
        item_code: 'HR_ATM_SUB',
        name: 'WAHRMS HR + ATM Subscription',
        description: 'WAHRMS HR + ATM Subscription',
        hsn: '998314',
        qty: 120,
        rate: 40,
        gstRate: 0.18,
        discount: 0,
        billingBasis: 'employee_month',
        plans: buildPlans(40, 55)
      },
      {
        item_code: 'BIO_INTEGRATION',
        name: 'Biometric Integration',
        description: 'Biometric Integration',
        hsn: '998314',
        qty: 1,
        rate: 4999,
        gstRate: 0.18,
        discount: 0
      }
    ]
  },
  {
    bundleCode: 'hr_payroll',
    category: 'WAHRMS',
    name: 'HR + Payroll',
    tagline: 'Core HR with payroll & statutory.',
    description: 'Comprehensive employee records paired with full salary computation, payslips, PF, ESI, TDS, and statutory compliance.',
    badge: null,
    sortOrder: 2,
    features: [
      'Core HR & Employee Profiles',
      'Statutory Payroll Engine',
      'PF, ESI, PT & TDS Filings',
      'One-Click Payslips & Direct Bank Advice'
    ],
    items: [
      {
        item_code: 'HR_PAYROLL_SUB',
        name: 'WAHRMS HR + Payroll Subscription',
        description: 'WAHRMS HR + Payroll Subscription',
        hsn: '998314',
        qty: 120,
        rate: 45,
        gstRate: 0.18,
        discount: 0,
        billingBasis: 'employee_month',
        plans: buildPlans(45, 60)
      },
      {
        item_code: 'PAYROLL_SETUP',
        name: 'WA Payroll Cloud Setup & Deployment',
        description: 'WA Payroll Cloud Setup & Deployment',
        hsn: '998315',
        qty: 1,
        rate: 5000,
        gstRate: 0.18,
        discount: 0
      }
    ]
  },
  {
    bundleCode: 'hr_atm_payroll',
    category: 'WAHRMS',
    name: 'HR + ATM + Payroll',
    tagline: 'The full suite.',
    description: 'The complete all-in-one workforce powerhouse: Core HR, biometric attendance, statutory payroll, and self-service.',
    badge: 'Full Suite • Best Value',
    sortOrder: 3,
    features: [
      'Core HR & Lifecycle Management',
      'Biometric Attendance Sync',
      'Statutory Payroll & Compliance Engine',
      'One-Click Payslips & Direct Bank Advice'
    ],
    items: [
      {
        item_code: 'HR_ATM_PAYROLL_SUB',
        name: 'WAHRMS HR + ATM + Payroll Subscription',
        description: 'WAHRMS HR + ATM + Payroll Subscription',
        hsn: '998314',
        qty: 120,
        rate: 50,
        gstRate: 0.18,
        discount: 0,
        billingBasis: 'employee_month',
        plans: buildPlans(50, 70)
      },
      {
        item_code: 'BIO_PAYROLL_PACKAGE',
        name: 'bio & payroll Integrated Package',
        description: 'bio & payroll Integrated Package',
        hsn: '85437099',
        qty: 1,
        rate: 24500,
        gstRate: 0.18,
        discount: 0
      }
    ]
  },
  {
    bundleCode: 'bio_payroll',
    category: 'WAHRMS',
    name: 'Biometric + Payroll',
    tagline: 'Biometric attendance with statutory payroll.',
    description: 'Biometric device integration and attendance management paired with payroll processing, statutory compliance, and payslip generation.',
    badge: null,
    sortOrder: 4,
    features: [
      'Biometric Device Integration',
      'Attendance Management',
      'Payroll Processing',
      'PF, ESI & Statutory Compliance',
      'Payslip Generation'
    ],
    items: [
      {
        item_code: 'BIO_PAYROLL_SUB',
        name: 'WAHRMS Biometric + Payroll Subscription',
        description: 'WAHRMS Biometric + Payroll Subscription',
        hsn: '998314',
        qty: 120,
        rate: 45,
        gstRate: 0.18,
        discount: 0,
        billingBasis: 'employee_month',
        plans: buildPlans(45, 60)
      }
    ]
  }
];

export const WAHRMS_PACKAGE_CODES = WAHRMS_PACKAGE_CATALOG.map((pkg) => pkg.bundleCode);

/**
 * Offline fallback bundle master. The backend enriches legacy bundle records
 * with the same plan metadata, but the modal remains usable without the API.
 */
export const FALLBACK_WAHRMS_BUNDLES = WAHRMS_PACKAGE_CATALOG;

export function normalizeBundlePlans(rawPlans) {
  if (!Array.isArray(rawPlans)) return [];

  return rawPlans
    .map((plan, index) => {
      const fallback = BILLING_PLANS[index] || {};
      const rawName = plan.name || plan.planName || plan.plan_name || '';
      const nameCode = planCodeFromName(rawName);
      const code = String(
        plan.code || plan.planCode || plan.plan_code || nameCode || fallback.code || ''
      ).toLowerCase();
      const isCustom = Boolean(
        plan.isCustom ?? plan.is_custom ?? code === 'custom'
      );
      const numericRate = Number(plan.rate ?? plan.planRate ?? plan.plan_rate);

      return {
        code,
        name: rawName || fallback.name || code,
        rate: isCustom ? null : (Number.isFinite(numericRate) ? numericRate : null),
        isCustom
      };
    })
    .filter((plan) => plan.code);
}

export function getPackageCatalogEntry(bundleCode) {
  return WAHRMS_PACKAGE_CATALOG.find(
    (pkg) => pkg.bundleCode === bundleCode || pkg.bundleCode === String(bundleCode || '')
  ) || null;
}

/**
 * Resolve plans from the API bundle, its subscription item, or the local
 * catalogue, in that order.
 */
export function getBundlePlans(bundle = {}) {
  const direct = normalizeBundlePlans(bundle.plans);
  if (direct.length > 0) return direct;

  const items = Array.isArray(bundle.items) ? bundle.items : [];
  for (const item of items) {
    const itemPlans = normalizeBundlePlans(item.plans);
    if (itemPlans.length > 0) return itemPlans;
  }

  const catalog = getPackageCatalogEntry(bundle.bundleCode || bundle.bundle_code);
  if (catalog) {
    for (const item of catalog.items) {
      const itemPlans = normalizeBundlePlans(item.plans);
      if (itemPlans.length > 0) return itemPlans;
    }
  }

  return [];
}

export function getPlanByCode(plans, planCode) {
  const code = String(planCode || '').toLowerCase();
  if (!code) return null;
  return normalizeBundlePlans(plans).find((plan) => plan.code === code) || null;
}

export function getDefaultPlanCode(plans) {
  const normalized = normalizeBundlePlans(plans);
  return (normalized.find((plan) => !plan.isCustom) || normalized[0])?.code || '';
}

export function planCodeFromName(planName) {
  const value = String(planName || '').trim().toLowerCase();
  if (value === 'pro') return 'pro';
  if (value === 'business') return 'business';
  if (value === 'custom') return 'custom';
  return '';
}

export function normalizePlanName(planName) {
  const code = planCodeFromName(planName);
  if (code) return code.charAt(0).toUpperCase() + code.slice(1);
  return String(planName || '').trim();
}
