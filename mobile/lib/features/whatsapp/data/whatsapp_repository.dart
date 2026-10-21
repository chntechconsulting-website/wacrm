import '../../../core/constants/api_endpoints.dart';
import '../../../core/network/api_client.dart';
import '../models/whatsapp_model.dart';

class WhatsAppRepository {
  final ApiClient _client = ApiClient();

  Future<List<WhatsAppConversationModel>> getConversations({
    String tab = 'all',
    String? search,
  }) async {
    final params = <String, dynamic>{'tab': tab};
    if (search != null && search.isNotEmpty) {
      params['search'] = search;
    }

    final response = await _client.get(
      ApiEndpoints.whatsappConversations,
      queryParameters: params,
    );

    if (response is List) {
      return response.map((json) => WhatsAppConversationModel.fromJson(json)).toList();
    } else if (response is Map && response['items'] is List) {
      return (response['items'] as List)
          .map((json) => WhatsAppConversationModel.fromJson(json))
          .toList();
    }
    return [];
  }

  Future<Map<String, dynamic>> getLeadConversation(int leadId) async {
    final response = await _client.get(ApiEndpoints.whatsappLeadMessages(leadId));
    if (response is Map<String, dynamic>) {
      return response;
    }
    return {};
  }

  Future<Map<String, dynamic>> sendMessage({
    int? leadId,
    required String phoneNumber,
    required String messageText,
    String? templateName,
  }) async {
    final body = <String, dynamic>{
      'phone_number': phoneNumber,
      'message_text': messageText,
      if (leadId != null) 'lead_id': leadId,
      if (templateName != null) 'template_name': templateName,
    };

    final response = await _client.post(
      ApiEndpoints.whatsappSendMessage,
      body: body,
    );

    if (response is Map<String, dynamic>) {
      return response;
    }
    return {'success': true};
  }
}
