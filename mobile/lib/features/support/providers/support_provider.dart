import 'package:flutter/material.dart';
import '../data/support_repository.dart';
import '../models/support_ticket_model.dart';

class SupportProvider extends ChangeNotifier {
  final SupportRepository _repository = SupportRepository();

  List<SupportTicketModel> _tickets = [];
  bool _isLoading = false;
  String? _errorMessage;

  List<SupportTicketModel> get tickets => _tickets;
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;

  Future<void> fetchTickets({bool showLoading = true}) async {
    if (showLoading) {
      _isLoading = true;
      _errorMessage = null;
      notifyListeners();
    }

    try {
      _tickets = await _repository.getSupportTickets();
      _errorMessage = null;
    } catch (e) {
      _errorMessage = e.toString().replaceAll('ApiException: ', '');
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<bool> updateStatus(int id, String status) async {
    try {
      await _repository.updateTicketStatus(id, status);
      await fetchTickets(showLoading: false);
      return true;
    } catch (e) {
      _errorMessage = e.toString().replaceAll('ApiException: ', '');
      notifyListeners();
      return false;
    }
  }
}
