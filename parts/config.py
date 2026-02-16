import os
from pathlib import Path

class Config:
    BASE_DIR = Path(__file__).parent.parent
    IMAGES_DIR = BASE_DIR / "images"
    MODELS_DIR = BASE_DIR / "models"
    
    WINDOW_WIDTH = 800
    WINDOW_HEIGHT = 1000
    CHARACTER_DISPLAY_SIZE = (400, 400)
    PHYSICS_FPS = 60
    GRAVITY = (0, 900.0)

    # 4x4分割の基本設定
    GRID_COLS = 4
    GRID_ROWS = 4
    TOTAL_EXPRESSIONS = 16
    CELL_SIZE = 256  # 画像読み込み時に自動更新されます

    EXPRESSIONS = [
        "neutral", "happy", "sad", "angry", 
        "surprised", "blink", "wink", "smile",
        "thinking", "embarrassed", "sleepy", "cry",
        "serious", "love", "shout", "dead"
    ]

    VOICEVOX_ENGINE_URL = "http://localhost:50021"
    VOICEVOX_SPEAKER_ID = 3
    OLLAMA_MODEL = "qwen2.5:latest"

    @classmethod
    def ensure_directories(cls):
        cls.IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        cls.MODELS_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def set_cell_preset(cls, preset_name: str):
        # 互換性のために残していますが、現在は自動取得を優先しています
        print(f"⚙️ Config: プリセット '{preset_name}' を適用しました")