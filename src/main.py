import pygame
import sys
import os
import time as t

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from entities.player import Player, start_camera_thread, MEDIAPIPE_AVAILABLE
from entities.foods import Food, RottenBanana, Rock

from config import (BACKGROUND_PATH,
                    SCREEN_WIDTH,
                    SCREEN_HEIGHT,
                    FPS,
                    HEART_PATH,
                    HEARTBREAK_PATH,
                    JUMP_SOUNDS,
                    EAT_SOUND,
                    VOMIT_SOUND,
                    DIZZY_SOUND,
                    COUNTDOWN_TICK_SOUND,
                    COUNTDOWN_GO_SOUND,
                    GAME_OVER_SOUND,
                    FONT_PATH,
                    MAX_LIVES,
                    )

NUM_BANANAS        = 4
NUM_ROTTEN_BANANAS = 2
NUM_ROCKS          = 2
SCORE_PER_BANANA   = 10

# Minimum frames between two hazard hits (invincibility window)
HIT_COOLDOWN = 90   # 1.5 s at 60 fps


# ── Helpers ──────────────────────────────────────────────────────────────────

def draw_score(screen, font, score):
    score_text = f"Score: {score}"
    shadow = font.render(score_text, True, (0, 0, 0))
    text   = font.render(score_text, True, (255, 255, 0))
    screen.blit(shadow, (12, 12))
    screen.blit(text,   (10, 10))


def draw_lives(screen, heart_img, heartbreak_img, lives):
    """Draw heart icons top-right to represent remaining lives."""
    icon_size = 40
    h_img = pygame.transform.scale(heart_img,      (icon_size, icon_size))
    b_img = pygame.transform.scale(heartbreak_img, (icon_size, icon_size))
    start_x = SCREEN_WIDTH - (MAX_LIVES * (icon_size + 6)) - 10
    for i in range(MAX_LIVES):
        img = h_img if i < lives else b_img
        screen.blit(img, (start_x + i * (icon_size + 6), 10))


def draw_status_label(screen, font, text, colour=(255, 80, 80)):
    """Small centred label near the top of the screen."""
    surf   = font.render(text, True, colour)
    shadow = font.render(text, True, (0, 0, 0))
    cx = SCREEN_WIDTH // 2 - surf.get_width() // 2
    screen.blit(shadow, (cx + 2, 72))
    screen.blit(surf,   (cx,     70))


def draw_game_over(screen, font, big_font, score):
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 160))
    screen.blit(overlay, (0, 0))

    title  = big_font.render("GAME OVER", True, (255, 60, 60))
    s_text = font.render(f"Final Score: {score}", True, (255, 255, 255))
    hint   = font.render("Press R to Restart  |  ESC to Quit", True, (200, 200, 200))

    screen.blit(title,  title.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 80)))
    screen.blit(s_text, s_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)))
    screen.blit(hint,   hint.get_rect(center=(SCREEN_WIDTH // 2,  SCREEN_HEIGHT // 2 + 70)))


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Monkey Banana Catcher")

    # Explicit mixer settings — avoids MP3 compatibility issues
    pygame.mixer.pre_init(44100, -16, 2, 512)
    pygame.mixer.init()
    pygame.mixer.set_num_channels(16)   # enough channels for overlapping sounds

    def load_sound(path, volume=1.0):
        """Load a sound file safely; returns a silent dummy on failure."""
        try:
            snd = pygame.mixer.Sound(path)
            snd.set_volume(volume)
            print(f"[SOUND OK] {path}")
            return snd
        except Exception as e:
            print(f"[SOUND FAIL] {path} — {e}")
            # Return a silent 0-length buffer so .play() never crashes
            buf = pygame.mixer.Sound(buffer=bytes(44))
            return buf

    # ── Camera / gesture thread ──────────────────────────────────────────────
    camera_active = start_camera_thread()
    if camera_active:
        print("[INFO] MediaPipe hand control active.")
    else:
        print("[INFO] MediaPipe not found – using keyboard only.")

    # ── Sounds ──────────────────────────────────────────────────────────────
    jump_sound           = load_sound(JUMP_SOUNDS,           volume=0.4)
    eat_sound           = load_sound(EAT_SOUND,            volume=1.0)
    vomit_sound          = load_sound(VOMIT_SOUND,           volume=0.8)
    dizzy_sound          = load_sound(DIZZY_SOUND,           volume=0.8)
    countdown_tick_sound = load_sound(COUNTDOWN_TICK_SOUND,  volume=1.0)
    countdown_go_sound   = load_sound(COUNTDOWN_GO_SOUND,    volume=1.0)
    game_over_sound      = load_sound(GAME_OVER_SOUND,       volume=1.0)

    last_jump_time = 0
    jump_delay = 200  # ms

    # ── Fonts ────────────────────────────────────────────────────────────────
    score_font   = pygame.font.Font(FONT_PATH, 54)
    small_font   = pygame.font.Font(FONT_PATH, 28)
    message_font = pygame.font.Font(FONT_PATH, 80)
    big_font     = pygame.font.Font(FONT_PATH, 120)

    # ── Images ───────────────────────────────────────────────────────────────
    background = pygame.image.load(BACKGROUND_PATH)
    background = pygame.transform.scale(background, (SCREEN_WIDTH, SCREEN_HEIGHT))

    heart      = pygame.image.load(HEART_PATH)
    heartbreak = pygame.image.load(HEARTBREAK_PATH)

    # ── Game state ───────────────────────────────────────────────────────────
    def build_game_state():
        player  = Player(100, 300)
        bananas = [Food() for _ in range(NUM_BANANAS)]
        for i, b in enumerate(bananas):
            b.rect.y = -60 - i * (SCREEN_HEIGHT // NUM_BANANAS)

        rotten  = [RottenBanana() for _ in range(NUM_ROTTEN_BANANAS)]
        rocks   = [Rock()         for _ in range(NUM_ROCKS)]

        return dict(
            player          = player,
            bananas         = bananas,
            rotten          = rotten,
            rocks           = rocks,
            score           = 0,
            lives           = MAX_LIVES,
            hit_cooldown    = 0,
            jump_count      = 0,
            table_7_triggered = False,
            # UI
            message         = "",
            show_message    = False,
            show_heart      = False,
            show_heartbreak = False,
            catch_flash_timer = 0,
            catch_flash_text  = "",
            status_label    = "",       # "Yuck!" / "Dizzy!" shown briefly
            status_timer    = 0,
            game_over       = False,
        )

    state = build_game_state()

    running = True
    clock   = pygame.time.Clock()

    # ── 5-second countdown ───────────────────────────────────────────────────
    countdown_font = pygame.font.Font(FONT_PATH, 160)
    ready_font     = pygame.font.Font(FONT_PATH, 80)
    countdown_start = pygame.time.get_ticks()
    COUNTDOWN_SECS  = 5
    last_tick_played = -1   # track which second we last played the tick for

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return

        elapsed = (pygame.time.get_ticks() - countdown_start) // 1000
        remaining = COUNTDOWN_SECS - elapsed

        if remaining <= 0:
            break

        # Play tick once per second
        if remaining != last_tick_played:
            countdown_tick_sound.play()
            last_tick_played = remaining

        screen.blit(background, (0, 0))

        # Dimmed overlay
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 120))
        screen.blit(overlay, (0, 0))

        # "GET READY" label
        ready_surf   = ready_font.render("GET READY!", True, (255, 255, 255))
        ready_shadow = ready_font.render("GET READY!", True, (0, 0, 0))
        rx = SCREEN_WIDTH  // 2 - ready_surf.get_width()  // 2
        ry = SCREEN_HEIGHT // 2 - 140
        screen.blit(ready_shadow, (rx + 3, ry + 3))
        screen.blit(ready_surf,   (rx, ry))

        # Big countdown number with a pulsing scale effect
        scale = 1.0 + 0.3 * (1.0 - ((pygame.time.get_ticks() - countdown_start) % 1000) / 1000)
        num_surf   = countdown_font.render(str(remaining), True, (255, 220, 0))
        num_shadow = countdown_font.render(str(remaining), True, (0, 0, 0))
        scaled_w = int(num_surf.get_width()  * scale)
        scaled_h = int(num_surf.get_height() * scale)
        num_surf   = pygame.transform.smoothscale(num_surf,   (scaled_w, scaled_h))
        num_shadow = pygame.transform.smoothscale(num_shadow, (scaled_w, scaled_h))
        nx = SCREEN_WIDTH  // 2 - scaled_w // 2
        ny = SCREEN_HEIGHT // 2 - scaled_h // 2 + 20
        screen.blit(num_shadow, (nx + 4, ny + 4))
        screen.blit(num_surf,   (nx, ny))

        pygame.display.flip()
        clock.tick(FPS)

    # ── "GO!" flash ──────────────────────────────────────────────────────────
    go_start = pygame.time.get_ticks()
    countdown_go_sound.play()
    while pygame.time.get_ticks() - go_start < 700:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return
        screen.blit(background, (0, 0))
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 80))
        screen.blit(overlay, (0, 0))
        go_surf   = countdown_font.render("GO!", True, (0, 255, 100))
        go_shadow = countdown_font.render("GO!", True, (0, 0, 0))
        gx = SCREEN_WIDTH  // 2 - go_surf.get_width()  // 2
        gy = SCREEN_HEIGHT // 2 - go_surf.get_height() // 2
        screen.blit(go_shadow, (gx + 4, gy + 4))
        screen.blit(go_surf,   (gx, gy))
        pygame.display.flip()
        clock.tick(FPS)

    while running:
        gs = state   # shorthand

        # ── Events ───────────────────────────────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            if event.type == pygame.KEYDOWN:
                if gs["game_over"]:
                    if event.key == pygame.K_r:
                        game_over_sound.stop()
                        state = build_game_state()
                        countdown_start  = pygame.time.get_ticks()
                        last_tick_played = -1
                        counting = True
                        while counting:
                            for e2 in pygame.event.get():
                                if e2.type == pygame.QUIT:
                                    pygame.quit(); return
                            elapsed   = (pygame.time.get_ticks() - countdown_start) // 1000
                            remaining = COUNTDOWN_SECS - elapsed
                            if remaining <= 0:
                                counting = False
                                break
                            if remaining != last_tick_played:
                                countdown_tick_sound.play()
                                last_tick_played = remaining
                            screen.blit(background, (0, 0))
                            ov = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
                            ov.fill((0, 0, 0, 120)); screen.blit(ov, (0, 0))
                            rs = ready_font.render("GET READY!", True, (255,255,255))
                            screen.blit(rs, rs.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2-140)))
                            scale = 1.0 + 0.3*(1.0-((pygame.time.get_ticks()-countdown_start)%1000)/1000)
                            ns = countdown_font.render(str(remaining), True, (255,220,0))
                            ns = pygame.transform.smoothscale(ns,(int(ns.get_width()*scale),int(ns.get_height()*scale)))
                            screen.blit(ns, ns.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2+20)))
                            pygame.display.flip(); clock.tick(FPS)
                        countdown_go_sound.play()
                        go_s = pygame.time.get_ticks()
                        while pygame.time.get_ticks()-go_s < 700:
                            for e2 in pygame.event.get():
                                if e2.type == pygame.QUIT:
                                    pygame.quit(); return
                            screen.blit(background,(0,0))
                            gs2=countdown_font.render("GO!",True,(0,255,100))
                            screen.blit(gs2, gs2.get_rect(center=(SCREEN_WIDTH//2,SCREEN_HEIGHT//2)))
                            pygame.display.flip(); clock.tick(FPS)
                        continue
                    if event.key == pygame.K_ESCAPE:
                        running = False

                else:
                    if event.key == pygame.K_SPACE:
                        now = pygame.time.get_ticks()
                        if now - last_jump_time > jump_delay and gs["player"].on_ground:
                            gs["player"].jump()
                            jump_sound.play()
                            last_jump_time = now
                            gs["jump_count"] += 1

        if gs["game_over"]:
            # ── Draw game-over overlay and wait ──────────────────────────────
            screen.blit(background, (0, 0))
            for banana in gs["bananas"]:
                screen.blit(banana.image, banana.rect)
            screen.blit(gs["player"].image, gs["player"].rect)
            draw_score(screen, score_font, gs["score"])
            draw_game_over(screen, small_font, big_font, gs["score"])
            pygame.display.flip()
            clock.tick(FPS)
            continue

        # ── Update ───────────────────────────────────────────────────────────
        keys   = pygame.key.get_pressed()
        player = gs["player"]

        # Gesture-based jump — must run BEFORE player.update() which clears on_ground
        if player.handle_gesture_jump():
            jump_sound.play()
            last_jump_time = pygame.time.get_ticks()

        player.update(keys)

        # Tick hit cooldown
        if gs["hit_cooldown"] > 0:
            gs["hit_cooldown"] -= 1

        # ── Good bananas ─────────────────────────────────────────────────────
        for banana in gs["bananas"]:
            banana.update()
            if banana.check_catch(player.rect):
                eat_sound.play()
                gs["score"] += SCORE_PER_BANANA
                gs["catch_flash_text"]  = f"+{SCORE_PER_BANANA}"
                gs["catch_flash_timer"] = 40
                banana.reset()

        # ── Rotten bananas ────────────────────────────────────────────────────
        for rb in gs["rotten"]:
            rb.update()
            if rb.check_catch(player.rect) and gs["hit_cooldown"] == 0:
                vomit_sound.play()
                gs["lives"]       -= 1
                gs["hit_cooldown"] = HIT_COOLDOWN
                gs["status_label"] = "Yuck!  -1 ❤"
                gs["status_timer"] = 90
                rb.reset()
                if gs["lives"] <= 0:
                    gs["game_over"] = True
                    game_over_sound.play()

        # ── Rocks ─────────────────────────────────────────────────────────────
        for rock in gs["rocks"]:
            rock.update()
            if rock.check_catch(player.rect) and gs["hit_cooldown"] == 0:
                dizzy_sound.play()
                player.trigger_dizzy()
                gs["lives"]       -= 1
                gs["hit_cooldown"] = HIT_COOLDOWN
                gs["status_label"] = "Dizzy! -1 ❤"
                gs["status_timer"] = 90
                rock.reset()
                if gs["lives"] <= 0:
                    gs["game_over"] = True
                    game_over_sound.play()

        # Status label timer
        if gs["status_timer"] > 0:
            gs["status_timer"] -= 1



        # ── Draw ─────────────────────────────────────────────────────────────
        screen.blit(background, (0, 0))

        for banana in gs["bananas"]:
            screen.blit(banana.image, banana.rect)

        for rb in gs["rotten"]:
            screen.blit(rb.image, rb.rect)

        for rock in gs["rocks"]:
            screen.blit(rock.image, rock.rect)

        screen.blit(player.image, player.rect)

        # Dizzy stars overlay
        if player.is_dizzy:
            star_font = pygame.font.Font(FONT_PATH, 36)
            for offset in (-30, 0, 30):
                star = star_font.render("Z", True, (255, 230, 0))
                screen.blit(star, (player.rect.centerx + offset - 8,
                                   player.rect.top - 30))

        draw_score(screen, score_font, gs["score"])
        draw_lives(screen, heart, heartbreak, gs["lives"])

        # Catch flash
        if gs["catch_flash_timer"] > 0:
            alpha = min(255, gs["catch_flash_timer"] * 8)
            flash_surf = score_font.render(gs["catch_flash_text"], True, (255, 230, 0))
            flash_surf.set_alpha(alpha)
            fx = player.rect.centerx - flash_surf.get_width() // 2
            fy = player.rect.top - 40
            screen.blit(flash_surf, (fx, fy))
            gs["catch_flash_timer"] -= 1

        # Status label (Yuck! / Dizzy!)
        if gs["status_timer"] > 0:
            draw_status_label(screen, small_font, gs["status_label"])

        # Story message
        if gs["show_message"]:
            lines = gs["message"].split('\n')
            text_surfaces   = [message_font.render(l, True, (255, 255, 255)) for l in lines]
            shadow_surfaces = [message_font.render(l, True, (0, 0, 0))       for l in lines]
            total_height = sum(s.get_height() for s in text_surfaces)
            start_y = SCREEN_HEIGHT // 2 - total_height // 2

            for i, (ts, ss) in enumerate(zip(text_surfaces, shadow_surfaces)):
                y_pos = start_y + i * ts.get_height()
                tr = ts.get_rect(center=(SCREEN_WIDTH // 2, y_pos))
                screen.blit(ss, (tr.x + 3, tr.y + 3))
                screen.blit(ts, tr)

            if gs["show_heartbreak"] and text_surfaces:
                hb_scaled = pygame.transform.scale(heartbreak, (100, 100))
                last_rect = text_surfaces[-1].get_rect(
                    center=(SCREEN_WIDTH // 2,
                            start_y + (len(text_surfaces) - 1) * text_surfaces[-1].get_height()))
                screen.blit(hb_scaled, (last_rect.right + 10,
                                        last_rect.y + (last_rect.height - hb_scaled.get_height()) // 2))

        # Gesture hint
        if camera_active:
            hint = small_font.render("Hand: left/right/open=jump", True, (200, 255, 200))
            screen.blit(hint, (SCREEN_WIDTH // 2 - hint.get_width() // 2, SCREEN_HEIGHT - 36))

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()


if __name__ == "__main__":
    main()