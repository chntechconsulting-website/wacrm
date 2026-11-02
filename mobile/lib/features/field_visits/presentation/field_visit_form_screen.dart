import 'dart:io';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../../../core/constants/app_colors.dart';
import '../../../core/services/device_location_service.dart';
import '../../../core/widgets/pingo_mascot_widget.dart';
import '../../../core/widgets/pingo_popup_dialog.dart';
import '../../../core/widgets/wacrm_button.dart';
import '../../../core/widgets/wacrm_card.dart';
import '../../../core/widgets/wacrm_text_field.dart';
import '../../activities/providers/activities_provider.dart';
import '../../followups/providers/followups_provider.dart';
import '../../leads/models/lead_model.dart';
import '../../leads/providers/leads_provider.dart';
import '../providers/field_visits_provider.dart';

class FieldVisitFormScreen extends StatefulWidget {
  final LeadModel? preselectedLead;
  final int? preselectedCustomerId;
  final String? preselectedCustomerName;

  const FieldVisitFormScreen({
    super.key,
    this.preselectedLead,
    this.preselectedCustomerId,
    this.preselectedCustomerName,
  });

  @override
  State<FieldVisitFormScreen> createState() => _FieldVisitFormScreenState();
}

class _FieldVisitFormScreenState extends State<FieldVisitFormScreen> {
  static const int _maxPhotoBytes = 10 * 1024 * 1024;
  static const Set<String> _allowedPhotoExtensions = {
    '.jpg',
    '.jpeg',
    '.png',
    '.webp',
    '.heic',
    '.heif',
  };

  final _formKey = GlobalKey<FormState>();

  bool _useNewLead = false;
  int? _selectedLeadId;
  String _customerName = '';
  int? _customerId;

  DateTime _visitDate = DateTime.now();
  TimeOfDay _visitTime = TimeOfDay.now();

  // GPS values are never pre-filled with demo data. They are populated only by
  // a real device fix, while the address stays manually editable.
  final _latController = TextEditingController();
  final _lngController = TextEditingController();
  final _addressController = TextEditingController();
  final _customerController = TextEditingController();
  final _newLeadPhoneController = TextEditingController();
  final _newLeadCompanyController = TextEditingController();
  final _newLeadEmailController = TextEditingController();
  final _leadSearchController = TextEditingController();

  double? _gpsAccuracyM;
  DateTime? _gpsCapturedAt;
  bool _isLocating = false;
  String? _gpsError;

  File? _boardFile;
  String? _boardUrl;
  bool _boardUploading = false;
  String? _boardError;

  File? _cardFile;
  String? _cardUrl;
  bool _cardUploading = false;
  String? _cardError;

  final _requirementsController = TextEditingController();
  final _notesController = TextEditingController();

  String _visitOutcome = 'Interested';
  final List<String> _outcomeOptions = [
    'Interested',
    'Follow-up Required',
    'Quotation Requested',
    'Meeting Done',
    'Deal Won',
    'Closed / Not Interested',
  ];

  // Follow-up Scheduling Section
  bool _scheduleFollowup = false;
  DateTime _followupDate = DateTime.now().add(const Duration(days: 2));
  TimeOfDay _followupTime = const TimeOfDay(hour: 10, minute: 30);
  String _followupPriority = 'MEDIUM';
  final _followupNotesController = TextEditingController(
    text: 'Follow-up regarding product discussion and quotation proposal.',
  );

  late final String _clientToken;

  @override
  void initState() {
    super.initState();
    _clientToken =
        'visit_${DateTime.now().millisecondsSinceEpoch}_${(1000 + DateTime.now().microsecond % 9000)}';

    if (widget.preselectedLead != null) {
      _selectedLeadId = widget.preselectedLead!.id;
      _customerName = widget.preselectedLead!.name;
      _customerController.text = _customerName;
      _newLeadPhoneController.text = widget.preselectedLead!.phone;
      _newLeadCompanyController.text = widget.preselectedLead!.company ?? '';
    } else if (widget.preselectedCustomerName != null) {
      _customerName = widget.preselectedCustomerName!;
      _customerId = widget.preselectedCustomerId;
      _customerController.text = _customerName;
    }

    // Ensure the existing-lead selector has data even when the form is opened
    // directly from the field-visit list.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      final leadsProvider = context.read<LeadsProvider>();
      if (leadsProvider.leads.isEmpty && !leadsProvider.isLoading) {
        leadsProvider.fetchLeads(refresh: true);
      }
    });
  }

  @override
  void dispose() {
    _latController.dispose();
    _lngController.dispose();
    _addressController.dispose();
    _customerController.dispose();
    _newLeadPhoneController.dispose();
    _newLeadCompanyController.dispose();
    _newLeadEmailController.dispose();
    _leadSearchController.dispose();
    _requirementsController.dispose();
    _notesController.dispose();
    _followupNotesController.dispose();
    super.dispose();
  }

  Future<void> _detectGps() async {
    if (_isLocating) return;
    setState(() {
      _isLocating = true;
      _gpsError = null;
    });

    final result = await DeviceLocationService.detect();
    if (!mounted) return;

    if (!result.success) {
      setState(() {
        _isLocating = false;
        _gpsError = result.error ?? 'Unable to obtain the device location.';
      });
      return;
    }

    setState(() {
      _isLocating = false;
      _latController.text = result.latitude!.toStringAsFixed(6);
      _lngController.text = result.longitude!.toStringAsFixed(6);
      _gpsAccuracyM = result.accuracyMeters;
      _gpsCapturedAt = result.capturedAt;
      final address = (result.address ?? '').trim();
      if (address.isNotEmpty) {
        _addressController.text = address;
      }
    });

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          (result.address ?? '').trim().isEmpty
              ? 'GPS coordinates captured. Enter the verified address/landmark manually.'
              : 'GPS coordinates and verified address captured.',
        ),
        backgroundColor: AppColors.success,
        duration: const Duration(seconds: 2),
      ),
    );
  }

  Future<void> _pickVisitDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _visitDate,
      firstDate: DateTime.now().subtract(const Duration(days: 7)),
      lastDate: DateTime.now().add(const Duration(days: 1)),
    );
    if (picked != null) {
      setState(() => _visitDate = picked);
    }
  }

  Future<void> _pickVisitTime() async {
    final picked = await showTimePicker(
      context: context,
      initialTime: _visitTime,
    );
    if (picked != null) {
      setState(() => _visitTime = picked);
    }
  }

  Future<void> _pickFollowupDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _followupDate,
      firstDate: DateTime.now(),
      lastDate: DateTime.now().add(const Duration(days: 365)),
    );
    if (picked != null) {
      setState(() => _followupDate = picked);
    }
  }

  Future<void> _pickFollowupTime() async {
    final picked = await showTimePicker(
      context: context,
      initialTime: _followupTime,
    );
    if (picked != null) {
      setState(() => _followupTime = picked);
    }
  }

  String _formatTimeOfDay(TimeOfDay tod) {
    final now = DateTime.now();
    final dt = DateTime(now.year, now.month, now.day, tod.hour, tod.minute);
    return DateFormat('hh:mm a').format(dt);
  }

  bool get _isBusy => _isLocating || _boardUploading || _cardUploading;

  Future<void> _choosePhoto(String kind) async {
    final source = await showModalBottomSheet<ImageSource>(
      context: context,
      builder: (ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: const Icon(Icons.photo_camera_rounded),
              title: const Text('Capture Photo'),
              onTap: () => Navigator.pop(ctx, ImageSource.camera),
            ),
            ListTile(
              leading: const Icon(Icons.photo_library_rounded),
              title: const Text('Choose from Gallery'),
              onTap: () => Navigator.pop(ctx, ImageSource.gallery),
            ),
          ],
        ),
      ),
    );
    if (source == null) return;
    await _pickAndUpload(kind: kind, source: source);
  }

  Future<void> _pickAndUpload({
    required String kind,
    required ImageSource source,
  }) async {
    final isBoard = kind == 'company_board';
    setState(() {
      if (isBoard) {
        _boardError = null;
        _boardUploading = true;
      } else {
        _cardError = null;
        _cardUploading = true;
      }
    });

    try {
      final picked = await ImagePicker().pickImage(
        source: source,
        imageQuality: 85,
        maxWidth: 2200,
      );
      if (picked == null) {
        setState(() {
          if (isBoard) {
            _boardUploading = false;
          } else {
            _cardUploading = false;
          }
        });
        return;
      }

      final file = File(picked.path);
      final extension = _extensionOf(
        picked.name.isNotEmpty ? picked.name : picked.path,
      );
      if (!_allowedPhotoExtensions.contains(extension)) {
        throw Exception('Unsupported image type. Use JPG, PNG, WEBP or HEIC.');
      }
      final bytes = await file.length();
      if (bytes == 0) {
        throw Exception('The selected image is empty.');
      }
      if (bytes > _maxPhotoBytes) {
        throw Exception('Each photo must be 10 MB or smaller.');
      }

      if (!mounted) return;
      setState(() {
        if (isBoard) {
          _boardFile = file;
          _boardUrl = null;
        } else {
          _cardFile = file;
          _cardUrl = null;
        }
      });

      final url = await context.read<FieldVisitsProvider>().uploadPhoto(
        file: file,
        kind: kind,
      );
      if (!mounted) return;
      if (url == null) {
        throw Exception(
          context.read<FieldVisitsProvider>().errorMessage ??
              'Photo upload failed. Please try again.',
        );
      }
      setState(() {
        if (isBoard) {
          _boardUrl = url;
        } else {
          _cardUrl = url;
        }
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        final message = error.toString().replaceAll('Exception: ', '');
        if (isBoard) {
          _boardError = message;
        } else {
          _cardError = message;
        }
      });
    } finally {
      if (mounted) {
        setState(() {
          if (isBoard) {
            _boardUploading = false;
          } else {
            _cardUploading = false;
          }
        });
      }
    }
  }

  String _extensionOf(String name) {
    final dot = name.lastIndexOf('.');
    if (dot < 0) return '';
    return name.substring(dot).toLowerCase();
  }

  void _removePhoto(String kind) {
    setState(() {
      if (kind == 'company_board') {
        _boardFile = null;
        _boardUrl = null;
        _boardError = null;
      } else {
        _cardFile = null;
        _cardUrl = null;
        _cardError = null;
      }
    });
  }

  Future<void> _submitFieldVisit() async {
    if (!_formKey.currentState!.validate()) {
      return;
    }

    if (_useNewLead) {
      if (_customerController.text.trim().isEmpty ||
          _newLeadPhoneController.text.trim().isEmpty) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Enter the new customer name and phone number.'),
            backgroundColor: AppColors.danger,
          ),
        );
        return;
      }
    } else if (_selectedLeadId == null && _customerName.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Please select a lead or enter the customer name.'),
          backgroundColor: AppColors.danger,
        ),
      );
      return;
    }

    if (_boardUploading || _cardUploading) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Wait for the photo upload to finish.'),
          backgroundColor: AppColors.warning,
        ),
      );
      return;
    }
    if ((_boardFile != null && _boardUrl == null) ||
        (_cardFile != null && _cardUrl == null)) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Retake or remove the photo that failed to upload.'),
          backgroundColor: AppColors.danger,
        ),
      );
      return;
    }

    final combinedVisitDt = DateTime(
      _visitDate.year,
      _visitDate.month,
      _visitDate.day,
      _visitTime.hour,
      _visitTime.minute,
    );

    final payload = <String, dynamic>{
      'client_token': _clientToken,
      'lead_id': _useNewLead ? null : _selectedLeadId,
      'customer_id': _customerId,
      'customer_name': _customerController.text.trim(),
      'checkin_time': combinedVisitDt.toIso8601String(),
      'checkin_lat': _latController.text.trim(),
      'checkin_lng': _lngController.text.trim(),
      'checkin_address': _addressController.text.trim(),
      'checkin_accuracy_m': _gpsAccuracyM,
      'gps_captured_at': _gpsCapturedAt?.toIso8601String(),
      'company_board_photo': _boardUrl,
      'visiting_card_photo': _cardUrl,
      'customer_requirements': _requirementsController.text.trim(),
      'visit_outcome': _visitOutcome,
      'notes': _notesController.text.trim(),
      'schedule_followup': _scheduleFollowup,
      'create_new_lead': _useNewLead,
    };

    if (_useNewLead) {
      payload['new_lead'] = {
        'name': _customerController.text.trim(),
        'phone': _newLeadPhoneController.text.trim(),
        'company': _newLeadCompanyController.text.trim(),
        'email': _newLeadEmailController.text.trim(),
      };
    }

    if (_scheduleFollowup) {
      payload['followup_date'] = DateFormat('yyyy-MM-dd').format(_followupDate);
      payload['followup_time'] = _formatTimeOfDay(_followupTime);
      payload['followup_priority'] = _followupPriority;
      payload['followup_notes'] = _followupNotesController.text.trim();
    }

    final provider = context.read<FieldVisitsProvider>();
    final result = await provider.submitFieldVisit(payload);

    if (result != null && mounted) {
      // Refresh global Activity and Follow-up providers so timelines immediately update
      context.read<ActivitiesProvider>().fetchActivities(leadId: result.leadId);
      context.read<FollowupsProvider>().fetchFollowups();
      context.read<LeadsProvider>().fetchLeads(refresh: true);

      final createdLead = result.leadId != null && _useNewLead;
      PingoPopupDialog.showSuccessModal(
        context,
        title: 'Field Visit Recorded!',
        subtitle: createdLead
            ? 'Lead #${result.leadId} was created and linked to this visit. '
                  'It is now available in the CRM Leads page.'
            : _scheduleFollowup
            ? 'Visit activity logged and follow-up scheduled with 1-hour automated reminder.'
            : 'Visit activity logged successfully in lead and customer timeline.',
        pose: PingoPoses.celebrate,
        onConfirm: () {
          Navigator.pop(context, true);
        },
      );
    } else if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            provider.errorMessage ?? 'Failed to submit field visit.',
          ),
          backgroundColor: AppColors.danger,
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final leads = context.watch<LeadsProvider>().leads;
    final isSubmitting = context.watch<FieldVisitsProvider>().isSubmitting;
    final search = _leadSearchController.text.trim().toLowerCase();
    final filteredLeads = leads.where((l) {
      if (l.id == _selectedLeadId) return true;
      if (search.isEmpty) return true;
      return l.name.toLowerCase().contains(search) ||
          l.phone.toLowerCase().contains(search) ||
          (l.company ?? '').toLowerCase().contains(search);
    }).toList();

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(title: const Text('Record Field Visit')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Lead / Customer Card
              WacrmCard(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Row(
                      children: [
                        Icon(
                          Icons.business_rounded,
                          color: AppColors.primary,
                          size: 20,
                        ),
                        SizedBox(width: 8),
                        Text(
                          'Client & Contact Information',
                          style: TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.w700,
                            color: AppColors.textMain,
                          ),
                        ),
                      ],
                    ),
                    const Divider(height: 20),
                    if (widget.preselectedLead != null)
                      WacrmTextField(
                        label: 'Associated Lead',
                        hintText: widget.preselectedLead!.name,
                        readOnly: true,
                        prefixIcon: Icons.person_outline_rounded,
                      )
                    else ...[
                      SegmentedButton<bool>(
                        segments: const [
                          ButtonSegment<bool>(
                            value: false,
                            label: Text('Existing Lead'),
                            icon: Icon(Icons.link_rounded, size: 16),
                          ),
                          ButtonSegment<bool>(
                            value: true,
                            label: Text('New Lead'),
                            icon: Icon(
                              Icons.person_add_alt_1_rounded,
                              size: 16,
                            ),
                          ),
                        ],
                        selected: {_useNewLead},
                        onSelectionChanged: (selection) {
                          setState(() {
                            _useNewLead = selection.first;
                            if (_useNewLead) {
                              _selectedLeadId = null;
                            }
                          });
                        },
                      ),
                      const SizedBox(height: 12),
                      if (!_useNewLead) ...[
                        WacrmTextField(
                          label: 'Search existing leads',
                          hintText: 'Search by name, company or phone',
                          controller: _leadSearchController,
                          prefixIcon: Icons.search_rounded,
                          onChanged: (_) => setState(() {}),
                        ),
                        const SizedBox(height: 12),
                        DropdownButtonFormField<int>(
                          value: _selectedLeadId,
                          hint: const Text('Choose a lead...'),
                          isExpanded: true,
                          decoration: InputDecoration(
                            prefixIcon: const Icon(
                              Icons.people_outline_rounded,
                              color: AppColors.textMuted,
                            ),
                            filled: true,
                            fillColor: AppColors.inputBackground,
                            border: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(10),
                            ),
                          ),
                          items: filteredLeads.map((l) {
                            return DropdownMenuItem<int>(
                              value: l.id,
                              child: Text(
                                '${l.name} (${l.phone})',
                                overflow: TextOverflow.ellipsis,
                              ),
                            );
                          }).toList(),
                          onChanged: (val) {
                            setState(() {
                              _selectedLeadId = val;
                              if (val != null) {
                                final match = leads.firstWhere(
                                  (l) => l.id == val,
                                );
                                _customerName = match.name;
                                _customerController.text = match.name;
                              }
                            });
                          },
                        ),
                      ] else ...[
                        Container(
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: AppColors.primary.withValues(alpha: 0.06),
                            borderRadius: BorderRadius.circular(10),
                            border: Border.all(
                              color: AppColors.primary.withValues(alpha: 0.25),
                            ),
                          ),
                          child: const Row(
                            children: [
                              Icon(
                                Icons.info_outline_rounded,
                                size: 18,
                                color: AppColors.primary,
                              ),
                              SizedBox(width: 8),
                              Expanded(
                                child: Text(
                                  'A new lead will be created in the CRM when this visit is '
                                  'submitted. If the phone number already exists, the visit is '
                                  'linked to that lead instead of creating a duplicate.',
                                  style: TextStyle(
                                    fontSize: 11.5,
                                    height: 1.4,
                                    color: AppColors.textMuted,
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(height: 12),
                        WacrmTextField(
                          label: 'Phone Number *',
                          hintText: '+91 98765 43210',
                          controller: _newLeadPhoneController,
                          prefixIcon: Icons.phone_outlined,
                          keyboardType: TextInputType.phone,
                          validator: (v) {
                            final digits = (v ?? '').replaceAll(
                              RegExp(r'\D'),
                              '',
                            );
                            if (digits.length < 7) {
                              return 'Please enter a valid phone number';
                            }
                            return null;
                          },
                        ),
                        const SizedBox(height: 12),
                        WacrmTextField(
                          label: 'Company',
                          hintText: 'Company / organisation name',
                          controller: _newLeadCompanyController,
                          prefixIcon: Icons.apartment_rounded,
                        ),
                        const SizedBox(height: 12),
                        WacrmTextField(
                          label: 'Email',
                          hintText: 'name@company.com',
                          controller: _newLeadEmailController,
                          prefixIcon: Icons.email_outlined,
                          keyboardType: TextInputType.emailAddress,
                        ),
                      ],
                      const SizedBox(height: 12),
                      WacrmTextField(
                        label: _useNewLead
                            ? 'Customer Name *'
                            : 'Client / Company Name *',
                        hintText: _useNewLead
                            ? 'e.g. Ramesh Kumar'
                            : 'e.g. Apex Industrial Supplies',
                        controller: _customerController,
                        prefixIcon: _useNewLead
                            ? Icons.person_outline_rounded
                            : Icons.apartment_rounded,
                        onChanged: (v) => _customerName = v,
                        validator: (v) => (v == null || v.trim().isEmpty)
                            ? 'Please enter customer name'
                            : null,
                      ),
                    ],
                  ],
                ),
              ),
              const SizedBox(height: 16),

              // Date & Time Card
              WacrmCard(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Row(
                      children: [
                        Icon(
                          Icons.calendar_month_rounded,
                          color: AppColors.primary,
                          size: 20,
                        ),
                        SizedBox(width: 8),
                        Text(
                          'Visit Date & Time',
                          style: TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.w700,
                            color: AppColors.textMain,
                          ),
                        ),
                      ],
                    ),
                    const Divider(height: 20),
                    Row(
                      children: [
                        Expanded(
                          child: InkWell(
                            onTap: _pickVisitDate,
                            child: Container(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 14,
                                vertical: 12,
                              ),
                              decoration: BoxDecoration(
                                color: AppColors.inputBackground,
                                border: Border.all(color: AppColors.border),
                                borderRadius: BorderRadius.circular(10),
                              ),
                              child: Row(
                                children: [
                                  const Icon(
                                    Icons.event_rounded,
                                    size: 18,
                                    color: AppColors.primary,
                                  ),
                                  const SizedBox(width: 8),
                                  Text(
                                    DateFormat('dd MMM yyyy')
                                        .format(_visitDate),
                                    style: const TextStyle(
                                      fontWeight: FontWeight.w600,
                                      fontSize: 13,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: InkWell(
                            onTap: _pickVisitTime,
                            child: Container(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 14,
                                vertical: 12,
                              ),
                              decoration: BoxDecoration(
                                color: AppColors.inputBackground,
                                border: Border.all(color: AppColors.border),
                                borderRadius: BorderRadius.circular(10),
                              ),
                              child: Row(
                                children: [
                                  const Icon(
                                    Icons.schedule_rounded,
                                    size: 18,
                                    color: AppColors.primary,
                                  ),
                                  const SizedBox(width: 8),
                                  Text(
                                    _formatTimeOfDay(_visitTime),
                                    style: const TextStyle(
                                      fontWeight: FontWeight.w600,
                                      fontSize: 13,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),

              // Location Card
              WacrmCard(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Row(
                          children: [
                            Icon(
                              Icons.location_on_rounded,
                              color: AppColors.primary,
                              size: 20,
                            ),
                            SizedBox(width: 8),
                            Text(
                              'Captured Location (GPS)',
                              style: TextStyle(
                                fontSize: 15,
                                fontWeight: FontWeight.w700,
                                color: AppColors.textMain,
                              ),
                            ),
                          ],
                        ),
                        TextButton.icon(
                          onPressed: _isLocating ? null : _detectGps,
                          icon: _isLocating
                              ? const SizedBox(
                                  width: 14,
                                  height: 14,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2,
                                  ),
                                )
                              : const Icon(Icons.my_location_rounded, size: 16),
                          label: Text(
                            _isLocating ? 'Detecting...' : 'Detect GPS',
                          ),
                          style: TextButton.styleFrom(
                            foregroundColor: AppColors.primary,
                            padding: const EdgeInsets.symmetric(
                              horizontal: 10,
                              vertical: 4,
                            ),
                          ),
                        ),
                      ],
                    ),
                    const Divider(height: 16),
                    if (_gpsError != null) ...[
                      Container(
                        padding: const EdgeInsets.all(10),
                        decoration: BoxDecoration(
                          color: AppColors.danger.withValues(alpha: 0.08),
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(
                            color: AppColors.danger.withValues(alpha: 0.3),
                          ),
                        ),
                        child: Text(
                          _gpsError!,
                          style: const TextStyle(
                            fontSize: 11.5,
                            color: AppColors.danger,
                            height: 1.4,
                          ),
                        ),
                      ),
                      const SizedBox(height: 12),
                    ],
                    Row(
                      children: [
                        Expanded(
                          child: WacrmTextField(
                            label: 'Latitude',
                            controller: _latController,
                            prefixIcon: Icons.explore_outlined,
                            readOnly: true,
                            hintText: 'Detect GPS',
                            keyboardType: const TextInputType.numberWithOptions(
                              decimal: true,
                            ),
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: WacrmTextField(
                            label: 'Longitude',
                            controller: _lngController,
                            prefixIcon: Icons.explore_outlined,
                            readOnly: true,
                            hintText: 'Detect GPS',
                            keyboardType: const TextInputType.numberWithOptions(
                              decimal: true,
                            ),
                          ),
                        ),
                      ],
                    ),
                    if (_gpsAccuracyM != null || _gpsCapturedAt != null)
                      Padding(
                        padding: const EdgeInsets.only(top: 8),
                        child: Text(
                          [
                            if (_gpsAccuracyM != null)
                              'Accuracy: ${_gpsAccuracyM!.toStringAsFixed(1)} m',
                            if (_gpsCapturedAt != null)
                              'Captured: ${DateFormat('dd MMM yyyy, hh:mm a').format(_gpsCapturedAt!.toLocal())}',
                          ].join('  •  '),
                          style: const TextStyle(
                            fontSize: 11,
                            color: AppColors.textMuted,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    const SizedBox(height: 12),
                    WacrmTextField(
                      label: 'Verified Address / Landmark',
                      controller: _addressController,
                      prefixIcon: Icons.pin_drop_outlined,
                      hintText: 'Edit the verified address without changing GPS coordinates',
                      maxLines: 2,
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),

              // Photo Verification Card
              WacrmCard(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Row(
                      children: [
                        Icon(
                          Icons.photo_camera_rounded,
                          color: AppColors.primary,
                          size: 20,
                        ),
                        SizedBox(width: 8),
                        Text(
                          'Photos & Verification',
                          style: TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.w700,
                            color: AppColors.textMain,
                          ),
                        ),
                      ],
                    ),
                    const Divider(height: 20),
                    _buildPhotoPicker(
                      kind: 'company_board',
                      title: 'Company Board Photo',
                      helper: 'Capture or select the office/company board.',
                      file: _boardFile,
                      url: _boardUrl,
                      uploading: _boardUploading,
                      error: _boardError,
                    ),
                    const SizedBox(height: 16),
                    _buildPhotoPicker(
                      kind: 'visiting_card',
                      title: 'Visiting Card Photo',
                      helper: 'Capture or select the visiting card.',
                      file: _cardFile,
                      url: _cardUrl,
                      uploading: _cardUploading,
                      error: _cardError,
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),

              // Requirements & Outcome Card
              WacrmCard(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Row(
                      children: [
                        Icon(
                          Icons.assignment_turned_in_rounded,
                          color: AppColors.primary,
                          size: 20,
                        ),
                        SizedBox(width: 8),
                        Text(
                          'Requirements & Outcome',
                          style: TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.w700,
                            color: AppColors.textMain,
                          ),
                        ),
                      ],
                    ),
                    const Divider(height: 20),
                    const Text(
                      'Visit Outcome *',
                      style: TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                        color: AppColors.textMain,
                      ),
                    ),
                    const SizedBox(height: 6),
                    DropdownButtonFormField<String>(
                      value: _visitOutcome,
                      decoration: InputDecoration(
                        prefixIcon: const Icon(
                          Icons.flag_rounded,
                          color: AppColors.primary,
                        ),
                        filled: true,
                        fillColor: AppColors.inputBackground,
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(10),
                        ),
                      ),
                      items: _outcomeOptions.map((o) {
                        return DropdownMenuItem<String>(
                          value: o,
                          child: Text(o),
                        );
                      }).toList(),
                      onChanged: (val) {
                        if (val != null) {
                          setState(() {
                            _visitOutcome = val;
                            if (val == 'Follow-up Required' ||
                                val == 'Quotation Requested') {
                              _scheduleFollowup = true;
                            }
                          });
                        }
                      },
                    ),
                    const SizedBox(height: 14),
                    WacrmTextField(
                      label: 'Customer Requirements',
                      controller: _requirementsController,
                      hintText: 'Specify requirements, volume, machinery, or software specifications...',
                      maxLines: 3,
                    ),
                    const SizedBox(height: 14),
                    WacrmTextField(
                      label: 'Visit Discussion Notes',
                      controller: _notesController,
                      hintText: 'Key discussion points, objections handled, agreed action items...',
                      maxLines: 3,
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),

              // Schedule Next Follow-up Switch Card
              WacrmCard(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Row(
                          children: [
                            Icon(
                              Icons.alarm_add_rounded,
                              color: Color(0xFFD97706),
                              size: 20,
                            ),
                            SizedBox(width: 8),
                            Text(
                              'Schedule Next Follow-up',
                              style: TextStyle(
                                fontSize: 15,
                                fontWeight: FontWeight.w700,
                                color: AppColors.textMain,
                              ),
                            ),
                          ],
                        ),
                        Switch(
                          value: _scheduleFollowup,
                          activeColor: AppColors.primary,
                          onChanged: (val) =>
                              setState(() => _scheduleFollowup = val),
                        ),
                      ],
                    ),
                    if (_scheduleFollowup) ...[
                      const Divider(height: 20),
                      Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: const Color(0xFFFEF3C7).withValues(alpha: 0.5),
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(color: const Color(0xFFFDE68A)),
                        ),
                        child: const Row(
                          children: [
                            Icon(
                              Icons.notifications_active_rounded,
                              color: Color(0xFFD97706),
                              size: 18,
                            ),
                            SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                'An automated CRM notification will trigger 1 hour before the scheduled follow-up.',
                                style: TextStyle(
                                  fontSize: 11,
                                  fontWeight: FontWeight.w600,
                                  color: Color(0xFF92400E),
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 14),
                      Row(
                        children: [
                          Expanded(
                            child: InkWell(
                              onTap: _pickFollowupDate,
                              child: Container(
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 14,
                                  vertical: 12,
                                ),
                                decoration: BoxDecoration(
                                  color: AppColors.inputBackground,
                                  border: Border.all(color: AppColors.border),
                                  borderRadius: BorderRadius.circular(10),
                                ),
                                child: Row(
                                  children: [
                                    const Icon(
                                      Icons.event_available_rounded,
                                      size: 18,
                                      color: AppColors.primary,
                                    ),
                                    const SizedBox(width: 8),
                                    Text(
                                      DateFormat('dd MMM yyyy')
                                          .format(_followupDate),
                                      style: const TextStyle(
                                        fontWeight: FontWeight.w600,
                                        fontSize: 13,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: InkWell(
                              onTap: _pickFollowupTime,
                              child: Container(
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 14,
                                  vertical: 12,
                                ),
                                decoration: BoxDecoration(
                                  color: AppColors.inputBackground,
                                  border: Border.all(color: AppColors.border),
                                  borderRadius: BorderRadius.circular(10),
                                ),
                                child: Row(
                                  children: [
                                    const Icon(
                                      Icons.access_time_rounded,
                                      size: 18,
                                      color: AppColors.primary,
                                    ),
                                    const SizedBox(width: 8),
                                    Text(
                                      _formatTimeOfDay(_followupTime),
                                      style: const TextStyle(
                                        fontWeight: FontWeight.w600,
                                        fontSize: 13,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 14),
                      const Text(
                        'Follow-up Priority',
                        style: TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w600,
                          color: AppColors.textMain,
                        ),
                      ),
                      const SizedBox(height: 6),
                      DropdownButtonFormField<String>(
                        value: _followupPriority,
                        decoration: InputDecoration(
                          prefixIcon: const Icon(
                            Icons.priority_high_rounded,
                            color: Color(0xFFD97706),
                          ),
                          filled: true,
                          fillColor: AppColors.inputBackground,
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(10),
                          ),
                        ),
                        items: ['LOW', 'MEDIUM', 'HIGH'].map((p) {
                          return DropdownMenuItem<String>(
                            value: p,
                            child: Text('$p Priority'),
                          );
                        }).toList(),
                        onChanged: (val) {
                          if (val != null)
                            setState(() => _followupPriority = val);
                        },
                      ),
                      const SizedBox(height: 14),
                      WacrmTextField(
                        label: 'Follow-up Purpose / Reminder Notes',
                        controller: _followupNotesController,
                        maxLines: 2,
                      ),
                    ],
                  ],
                ),
              ),
              const SizedBox(height: 24),

              // Submit Button
              WacrmButton(
                text: 'Submit Field Visit',
                icon: Icons.check_circle_outline_rounded,
                isLoading: isSubmitting,
                onPressed: (isSubmitting || _isBusy) ? null : _submitFieldVisit,
              ),
              const SizedBox(height: 24),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildPhotoPicker({
    required String kind,
    required String title,
    required String helper,
    required File? file,
    required String? url,
    required bool uploading,
    required String? error,
  }) {
    final hasPhoto = file != null || (url ?? '').isNotEmpty;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          style: const TextStyle(
            fontSize: 13,
            fontWeight: FontWeight.w700,
            color: AppColors.textMain,
          ),
        ),
        const SizedBox(height: 4),
        Text(
          helper,
          style: const TextStyle(fontSize: 11, color: AppColors.textMuted),
        ),
        const SizedBox(height: 10),
        if (hasPhoto)
          ClipRRect(
            borderRadius: BorderRadius.circular(12),
            child: Container(
              height: 180,
              width: double.infinity,
              color: AppColors.inputBackground,
              child: file != null
                  ? Image.file(file, fit: BoxFit.cover)
                  : Image.network(
                      url!,
                      fit: BoxFit.cover,
                      errorBuilder: (_, __, ___) => const Center(
                        child: Icon(
                          Icons.broken_image_outlined,
                          color: AppColors.textMuted,
                        ),
                      ),
                    ),
            ),
          ),
        if (!hasPhoto)
          InkWell(
            onTap: uploading ? null : () => _choosePhoto(kind),
            child: Container(
              height: 110,
              decoration: BoxDecoration(
                color: AppColors.inputBackground,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(
                  color: AppColors.border,
                  style: BorderStyle.solid,
                ),
              ),
              child: Center(
                child: uploading
                    ? const CircularProgressIndicator(strokeWidth: 2)
                    : const Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(
                            Icons.add_a_photo_outlined,
                            color: AppColors.primary,
                          ),
                          SizedBox(height: 6),
                          Text(
                            'Capture Photo  •  Choose from Gallery',
                            style: TextStyle(
                              fontSize: 11.5,
                              fontWeight: FontWeight.w600,
                              color: AppColors.textMuted,
                            ),
                          ),
                        ],
                      ),
              ),
            ),
          ),
        if (hasPhoto) ...[
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: uploading ? null : () => _choosePhoto(kind),
                  icon: const Icon(Icons.cameraswitch_rounded, size: 16),
                  label: const Text('Retake / Replace'),
                ),
              ),
              const SizedBox(width: 10),
              OutlinedButton.icon(
                onPressed: uploading ? null : () => _removePhoto(kind),
                icon: const Icon(Icons.delete_outline_rounded, size: 16),
                label: const Text('Remove'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: AppColors.danger,
                ),
              ),
            ],
          ),
          if (uploading)
            const Padding(
              padding: EdgeInsets.only(top: 8),
              child: LinearProgressIndicator(minHeight: 3),
            )
          else if ((url ?? '').isNotEmpty)
            const Padding(
              padding: EdgeInsets.only(top: 8),
              child: Row(
                children: [
                  Icon(
                    Icons.cloud_done_rounded,
                    size: 14,
                    color: AppColors.success,
                  ),
                  SizedBox(width: 6),
                  Text(
                    'Uploaded',
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                      color: AppColors.success,
                    ),
                  ),
                ],
              ),
            ),
        ],
        if (error != null)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Text(
              error,
              style: const TextStyle(
                fontSize: 11.5,
                color: AppColors.danger,
                height: 1.4,
              ),
            ),
          ),
      ],
    );
  }
}
