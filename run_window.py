#!/usr/bin/env python3
"""
🖥️ GPU-Accelerated Fullscreen ASCII Video Player (Pygame)
Воспроизводит цветной ASCII-видеоряд Caramelldansen на полный экран
с автоматической адаптацией под любое разрешение, аппаратным ускорением GPU на 60 FPS
и возможностью переключения в полноэкранный режим по клавише F.
"""

import os
import sys
import time
import cv2
import numpy as np
import pygame

RAMP = "$@B%8&WM#*oahkbdpqwmZO0QLCJYXzcvunxrjft/\\|()1{}[]?-_+~<>i!lI;:,\"^`'. "

def compute_grid_layout(win_w, win_h, vid_aspect=16.0/9.0, font_size=16):
    """
    Рассчитывает параметры сетки символов, чтобы видео занимало максимум экрана.
    """
    font = pygame.font.SysFont("Consolas", font_size, bold=True)
    char_w, char_h = font.size("M")
    if char_w <= 0: char_w = 9
    if char_h <= 0: char_h = 16

    char_aspect = char_h / float(char_w)

    # Максимальное количество символов, умещающееся на экране
    max_cols = max(10, win_w // char_w)
    max_rows = max(5, win_h // char_h)

    # Рассчитываем cols и rows с сохранением пропорций видео
    cols_from_h = int(max_rows * vid_aspect * char_aspect)
    if cols_from_h <= max_cols:
        cols = cols_from_h
        rows = max_rows
    else:
        cols = max_cols
        rows = int(cols / (vid_aspect * char_aspect))

    cols = max(10, cols)
    rows = max(5, rows)

    render_w = cols * char_w
    render_h = rows * char_h
    offset_x = (win_w - render_w) // 2
    offset_y = (win_h - render_h) // 2

    return font, char_w, char_h, cols, rows, offset_x, offset_y

def play_in_window(video_path="caramelldansen.mp4", audio_path="audio.mp3"):
    pygame.init()
    pygame.font.init()

    if not os.path.isfile(video_path):
        print(f"[Ошибка] Видеофайл '{video_path}' не найден!")
        return

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"[Ошибка] Не удалось открыть '{video_path}'!")
        return

    vid_w = cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 426
    vid_h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 240
    vid_aspect = vid_w / float(vid_h)

    # Определяем разрешение рабочего стола
    display_info = pygame.display.Info()
    screen_w = min(1600, display_info.current_w - 80)
    screen_h = min(900, display_info.current_h - 100)

    # Открываем окно с поддержкой изменения размера
    screen = pygame.display.set_mode((screen_w, screen_h), pygame.RESIZABLE)
    pygame.display.set_caption("✨ Caramelldansen Fullscreen ASCII Player (GPU 60 FPS) [F: Полный экран]")
    clock = pygame.time.Clock()

    font_size = 16
    is_fullscreen = False

    # Рассчитываем начальную сетку
    font, char_w, char_h, cols, rows, off_x, off_y = compute_grid_layout(screen_w, screen_h, vid_aspect, font_size)

    # Запуск аудио через Pygame Mixer
    if audio_path and os.path.isfile(audio_path):
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)
            pygame.mixer.music.load(audio_path)
            pygame.mixer.music.play(-1)
        except Exception as e:
            print(f"[Предупреждение] Аудио: {e}")

    ramp_len = len(RAMP)
    running = True

    while running:
        clock.tick(30)  # Синхронизация с 30 FPS

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE or event.key == pygame.K_q:
                    running = False

                elif event.key == pygame.K_SPACE:
                    if pygame.mixer.music.get_busy():
                        pygame.mixer.music.pause()
                    else:
                        pygame.mixer.music.unpause()

                elif event.key == pygame.K_f:
                    # Переключение полноэкранного режима
                    is_fullscreen = not is_fullscreen
                    if is_fullscreen:
                        screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
                    else:
                        screen = pygame.display.set_mode((screen_w, screen_h), pygame.RESIZABLE)
                    cur_w, cur_h = screen.get_size()
                    font, char_w, char_h, cols, rows, off_x, off_y = compute_grid_layout(cur_w, cur_h, vid_aspect, font_size)

                elif event.key in (pygame.K_PLUS, pygame.K_EQUALS):
                    # Увеличение шрифта
                    font_size = min(32, font_size + 2)
                    cur_w, cur_h = screen.get_size()
                    font, char_w, char_h, cols, rows, off_x, off_y = compute_grid_layout(cur_w, cur_h, vid_aspect, font_size)

                elif event.key in (pygame.K_MINUS, pygame.K_UNDERSCORE):
                    # Уменьшение шрифта (более высокая плотность ASCII)
                    font_size = max(8, font_size - 2)
                    cur_w, cur_h = screen.get_size()
                    font, char_w, char_h, cols, rows, off_x, off_y = compute_grid_layout(cur_w, cur_h, vid_aspect, font_size)

            elif event.type == pygame.VIDEORESIZE:
                cur_w, cur_h = event.w, event.h
                screen = pygame.display.set_mode((cur_w, cur_h), pygame.RESIZABLE)
                font, char_w, char_h, cols, rows, off_x, off_y = compute_grid_layout(cur_w, cur_h, vid_aspect, font_size)

        ret, frame = cap.read()
        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = cap.read()
            if not ret:
                break

        # Ресайз кадра точно под рассчитанную сетку символов
        small = cv2.resize(frame, (cols, rows), interpolation=cv2.INTER_LINEAR)
        rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)

        # Вычисление яркости и индексов символов (Rec. 601)
        gray = (0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]).astype(np.int32)
        char_indices = np.clip(gray * (ramp_len - 1) // 255, 0, ramp_len - 1)

        # Заливка черным фоном
        screen.fill((5, 5, 10))

        # Отрисовка символов по всей сетке
        for y in range(rows):
            y_pos = off_y + y * char_h
            for x in range(cols):
                ch = RAMP[char_indices[y, x]]
                if ch == ' ':
                    continue
                color = (int(rgb[y, x, 0]), int(rgb[y, x, 1]), int(rgb[y, x, 2]))
                ch_surf = font.render(ch, True, color)
                screen.blit(ch_surf, (off_x + x * char_w, y_pos))

        pygame.display.flip()

    cap.release()
    try:
        pygame.mixer.music.stop()
        pygame.quit()
    except Exception:
        pass

if __name__ == "__main__":
    play_in_window()
