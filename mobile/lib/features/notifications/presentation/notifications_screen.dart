import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/utils/date_formatter.dart';
import '../../../core/widgets/empty_state.dart';
import '../../../core/widgets/error_view.dart';
import '../../../core/widgets/loading_indicator.dart';
import '../../../core/widgets/pingo_mascot_widget.dart';
import '../../../core/widgets/wacrm_card.dart';
import '../providers/notifications_provider.dart';

class NotificationsScreen extends StatefulWidget {
  const NotificationsScreen({super.key});

  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<NotificationsProvider>().fetchNotifications();
    });
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<NotificationsProvider>();
    final notifications = provider.notifications;

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Notifications & Alerts'),
        actions: [
          if (notifications.isNotEmpty) ...[
            TextButton(
              onPressed: () => provider.markAllAsRead(),
              child: const Text('Mark all read', style: TextStyle(fontSize: 12, color: AppColors.primary)),
            ),
            IconButton(
              icon: const Icon(Icons.delete_sweep_outlined, size: 20),
              tooltip: 'Clear all',
              onPressed: () => provider.clearAll(),
            ),
          ],
        ],
      ),
      body: provider.isLoading && notifications.isEmpty
          ? const LoadingIndicator(message: 'Loading notifications...')
          : provider.errorMessage != null && notifications.isEmpty
              ? ErrorView(
                  message: provider.errorMessage!,
                  onRetry: () => provider.fetchNotifications(),
                )
              : notifications.isEmpty
                  ? const EmptyState(
                      title: 'No Notifications',
                      subtitle: 'You are all caught up on alerts, new leads, and handoffs.',
                      pingoPose: PingoPoses.salute,
                    )
                  : RefreshIndicator(
                      color: AppColors.primary,
                      onRefresh: () => provider.fetchNotifications(showLoading: false),
                      child: ListView.separated(
                        padding: const EdgeInsets.all(16),
                        itemCount: notifications.length,
                        separatorBuilder: (_, __) => const SizedBox(height: 10),
                        itemBuilder: (context, index) {
                          final n = notifications[index];

                          return WacrmCard(
                            onTap: () {
                              if (!n.isRead) {
                                provider.markAsRead(n.id);
                              }
                            },
                            backgroundColor: n.isRead ? AppColors.card : const Color(0xFFF0FDF4),
                            border: Border.all(
                              color: n.isRead ? AppColors.border : AppColors.primary.withValues(alpha: 0.3),
                            ),
                            padding: const EdgeInsets.all(14),
                            child: Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Container(
                                  padding: const EdgeInsets.all(8),
                                  decoration: BoxDecoration(
                                    color: n.isRead ? AppColors.cardHover : AppColors.primaryLight,
                                    shape: BoxShape.circle,
                                  ),
                                  child: Icon(
                                    Icons.notifications_rounded,
                                    color: n.isRead ? AppColors.textLight : AppColors.primary,
                                    size: 18,
                                  ),
                                ),
                                const SizedBox(width: 12),
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Row(
                                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                        children: [
                                          Expanded(
                                            child: Text(
                                              n.title,
                                              style: TextStyle(
                                                fontSize: 14,
                                                fontWeight: n.isRead ? FontWeight.w600 : FontWeight.w700,
                                                color: AppColors.textMain,
                                              ),
                                            ),
                                          ),
                                          Text(
                                            DateFormatter.timeAgo(n.createdAt),
                                            style: const TextStyle(fontSize: 11, color: AppColors.textLight),
                                          ),
                                        ],
                                      ),
                                      const SizedBox(height: 4),
                                      Text(
                                        n.message,
                                        style: const TextStyle(fontSize: 13, color: AppColors.textMuted, height: 1.4),
                                      ),
                                    ],
                                  ),
                                ),
                              ],
                            ),
                          );
                        },
                      ),
                    ),
    );
  }
}
