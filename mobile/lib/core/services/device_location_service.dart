import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:geocoding/geocoding.dart';
import 'package:geolocator/geolocator.dart';

/// Result of a real (never simulated) device GPS capture.
@immutable
class DeviceLocationResult {
  final bool success;
  final double? latitude;
  final double? longitude;

  /// Horizontal accuracy in meters as reported by Android.
  final double? accuracyMeters;
  final DateTime? capturedAt;

  /// Reverse-geocoded address/landmark. Null when geocoding failed; the raw
  /// coordinates are still valid and can be manually annotated by the user.
  final String? address;
  final String? error;

  const DeviceLocationResult({
    required this.success,
    this.latitude,
    this.longitude,
    this.accuracyMeters,
    this.capturedAt,
    this.address,
    this.error,
  });

  const DeviceLocationResult.failure(String message)
    : success = false,
      latitude = null,
      longitude = null,
      accuracyMeters = null,
      capturedAt = null,
      address = null,
      error = message;
}

/// High-accuracy GPS capture with runtime permission handling and reverse
/// geocoding. The app never falls back to hardcoded/demo coordinates.
class DeviceLocationService {
  static const Duration _timeout = Duration(seconds: 25);

  static Future<DeviceLocationResult> detect() async {
    if (kIsWeb) {
      return const DeviceLocationResult.failure(
        'GPS capture is available in the Android app only.',
      );
    }

    try {
      final serviceEnabled = await Geolocator.isLocationServiceEnabled();
      if (!serviceEnabled) {
        return const DeviceLocationResult.failure(
          'Location services are turned off. Enable GPS in Android settings '
          'and try again.',
        );
      }

      var permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
      }
      if (permission == LocationPermission.denied) {
        return const DeviceLocationResult.failure(
          'Location permission was denied. Allow location access to capture '
          'the visit GPS location.',
        );
      }
      if (permission == LocationPermission.deniedForever) {
        return const DeviceLocationResult.failure(
          'Location permission is permanently denied. Open Android app '
          'settings and allow location access for WACRM.',
        );
      }

      Position? position;
      try {
        position = await Geolocator.getCurrentPosition(
          locationSettings: const LocationSettings(
            accuracy: LocationAccuracy.high,
            timeLimit: _timeout,
          ),
        );
      } on TimeoutException {
        position = await Geolocator.getLastKnownPosition();
        if (position == null) {
          return const DeviceLocationResult.failure(
            'Could not obtain a GPS fix. Move to an open area and try again.',
          );
        }
      }

      final capturedAt = position.timestamp;

      String? address;
      try {
        final placemarks = await Geocoding()
            .placemarkFromCoordinates(position.latitude, position.longitude)
            .timeout(const Duration(seconds: 12));
        if (placemarks.isNotEmpty) {
          address = _formatPlacemark(placemarks.first);
        }
      } catch (_) {
        // Reverse geocoding needs network/Google services. Coordinates remain
        // valid, so the employee can type the verified landmark manually.
        address = null;
      }

      return DeviceLocationResult(
        success: true,
        latitude: position.latitude,
        longitude: position.longitude,
        accuracyMeters: position.accuracy,
        capturedAt: capturedAt,
        address: address,
      );
    } on LocationServiceDisabledException {
      return const DeviceLocationResult.failure(
        'Location services are turned off. Enable GPS in Android settings and '
        'try again.',
      );
    } on PermissionDeniedException {
      return const DeviceLocationResult.failure(
        'Location permission was denied. Allow location access to capture the '
        'visit GPS location.',
      );
    } catch (error) {
      debugPrint('[FieldVisit GPS] detection failed: $error');
      return const DeviceLocationResult.failure(
        'Unable to obtain the device location. Check that GPS is enabled and '
        'try again.',
      );
    }
  }

  static String _formatPlacemark(Placemark place) {
    final parts = <String>[
      if ((place.name ?? '').trim().isNotEmpty &&
          (place.name ?? '').trim() != (place.street ?? '').trim())
        place.name!.trim(),
      if ((place.street ?? '').trim().isNotEmpty) place.street!.trim(),
      if ((place.subLocality ?? '').trim().isNotEmpty)
        place.subLocality!.trim(),
      if ((place.locality ?? '').trim().isNotEmpty) place.locality!.trim(),
      if ((place.administrativeArea ?? '').trim().isNotEmpty)
        place.administrativeArea!.trim(),
      if ((place.postalCode ?? '').trim().isNotEmpty) place.postalCode!.trim(),
      if ((place.country ?? '').trim().isNotEmpty) place.country!.trim(),
    ];
    final unique = <String>[];
    for (final part in parts) {
      if (!unique.contains(part)) unique.add(part);
    }
    return unique.join(', ');
  }
}
