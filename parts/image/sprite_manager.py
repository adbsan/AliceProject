import numpy as np
import warnings
from PIL import Image as PILImage, ImageFilter, ImageOps, ImageEnhance
from pathlib import Path
from parts.config import Config

try:
    from scipy import ndimage
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    print("警告: scipyがインストールされていません。一部の機能が制限されます。")

# NumPyの警告を抑制（画像処理では無効値が発生することがある）
warnings.filterwarnings('ignore', category=RuntimeWarning, module='numpy')
np.seterr(invalid='ignore', divide='ignore')


class SpriteManager:
    def __init__(self):
        self.sprites = {}
        self.current_expression = "neutral"
        self.sprite_size = 1024  # 出力は常に 1024 x 1024
        self.load_spritesheet()

    def load_spritesheet(self):
        raw_path = Config.IMAGES_DIR / "default_images.png"
        processed_path = Config.IMAGES_DIR / "processed_default_images.png"

        # 処理済みファイルが存在し、元の画像より新しい場合は読み込むだけ
        if processed_path.exists() and raw_path.exists():
            # 元の画像と処理済み画像の更新時刻を比較
            original_mtime = raw_path.stat().st_mtime
            processed_mtime = processed_path.stat().st_mtime
            
            if processed_mtime >= original_mtime:
                # 処理済みファイルを読み込むだけ
                print(f"Loading existing cache: {processed_path}")
                img = PILImage.open(processed_path).convert("RGBA")
                # 1024x1024にリサイズ（既に1024x1024の場合はそのまま）
                if img.size != (self.sprite_size, self.sprite_size):
                    img = img.resize((self.sprite_size, self.sprite_size), PILImage.LANCZOS)
                self.sprites["neutral"] = img
                return
        
        # 処理済みファイルがない、または元の画像が新しい場合は処理を実行
        if not raw_path.exists():
            print("Raw image not found.")
            return

        print(f"Processing spritesheet: {raw_path}")
        full_sheet = PILImage.open(raw_path).convert("RGBA")
        
        # スプライトシートから1つのキャラクター（左上のneutral）だけを切り出す
        img_w, img_h = full_sheet.size
        
        # グリッドサイズを自動検出（2x2または4x4）
        # 2x2グリッドの場合: 各セルは約 img_w/2 x img_h/2
        # 4x4グリッドの場合: 各セルは約 img_w/4 x img_h/4
        
        # まず2x2グリッドかどうかを判定（1024x1024の画像で2x2なら各セル512x512）
        if img_w >= 2 * 400 and img_h >= 2 * 400:
            # 2x2グリッドの可能性をチェック
            # 画像サイズが1024x1024程度で、2x2グリッドの場合
            if abs(img_w - 1024) < 100 and abs(img_h - 1024) < 100:
                # 2x2グリッドと判断して左上のセルを切り出す
                cell_w = img_w // 2
                cell_h = img_h // 2
                img = full_sheet.crop((0, 0, cell_w, cell_h))
                print(f"📦 2x2グリッドから左上のセル ({cell_w}x{cell_h}) を切り出しました")
            elif img_w >= 4 * 256 and img_h >= 4 * 256:
                # 4x4グリッドと判断して左上のセルを切り出す
                cell_w = img_w // 4
                cell_h = img_h // 4
                img = full_sheet.crop((0, 0, cell_w, cell_h))
                print(f"📦 4x4グリッドから左上のセル ({cell_w}x{cell_h}) を切り出しました")
            else:
                # 単一画像として処理
                img = full_sheet
                print(f"📦 単一画像として処理します ({img_w}x{img_h})")
        else:
            # 単一画像として処理
            img = full_sheet
            print(f"📦 単一画像として処理します ({img_w}x{img_h})")

        # 処理順序を変更：トリミング前にノイズ除去をしない
        # 背景除去 → エッジ調整（軽め） → トリミング → ノイズ除去（トリミング後） → エッジ調整（最終）
        img = self._advanced_background_removal(img)
        img = self._smooth_edges(img)  # 軽めのエッジ調整
        img = self._crop_to_square(img, self.sprite_size)  # トリミング（内部でノイズ除去も実行）
        img = self._remove_noise(img)  # トリミング後のノイズ除去
        img = self._smooth_edges(img)  # 最終的なエッジ調整

        # 最終的に1024x1024であることを確認
        if img.size != (self.sprite_size, self.sprite_size):
            img = img.resize((self.sprite_size, self.sprite_size), PILImage.LANCZOS)

        # 処理済みファイルを保存
        processed_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(processed_path)

        self.sprites["neutral"] = img
        print(f"✅ 1体のキャラクターを {self.sprite_size}x{self.sprite_size} で処理完了")

    # ===================== 背景除去系 =====================

    def _advanced_background_removal(self, img: PILImage.Image) -> PILImage.Image:
        """背景色を自動推定して高精度に除去（赤色ハロー完全除去版）"""
        arr = np.array(img).astype(np.float32)  # float32で計算精度を上げる
        r, g, b, a = arr[..., 0], arr[..., 1], arr[..., 2], arr[..., 3]

        h, w = r.shape

        # 1. 画像の外周ピクセルから「背景色」を推定（より広範囲に）
        border_thickness = max(15, min(h, w) // 20)  # さらに広い範囲をサンプル
        top = arr[0:border_thickness, :, :3]
        bottom = arr[h-border_thickness:h, :, :3]
        left = arr[:, 0:border_thickness, :3]
        right = arr[:, w-border_thickness:w, :3]
        border_pixels = np.concatenate(
            [top.reshape(-1, 3), bottom.reshape(-1, 3),
             left.reshape(-1, 3), right.reshape(-1, 3)],
            axis=0
        )
        
        # 中央値と平均の両方を使用してより正確な背景色を推定
        bg_color_median = np.median(border_pixels, axis=0)
        bg_color_mean = np.mean(border_pixels, axis=0)
        bg_color = (bg_color_median * 0.8 + bg_color_mean * 0.2)

        # 2. 赤色を積極的に検出（赤背景の場合）
        # 赤色の特徴: Rが高く、GとBが低い
        red_mask = (r > 150) & (g < 100) & (b < 100)
        
        # 3. 背景色との距離を計算（NaN/Infを防ぐ）
        rgb = arr[..., :3]
        diff = rgb - bg_color[None, None, :]
        
        # ユークリッド距離（NaN/Inf/負の値を安全に処理）
        dist_squared = np.sum(diff ** 2, axis=-1)
        # 負の値を0にクリップ（数値誤差による負の値の発生を防ぐ）
        dist_squared = np.maximum(dist_squared, 0.0)
        dist_squared = np.nan_to_num(dist_squared, nan=0.0, posinf=1e6, neginf=0.0)
        # 安全に平方根を計算（負の値は既に0にクリップ済み）
        dist_euclidean = np.sqrt(dist_squared)
        dist_euclidean = np.nan_to_num(dist_euclidean, nan=0.0, posinf=1e6, neginf=0.0)
        
        # マンハッタン距離
        dist_manhattan = np.sum(np.abs(diff), axis=-1)
        dist_manhattan = np.nan_to_num(dist_manhattan, nan=0.0, posinf=1e6, neginf=0.0)
        
        # 組み合わせた距離（NaN/Infを安全に処理）
        dist_combined = dist_euclidean * 0.8 + (dist_manhattan / 3.0) * 0.2
        dist_combined = np.nan_to_num(dist_combined, nan=0.0, posinf=1e6, neginf=0.0)
        
        # 4. 適応的な閾値（画像の統計に基づく）
        border_distances = dist_combined[0:border_thickness, :]
        border_distances = np.concatenate([
            border_distances.flatten(),
            dist_combined[h-border_thickness:h, :].flatten(),
            dist_combined[:, 0:border_thickness].flatten(),
            dist_combined[:, w-border_thickness:w].flatten()
        ])
        
        # 有効な値のみを使用（NaN/Infを除外）
        valid_distances = border_distances[np.isfinite(border_distances) & (border_distances >= 0)]
        if len(valid_distances) > 0:
            bg_threshold = np.percentile(valid_distances, 90) + 20.0  # より厳密に
            # 閾値も有効な値であることを確認
            bg_threshold = max(0.0, min(bg_threshold, 1e6))
        else:
            bg_threshold = 50.0
        
        # 5. 背景マスクを作成（赤色マスクも含める）
        bg_mask = (dist_combined < bg_threshold) | red_mask
        
        # 6. エッジ付近の赤色も除去（より積極的に）
        # エッジ検出（簡易版、安全に）
        try:
            gray = (r * 0.299 + g * 0.587 + b * 0.114)
            # 簡易的なエッジ検出（上下左右の差分）
            edge_h = np.zeros_like(gray)
            edge_v = np.zeros_like(gray)
            edge_h[:, 1:] = np.abs(gray[:, 1:] - gray[:, :-1])
            edge_v[1:, :] = np.abs(gray[1:, :] - gray[:-1, :])
            edge_strength = edge_h + edge_v
            edge_mask = edge_strength > 20
            edge_red_mask = edge_mask & red_mask
            bg_mask = bg_mask | edge_red_mask
        except Exception as e:
            # エラー時は赤色マスクのみ使用
            print(f"エッジ検出でエラー（無視します）: {e}")
            pass

        # 7. キャラ部分のマスクに変換して精製
        char_mask = self._refine_mask(bg_mask)
        img.putalpha(char_mask)

        return img

    def _refine_mask(self, bg_mask: np.ndarray) -> PILImage.Image:
        """マスクを精製して小さいノイズを除去（赤色ハロー完全除去版）"""
        # 背景マスクを反転 → キャラ領域を 255 に
        char_mask = (~bg_mask).astype("uint8") * 255
        mask_img = PILImage.fromarray(char_mask, mode="L")

        # 1. 強力なモルフォロジー演算で外側のノイズを完全に削除（より強力に）
        mask_img = self._morphology_clean(mask_img, iterations=5)  # 5回に増加

        # 2. 小さな孤立したノイズを除去（連結成分解析）
        mask_img = self._remove_small_components(mask_img, min_size=100)  # より大きなノイズも除去

        # 3. エッジを滑らかに（段階的に、最適化された回数で適用）
        mask_img = mask_img.filter(ImageFilter.GaussianBlur(radius=1.2))  # より強く
        # SMOOTH_MOREは2回で十分（過度な適用は品質を低下させる可能性がある）
        mask_img = mask_img.filter(ImageFilter.SMOOTH_MORE)
        mask_img = mask_img.filter(ImageFilter.SMOOTH_MORE)
        
        # 4. 適応的閾値でマスクをくっきり（ただしエッジは滑らかに保つ）
        mask_img = self._adaptive_threshold_soft(mask_img, threshold_ratio=0.5)  # より厳密に

        # 5. 最終的なエッジ平滑化（より強力に）
        mask_img = mask_img.filter(ImageFilter.GaussianBlur(radius=0.8))

        return mask_img

    def _morphology_clean(self, mask_img, iterations=3):
        """モルフォロジー演算でクリーニング（強め）"""
        for _ in range(iterations):
            # 収縮（外側の細かいノイズを落とす）
            mask_img = mask_img.filter(ImageFilter.MinFilter(3))
        for _ in range(iterations):
            # 膨張（削れたキャラ輪郭を戻す）
            mask_img = mask_img.filter(ImageFilter.MaxFilter(3))
        return mask_img
    
    def _remove_small_components(self, mask_img, min_size=50):
        """小さな孤立したノイズコンポーネントを除去"""
        if not SCIPY_AVAILABLE:
            # scipyがない場合は、より強力なモルフォロジー演算で代替
            for _ in range(2):
                mask_img = mask_img.filter(ImageFilter.MinFilter(5))
            for _ in range(2):
                mask_img = mask_img.filter(ImageFilter.MaxFilter(5))
            return mask_img
        
        arr = np.array(mask_img)
        # 二値化
        binary = (arr > 127).astype(np.uint8)
        
        # 連結成分ラベリング
        labeled, num_features = ndimage.label(binary)
        
        # 各コンポーネントのサイズを計算
        component_sizes = ndimage.sum(binary, labeled, range(1, num_features + 1))
        
        # 小さなコンポーネントを除去
        for i, size in enumerate(component_sizes, start=1):
            if size < min_size:
                arr[labeled == i] = 0
        
        return PILImage.fromarray(arr, mode="L")

    def _adaptive_threshold(self, img, block_size=35, C=10):
        """適応的閾値処理（numpy ベースに最適化）"""
        arr = np.array(img).astype(np.int16)

        # グローバルな平均を使った簡易版で十分な場合が多い
        mean = np.mean(arr)
        threshold = mean - C
        result = (arr > threshold).astype("uint8") * 255

        return PILImage.fromarray(result, mode="L")
    
    def _adaptive_threshold_soft(self, img, threshold_ratio=0.4):
        """ソフト閾値処理（エッジを滑らかに保ちながら二値化）"""
        arr = np.array(img).astype(np.float32)
        
        # 有効な値のみを使用（NaN/Infを除外）
        valid_arr = arr[np.isfinite(arr) & (arr >= 0) & (arr <= 255)]
        
        if len(valid_arr) == 0:
            # 有効な値がない場合は元の画像を返す
            return img
        
        # Otsuの方法に基づく適応的閾値
        # ヒストグラムから最適な閾値を計算
        hist, bins = np.histogram(valid_arr, bins=256, range=(0, 256))
        hist = hist.astype(np.float32)
        
        # 重み付き平均で閾値を決定
        total = np.sum(hist)
        if total > 0:
            mean_val = np.sum(hist * bins[:-1]) / total
            threshold = mean_val * threshold_ratio + 127 * (1 - threshold_ratio)
            # 閾値を有効な範囲にクリップ
            threshold = np.clip(threshold, 0.0, 255.0)
        else:
            threshold = 127.0
        
        # ソフト閾値（完全に二値化せず、エッジを滑らかに保つ）
        # NaN/Infを安全に処理
        diff = arr - threshold
        diff = np.nan_to_num(diff, nan=0.0, posinf=255.0, neginf=-255.0)
        result = np.clip(diff * 2.0 + 127, 0, 255).astype(np.uint8)
        
        return PILImage.fromarray(result, mode="L")

    def _remove_noise(self, img):
        """ノイズ除去（赤色ハロー完全除去版）"""
        # RGBチャンネルも滑らかに（色のノイズを除去、最適化された回数で適用）
        img = img.filter(ImageFilter.SMOOTH_MORE)
        img = img.filter(ImageFilter.SMOOTH_MORE)  # 2回で十分

        r, g, b, a = img.split()
        
        # アルファチャンネルに基づいて、エッジ付近の赤色ピクセルを除去
        alpha_arr = np.array(a).astype(np.float32) / 255.0
        r_arr = np.array(r).astype(np.float32)
        g_arr = np.array(g).astype(np.float32)
        b_arr = np.array(b).astype(np.float32)
        
        # エッジ領域（アルファが低い領域）で赤色を検出
        edge_region = alpha_arr < 0.3  # エッジ領域
        red_in_edge = edge_region & (r_arr > 150) & (g_arr < 100) & (b_arr < 100)
        
        # エッジの赤色ピクセルを透明に
        alpha_arr[red_in_edge] = 0.0
        
        # アルファチャンネルの処理を強化
        a_new = PILImage.fromarray((alpha_arr * 255).astype(np.uint8), mode="L")
        
        # 1. コントラストを上げてエッジを明確に
        a_enhanced = ImageEnhance.Contrast(a_new).enhance(3.0)  # より強く
        
        # 2. 小さなノイズを除去
        a_enhanced = a_enhanced.filter(ImageFilter.MedianFilter(size=5))  # より大きく
        
        # 3. 滑らかに（ただしエッジは保つ）
        a_smooth = a_enhanced.filter(ImageFilter.GaussianBlur(radius=0.5))
        
        # 4. 最終的なコントラスト調整
        a_final = ImageEnhance.Contrast(a_smooth).enhance(1.3)

        img.putalpha(a_final)
        return img

    def _smooth_edges(self, img):
        """エッジを滑らかにする（赤色ハロー完全除去版）"""
        # RGBチャンネルも処理（エッジの色のブレを防ぐ）
        r, g, b, a = img.split()
        
        # アルファチャンネルに基づいてエッジを滑らかに
        alpha_arr = np.array(a).astype(np.float32) / 255.0
        
        # エッジ領域（アルファが0と255の中間）を特定
        edge_mask = (alpha_arr > 0.05) & (alpha_arr < 0.95)  # より広い範囲
        
        # RGBチャンネルを滑らかに（エッジ領域のみ）
        r_arr = np.array(r).astype(np.float32)
        g_arr = np.array(g).astype(np.float32)
        b_arr = np.array(b).astype(np.float32)
        
        # エッジ領域で赤色を検出して除去
        red_in_edge = edge_mask & (r_arr > 140) & (g_arr < 110) & (b_arr < 110)
        # 赤色ピクセルを背景色（黒）に近づける
        r_arr[red_in_edge] = np.minimum(r_arr[red_in_edge], g_arr[red_in_edge])
        g_arr[red_in_edge] = np.minimum(g_arr[red_in_edge], r_arr[red_in_edge])
        b_arr[red_in_edge] = np.minimum(b_arr[red_in_edge], r_arr[red_in_edge])
        
        # エッジ領域の色を滑らかに
        if np.any(edge_mask) and SCIPY_AVAILABLE:
            # ガウシアンブラーを適用（エッジのみ）
            r_smooth = ndimage.gaussian_filter(r_arr, sigma=0.8)  # より強く
            g_smooth = ndimage.gaussian_filter(g_arr, sigma=0.8)
            b_smooth = ndimage.gaussian_filter(b_arr, sigma=0.8)
            
            # エッジ領域のみを置き換え
            r_arr[edge_mask] = r_smooth[edge_mask]
            g_arr[edge_mask] = g_smooth[edge_mask]
            b_arr[edge_mask] = b_smooth[edge_mask]
        elif np.any(edge_mask):
            # scipyがない場合は、PILのフィルタで代替
            r_pil = PILImage.fromarray(r_arr.astype(np.uint8), mode="L")
            g_pil = PILImage.fromarray(g_arr.astype(np.uint8), mode="L")
            b_pil = PILImage.fromarray(b_arr.astype(np.uint8), mode="L")
            
            r_smooth = np.array(r_pil.filter(ImageFilter.GaussianBlur(radius=1.0))).astype(np.float32)
            g_smooth = np.array(g_pil.filter(ImageFilter.GaussianBlur(radius=1.0))).astype(np.float32)
            b_smooth = np.array(b_pil.filter(ImageFilter.GaussianBlur(radius=1.0))).astype(np.float32)
            
            r_arr[edge_mask] = r_smooth[edge_mask]
            g_arr[edge_mask] = g_smooth[edge_mask]
            b_arr[edge_mask] = b_smooth[edge_mask]
        
        r = PILImage.fromarray(np.clip(r_arr, 0, 255).astype(np.uint8), mode="L")
        g = PILImage.fromarray(np.clip(g_arr, 0, 255).astype(np.uint8), mode="L")
        b = PILImage.fromarray(np.clip(b_arr, 0, 255).astype(np.uint8), mode="L")
        
        # アルファチャンネルを滑らかに（より強力に）
        alpha_smooth = a.filter(ImageFilter.GaussianBlur(radius=1.2))
        
        # 最終的なアルファチャンネル（エッジをより滑らかに、最適化された回数で適用）
        alpha_final = alpha_smooth.filter(ImageFilter.SMOOTH_MORE)
        alpha_final = alpha_final.filter(ImageFilter.SMOOTH_MORE)  # 2回で十分
        
        img = PILImage.merge("RGBA", (r, g, b, alpha_final))
        return img

    # ===================== トリミング & 比率調整 =====================

    def _crop_to_square(self, img: PILImage.Image, size: int, padding: int = 20) -> PILImage.Image:
        """
        アルファチャンネルからキャラ部分を検出してトリミングし、
        指定サイズの正方形に収まるようにリサイズ＆中央配置する。
        リサイズ後にノイズが発生する可能性があるため、追加のクリーニングを行う。
        """
        alpha = img.split()[-1]

        # 透明でない部分のバウンディングボックス
        bbox = alpha.getbbox()
        if bbox is None:
            # 何も描かれていない場合はそのままリサイズだけ
            result = img.resize((size, size), PILImage.LANCZOS, reducing_gap=3.0)
            # リサイズ後のノイズ除去
            return self._clean_after_resize(result)

        left, upper, right, lower = bbox
        left = max(left - padding, 0)
        upper = max(upper - padding, 0)
        right = min(right + padding, img.width)
        lower = min(lower + padding, img.height)

        char_img = img.crop((left, upper, right, lower))

        # 比率を保ったまま、正方形 size x size に収まるようリサイズ
        # reducing_gapを使用してリサイズ品質を向上
        cw, ch = char_img.size
        scale = min(size / cw, size / ch)
        new_w = int(cw * scale)
        new_h = int(ch * scale)
        
        # 高品質なリサイズ（reducing_gapで段階的にリサイズしてノイズを減らす）
        char_img = char_img.resize((new_w, new_h), PILImage.LANCZOS, reducing_gap=3.0)

        # 透明な正方形キャンバスを作成し、中央に貼り付け
        canvas = PILImage.new("RGBA", (size, size), (0, 0, 0, 0))
        offset_x = (size - new_w) // 2
        offset_y = (size - new_h) // 2
        canvas.paste(char_img, (offset_x, offset_y), char_img)

        # リサイズ後のノイズ除去とエッジクリーニング
        return self._clean_after_resize(canvas)
    
    def _clean_after_resize(self, img: PILImage.Image) -> PILImage.Image:
        """
        リサイズ後に発生する可能性のあるノイズを除去し、エッジを滑らかにする
        """
        # アルファチャンネルを分離
        r, g, b, a = img.split()
        
        # アルファチャンネルのエッジをクリーニング
        alpha_arr = np.array(a).astype(np.float32)
        
        # 1. 小さなノイズを除去（メディアンフィルタ）
        a_cleaned = PILImage.fromarray(alpha_arr.astype(np.uint8), mode="L")
        a_cleaned = a_cleaned.filter(ImageFilter.MedianFilter(size=3))
        
        # 2. エッジを滑らかに（軽めのガウシアンブラー）
        a_smooth = a_cleaned.filter(ImageFilter.GaussianBlur(radius=0.5))
        
        # 3. アルファチャンネルのコントラストを調整（エッジをくっきり）
        a_final = ImageEnhance.Contrast(a_smooth).enhance(1.1)
        
        # RGBチャンネルも軽くノイズ除去（リサイズによる色のブレを軽減）
        r_arr = np.array(r).astype(np.float32)
        g_arr = np.array(g).astype(np.float32)
        b_arr = np.array(b).astype(np.float32)
        alpha_final_arr = np.array(a_final).astype(np.float32) / 255.0
        
        # 透明な部分のRGBを0に（ノイズを除去）
        mask = alpha_final_arr < 0.01  # ほぼ透明な部分
        r_arr[mask] = 0
        g_arr[mask] = 0
        b_arr[mask] = 0
        
        # エッジ付近の色も滑らかに
        edge_mask = (alpha_final_arr > 0.01) & (alpha_final_arr < 0.99)
        if np.any(edge_mask) and SCIPY_AVAILABLE:
            r_arr[edge_mask] = ndimage.gaussian_filter(r_arr, sigma=0.5)[edge_mask]
            g_arr[edge_mask] = ndimage.gaussian_filter(g_arr, sigma=0.5)[edge_mask]
            b_arr[edge_mask] = ndimage.gaussian_filter(b_arr, sigma=0.5)[edge_mask]
        
        r_final = PILImage.fromarray(np.clip(r_arr, 0, 255).astype(np.uint8), mode="L")
        g_final = PILImage.fromarray(np.clip(g_arr, 0, 255).astype(np.uint8), mode="L")
        b_final = PILImage.fromarray(np.clip(b_arr, 0, 255).astype(np.uint8), mode="L")
        
        return PILImage.merge("RGBA", (r_final, g_final, b_final, a_final))

    # ===================== 外部 API =====================

    def add_sprite(self, name, image_path):
        """新しいスプライトを追加（処理済みファイルがあれば読み込むだけ）"""
        if not image_path.exists():
            return False
        
        # 処理済みファイルのパスを生成
        processed_path = Config.IMAGES_DIR / f"processed_{name}.png"
        
        # 処理済みファイルが存在し、元の画像より新しい場合は読み込むだけ
        if processed_path.exists():
            # 元の画像と処理済み画像の更新時刻を比較
            original_mtime = image_path.stat().st_mtime
            processed_mtime = processed_path.stat().st_mtime
            
            if processed_mtime >= original_mtime:
                # 処理済みファイルを読み込むだけ
                print(f"Loading cached sprite: {processed_path}")
                img = PILImage.open(processed_path).convert("RGBA")
                self.sprites[name] = img
                return True
        
        # 処理済みファイルがない、または元の画像が新しい場合は処理を実行
        print(f"Processing sprite: {name}")
        img = PILImage.open(image_path).convert("RGBA")
        # 処理順序を変更：トリミング後にノイズ除去
        img = self._advanced_background_removal(img)
        img = self._smooth_edges(img)  # 軽めのエッジ調整
        img = self._crop_to_square(img, self.sprite_size)  # トリミング（内部でノイズ除去も実行）
        img = self._remove_noise(img)  # トリミング後のノイズ除去
        img = self._smooth_edges(img)  # 最終的なエッジ調整
        
        # 処理済みファイルを保存
        processed_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(processed_path)
        
        self.sprites[name] = img
        return True

    def remove_background_from_image(self, image_path, output_path):
        """単一画像の背景を除去（処理済みファイルがあれば読み込むだけ）"""
        if not image_path.exists():
            return False
        
        # 処理済みファイル（output_path）が存在し、元の画像より新しい場合は読み込むだけ
        if output_path.exists():
            # 元の画像と処理済み画像の更新時刻を比較
            original_mtime = image_path.stat().st_mtime
            processed_mtime = output_path.stat().st_mtime
            
            if processed_mtime >= original_mtime:
                # 処理済みファイルが存在し、新しい場合は処理をスキップ
                print(f"Output file already exists and is up-to-date: {output_path}")
                return True
        
        # 処理済みファイルがない、または元の画像が新しい場合は処理を実行
        print(f"Processing image: {image_path}")
        img = PILImage.open(image_path).convert("RGBA")
        # 処理順序を変更：トリミング後にノイズ除去
        img = self._advanced_background_removal(img)
        img = self._smooth_edges(img)  # 軽めのエッジ調整
        img = self._crop_to_square(img, self.sprite_size)  # トリミング（内部でノイズ除去も実行）
        img = self._remove_noise(img)  # トリミング後のノイズ除去
        img = self._smooth_edges(img)  # 最終的なエッジ調整
        
        # 出力ファイルを保存
        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path)
        return True
    
    def get_current_sprite(self):
        """現在の表情スプライトを返す"""
        return self.sprites.get(self.current_expression, self.sprites.get("neutral"))

    def set_expression(self, expr: str):
        """表情を変更する"""
        if expr in self.sprites:
            self.current_expression = expr

    def reset_expression(self):
        """表情をニュートラルに戻す（必要なら）"""
        self.current_expression = "neutral"
    
    def clear_cache(self, force_reload: bool = False):
        """
        処理済み画像のキャッシュを削除する
        
        Args:
            force_reload: Trueの場合、キャッシュ削除後にスプライトを再読み込みする
        """
        processed_path = Config.IMAGES_DIR / "processed_default_images.png"
        deleted_files = []
        
        if processed_path.exists():
            try:
                processed_path.unlink()
                deleted_files.append(str(processed_path))
                print(f"✓ キャッシュファイルを削除しました: {processed_path}")
            except Exception as e:
                print(f"✗ キャッシュファイルの削除に失敗しました: {e}")
        
        # その他の処理済み画像ファイルも検索して削除
        if Config.IMAGES_DIR.exists():
            for cache_file in Config.IMAGES_DIR.glob("processed_*.png"):
                if cache_file != processed_path:  # 既に削除済みの場合はスキップ
                    try:
                        cache_file.unlink()
                        deleted_files.append(str(cache_file))
                        print(f"✓ キャッシュファイルを削除しました: {cache_file}")
                    except Exception as e:
                        print(f"✗ キャッシュファイルの削除に失敗しました ({cache_file}): {e}")
        
        if deleted_files:
            print(f"合計 {len(deleted_files)} 個のキャッシュファイルを削除しました。")
        else:
            print("削除するキャッシュファイルが見つかりませんでした。")
        
        # 強制再読み込みが指定されている場合、スプライトを再読み込み
        if force_reload:
            self.load_spritesheet()
        
        return len(deleted_files)
    
    def clear_all_image_cache(self):
        """
        画像ディレクトリ内のすべてのキャッシュファイルを削除する
        （processed_*.png パターンに一致するファイル）
        """
        if not Config.IMAGES_DIR.exists():
            print("画像ディレクトリが存在しません。")
            return 0
        
        deleted_count = 0
        for cache_file in Config.IMAGES_DIR.glob("processed_*.png"):
            try:
                cache_file.unlink()
                deleted_count += 1
                print(f"✓ キャッシュファイルを削除しました: {cache_file.name}")
            except Exception as e:
                print(f"✗ キャッシュファイルの削除に失敗しました ({cache_file.name}): {e}")
        
        if deleted_count > 0:
            print(f"合計 {deleted_count} 個のキャッシュファイルを削除しました。")
        else:
            print("削除するキャッシュファイルが見つかりませんでした。")
        
        return deleted_count