import '../../../core/constants/api_endpoints.dart';
import '../../../core/network/api_client.dart';
import '../models/deal_summary_model.dart';

class DealsRepository {
  final ApiClient _client = ApiClient();

  Future<DealSummaryModel> getDealSummary(int leadId) async {
    final response = await _client.get(ApiEndpoints.dealSummary(leadId));
    return DealSummaryModel.fromJson(response);
  }

  Future<List<FinanceHandoffModel>> getFinanceHandoffs() async {
    final response = await _client.get(ApiEndpoints.financeHandoffs);
    if (response is List) {
      return response.map((json) => FinanceHandoffModel.fromJson(json)).toList();
    }
    return [];
  }

  Future<void> markDealWon(int leadId, {String? proformaId, int biometricCount = 0}) async {
    await _client.post(
      ApiEndpoints.dealWon(leadId),
      body: {
        'lead_id': leadId,
        if (proformaId != null) 'proforma_id': proformaId,
        'biometric_device_count': biometricCount,
      },
    );
  }

  Future<void> handoffToFinance(int leadId) async {
    await _client.post(ApiEndpoints.dealHandoffToFinance(leadId));
  }

  Future<void> confirmFinancePayment(int handoffId, {String? paymentRef}) async {
    await _client.post(
      ApiEndpoints.confirmFinancePayment(handoffId),
      body: {
        if (paymentRef != null) 'payment_reference': paymentRef,
      },
    );
  }
}
