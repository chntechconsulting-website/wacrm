import React from 'react';
import './PingoMascot.css';

/**
 * Pingo 3D Mascot Component
 * Represents official WA! CRM brand character in 12 distinct action/guidance poses.
 * 
 * Available Poses:
 * - 'walk'         : Walking with shoulder messenger bag, smiling (welcome, onboarding)
 * - 'action'       : Superhero crouch landing (quick actions, speed)
 * - 'run'          : Sprinting forward eagerly (urgent follow-ups, speed dialer)
 * - 'kick'         : Dynamic karate kick (target breakthrough, high energy)
 * - 'idea'         : Breakdancing handstand pointing up with spark (insights, pro tips)
 * - 'victory'      : Clenched fist pointing up #1 champion (deal won, quota crushed)
 * - 'playful'      : One-leg balancing pose pointing up/down (empty states, guidance)
 * - 'salute'       : Confident salute / friendly wave (greeting, dashboard companion)
 * - 'point-right'  : Dance stance pointing right (call to action, proceed)
 * - 'inspect'      : Crouching low pointing down (lead details, record audit)
 * - 'point-side'   : Smooth side pointing gesture (lead assignments, recommendations)
 * - 'celebrate'    : Aerial flare spin celebration (quotation approved, PI issued)
 */

export const PINNGO_POSES = {
  walk: '/mascot/pingo-walk.png',
  action: '/mascot/pingo-action.png',
  run: '/mascot/pingo-run.png',
  kick: '/mascot/pingo-kick.png',
  idea: '/mascot/pingo-idea.png',
  victory: '/mascot/pingo-victory.png',
  playful: '/mascot/pingo-playful.png',
  salute: '/mascot/pingo-salute.png',
  'point-right': '/mascot/pingo-point-right.png',
  inspect: '/mascot/pingo-inspect.png',
  'point-side': '/mascot/pingo-point-side.png',
  celebrate: '/mascot/pingo-celebrate.png',
};

const PingoMascot = ({
  pose = 'salute',
  height = 140,
  alt = 'WA! CRM Mascot Pingo',
  withShadow = true,
  shadowWidth,
  speechBubble = null,
  speechBubblePosition = 'right',
  className = '',
  style = {},
  onClick,
  badge = null
}) => {
  const src = PINNGO_POSES[pose] || PINNGO_POSES.salute;
  const computedShadowWidth = shadowWidth || Math.round(height * 0.75);

  return (
    <div
      className={`pingo-mascot-container ${className} ${onClick ? 'pingo-clickable' : ''}`}
      style={{ '--pingo-height': `${height}px`, ...style }}
      onClick={onClick}
    >
      {speechBubble && (
        <div className={`pingo-speech-bubble pingo-speech-${speechBubblePosition}`}>
          {speechBubble}
          <div className="pingo-speech-arrow" />
        </div>
      )}

      <div className="pingo-img-wrapper" style={{ height: `${height}px` }}>
        <img
          src={src}
          alt={alt}
          className="pingo-img"
          style={{ maxHeight: `${height}px` }}
          loading="lazy"
        />
        {badge && <div className="pingo-floating-badge">{badge}</div>}
      </div>

      {withShadow && (
        <div
          className="pingo-floor-shadow"
          style={{ width: `${computedShadowWidth}px` }}
        />
      )}
    </div>
  );
};

export default PingoMascot;
