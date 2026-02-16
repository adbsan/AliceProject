import os
from PIL import Image
from parts.config import Config

class SpriteManager:
    def __init__(self):
        self.sprites = {}
        self.current_expression = "neutral"
        self.load_spritesheet()

    def load_spritesheet(self):
        """images/default_images.png を読み込み、16等分(4x4)してロードする"""
        path = Config.IMAGES_DIR / "default_images.png"
        
        if not path.exists():
            print(f"❌ ファイルが見つかりません: {path}")
            self._create_dummy_sprites()
            return

        # 画像を開く
        full_sheet = Image.open(path).convert("RGBA")
        img_w, img_h = full_sheet.size
        
        # 4x4であることを前提に、1マスの幅と高さを計算
        cell_w = img_w // 4
        cell_h = img_h // 4
        
        # 物理演算で使うサイズもこれに合わせる（重要！）
        Config.CELL_SIZE = cell_w 

        # 表情名リストを順番にスキャンして切り出す
        for i, expr in enumerate(Config.EXPRESSIONS):
            if i >= 16: break # 最大16個まで
                
            # 何列目(col)、何行目(row)かを計算
            col = i % 4
            row = i // 4
            
            # クロップ範囲 (左, 上, 右, 下)
            left = col * cell_w
            top = row * cell_h
            right = left + cell_w
            bottom = top + cell_h
            
            # 正確な範囲で切り出し
            self.sprites[expr] = full_sheet.crop((left, top, right, bottom))
        
        print(f"✅ ロード完了: {img_w}x{img_h} の画像を {cell_w}x{cell_h} ずつ16分割しました")

    def get_current_sprite(self):
        return self.sprites.get(self.current_expression, self.sprites.get("neutral"))

    def set_expression(self, expression):
        if expression in self.sprites:
            self.current_expression = expression
    
    def _create_dummy_sprites(self):
        """スプライトシートが見つからない場合のダミースプライトを生成"""
        # デフォルトサイズ（256x256）
        dummy_size = Config.CELL_SIZE if hasattr(Config, 'CELL_SIZE') else 256
        
        # 各表情に対してダミースプライトを作成
        for expr in Config.EXPRESSIONS:
            # シンプルな色付き四角形をダミーとして作成
            # 表情ごとに異なる色を使用して識別しやすくする
            dummy_img = Image.new("RGBA", (dummy_size, dummy_size), (200, 200, 255, 255))
            
            # 表情名をテキストで描画（PILのImageDrawを使用）
            from PIL import ImageDraw, ImageFont
            draw = ImageDraw.Draw(dummy_img)
            
            # フォントの試行（システムフォントを使用）
            try:
                # Windowsの場合
                font = ImageFont.truetype("arial.ttf", 20)
            except:
                try:
                    # Linuxの場合
                    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
                except:
                    # フォールバック
                    font = ImageFont.load_default()
            
            # テキストを中央に描画
            text = expr[:8]  # 長い名前は切り詰め
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            position = ((dummy_size - text_width) // 2, (dummy_size - text_height) // 2)
            
            draw.text(position, text, fill=(0, 0, 0, 255), font=font)
            
            self.sprites[expr] = dummy_img
        
        print(f"⚠️ ダミースプライトを {len(self.sprites)} 個生成しました")