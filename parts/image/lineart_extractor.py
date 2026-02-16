"""
lineart_extractor.py - 線画抽出モジュール
ベース画像から一貫したスタイルを抽出するための専用クラス
"""

import cv2
import numpy as np
from PIL import Image
from pathlib import Path
from typing import Optional, Union

class LineartExtractor:
    """ベース画像から線画を抽出し、スタイル整合性を確保するクラス"""
    
    @staticmethod
    def extract(
        image_path: Union[str, Path],
        method: str = "advanced",
        canny_low: int = 50,
        canny_high: int = 150,
        blur_size: int = 5,
        adaptive_block_size: int = 11,
        adaptive_c: int = 2,
        transparency_threshold: int = 200,
        dilation_iterations: int = 1
    ) -> Optional[Image.Image]:
        """
        画像から線画を抽出する
        
        Args:
            image_path: 画像ファイルのパス（strまたはPath）
            method: 抽出方法 ("basic" または "advanced")
            canny_low: Cannyエッジ検出の低閾値（basicメソッド用）
            canny_high: Cannyエッジ検出の高閾値（basicメソッド用）
            blur_size: ガウシアンブラーのサイズ（advancedメソッド用）
            adaptive_block_size: 適応的閾値のブロックサイズ（advancedメソッド用）
            adaptive_c: 適応的閾値の定数（advancedメソッド用）
            transparency_threshold: 透明化する閾値（0-255）
            dilation_iterations: 膨張処理の繰り返し回数（basicメソッド用）
        
        Returns:
            抽出された線画（RGBA形式のPIL Image）、エラー時はNone
        """
        try:
            # パスをPathオブジェクトに変換
            if isinstance(image_path, str):
                image_path = Path(image_path)
            
            # ファイルの存在確認
            if not image_path.exists():
                raise FileNotFoundError(f"画像が見つかりません: {image_path}")
            
            # OpenCVで読み込み
            img = cv2.imread(str(image_path))
            if img is None:
                raise ValueError(f"画像の読み込みに失敗しました: {image_path}")
            
            # グレースケール変換
            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                gray = img
            
            # メソッドに応じた線画抽出
            if method == "basic":
                lineart = LineartExtractor._extract_basic(
                    gray, canny_low, canny_high, dilation_iterations
                )
            elif method == "advanced":
                lineart = LineartExtractor._extract_advanced(
                    gray, blur_size, adaptive_block_size, adaptive_c
                )
            else:
                raise ValueError(f"不明なメソッド: {method} (使用可能: 'basic', 'advanced')")
            
            # PIL Imageに変換
            pil_img = Image.fromarray(lineart).convert("L")
            
            # 白い部分を透明にする処理（線画のみを残す）
            rgba_img = LineartExtractor._apply_transparency(
                pil_img, transparency_threshold
            )
            
            return rgba_img
        
        except FileNotFoundError as e:
            print(f"❌ {e}")
            return None
        except ValueError as e:
            print(f"❌ {e}")
            return None
        except cv2.error as e:
            print(f"❌ OpenCVエラー: {e}")
            return None
        except MemoryError:
            print(f"❌ メモリ不足: 画像が大きすぎる可能性があります")
            return None
        except Exception as e:
            print(f"❌ 予期しないエラー: {e}")
            return None
    
    @staticmethod
    def _extract_basic(gray: np.ndarray, low: int, high: int, iterations: int) -> np.ndarray:
        """基本的なCannyエッジ検出を使用した線画抽出"""
        # Cannyエッジ検出
        edges = cv2.Canny(gray, low, high)
        
        # 線を少し太くして安定させる
        if iterations > 0:
            kernel = np.ones((2, 2), np.uint8)
            edges = cv2.dilate(edges, kernel, iterations=iterations)
        
        # 反転（白背景に黒線）
        lineart = cv2.bitwise_not(edges)
        return lineart
    
    @staticmethod
    def _extract_advanced(
        gray: np.ndarray,
        blur_size: int,
        block_size: int,
        c: int
    ) -> np.ndarray:
        """アニメ調に適した適応的閾値処理を使用した線画抽出"""
        # ガウシアンブラーでノイズを除去
        if blur_size > 0:
            # サイズは奇数である必要がある
            blur_size = blur_size if blur_size % 2 == 1 else blur_size + 1
            blurred = cv2.GaussianBlur(gray, (blur_size, blur_size), 0)
        else:
            blurred = gray
        
        # 適応的閾値処理
        # block_sizeは奇数である必要がある
        block_size = block_size if block_size % 2 == 1 else block_size + 1
        adaptive = cv2.adaptiveThreshold(
            blurred, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            block_size, c
        )
        return adaptive
    
    @staticmethod
    def _apply_transparency(img: Image.Image, threshold: int) -> Image.Image:
        """白い部分を透明にする処理"""
        rgba_img = img.convert("RGBA")
        datas = rgba_img.getdata()
        
        new_data = []
        for item in datas:
            # グレースケール画像なので、1つの値のみをチェック
            gray_value = item[0] if isinstance(item, tuple) else item
            
            # 白に近い色を透明にする
            if gray_value > threshold:
                new_data.append((255, 255, 255, 0))  # 透明
            else:
                # 線（黒）はそのまま
                new_data.append((gray_value, gray_value, gray_value, 255))
        
        rgba_img.putdata(new_data)
        return rgba_img