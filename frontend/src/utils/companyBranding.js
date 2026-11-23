/**
 * Issuer (Company of Record) resolution and branding.
 *
 * Company identity, logo references, GSTIN/PAN and document prefixes live in
 * the COMPANIES configuration. Callers must resolve a saved companyId through
 * this module instead of selecting a default issuer or comparing company names.
 */
import { COMPANIES, COMPANY_DEFAULTS } from './billingMoney';

export function getCompanyById(companyId) {
  if (!companyId) return null;
  return COMPANIES.find((company) => company.id === companyId) || null;
}

export function getCompanyForCategory(productCategory) {
  const category = String(productCategory || '').trim().toLowerCase();
  if (!category) return null;
  return COMPANIES.find(
    (company) => String(company.productCategory || '').toLowerCase() === category
  ) || null;
}

export function getDefaultCompanyId(productCategory = '') {
  const category = String(productCategory || '').trim().toLowerCase();
  const categoryCompany = getCompanyForCategory(category);
  return categoryCompany?.id || COMPANY_DEFAULTS.id;
}

/**
 * Resolve the issuer from an API document or modal initialData.
 * Explicit saved identity always wins; category is only a historical fallback.
 */
export function resolveIssuerCompanyId(source = {}) {
  const issuer = source.issuer || {};
  const explicitCandidates = [
    source.companyId,
    source.company_id,
    issuer.companyId,
    issuer.company_id
  ];
  for (const candidate of explicitCandidates) {
    const company = getCompanyById(candidate);
    if (company) return company.id;
  }

  const categoryCompany = getCompanyForCategory(
    source.productCategory ?? source.product_category
  );
  if (categoryCompany) return categoryCompany.id;

  return COMPANY_DEFAULTS.id;
}

export function getCompanyDocumentPrefix(companyId, docType = 'quotation') {
  const company = getCompanyById(companyId) || COMPANY_DEFAULTS;
  const prefixes = company.documentPrefixes || {};
  const normalizedType = String(docType || 'quotation').toLowerCase();
  return prefixes[normalizedType] || prefixes.quotation || '';
}
