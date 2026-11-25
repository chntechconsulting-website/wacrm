import test from 'node:test';
import assert from 'node:assert/strict';

import {
  applyIssuerPrefix,
  quotationFilename,
  readDownloadFilename,
  resolveIssuerPrefix
} from './documentFilename.js';

test('explicit company id wins over category', () => {
  assert.equal(resolveIssuerPrefix({ companyId: 'wahrms', productCategory: 'biometric' }), 'WAHRMS');
  assert.equal(resolveIssuerPrefix({ companyId: 'chn-tech', productCategory: 'wahrms' }), 'CHN');
});

test('logo ref is used when company id is missing', () => {
  assert.equal(resolveIssuerPrefix({ logoRef: 'wahrms' }), 'WAHRMS');
  assert.equal(resolveIssuerPrefix({ logo_ref: 'chn-tech' }), 'CHN');
});

test('issuer snapshot is honoured', () => {
  assert.equal(resolveIssuerPrefix({ issuer: { companyId: 'chn-tech' } }), 'CHN');
  assert.equal(resolveIssuerPrefix({ issuer: { logoRef: 'wahrms' } }), 'WAHRMS');
});

test('product category is the historical fallback', () => {
  assert.equal(resolveIssuerPrefix({ productCategory: 'biometric' }), 'CHN');
  assert.equal(resolveIssuerPrefix({ product_category: 'wahrms' }), 'WAHRMS');
  assert.equal(resolveIssuerPrefix(), 'WAHRMS');
});

test('wahrms replaces an existing CHN prefix', () => {
  assert.equal(
    quotationFilename(
      { companyId: 'wahrms' },
      'CHN-PI-26-1476-SRI-VENKATESHWARA-COLLEGE.pdf'
    ),
    'WAHRMS-PI-26-1476-SRI-VENKATESHWARA-COLLEGE.pdf'
  );
});

test('chn keeps the CHN filename', () => {
  assert.equal(
    quotationFilename(
      { companyId: 'chn-tech' },
      'CHN-QT-2627-0020-CHANDRA-MOHAN.pdf'
    ),
    'CHN-QT-2627-0020-CHANDRA-MOHAN.pdf'
  );
});

test('prefix is prepended when the filename has none', () => {
  assert.equal(
    quotationFilename({ companyId: 'wahrms' }, 'Quotation_CHN-QT-2627-0020.pdf'),
    'WAHRMS-Quotation_CHN-QT-2627-0020.pdf'
  );
  assert.equal(
    quotationFilename({ productCategory: 'biometric' }, 'Quotation_CHN-QT-2627-0020.pdf'),
    'CHN-Quotation_CHN-QT-2627-0020.pdf'
  );
});

test('every component after the company token is preserved', () => {
  const base = 'CHN-PI-26-1476-SRI-VENKATESHWARA-ENGINEERING-COLLEGE.pdf';
  const prefixed = applyIssuerPrefix(base, 'WAHRMS');
  assert.equal(prefixed, `WAHRMS${base.slice('CHN'.length)}`);
  assert.equal(prefixed.slice('WAHRMS'.length), base.slice('CHN'.length));
});

test('mid-filename company tokens are not rewritten', () => {
  assert.equal(
    applyIssuerPrefix('QT-CHN-2627-0001.pdf', 'WAHRMS'),
    'WAHRMS-QT-CHN-2627-0001.pdf'
  );
});

test('server filename header is preferred over the fallback', () => {
  assert.equal(
    readDownloadFilename(
      { 'content-disposition': 'attachment; filename="WAHRMS-Quotation_CHN-QT-1.pdf"' },
      'fallback.pdf'
    ),
    'WAHRMS-Quotation_CHN-QT-1.pdf'
  );
  assert.equal(readDownloadFilename({}, 'fallback.pdf'), 'fallback.pdf');
});
