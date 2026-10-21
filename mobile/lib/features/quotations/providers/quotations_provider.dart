import 'dart:typed_data';
import 'package:flutter/material.dart';
import '../data/quotations_repository.dart';
import '../models/quotation_model.dart';

class QuotationsProvider extends ChangeNotifier {
  final QuotationsRepository _repository = QuotationsRepository();

  List<QuotationModel> _documents = [];
  bool _isLoading = false;
  String? _errorMessage;
  String _selectedDocType = 'all';

  List<QuotationModel> get documents => _documents;
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;
  String get selectedDocType => _selectedDocType;

  Future<void> fetchDocuments({bool showLoading = true}) async {
    if (showLoading) {
      _isLoading = true;
      _errorMessage = null;
      notifyListeners();
    }

    try {
      _documents = await _repository.getDocuments(
        docType: _selectedDocType == 'all' ? null : _selectedDocType,
      );
      _errorMessage = null;
    } catch (e) {
      _errorMessage = e.toString().replaceAll('ApiException: ', '');
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  void setDocType(String type) {
    _selectedDocType = type;
    fetchDocuments();
  }

  Future<bool> convertQuoteToProforma(dynamic quoteId) async {
    try {
      await _repository.generateProformaFromQuote(quoteId);
      await fetchDocuments(showLoading: false);
      return true;
    } catch (e) {
      _errorMessage = e.toString().replaceAll('ApiException: ', '');
      notifyListeners();
      return false;
    }
  }

  Future<Map<String, dynamic>?> syncToWebsite(dynamic proformaId) async {
    try {
      final res = await _repository.syncDestinationProforma(proformaId);
      return res;
    } catch (e) {
      _errorMessage = e.toString().replaceAll('ApiException: ', '');
      notifyListeners();
      return null;
    }
  }

  Future<Uint8List?> downloadPdf(dynamic docId, String docType) async {
    try {
      return await _repository.downloadPdf(docId, docType);
    } catch (e) {
      _errorMessage = e.toString().replaceAll('ApiException: ', '');
      notifyListeners();
      return null;
    }
  }
}
