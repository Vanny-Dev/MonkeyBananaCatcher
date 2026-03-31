import pygame
import sys
import random

sys.path.append("../")
from config import BANANA_PATH, ROTTEN_BANANA_PATH, ROCK_PATH, SCREEN_WIDTH, SCREEN_HEIGHT


class Food(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()
        self.image = pygame.image.load(BANANA_PATH).convert_alpha()
        self.image = pygame.transform.scale(self.image, (60, 60))
        self.rect = self.image.get_rect()
        self.reset()

    def reset(self):
        """Spawn banana at a random x position at the top of the screen"""
        self.rect.x = random.randint(0, SCREEN_WIDTH - 60)
        self.rect.y = -60
        self.speed = random.uniform(3, 7)

    def update(self):
        self.rect.y += self.speed
        if self.rect.top > SCREEN_HEIGHT:
            self.reset()

    def check_catch(self, player_rect):
        return self.rect.colliderect(player_rect)


class RottenBanana(pygame.sprite.Sprite):
    """Catching this loses 1 life and plays vomit sound."""

    def __init__(self):
        super().__init__()
        self.image = pygame.image.load(ROTTEN_BANANA_PATH).convert_alpha()
        self.image = pygame.transform.scale(self.image, (60, 60))
        self.rect = self.image.get_rect()
        self.reset()

    def reset(self):
        self.rect.x = random.randint(0, SCREEN_WIDTH - 60)
        self.rect.y = random.randint(-300, -60)   # staggered start
        self.speed = random.uniform(2, 5)

    def update(self):
        self.rect.y += self.speed
        if self.rect.top > SCREEN_HEIGHT:
            self.reset()

    def check_catch(self, player_rect):
        return self.rect.colliderect(player_rect)


class Rock(pygame.sprite.Sprite):
    """Catching this causes dizziness and loses 1 life."""

    def __init__(self):
        super().__init__()
        self.image = pygame.image.load(ROCK_PATH).convert_alpha()
        self.image = pygame.transform.scale(self.image, (55, 55))
        self.rect = self.image.get_rect()
        self.reset()

    def reset(self):
        self.rect.x = random.randint(0, SCREEN_WIDTH - 55)
        self.rect.y = random.randint(-400, -60)
        self.speed = random.uniform(4, 8)   # rocks fall faster

    def update(self):
        self.rect.y += self.speed
        if self.rect.top > SCREEN_HEIGHT:
            self.reset()

    def check_catch(self, player_rect):
        return self.rect.colliderect(player_rect)