import test from 'node:test';
import assert from 'node:assert/strict';

import {
  BIOMETRIC_DEVICE_COUNT,
  BIOMETRIC_DEVICES,
  BIOMETRIC_DEVICE_GROUPS,
  FALLBACK_BIOMETRIC_DEVICE_BUNDLES,
  createBiometricDeviceBundle,
  getBiometricDeviceByCode,
  isBiometricDeviceBundle
} from './biometricDevices.js';

const EXPECTED_PRICES = {
  bio_dev_ai_mercury: 12000,
  bio_dev_ai_urans: 11700,
  bio_dev_ai_neptune: 15000,
  bio_dev_ai_neptune_bat: 16000,
  bio_dev_ai_pluto: 20700,
  bio_dev_ai_mars: 25000,
  bio_dev_ai_mars_wifi: 25500,
  bio_dev_ai_mars_palm: 27700,
  bio_dev_ai_jupiter: 36200,
  bio_dev_ai_orcus: 15000,
  bio_dev_ai_magnum_lite: 16400,
  bio_dev_ai_magnum: 19800,
  bio_dev_ai_magnum_wifi: 22500,
  bio_dev_mb160: 13900,
  bio_dev_mb160_bat: 15000,
  bio_dev_mb160_bat_wifi_lan_bat: 17500,
  bio_dev_mb20: 11600,
  bio_dev_uface302: 28000,
  bio_dev_uface302_4g: 37000,
  bio_dev_silkbio_101tc_id_bat: 19700,
  bio_dev_ai_eris: 29000,
  bio_dev_ai_arion: 37200,
  bio_dev_k30_bat: 7400,
  bio_dev_k30_wifi_bat: 9400,
  bio_dev_k90: 7200,
  bio_dev_f22_wifi: 13400,
  bio_dev_x990: 16300,
  bio_dev_iclock_990: 25000,
  bio_dev_fr1200: 6700,
  bio_dev_kr500_e: 2000,
  bio_dev_x7: 4500,
  bio_dev_f_18: 18300,
  bio_dev_sf_100: 11100,
  bio_dev_sc_405: 12600
};

test('catalogue exposes all 34 devices from the 2026 price list', () => {
  assert.equal(BIOMETRIC_DEVICE_COUNT, 34);
  assert.equal(BIOMETRIC_DEVICES.length, 34);
  assert.equal(new Set(BIOMETRIC_DEVICES.map((device) => device.code)).size, 34);
  assert.deepEqual(
    BIOMETRIC_DEVICES.map((device) => device.code).sort(),
    Object.keys(EXPECTED_PRICES).sort()
  );
});

test('device groups contain 22 face/finger, 6 fingerprint and 6 reader models', () => {
  const counts = {};
  for (const device of BIOMETRIC_DEVICES) {
    counts[device.group] = (counts[device.group] || 0) + 1;
  }
  assert.deepEqual(counts, { face_finger: 22, finger: 6, reader: 6 });
  assert.deepEqual(
    BIOMETRIC_DEVICE_GROUPS.map((group) => group.code),
    ['face_finger', 'finger', 'reader']
  );
});

test('every device bundle keeps the exact dealer price and 18% GST', () => {
  const bundles = new Map(
    FALLBACK_BIOMETRIC_DEVICE_BUNDLES.map((bundle) => [bundle.bundleCode, bundle])
  );

  for (const [code, price] of Object.entries(EXPECTED_PRICES)) {
    const bundle = bundles.get(code);
    assert.ok(bundle, `missing bundle ${code}`);
    assert.equal(bundle.category, 'BIOMETRIC');
    assert.equal(bundle.items.length, 1);
    assert.equal(bundle.items[0].hsn, '85437099');
    assert.equal(bundle.items[0].rate, price);
    assert.equal(bundle.items[0].gstRate, 0.18);
    assert.equal(bundle.items[0].qty, 1);
    assert.ok(bundle.features.includes('GST 18% Extra'));
  }
});

test('device bundles are distinguishable from the existing biometric packages', () => {
  assert.equal(isBiometricDeviceBundle({ bundleCode: 'bio_dev_ai_mars' }), true);
  assert.equal(isBiometricDeviceBundle({ bundle_code: 'bio_dev_kr500_e' }), true);
  assert.equal(isBiometricDeviceBundle({ bundleCode: 'bio_standard' }), false);
  assert.equal(isBiometricDeviceBundle({ bundleCode: 'bio_atm' }), false);
  assert.equal(isBiometricDeviceBundle({ bundleCode: 'bio_enterprise' }), false);
});

test('device lookup and bundle creation stay consistent', () => {
  const device = getBiometricDeviceByCode('bio_dev_mb160_bat');
  assert.equal(device.name, 'MB160 -BAT');
  assert.equal(device.price, 15000);

  const bundle = createBiometricDeviceBundle(device, 4);
  assert.equal(bundle.name, 'MB160 -BAT');
  assert.equal(bundle.badge, 'Face + Finger');
  assert.equal(bundle.sortOrder, 104);
  assert.match(bundle.description, /15,000/);
  assert.match(bundle.description, /18% GST/);
  assert.equal(getBiometricDeviceByCode('missing'), null);
});
