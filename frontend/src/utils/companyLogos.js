/**
 * Company logo assets.
 *
 * Kept separate from companyBranding.js because the base64 logos are large
 * (~330 KB). List pages only need issuer metadata, so importing this module
 * must stay limited to PDF/modal code paths.
 */
import { getCompanyById } from './companyBranding';
import { WAHRMS_LOGO_BASE64, CHN_LOGO_BASE64 } from './logoBase64';

// Logo assets are keyed by the configured logo type, not by a company name.
const LOGO_ASSETS = {
  wahrms: WAHRMS_LOGO_BASE64,
  'chn-tech': CHN_LOGO_BASE64
};

export function resolveCompanyLogoRef(companyId, logoRef = null) {
  const company = getCompanyById(companyId);
  const candidates = [logoRef, company?.logoRef, company?.logoType].filter(Boolean);
  return candidates.find((ref) => Boolean(LOGO_ASSETS[ref])) || null;
}

export function getCompanyLogo(companyId, logoRef = null) {
  const resolvedRef = resolveCompanyLogoRef(companyId, logoRef);
  return resolvedRef ? LOGO_ASSETS[resolvedRef] : null;
}
