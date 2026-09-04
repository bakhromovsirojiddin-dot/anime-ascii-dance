#!/usr/bin/env python3
"""
✨ Terminal True-Color ASCII Video Player
Полноцветный консольный ASCII-плеер для аниме-видео (Caramelldansen)
с точной синхронизацией музыки через Pygame и ускоренным ANSI-рендерингом через NumPy.
"""

import os
import sys
import time
import argparse
from pathlib import Path

import cv2
import numpy as np
import pygame

# Наборы символов по яркости (от темного к светлому)
CHARSETS = {
    "detailed": "$@B%8&WM#*oahkbdpqwmZO0QLCJYXzcvunxrjft/\\|()1{}[]?-_+~<>i!lI;:,\"^`'. ",
    "standard": "@%#*+=-:. ",
    "blocks": "████████▓▓▒▒░░  ",
    "simple": "#*:. ",
}

def enable_windows_ansi():
    """Включает обработку ANSI escape-кодов в консоли Windows и переключает фон на черный."""
    if os.name == "nt":
        import ctypes
        kernel32 = ctypes.windll.kernel32
        h_out = kernel32.GetStdHandle(-11)
        mode = ctypes.c_ulong()
        kernel32.GetConsoleMode(h_out, ctypes.byref(mode))
        kernel32.SetConsoleMode(h_out, mode.value | 0x0007)
        # Сбрасываем синий фон PowerShell на глубокий черный
        os.system("color 07")
        os.system("")

def get_terminal_dimensions():
    """Получает текущие размеры терминала (столбцы, строки)."""
    try:
        size = os.get_terminal_size()
        return size.columns, size.lines
    except (AttributeError, OSError):
        return 120, 38

def compute_target_size(term_cols, term_rows, vid_w, vid_h, max_cols=None, char_aspect=2.05):
    """
    Рассчитывает размер матрицы символов.
    Важно: ширина строго ограничивается (term_cols - 2), чтобы избежать автоматического переноса строк в консоли!
    """
    safe_max_cols = max(10, term_cols - 2)
    max_w = min(safe_max_cols, max_cols) if max_cols else safe_max_cols
    max_h = max(5, term_rows - 2)

    vid_aspect = vid_w / float(vid_h)

    # Вариант 1: по ширине
    w1 = max_w
    h1 = int(w1 / vid_aspect / char_aspect)

    # Вариант 2: по высоте
    h2 = max_h
    w2 = int(h2 * vid_aspect * char_aspect)

    if h1 <= max_h:
        final_w = w1
        final_h = h1
    else:
        final_w = min(w2, max_w)
        final_h = h2

    # Обязательный зазор в 2 символа от края экрана для предотвращения дублирования строк
    final_w = min(final_w, safe_max_cols)
    return max(10, final_w), max(5, final_h)

def render_ascii_frame(rgb_frame, cols, rows, ramp, quant_step=16):
    """
    Сверхбыстрый векторизованный рендеринг кадра в строку ANSI TrueColor.
    Добавлен \033[K для мгновенной очистки остаточных символов справа от картинки.
    """
    disp = rgb_frame.astype(np.int32)
    brightness = 0.299 * disp[..., 0] + 0.587 * disp[..., 1] + 0.114 * disp[..., 2]
    char_idx = np.clip((brightness * (len(ramp) - 1) / 255).astype(np.int32), 0, len(ramp) - 1)

    color_q = (disp // quant_step) * quant_step
    key = (
        (color_q[..., 0].astype(np.int64) << 40)
        | (color_q[..., 1].astype(np.int64) << 32)
        | (color_q[..., 2].astype(np.int64) << 24)
        | char_idx.astype(np.int64)
    )

    lines = []
    for y in range(rows):
        row_key = key[y]
        changes = np.flatnonzero(row_key[1:] != row_key[:-1]) + 1
        starts = np.concatenate(([0], changes))
        ends = np.concatenate((changes, [cols]))

        parts = []
        for s, e in zip(starts.tolist(), ends.tolist()):
            r, g, b = disp[y, s]
            ch = ramp[char_idx[y, s]]
            parts.append(f"\033[38;2;{r};{g};{b}m" + ch * (e - s))
        # \033[K очищает строку до правого края терминала
        lines.append("".join(parts) + "\033[0m\033[K")

    return "\n".join(lines) + "\033[J"

def find_default_media():
    """Ищет видео и аудио файлы Caramelldansen в текущей директории."""
    base = Path(__file__).resolve().parent
    video_candidates = [
        base / "caramelldansen.mp4",
        base / "video.mp4",
        Path("caramelldansen.mp4"),
    ]
    audio_candidates = [
        base / "audio.mp3",
        base / "caramelldansen.mp3",
        Path("audio.mp3"),
    ]

    video_file = next((str(v) for v in video_candidates if v.is_file()), None)
    audio_file = next((str(a) for a in audio_candidates if a.is_file()), None)

    return video_file, audio_file

def play_ascii_video(video_path=None, audio_path=None, charset="detailed", fps=None, max_width=100, loop=True, quant_step=16):
    enable_windows_ansi()

    if not video_path:
        default_vid, default_aud = find_default_media()
        video_path = default_vid
        if not audio_path:
            audio_path = default_aud

    if not video_path or not os.path.isfile(video_path):
        print(f"\033[91m[Ошибка] Видеофайл не найден: {video_path}\033[0m")
        print("Пожалуйста, убедитесь, что 'caramelldansen.mp4' лежит в папке проекта.")
        return

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"\033[91m[Ошибка] Не удалось открыть видео через OpenCV: {video_path}\033[0m")
        return

    vid_w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    vid_h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    source_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    target_fps = fps if fps else min(30.0, source_fps)
    frame_duration = 1.0 / target_fps

    ramp = CHARSETS.get(charset, CHARSETS["detailed"])

    # Инициализация звука через Pygame
    has_audio = False
    if audio_path and os.path.isfile(audio_path):
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)
            pygame.mixer.music.load(audio_path)
            pygame.mixer.music.play(-1 if loop else 0)
            has_audio = True
        except Exception as e:
            print(f"\033[93m[Предупреждение] Не удалось запустить аудио: {e}\033[0m")

    # Подготовка терминала: очистка и скрытие курсора
    sys.stdout.buffer.write(b"\033[2J\033[H\033[?25l")
    sys.stdout.buffer.flush()

    start_time = time.perf_counter()
    frame_idx = 0
    max_frame_skip = 2

    # Предварительный расчет размеров
    term_cols, term_rows = get_terminal_dimensions()
    cols, rows = compute_target_size(term_cols, term_rows, vid_w, vid_h, max_cols=max_width)
    last_term_check = time.perf_counter()

    try:
        while True:
            # Чтение кадра
            ret, frame = cap.read()
            if not ret:
                if loop:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ret, frame = cap.read()
                    if not ret:
                        break
                    start_time = time.perf_counter()
                    frame_idx = 0
                else:
                    break

            # Синхронизация по времени (Audio-Video Sync)
            target_time = start_time + frame_idx * frame_duration
            now = time.perf_counter()
            lag = now - target_time

            # Если отстаем, мягко пропускаем
            if lag > frame_duration * 1.5:
                frame_idx += 1
                continue

            # Если быстрее, ждем точного тайминга
            if lag < 0:
                time.sleep(-lag)

            # Проверяем размер терминала не каждый кадр, а раз в секунду
            if now - last_term_check > 1.0:
                term_cols, term_rows = get_terminal_dimensions()
                cols, rows = compute_target_size(term_cols, term_rows, vid_w, vid_h, max_cols=max_width)
                last_term_check = now

            # Ресайз и цветовое преобразование
            small_frame = cv2.resize(frame, (cols, rows), interpolation=cv2.INTER_LINEAR)
            rgb_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

            # Быстрый ASCII-рендеринг
            ascii_text = render_ascii_frame(rgb_frame, cols, rows, ramp, quant_step=quant_step)

            # Моментальный вывод в бинарный буфер
            payload = b"\033[H" + ascii_text.encode("utf-8")
            sys.stdout.buffer.write(payload)
            sys.stdout.buffer.flush()

            frame_idx += 1

    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.buffer.write(b"\033[0m\033[?25h\n\n")
        sys.stdout.buffer.flush()
        if has_audio:
            try:
                pygame.mixer.music.stop()
                pygame.mixer.quit()
            except Exception:
                pass
        cap.release()
        print("\033[92m[Завершено] Сеанс воспроизведения остановлен.\033[0m")

def main():
    parser = argparse.ArgumentParser(description="Terminal True-Color ASCII Video Player")
    parser.add_argument("video", nargs="?", default=None, help="Путь к видеофайлу (по умолчанию caramelldansen.mp4)")
    parser.add_argument("--audio", default=None, help="Путь к аудиофайлу (по умолчанию audio.mp3)")
    parser.add_argument("--charset", choices=list(CHARSETS.keys()), default="detailed", help="Набор ASCII-символов")
    parser.add_argument("--fps", type=float, default=None, help="Частота кадров (по умолчанию из видео)")
    parser.add_argument("--width", type=int, default=105, help="Ширина в символах (по умолчанию 105 для плавности)")
    parser.add_argument("--quant", type=int, default=16, help="Шаг квантования цвета (16 дает высокую скорость)")
    parser.add_argument("--no-loop", action="store_true", help="Не зацикливать видео")

    args = parser.parse_args()
    play_ascii_video(
        video_path=args.video,
        audio_path=args.audio,
        charset=args.charset,
        fps=args.fps,
        max_width=args.width,
        quant_step=args.quant,
        loop=not args.no_loop
    )

if __name__ == "__main__":
    main()
