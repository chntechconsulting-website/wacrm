import 'dart:io';

import '../../../core/constants/api_endpoints.dart';
import '../../../core/network/api_client.dart';
import '../models/field_visit_model.dart';

class FieldVisitsRepository {
  final ApiClient _client = ApiClient();

  Future<List<FieldVisitModel>> getFieldVisits({
    int? employeeId,
    int? leadId,
    int? customerId,
    String? status,
    int limit = 100,
  }) async {
    final params = <String, dynamic>{'limit': limit};
    if (employeeId != null) params['employee_id'] = employeeId;
    if (leadId != null) params['lead_id'] = leadId;
    if (customerId != null) params['customer_id'] = customerId;
    if (status != null && status.isNotEmpty) params['status'] = status;

    final response = await _client.get(
      ApiEndpoints.fieldVisits,
      queryParameters: params,
    );
    if (response is List) {
      return response.map((json) => FieldVisitModel.fromJson(json)).toList();
    }
    return [];
  }

  Future<FieldVisitModel> getFieldVisitById(int id) async {
    final response = await _client.get(ApiEndpoints.fieldVisitById(id));
    return FieldVisitModel.fromJson(response);
  }

  Future<FieldVisitModel> submitFieldVisit(Map<String, dynamic> data) async {
    final response = await _client.post(ApiEndpoints.fieldVisits, body: data);
    return FieldVisitModel.fromJson(response);
  }

  /// Uploads a company-board or visiting-card photo and returns the permanent
  /// URL to store against the visit. Temporary device paths never leave here.
  Future<String> uploadFieldVisitImage({
    required File file,
    required String kind,
  }) async {
    final response = await _client.postMultipart(
      ApiEndpoints.fieldVisitUploads,
      file: file,
      field: 'file',
      fields: {'kind': kind},
    );
    final url = (response is Map ? response['url'] : null)?.toString().trim();
    if (url == null || url.isEmpty) {
      throw Exception('The server did not return an image URL.');
    }
    return url;
  }

  /// Resolves a stored `/uploads/...` path against the configured backend, so
  /// the same visit photo is displayed on mobile and web.
  static String? resolveImageUrl(String? rawUrl) {
    final raw = (rawUrl ?? '').trim();
    if (raw.isEmpty) return null;
    final uri = Uri.tryParse(raw);
    if (uri == null) return null;
    if (!uri.hasScheme) {
      return '${ApiEndpoints.baseUrl.replaceAll(RegExp(r'/+$'), '')}$raw';
    }
    return raw;
  }
}
