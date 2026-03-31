import pygame
import sys
import threading
import math

sys.path.append("../")
from config import SCREEN_WIDTH, CAT_SPEED, CAT_JUMP_POWER, MONKEY

# ── MediaPipe / OpenCV ────────────────────────────────────────────────────────
try:
    import cv2
    import mediapipe as mp
    import numpy as np
    MEDIAPIPE_AVAILABLE = True
except ImportError:
    MEDIAPIPE_AVAILABLE = False

# ─────────────────────────────────────────────────────────────────────────────
#  Gesture tuning constants
# ─────────────────────────────────────────────────────────────────────────────

# LEFT HAND – index-finger tilt controls left / right movement
# Angle = deviation of the MCP→TIP vector from straight-up (vertical).
# Positive angle = tilted right, negative = tilted left.
TILT_DEAD_ZONE  = 10    # degrees: ignore small wobble around centre
TILT_MAX_ANGLE  = 70    # degrees: full-speed clamp (reached before 90°)
MIN_SPEED_MULT  = 0.3   # speed multiplier just outside the dead zone
MAX_SPEED_MULT  = 2.5   # speed multiplier at max tilt

# RIGHT HAND – pinch (thumb tip ↔ index tip) triggers jump
# Distance is normalised to hand size so it works at any camera distance.
PINCH_THRESHOLD = 0.18  # below = "pinched"


# ─────────────────────────────────────────────────────────────────────────────
#  Thread-safe gesture state
# ─────────────────────────────────────────────────────────────────────────────

class GestureState:
    def __init__(self):
        self._lock         = threading.Lock()
        # movement: signed float, negative = left, positive = right, |val| 0..MAX_SPEED_MULT
        self.speed_x       = 0.0
        # jump: rising-edge latch
        self._jump_latch   = False
        self._prev_pinch   = False
        # debug display values
        self.tilt_angle    = 0.0
        self.pinch_dist    = 1.0
        self.left_visible  = False
        self.right_visible = False

    # ── called from camera thread ─────────────────────────────────────────────
    def set_movement(self, speed_x, tilt_angle):
        with self._lock:
            self.speed_x    = speed_x
            self.tilt_angle = tilt_angle

    def set_left_visible(self, v):
        with self._lock:
            self.left_visible = v

    def set_right_hand(self, pinch_dist, visible):
        with self._lock:
            is_pinched = visible and (pinch_dist < PINCH_THRESHOLD)
            # Latch on rising edge only (first frame pinch is detected)
            if is_pinched and not self._prev_pinch:
                self._jump_latch = True
            self._prev_pinch   = is_pinched
            self.pinch_dist    = pinch_dist
            self.right_visible = visible

    # ── called from main (game) thread ───────────────────────────────────────
    def read_speed_x(self):
        with self._lock:
            return self.speed_x

    def consume_jump(self):
        with self._lock:
            j = self._jump_latch
            self._jump_latch = False
            return j

    def read_debug(self):
        with self._lock:
            return (self.tilt_angle, self.pinch_dist,
                    self.left_visible, self.right_visible)


_gesture = GestureState()


# ─────────────────────────────────────────────────────────────────────────────
#  Geometry helpers
# ─────────────────────────────────────────────────────────────────────────────

def _lm_xy(hand_landmarks, idx):
    """Return (x, y) normalised 0-1 for landmark idx."""
    p = hand_landmarks.landmark[idx]
    return p.x, p.y


def _index_tilt_angle(hand_landmarks):
    """
    Angle (degrees) of the index finger from vertical (pointing straight up = 0°).
    Positive  = tilted RIGHT   → move right
    Negative  = tilted LEFT    → move left
    Uses the index MCP (knuckle, #5) → TIP (#8) vector.
    """
    x0, y0 = _lm_xy(hand_landmarks, 5)   # index MCP
    x1, y1 = _lm_xy(hand_landmarks, 8)   # index TIP
    # atan2(horizontal_delta, upward_delta):  up = -y in image space
    angle = math.degrees(math.atan2(x1 - x0, -(y1 - y0)))
    return angle


def _pinch_distance(hand_landmarks):
    """
    Normalised thumb-tip (#4) ↔ index-tip (#8) distance.
    Divided by wrist-to-middle-MCP span so it is size-invariant.
    """
    tx, ty = _lm_xy(hand_landmarks, 4)
    ix, iy = _lm_xy(hand_landmarks, 8)
    wx, wy = _lm_xy(hand_landmarks, 0)   # wrist
    mx, my = _lm_xy(hand_landmarks, 9)   # middle finger MCP
    hand_size = math.hypot(mx - wx, my - wy) + 1e-6
    return math.hypot(ix - tx, iy - ty) / hand_size


def _speed_from_tilt(angle):
    """
    Map tilt angle → signed speed multiplier.
    Dead zone → 0.  Full tilt → ±MAX_SPEED_MULT.  Linear ramp in between.
    """
    abs_a = abs(angle)
    if abs_a < TILT_DEAD_ZONE:
        return 0.0
    t = min(1.0, (abs_a - TILT_DEAD_ZONE) / (TILT_MAX_ANGLE - TILT_DEAD_ZONE))
    mult = MIN_SPEED_MULT + t * (MAX_SPEED_MULT - MIN_SPEED_MULT)
    return math.copysign(mult, angle)


# ─────────────────────────────────────────────────────────────────────────────
#  Background camera / MediaPipe thread
# ─────────────────────────────────────────────────────────────────────────────

def _camera_worker():
    mp_hands = mp.solutions.hands
    mp_draw  = mp.solutions.drawing_utils
    cap      = cv2.VideoCapture(0)

    with mp_hands.Hands(
        max_num_hands            = 2,
        min_detection_confidence = 0.75,
        min_tracking_confidence  = 0.65,
    ) as hands:
        while cap.isOpened():
            ok, frame = cap.read()
            if not ok:
                continue

            frame  = cv2.flip(frame, 1)                     # mirror → player's L/R matches screen
            h, w   = frame.shape[:2]
            rgb    = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = hands.process(rgb)

            left_found  = False
            right_found = False

            if result.multi_hand_landmarks and result.multi_handedness:
                for lm_data, handedness in zip(result.multi_hand_landmarks,
                                               result.multi_handedness):
                    # After flipping the frame MediaPipe's "Left"/"Right" labels
                    # match the player's actual left and right hands.
                    hand_label = handedness.classification[0].label
                    mp_draw.draw_landmarks(frame, lm_data, mp_hands.HAND_CONNECTIONS)

                    # ── LEFT HAND → tilt to move ──────────────────────────────
                    if hand_label == "Left":
                        left_found = True
                        angle = _index_tilt_angle(lm_data)
                        speed = _speed_from_tilt(angle)
                        _gesture.set_movement(speed, angle)
                        _gesture.set_left_visible(True)

                        # Draw the MCP→TIP line with tilt feedback
                        x5 = int(lm_data.landmark[5].x * w)
                        y5 = int(lm_data.landmark[5].y * h)
                        x8 = int(lm_data.landmark[8].x * w)
                        y8 = int(lm_data.landmark[8].y * h)
                        colour = (0, 255, 0) if abs(angle) > TILT_DEAD_ZONE else (0, 200, 255)
                        cv2.line(frame, (x5, y5), (x8, y8), colour, 4)
                        cv2.putText(frame,
                                    f"L tilt:{angle:+.0f}deg  spd:{speed:.2f}",
                                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, colour, 2)

                    # ── RIGHT HAND → pinch to jump ────────────────────────────
                    elif hand_label == "Right":
                        right_found = True
                        pdist = _pinch_distance(lm_data)
                        _gesture.set_right_hand(pdist, True)

                        # Draw thumb-tip ↔ index-tip connector
                        t4x = int(lm_data.landmark[4].x * w)
                        t4y = int(lm_data.landmark[4].y * h)
                        i8x = int(lm_data.landmark[8].x * w)
                        i8y = int(lm_data.landmark[8].y * h)
                        p_col = (0, 0, 255) if pdist < PINCH_THRESHOLD else (255, 220, 0)
                        cv2.line(frame, (t4x, t4y), (i8x, i8y), p_col, 4)
                        label_txt = ("PINCH → JUMP!" if pdist < PINCH_THRESHOLD
                                     else f"R pinch dist:{pdist:.2f}")
                        cv2.putText(frame, label_txt,
                                    (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, p_col, 2)

            # Reset state for hands that disappeared
            if not left_found:
                _gesture.set_movement(0.0, 0.0)
                _gesture.set_left_visible(False)
            if not right_found:
                _gesture.set_right_hand(1.0, False)

            small = cv2.resize(frame, (420, 300))   # change 426x240 to any size you like
            cv2.imshow("Gesture Control  |  Q = close debug", small)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    cap.release()
    cv2.destroyAllWindows()


def start_camera_thread():
    """Start the background camera thread. Returns True if MediaPipe is available."""
    if not MEDIAPIPE_AVAILABLE:
        return False
    t = threading.Thread(target=_camera_worker, daemon=True)
    t.start()
    return True


# ─────────────────────────────────────────────────────────────────────────────
#  Player sprite
# ─────────────────────────────────────────────────────────────────────────────

class Player(pygame.sprite.Sprite):
    DIZZY_DURATION = 180   # frames (~3 s at 60 fps)
    DIZZY_WOBBLE   = 8     # pixels

    def __init__(self, x, y):
        super().__init__()
        self.image = pygame.image.load(MONKEY).convert_alpha()
        self.image = pygame.transform.scale(self.image, (80, 80))
        self.rect  = self.image.get_rect()
        self.rect.x = x
        self.rect.y = y
        self.vel_y  = 0
        self.on_ground      = False
        self.original_image = self.image.copy()
        self.facing_right   = True
        self.dizzy_timer    = 0
        self._dizzy_angle   = 0

    # ── public ────────────────────────────────────────────────────────────────

    def trigger_dizzy(self):
        self.dizzy_timer = self.DIZZY_DURATION

    @property
    def is_dizzy(self):
        return self.dizzy_timer > 0

    # ── update (called every frame from main loop) ─────────────────────────--

    def update(self, keys):
        # ── Input resolution ──────────────────────────────────────────────────
        kb_left  = keys[pygame.K_LEFT]  or keys[pygame.K_a]
        kb_right = keys[pygame.K_RIGHT] or keys[pygame.K_d]

        if MEDIAPIPE_AVAILABLE:
            cam_speed_x = _gesture.read_speed_x()   # signed; 0 = no gesture
            if cam_speed_x != 0.0:
                # Gesture active: use tilt-derived speed
                actual_speed = abs(cam_speed_x) * CAT_SPEED
                go_left  = cam_speed_x < 0
                go_right = cam_speed_x > 0
            else:
                # Gesture idle: fall back to keyboard
                actual_speed = float(CAT_SPEED)
                go_left  = kb_left
                go_right = kb_right
        else:
            actual_speed = float(CAT_SPEED)
            go_left  = kb_left
            go_right = kb_right

        # ── Dizzy: invert controls ─────────────────────────────────────────────
        if self.is_dizzy:
            go_left, go_right = go_right, go_left
            self.dizzy_timer -= 1

        # ── Horizontal movement ───────────────────────────────────────────────
        if go_left:
            self.rect.x -= int(actual_speed)
            if not self.facing_right:
                self.facing_right = True
                self.image = self.original_image.copy()

        if go_right:
            self.rect.x += int(actual_speed)
            if self.facing_right:
                self.facing_right = False
                self.image = pygame.transform.flip(self.original_image, True, False)

        # ── Gravity ───────────────────────────────────────────────────────────
        self.vel_y += 0.5
        self.rect.y += self.vel_y

        # ── Screen boundaries ─────────────────────────────────────────────────
        if self.rect.left < 0:
            self.rect.left = 0
        if self.rect.right > SCREEN_WIDTH:
            self.rect.right = SCREEN_WIDTH

        if self.rect.bottom >= 700:
            self.rect.bottom = 700
            self.vel_y  = 0
            self.on_ground = True
        else:
            self.on_ground = False

        # ── Dizzy wobble overlay ───────────────────────────────────────────────
        if self.is_dizzy:
            self._dizzy_angle = (self._dizzy_angle + 15) % 360
            wobble = int(math.sin(math.radians(self._dizzy_angle)) * self.DIZZY_WOBBLE)
            self.rect.x += wobble

    # ── Jump helpers ──────────────────────────────────────────────────────────

    def jump(self):
        """Apply jump impulse. Returns True if the jump actually happened."""
        if self.on_ground:
            self.vel_y     = CAT_JUMP_POWER
            self.on_ground = False
            return True
        return False

    def handle_gesture_jump(self):
        """
        Consume a latched pinch-jump from the gesture state.
        Returns True only if a jump impulse was actually applied.
        Call once per frame from main loop BEFORE playing the sound.
        """
        if MEDIAPIPE_AVAILABLE and _gesture.consume_jump():
            return self.jump()   # True only when on_ground
        return False