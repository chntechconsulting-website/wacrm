import 'package:flutter/material.dart';

class PingoPoses {
  static const String walk = 'walk';
  static const String action = 'action';
  static const String run = 'run';
  static const String kick = 'kick';
  static const String idea = 'idea';
  static const String victory = 'victory';
  static const String playful = 'playful';
  static const String salute = 'salute';
  static const String pointRight = 'point-right';
  static const String inspect = 'inspect';
  static const String pointSide = 'point-side';
  static const String celebrate = 'celebrate';

  // Semantic 3D character pose aliases
  static const String standingWelcome = 'standing_welcome';
  static const String actionLanding = 'action_landing';
  static const String runForward = 'run_forward';
  static const String kickJump = 'kick_jump';
  static const String ideaPoint = 'idea_point';
  static const String targetVictory = 'target_victory';
  static const String saluteService = 'salute_service';
  static const String celebrateSuccess = 'celebrate_success';
  static const String inspectSearch = 'inspect_search';

  static String getAssetPath(String pose) {
    switch (pose.toLowerCase().replaceAll('-', '_')) {
      case 'action':
      case 'action_landing':
        return 'assets/mascot/pingo-action.png';
      case 'celebrate':
      case 'celebrate_success':
        return 'assets/mascot/pingo-celebrate.png';
      case 'idea':
      case 'idea_point':
        return 'assets/mascot/pingo-idea.png';
      case 'inspect':
      case 'inspect_search':
        return 'assets/mascot/pingo-inspect.png';
      case 'kick':
      case 'kick_jump':
        return 'assets/mascot/pingo-kick.png';
      case 'playful':
      case 'dynamic_kick':
        return 'assets/mascot/pingo-playful.png';
      case 'point_right':
        return 'assets/mascot/pingo-point-right.png';
      case 'point_side':
      case 'point_forward':
        return 'assets/mascot/pingo-point-side.png';
      case 'run':
      case 'run_forward':
        return 'assets/mascot/pingo-run.png';
      case 'victory':
      case 'target_victory':
        return 'assets/mascot/pingo-victory.png';
      case 'walk':
      case 'standing_welcome':
        return 'assets/mascot/pingo-walk.png';
      case 'salute':
      case 'salute_service':
      default:
        return 'assets/mascot/pingo-salute.png';
    }
  }

  static String mapStatusToPose(String status) {
    final s = status.toUpperCase().replaceAll('-', '_');
    if (s.contains('CONVERTED') || s.contains('WON') || s.contains('PAID') || s == 'COMPLETED') {
      return celebrate;
    }
    if (s.contains('LOST') || s.contains('CANCELLED') || s.contains('NOT_INTERESTED')) {
      return kick;
    }
    if (s.contains('QUALIFIED') || s.contains('HOT')) {
      return victory;
    }
    if (s.contains('FOLLOW_UP') || s.contains('IN_PROGRESS')) {
      return pointRight;
    }
    if (s.contains('CONTACTED') || s.contains('ASSIGNED')) {
      return action;
    }
    if (s.contains('NEW')) {
      return idea;
    }
    return salute;
  }
}

class PingoMascotWidget extends StatelessWidget {
  final String pose;
  final double height;
  final BoxFit fit;

  const PingoMascotWidget({
    super.key,
    this.pose = PingoPoses.salute,
    this.height = 100,
    this.fit = BoxFit.contain,
  });

  @override
  Widget build(BuildContext context) {
    final asset = PingoPoses.getAssetPath(pose);
    return Image.asset(
      asset,
      height: height,
      fit: fit,
      errorBuilder: (context, error, stackTrace) {
        return Icon(
          Icons.sentiment_very_satisfied_rounded,
          size: height * 0.7,
          color: const Color(0xFF059669),
        );
      },
    );
  }
}
