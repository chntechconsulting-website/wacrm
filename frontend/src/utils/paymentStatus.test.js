import test from 'node:test';
import assert from 'node:assert/strict';

import {
  normalizeFinanceHandoffStatus,
  normalizePaymentStatus
} from './paymentStatus.js';

test('normalises lower-case proforma payment statuses', () => {
  assert.equal(normalizePaymentStatus('unpaid'), 'PAYMENT_PENDING');
  assert.equal(normalizePaymentStatus('paid'), 'PAID');
  assert.equal(normalizePaymentStatus('partially paid'), 'PARTIALLY_PAID');
  assert.equal(normalizePaymentStatus(' PENDING '), 'PAYMENT_PENDING');
});

test('normalises finance handoff statuses and keeps terminal states', () => {
  assert.equal(normalizeFinanceHandoffStatus('unpaid'), 'PAYMENT_PENDING');
  assert.equal(normalizeFinanceHandoffStatus('PAYMENT PENDING'), 'PAYMENT_PENDING');
  assert.equal(normalizeFinanceHandoffStatus('paid'), 'PAID');
  assert.equal(normalizeFinanceHandoffStatus('REJECTED'), 'REJECTED');
  assert.equal(normalizeFinanceHandoffStatus('cancelled'), 'CANCELLED');
  assert.equal(normalizeFinanceHandoffStatus(null), 'PAYMENT_PENDING');
});
