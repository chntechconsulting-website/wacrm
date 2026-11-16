/**
 * Biometric hardware catalogue from the 2026 dealer price list.
 *
 * Prices are dealer prices and GST is charged separately at 18%.
 * Keep this file in sync with backend/services/billing_catalog.py.
 */

export const BIOMETRIC_DEVICE_GROUPS = [
  { code: "face_finger", name: "Face + Finger" },
  { code: "finger", name: "Fingerprint" },
  { code: "reader", name: "Reader Devices" },
];

export const BIOMETRIC_DEVICES = [
  {
    code: "bio_dev_ai_mercury",
    name: "AI MERCURY",
    group: "face_finger",
    features: ["Face"],
    connectivity: "Wi-Fi",
    price: 12000
  },
  {
    code: "bio_dev_ai_urans",
    name: "AI URANS",
    group: "face_finger",
    features: ["Face", "Fingerprint", "RFID", "Password"],
    connectivity: "LAN",
    price: 11700
  },
  {
    code: "bio_dev_ai_neptune",
    name: "AI NEPTUNE",
    group: "face_finger",
    features: ["Face", "RFID"],
    connectivity: "LAN",
    price: 15000
  },
  {
    code: "bio_dev_ai_neptune_bat",
    name: "AI NEPTUNE+BAT",
    group: "face_finger",
    features: ["Face", "RFID"],
    connectivity: "Wi-Fi + LAN + Battery",
    price: 16000
  },
  {
    code: "bio_dev_ai_pluto",
    name: "AI PLUTO",
    group: "face_finger",
    features: ["Face", "RFID"],
    connectivity: "Wi-Fi + LAN",
    price: 20700
  },
  {
    code: "bio_dev_ai_mars",
    name: "AI MARS",
    group: "face_finger",
    features: ["Face", "RFID"],
    connectivity: "LAN",
    price: 25000
  },
  {
    code: "bio_dev_ai_mars_wifi",
    name: "AI MARS-WIFI",
    group: "face_finger",
    features: ["Face", "RFID"],
    connectivity: "Wi-Fi + LAN",
    price: 25500
  },
  {
    code: "bio_dev_ai_mars_palm",
    name: "AI MARS-PALM",
    group: "face_finger",
    features: ["Face", "RFID", "Password", "Palm"],
    connectivity: "Wi-Fi + LAN",
    price: 27700
  },
  {
    code: "bio_dev_ai_jupiter",
    name: "AI JUPITER",
    group: "face_finger",
    features: ["Face", "Fingerprint", "RFID"],
    connectivity: "Wi-Fi + LAN",
    price: 36200
  },
  {
    code: "bio_dev_ai_orcus",
    name: "AI ORCUS",
    group: "face_finger",
    features: ["Face", "Fingerprint", "RFID", "Password"],
    connectivity: "Wi-Fi + LAN",
    price: 15000
  },
  {
    code: "bio_dev_ai_magnum_lite",
    name: "AI MAGNUM LITE",
    group: "face_finger",
    features: ["Face", "RFID"],
    connectivity: "Wi-Fi + LAN",
    price: 16400
  },
  {
    code: "bio_dev_ai_magnum",
    name: "AI MAGNUM",
    group: "face_finger",
    features: ["Face", "Fingerprint", "RFID"],
    connectivity: "LAN",
    price: 19800
  },
  {
    code: "bio_dev_ai_magnum_wifi",
    name: "AI MAGNUM-WIFI",
    group: "face_finger",
    features: ["Face", "Fingerprint", "RFID"],
    connectivity: "Wi-Fi + LAN",
    price: 22500
  },
  {
    code: "bio_dev_mb160",
    name: "MB160",
    group: "face_finger",
    features: ["Face", "Fingerprint", "RFID"],
    connectivity: "LAN",
    price: 13900
  },
  {
    code: "bio_dev_mb160_bat",
    name: "MB160 -BAT",
    group: "face_finger",
    features: ["Face", "Fingerprint", "RFID"],
    connectivity: "LAN + Battery",
    price: 15000
  },
  {
    code: "bio_dev_mb160_bat_wifi_lan_bat",
    name: "MB160 -BAT (WIFI+LAN+BAT)",
    group: "face_finger",
    features: ["Face", "Fingerprint", "RFID"],
    connectivity: "Wi-Fi + LAN + Battery",
    price: 17500
  },
  {
    code: "bio_dev_mb20",
    name: "MB20",
    group: "face_finger",
    features: ["Face", "Fingerprint", "RFID"],
    connectivity: "LAN",
    price: 11600
  },
  {
    code: "bio_dev_uface302",
    name: "UFACE302",
    group: "face_finger",
    features: ["Face", "Fingerprint", "RFID"],
    connectivity: "LAN",
    price: 28000
  },
  {
    code: "bio_dev_uface302_4g",
    name: "UFACE302 (4G)",
    group: "face_finger",
    features: ["Face", "Fingerprint", "RFID"],
    connectivity: "4G GPRS + LAN + Battery",
    price: 37000
  },
  {
    code: "bio_dev_silkbio_101tc_id_bat",
    name: "SILKBIO-101TC+ID+BAT",
    group: "face_finger",
    features: ["Face", "Fingerprint", "RFID"],
    connectivity: "LAN",
    price: 19700
  },
  {
    code: "bio_dev_ai_eris",
    name: "AI ERIS",
    group: "face_finger",
    features: ["Face", "Fingerprint", "RFID"],
    connectivity: "Wi-Fi + LAN",
    price: 29000
  },
  {
    code: "bio_dev_ai_arion",
    name: "AI ARION",
    group: "face_finger",
    features: ["Face", "Fingerprint", "RFID"],
    connectivity: "Wi-Fi + LAN",
    price: 37200
  },
  {
    code: "bio_dev_k30_bat",
    name: "K30+B",
    group: "finger",
    features: ["Fingerprint", "RFID"],
    connectivity: "LAN + Battery",
    price: 7400
  },
  {
    code: "bio_dev_k30_wifi_bat",
    name: "K30 -WIFI",
    group: "finger",
    features: ["Fingerprint", "RFID"],
    connectivity: "Wi-Fi / LAN",
    price: 9400
  },
  {
    code: "bio_dev_k90",
    name: "K90",
    group: "finger",
    features: ["Fingerprint", "RFID"],
    connectivity: "LAN + Battery",
    price: 7200
  },
  {
    code: "bio_dev_f22_wifi",
    name: "F22 - WIFI",
    group: "finger",
    features: ["Fingerprint", "RFID"],
    connectivity: "Wi-Fi / LAN",
    price: 13400
  },
  {
    code: "bio_dev_x990",
    name: "X990",
    group: "finger",
    features: ["Fingerprint", "RFID"],
    connectivity: "LAN",
    price: 16300
  },
  {
    code: "bio_dev_iclock_990",
    name: "ICLOCK 990",
    group: "finger",
    features: ["Fingerprint", "RFID"],
    connectivity: "LAN",
    price: 25000
  },
  {
    code: "bio_dev_fr1200",
    name: "FR1200",
    group: "reader",
    features: ["Fingerprint"],
    connectivity: "LAN",
    price: 6700
  },
  {
    code: "bio_dev_kr500_e",
    name: "KR500-E",
    group: "reader",
    features: ["RFID"],
    connectivity: "LAN",
    price: 2000
  },
  {
    code: "bio_dev_x7",
    name: "X7",
    group: "reader",
    features: ["Fingerprint", "RFID", "Password"],
    connectivity: "LAN",
    price: 4500
  },
  {
    code: "bio_dev_f_18",
    name: "F-18",
    group: "reader",
    features: ["Fingerprint", "RFID"],
    connectivity: "LAN",
    price: 18300
  },
  {
    code: "bio_dev_sf_100",
    name: "SF-100",
    group: "reader",
    features: ["Fingerprint", "RFID"],
    connectivity: "LAN",
    price: 11100
  },
  {
    code: "bio_dev_sc_405",
    name: "SC-405",
    group: "reader",
    features: ["RFID"],
    connectivity: "LAN",
    price: 12600
  },
];

export const BIOMETRIC_DEVICE_COUNT = BIOMETRIC_DEVICES.length;

export function isBiometricDeviceBundle(bundle) {
  const code = String(bundle?.bundleCode || bundle?.bundle_code || '');
  return code.startsWith('bio_dev_');
}

export function getBiometricDeviceByCode(code) {
  const target = String(code || '');
  return BIOMETRIC_DEVICES.find((device) => device.code === target) || null;
}

export function createBiometricDeviceBundle(device, index = 0) {
  const featureLabel = device.features.join(' + ');
  const group = BIOMETRIC_DEVICE_GROUPS.find((entry) => entry.code === device.group);
  const price = Number(device.price || 0);
  const slug = device.code.replace('bio_dev_', '').toUpperCase();
  return {
    bundleCode: device.code,
    category: 'BIOMETRIC',
    name: device.name,
    tagline: `${featureLabel} \u2022 ${device.connectivity}`,
    description: `${device.name} biometric device with ${featureLabel.toLowerCase()} and ${device.connectivity} connectivity. Dealer price \u20b9${price.toLocaleString('en-IN')} + 18% GST.`,
    badge: group?.name || 'Biometric Device',
    features: [
      featureLabel,
      `${device.connectivity} Connectivity`,
      'Cloud Punch Sync Ready',
      '1-Year Manufacturer Warranty',
      'GST 18% Extra'
    ],
    items: [
      {
        item_code: `BIO_DEV_${slug}`,
        name: `${device.name} Biometric Device`,
        description: `${device.name} Biometric Device (${featureLabel}, ${device.connectivity})`,
        hsn: '85437099',
        qty: 1,
        rate: price,
        gstRate: 0.18,
        discount: 0
      }
    ],
    sortOrder: 100 + index,
    isActive: true,
    isDevice: true,
    deviceGroup: device.group,
    devicePrice: price
  };
}

export const FALLBACK_BIOMETRIC_DEVICE_BUNDLES = BIOMETRIC_DEVICES.map(
  (device, index) => createBiometricDeviceBundle(device, index)
);
