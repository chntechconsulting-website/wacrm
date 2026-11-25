/**
 * Downloaded quotation PDF filenames.
 *
 * The leading company token must match the company that issued the document
 * (the same issuer the PDF renders). The quotation number itself is never
 * rewritten; only the company prefix in the filename is normalised.
 */
const ISSUER_PREFIXES = {
  wahrms: 'WAHRMS',
  'chn-tech': 'CHN'
};

const LEADING_PREFIX_PATTERN = /^(WAHRMS|CHN)(?=[-_ ]|$)/i;

function normalizeIssuerId(value) {
  if (typeof value !== 'string') return null;
  const normalized = value.trim().toLowerCase();
  return ISSUER_PREFIXES[normalized] ? normalized : null;
}

/**
 * Resolve the filename prefix from the saved issuer identity first, then the
 * product category (biometric -> CHN, everything else -> WAHRMS).
 */
export function resolveIssuerPrefix(docData = {}) {
  const issuer = docData.issuer || {};
  const explicitId =
    normalizeIssuerId(docData.companyId) ||
    normalizeIssuerId(docData.company_id) ||
    normalizeIssuerId(docData.logoRef) ||
    normalizeIssuerId(docData.logo_ref) ||
    normalizeIssuerId(issuer.companyId) ||
    normalizeIssuerId(issuer.company_id) ||
    normalizeIssuerId(issuer.logoRef) ||
    normalizeIssuerId(issuer.logo_ref);

  if (explicitId) return ISSUER_PREFIXES[explicitId];

  const category = String(
    docData.productCategory || docData.product_category || issuer.productCategory || ''
  ).trim().toLowerCase();

  return category === 'biometric' ? ISSUER_PREFIXES['chn-tech'] : ISSUER_PREFIXES.wahrms;
}

/**
 * Replace a leading CHN/WAHRMS token, or prepend the issuer prefix when the
 * filename does not start with one. The rest of the filename is preserved.
 */
export function applyIssuerPrefix(filename, prefix) {
  const name = String(filename || '');
  const match = name.match(LEADING_PREFIX_PATTERN);
  if (match) {
    return `${prefix}${name.slice(match[1].length)}`;
  }
  return `${prefix}-${name}`;
}

/** Build a quotation download filename prefixed with its actual issuer. */
export function quotationFilename(docData, baseFilename) {
  return applyIssuerPrefix(baseFilename, resolveIssuerPrefix(docData));
}

/** Read the server-provided filename from a download response. */
export function readDownloadFilename(headers, fallback) {
  const disposition = headers?.['content-disposition'] || headers?.['Content-Disposition'] || '';
  const match = String(disposition).match(/filename="?([^";]+)"?/i);
  return match ? match[1] : fallback;
}
