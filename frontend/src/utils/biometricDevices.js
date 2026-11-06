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
    price: 10722
  },
  {
    code: "bio_dev_ai_urans",
    name: "AI URANS",
    group: "face_finger",
    features: ["Face", "Fingerprint", "RFID", "Password"],
    connectivity: "LAN",
    price: 10722
  },
  {
    code: "bio_dev_ai_neptune",
    name: "AI NEPTUNE",
    group: "face_finger",
    features: ["Face", "RFID"],
    connectivity: "LAN",
    price: 13809
  },
  {
    code: "bio_dev_ai_neptune_bat",
    name: "AI NEPTUNE+BAT",
    group: "face_finger",
    features: ["Face", "RFID"],
    connectivity: "Wi-Fi + LAN + Battery",
    price: 14732
  },
  {
    code: "bio_dev_ai_pluto",
    name: "AI PLUTO",
    group: "face_finger",
    features: ["Face", "RFID"],
    connectivity: "Wi-Fi + LAN",
    price: 19130
  },
  {
    code: "bio_dev_ai_mars",
    name: "AI MARS",
    group: "face_finger",
    features: ["Face", "RFID"],
    connectivity: "LAN",
    price: 23038
  },
  {
    code: "bio_dev_ai_mars_wifi",
    name: "AI MARS-WIFI",
    group: "face_finger",
    features: ["Face", "RFID"],
    connectivity: "Wi-Fi + LAN",
    price: 23571
  },
  {
    code: "bio_dev_ai_mars_palm",
    name: "AI MARS-PALM",
    group: "face_finger",
    features: ["Face", "RFID", "Password", "Palm"],
    connectivity: "Wi-Fi + LAN",
    price: 25539
  },
  {
    code: "bio_dev_ai_jupiter",
    name: "AI JUPITER",
    group: "face_finger",
    features: ["Face", "Fingerprint", "RFID"],
    connectivity: "Wi-Fi + LAN",
    price: 33420
  },
  {
    code: "bio_dev_ai_orcus",
    name: "AI ORCUS",
    group: "face_finger",
    features: ["Face", "Fingerprint", "RFID", "Password"],
    connectivity: "Wi-Fi + LAN",
    price: 13949
  },
  {
    code: "bio_dev_ai_magnum_lite",
    name: "AI MAGNUM LITE",
    group: "face_finger",
    features: ["Face", "RFID"],
    connectivity: "Wi-Fi + LAN",
    price: 15151
  },
  {
    code: "bio_dev_ai_magnum",
    name: "AI MAGNUM",
    group: "face_finger",
    features: ["Face", "Fingerprint", "RFID"],
    connectivity: "LAN",
    price: 18307
  },
  {
    code: "bio_dev_ai_magnum_wifi",
    name: "AI MAGNUM-WIFI",
    group: "face_finger",
    features: ["Face", "Fingerprint", "RFID"],
    connectivity: "Wi-Fi + LAN",
    price: 20718
  },
  {
    code: "bio_dev_mb160",
    name: "MB160",
    group: "face_finger",
    features: ["Face", "Fingerprint", "RFID"],
    connectivity: "LAN",
    price: 12800
  },
  {
    code: "bio_dev_mb160_bat",
    name: "MB160 -BAT",
    group: "face_finger",
    features: ["Face", "Fingerprint", "RFID"],
    connectivity: "LAN + Battery",
    price: 13785
  },
  {
    code: "bio_dev_mb160_bat_wifi_lan_bat",
    name: "MB160 -BAT (WIFI+LAN+BAT)",
    group: "face_finger",
    features: ["Face", "Fingerprint", "RFID"],
    connectivity: "Wi-Fi + LAN + Battery",
    price: 16151
  },
  {
    code: "bio_dev_mb20",
    name: "MB20",
    group: "face_finger",
    features: ["Face", "Fingerprint", "RFID"],
    connectivity: "LAN",
    price: 10722
  },
  {
    code: "bio_dev_uface302",
    name: "UFACE302",
    group: "face_finger",
    features: ["Face", "Fingerprint", "RFID"],
    connectivity: "LAN",
    price: 25804
  },
  {
    code: "bio_dev_silkbio_101tc_id_bat",
    name: "SILKBIO-101TC+ID+BAT",
    group: "face_finger",
    features: ["Face", "Fingerprint", "RFID"],
    connectivity: "LAN",
    price: 18181
  },
  {
    code: "bio_dev_ai_eris",
    name: "AI ERIS",
    group: "face_finger",
    features: ["Face", "Fingerprint", "RFID"],
    connectivity: "Wi-Fi + LAN",
    price: 26724
  },
  {
    code: "bio_dev_ai_arion",
    name: "AI ARION",
    group: "face_finger",
    features: ["Face", "Fingerprint", "RFID"],
    connectivity: "Wi-Fi + LAN",
    price: 34315
  },
  {
    code: "bio_dev_k30_bat",
    name: "K30 + BAT",
    group: "finger",
    features: ["Fingerprint", "RFID"],
    connectivity: "LAN + Battery",
    price: 6841
  },
  {
    code: "bio_dev_k30_wifi_bat",
    name: "K30 - WIFI+BAT",
    group: "finger",
    features: ["Fingerprint", "RFID"],
    connectivity: "Wi-Fi + LAN + Battery",
    price: 8633
  },
  {
    code: "bio_dev_k90",
    name: "K90",
    group: "finger",
    features: ["Fingerprint", "RFID"],
    connectivity: "LAN + Battery",
    price: 6553
  },
  {
    code: "bio_dev_f22_wifi",
    name: "F22 - WIFI",
    group: "finger",
    features: ["Fingerprint", "RFID"],
    connectivity: "Wi-Fi / LAN",
    price: 12322
  },
  {
    code: "bio_dev_x990",
    name: "X990",
    group: "finger",
    features: ["Fingerprint", "RFID"],
    connectivity: "LAN",
    price: 15012
  },
  {
    code: "bio_dev_iclock_990",
    name: "ICLOCK 990",
    group: "finger",
    features: ["Fingerprint", "RFID"],
    connectivity: "LAN",
    price: 23149
  },
  {
    code: "bio_dev_fr1200",
    name: "FR1200",
    group: "reader",
    features: ["Fingerprint"],
    connectivity: "LAN",
    price: 6194
  },
  {
    code: "bio_dev_kr500_e",
    name: "KR500-E",
    group: "reader",
    features: ["RFID"],
    connectivity: "LAN",
    price: 1651
  },
  {
    code: "bio_dev_x7",
    name: "X7",
    group: "reader",
    features: ["Fingerprint", "RFID", "Password"],
    connectivity: "LAN",
    price: 4009
  },
  {
    code: "bio_dev_f_18",
    name: "F-18",
    group: "reader",
    features: ["Fingerprint", "RFID"],
    connectivity: "LAN",
    price: 16927
  },
  {
    code: "bio_dev_sf_100",
    name: "SF-100",
    group: "reader",
    features: ["Fingerprint", "RFID"],
    connectivity: "LAN",
    price: 10253
  },
  {
    code: "bio_dev_sc_405",
    name: "SC-405",
    group: "reader",
    features: ["RFID"],
    connectivity: "LAN",
    price: 11684
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
