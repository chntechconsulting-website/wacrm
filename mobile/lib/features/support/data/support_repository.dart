import '../../../core/constants/api_endpoints.dart';
import '../../../core/network/api_client.dart';
import '../models/support_models.dart';
import '../models/support_ticket_model.dart';

class SupportRepository {
  final ApiClient _client = ApiClient();

  Future<List<SupportTicketModel>> getSupportTickets() async {
    final response = await _client.get(ApiEndpoints.supportHandoffs);
    if (response is List) {
      return response.map((json) => SupportTicketModel.fromJson(json)).toList();
    }
    return [];
  }

  Future<void> updateTicketStatus(int id, String status) async {
    await _client.put(
      ApiEndpoints.supportHandoffStatus(id),
      body: {'status': status},
    );
  }

  Future<void> reassignTicket(int id, int employeeId) async {
    await _client.put(
      ApiEndpoints.supportHandoffReassign(id),
      body: {'assigned_to': employeeId},
    );
  }

  Future<SupportCustomerPage> getAssignedCustomers({
    String? search,
    String? status,
    String? priority,
    String? source,
    int? assignedAgentId,
    int skip = 0,
    int limit = 30,
  }) async {
    final params = <String, dynamic>{'skip': skip, 'limit': limit};
    if (search != null && search.trim().isNotEmpty) {
      params['search'] = search.trim();
    }
    if (status != null && status.isNotEmpty && status != 'ALL') {
      params['status'] = status;
    }
    if (priority != null && priority.isNotEmpty && priority != 'ALL') {
      params['priority'] = priority;
    }
    if (source != null && source.isNotEmpty && source != 'ALL') {
      params['source'] = source;
    }
    if (assignedAgentId != null) {
      params['assigned_agent_id'] = assignedAgentId;
    }
    final response = await _client.get(
      ApiEndpoints.supportAssignedLeads,
      queryParameters: params,
    );
    if (response is Map) {
      return SupportCustomerPage.fromJson(Map<String, dynamic>.from(response));
    }
    return const SupportCustomerPage(total: 0, page: 1, limit: 30, items: []);
  }

  Future<SupportHistory> getCustomerHistory(
    int leadId, {
    int? customerId,
  }) async {
    final response = await _client.get(
      ApiEndpoints.supportCustomerHistory(leadId),
      queryParameters: {'customer_id': ?customerId},
    );
    if (response is Map) {
      return SupportHistory.fromJson(Map<String, dynamic>.from(response));
    }
    throw StateError('Unexpected Support history response.');
  }

  Future<SupportAssignmentState> getSupportAssignment(int leadId) async {
    final response = await _client.get(ApiEndpoints.supportAssignment(leadId));
    if (response is Map) {
      return SupportAssignmentState.fromJson(
        Map<String, dynamic>.from(response),
      );
    }
    throw StateError('Unexpected Support assignment response.');
  }

  Future<List<SupportAssignTeamMember>> getSupportAssignTeamMembers() async {
    final response = await _client.get(ApiEndpoints.supportTeamMembers);
    if (response is List) {
      return response
          .whereType<Map>()
          .map((item) => SupportAssignTeamMember.fromJson(
                Map<String, dynamic>.from(item),
              ))
          .toList();
    }
    return [];
  }

  /// Assign or reassign the Support owner. The backend enforces role/team scope
  /// and rejects a reassignment without a reason.
  Future<SupportAssignmentState> assignSupportOwner({
    required int leadId,
    required int employeeId,
    String? reason,
  }) async {
    final body = <String, dynamic>{'assigned_agent_id': employeeId};
    if (reason != null && reason.trim().isNotEmpty) {
      body['reason'] = reason.trim();
    }
    await _client.put(ApiEndpoints.supportAssign(leadId), body: body);
    return getSupportAssignment(leadId);
  }

  Future<SupportPurchaseDetails?> getPurchaseDetails(int leadId) async {
    try {
      final response = await _client.get(
        ApiEndpoints.leadPurchaseDetails(leadId),
      );
      if (response is Map) {
        return SupportPurchaseDetails.fromJson(
          Map<String, dynamic>.from(response),
        );
      }
      return null;
    } catch (_) {
      // Purchase details are optional for trial/legacy handovers. The screen
      // shows an explicit empty state instead of failing the whole customer.
      return null;
    }
  }

  Future<List<SupportPoc>> getCustomerPocs(
    int leadId, {
    int? customerId,
  }) async {
    final response = await _client.get(
      ApiEndpoints.supportCustomerPocs(leadId),
      queryParameters: {'customer_id': ?customerId},
    );
    if (response is Map) {
      final items = response['items'] ?? response['pocs'];
      if (items is List) {
        return items
            .whereType<Map>()
            .map((item) => SupportPoc.fromJson(Map<String, dynamic>.from(item)))
            .toList();
      }
    } else if (response is List) {
      return response
          .whereType<Map>()
          .map((item) => SupportPoc.fromJson(Map<String, dynamic>.from(item)))
          .toList();
    }
    return [];
  }

  Future<List<SupportPoc>> createCustomerPoc(
    int leadId,
    Map<String, dynamic> payload, {
    int? customerId,
  }) async {
    final response = await _client.post(
      ApiEndpoints.supportCustomerPocs(leadId),
      body: payload,
      queryParameters: {'customer_id': ?customerId},
    );
    if (response is Map) {
      // Create/PUT endpoints return the refreshed collection plus the row.
      final items = response['items'] ?? response['pocs'];
      if (items is List) {
        return items
            .whereType<Map>()
            .map((item) => SupportPoc.fromJson(Map<String, dynamic>.from(item)))
            .toList();
      }
    }
    return getCustomerPocs(leadId, customerId: customerId);
  }

  Future<void> setPrimaryPoc(int pocId) async {
    await _client.put(ApiEndpoints.supportPocPrimary(pocId));
  }

  Future<void> updateCustomerPoc(
    int pocId,
    Map<String, dynamic> payload,
  ) async {
    await _client.put(ApiEndpoints.supportPoc(pocId), body: payload);
  }

  Future<void> addInteraction(int leadId, Map<String, dynamic> payload) async {
    await _client.post(
      ApiEndpoints.supportCustomerInteractions(leadId),
      body: payload,
    );
  }

  Future<SupportManagerOverview> getManagerOverview() async {
    final response = await _client.get(ApiEndpoints.supportManagerOverview);
    if (response is Map) {
      return SupportManagerOverview.fromJson(
        Map<String, dynamic>.from(response),
      );
    }
    return const SupportManagerOverview();
  }

  Future<List<SupportEmployee>> getSupportEmployees() async {
    final response = await _client.get(ApiEndpoints.supportEmployees);
    if (response is List) {
      return response
          .whereType<Map>()
          .map(
            (item) => SupportEmployee.fromJson(Map<String, dynamic>.from(item)),
          )
          .toList();
    }
    return [];
  }

  Future<List<SupportLeave>> getLeaves({bool includePast = false}) async {
    final response = await _client.get(
      ApiEndpoints.supportLeaves,
      queryParameters: {'include_past': includePast},
    );
    if (response is List) {
      return response
          .whereType<Map>()
          .map((item) => SupportLeave.fromJson(Map<String, dynamic>.from(item)))
          .toList();
    }
    return [];
  }

  Future<List<SupportBackupCustomer>> getBackupCustomers() async {
    final response = await _client.get(
      ApiEndpoints.supportBackupCustomers,
      queryParameters: {'include_history': true},
    );
    if (response is Map) {
      final items = response['items'];
      if (items is List) {
        return items
            .whereType<Map>()
            .map(
              (item) => SupportBackupCustomer.fromJson(
                Map<String, dynamic>.from(item),
              ),
            )
            .toList();
      }
    }
    return [];
  }

  Future<Map<String, dynamic>?> getIncomingCallContext(String phone) async {
    try {
      final response = await _client.get(
        ApiEndpoints.supportIncomingCallContext,
        queryParameters: {'phone': phone},
      );
      if (response is Map<String, dynamic>) return response;
      if (response is Map) return Map<String, dynamic>.from(response);
      return null;
    } catch (_) {
      return null;
    }
  }
}
