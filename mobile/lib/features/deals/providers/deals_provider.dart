import 'package:flutter/material.dart';
import '../data/deals_repository.dart';
import '../models/deal_summary_model.dart';

class DealsProvider extends ChangeNotifier {
  final DealsRepository _repository = DealsRepository();

  List<FinanceHandoffModel> _financeHandoffs = [];
  bool _isLoading = false;
  String? _errorMessage;

  List<FinanceHandoffModel> get financeHandoffs => _financeHandoffs;
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;

  Future<void> fetchFinanceHandoffs({bool showLoading = true}) async {
    if (showLoading) {
      _isLoading = true;
      _errorMessage = null;
      notifyListeners();
    }

    try {
      _financeHandoffs = await _repository.getFinanceHandoffs();
      _errorMessage = null;
    } catch (e) {
      _errorMessage = e.toString().replaceAll('ApiException: ', '');
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<bool> confirmPayment(int handoffId, {String? paymentRef}) async {
    try {
      await _repository.confirmFinancePayment(handoffId, paymentRef: paymentRef);
      await fetchFinanceHandoffs(showLoading: false);
      return true;
    } catch (e) {
      _errorMessage = e.toString().replaceAll('ApiException: ', '');
      notifyListeners();
      return false;
    }
  }

  Future<bool> markDealWon(int leadId, {String? proformaId, int biometricCount = 0}) async {
    try {
      await _repository.markDealWon(leadId, proformaId: proformaId, biometricCount: biometricCount);
      return true;
    } catch (e) {
      _errorMessage = e.toString().replaceAll('ApiException: ', '');
      notifyListeners();
      return false;
    }
  }

  Future<bool> handoffToFinance(int leadId) async {
    try {
      await _repository.handoffToFinance(leadId);
      return true;
    } catch (e) {
      _errorMessage = e.toString().replaceAll('ApiException: ', '');
      notifyListeners();
      return false;
    }
  }
}
