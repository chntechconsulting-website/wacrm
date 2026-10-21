import '../../../core/constants/api_endpoints.dart';
import '../../../core/network/api_client.dart';
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
}
