# 🍌 Monkey Banana Catcher

A fun gesture-controlled jungle platformer built with **pygame** and **MediaPipe**. Control a monkey with your bare hands — tilt your left index finger to move and pinch your right hand to jump. Catch bananas to score, but watch out for rotten bananas and rocks!

---

## 🎮 Gameplay

- **Catch bananas** to earn points (+10 each)
- **Avoid rotten bananas** — catching one loses 1 life and triggers a vomit reaction
- **Avoid rocks** — catching one makes the monkey dizzy (controls invert!) and loses 1 life
- You have **3 lives** — lose them all and it's **Game Over**
- Press **R** to restart, **ESC** to quit

---

## 🖐️ Gesture Controls

> Requires a webcam. A small debug window will open showing your hand landmarks in real time.

| Hand           | Gesture                                 | Action                          |
|----------------|-----------------------------------------|---------------------------------|
| **Left hand**  | Point index finger **upright**          | No movement (neutral)           |
| **Left hand**  | Tilt index finger **left**              | Move left — more tilt = faster  |
| **Left hand**  | Tilt index finger **right**             | Move right — more tilt = faster |
| **Right hand** | **Pinch** (thumb + index tips together) | Jump                            |

**Speed ramp:** tilting past ~10° starts moving the monkey. At ~70° tilt you hit maximum speed (2.5× base). Anything in between scales proportionally.

> **No webcam / MediaPipe not installed?** The game automatically falls back to keyboard-only controls.

### ⌨️ Keyboard Controls (fallback)

| Key       | Action                        |
|-----------|-------------------------------|
| `←` / `A` | Move left                     |
| `→` / `D` | Move right                    |
| `SPACE`   | Jump                          |
| `R`       | Restart (on Game Over screen) |
| `ESC`     | Quit                          |

---

## 📁 Project Structure

```
project/
├── src/
│   ├── main.py              # Game loop, scoring, lives, UI
│   ├── config.py            # All constants and asset paths
│   └── entities/
│       ├── player.py        # Player sprite + MediaPipe gesture system
│       └── foods.py         # Banana, RottenBanana, Rock classes
├── assets/
│   ├── images/
│   │   ├── jungle.jpg       # Background
│   │   ├── monkey.png       # Player sprite
│   │   ├── banana.png       # Good banana
│   │   ├── rotten_banana.png# Hazard — loses 1 life
│   │   ├── rock.png         # Hazard — dizzy + loses 1 life
│   │   ├── heart.png        # Life indicator (full)
│   │   └── heartbreak.png   # Life indicator (lost)
│   ├── sounds/
│   │   ├── jump.mp3         # Jump sound effect
│   │   ├── eat.wav         # Banana catch sound
│   │   ├── vomit.mp3        # Rotten banana hit
│   │   ├── dizzy.mp3        # Rock hit
│   │   ├── countdown_tick.mp3  # Short beep — plays each second (5→1)
│   │   ├── countdown_go.wav    # "GO!" sound
│   │   ├── faaah.mp3        # For Fun Sound Effect Rock hit
│   │   └── gameover.mp3       # Plays when all lives are lost
│   └── fonts/
│       └── slkscr.ttf       # Pixel font
├── requirements.txt
└── README.md
```

---

## 🚀 Installation

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/monkey-banana-catcher.git
cd monkey-banana-catcher
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the game

```bash
cd src
python main.py
```

---

## 📦 Requirements

| Package         | Version     | Purpose                       |
|-----------------|-------------|-------------------------------|
| `pygame`        | ≥ 2.5.0     | Game engine, rendering, audio |
| `mediapipe`     | ≥ 0.10.9    | Hand landmark detection       |
| `opencv-python` | ≥ 4.13.0.92 | Webcam capture, debug window  |
| `numpy`         | ≥ 1.24.0    | Array ops used by MediaPipe   |

> `mediapipe`, `opencv-python`, and `numpy` are **optional** — the game runs in keyboard-only mode if they are not installed.

---

## 🔊 Sound Notes

The game uses `pygame.mixer.pre_init(44100, -16, 2, 512)` for reliable MP3 playback. If a sound file is missing or corrupt, the game will print a `[SOUND FAIL]` warning in the terminal and continue running silently for that effect rather than crashing.

---

## 🐛 Troubleshooting

| Problem                      | Fix                                                                                                            |
|------------------------------|----------------------------------------------------------------------------------------------------------------|
| Gesture controls not working | Make sure `mediapipe` and `opencv-python` are installed. Check terminal for `[INFO]` messages at startup.      |
| Jump not responding          | Make sure your **right hand** is visible and you are doing a clear pinch (thumb tip touching index tip).       |
| No sound                     | Check that all `.mp3` files exist in `assets/sounds/`. Terminal will show `[SOUND FAIL]` for any missing file. |
| Game runs slowly             | Close the MediaPipe debug window or reduce webcam resolution in `player.py`.                                   |
| `ModuleNotFoundError`        | Run `pip install -r requirements.txt` inside your virtual environment.                                         |

---

## 📝 License

MIT License — feel free to use, modify, and share.