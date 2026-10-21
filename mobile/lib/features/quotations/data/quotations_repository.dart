import 'dart:typed_data';
import '../../../core/constants/api_endpoints.dart';
import '../../../core/network/api_client.dart';
import '../models/quotation_model.dart';

class QuotationsRepository {
  final ApiClient _client = ApiClient();

  Future<List<QuotationModel>> getDocuments({String? docType, String? search}) async {
    final params = <String, dynamic>{};
    if (docType != null && docType.isNotEmpty && docType != 'all') {
      params['doc_type'] = docType;
    }
    if (search != null && search.isNotEmpty) {
      params['search'] = search;
    }

    final response = await _client.get(ApiEndpoints.waquoteDocuments, queryParameters: params);
    if (response is List) {
      return response.map((json) => QuotationModel.fromJson(json)).toList();
    }
    return [];
  }

  Future<QuotationModel> getDocumentById(dynamic id) async {
    final response = await _client.get(ApiEndpoints.waquoteDocumentById(id));
    return QuotationModel.fromJson(response);
  }

  Future<void> generateProformaFromQuote(dynamic quoteId) async {
    await _client.post(ApiEndpoints.generateProforma(quoteId));
  }

  Future<Map<String, dynamic>> syncDestinationProforma(dynamic id) async {
    final response = await _client.post(ApiEndpoints.syncDestinationProforma(id));
    return response as Map<String, dynamic>;
  }

  Future<Uint8List> downloadPdf(dynamic id, String docType) async {
    String url;
    if (docType == 'proforma') {
      url = ApiEndpoints.downloadWaquoteProformaPdf(id);
    } else if (docType == 'invoice') {
      url = ApiEndpoints.downloadWaquoteInvoicePdf(id);
    } else {
      url = ApiEndpoints.downloadWaquotePdf(id);
    }

    return await _client.downloadBytes(url);
  }
}
