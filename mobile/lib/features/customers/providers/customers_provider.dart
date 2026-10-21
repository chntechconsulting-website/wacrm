import 'package:flutter/material.dart';
import '../data/customers_repository.dart';
import '../models/customer_model.dart';

class CustomersProvider extends ChangeNotifier {
  final CustomersRepository _repository = CustomersRepository();

  List<CustomerModel> _customers = [];
  bool _isLoading = false;
  String? _errorMessage;
  String? _searchQuery;

  List<CustomerModel> get customers => _customers;
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;

  Future<void> fetchCustomers({bool showLoading = true}) async {
    if (showLoading) {
      _isLoading = true;
      _errorMessage = null;
      notifyListeners();
    }

    try {
      _customers = await _repository.getCustomers(search: _searchQuery);
      _errorMessage = null;
    } catch (e) {
      _errorMessage = e.toString().replaceAll('ApiException: ', '');
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  void search(String query) {
    _searchQuery = query.trim();
    fetchCustomers(showLoading: false);
  }
}
