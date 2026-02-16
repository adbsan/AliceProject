# Alice Project - 実装状況総合レポート（2024年最新版）

## 📊 実装状況サマリー

**全体進捗**: 約65%実装済み

| カテゴリ | 実装状況 | 詳細 |
|---------|---------|------|
| 🖼️ 画像処理 | ✅ 90% | スプライト管理・線画抽出・背景除去は実装済み |
| 💬 対話機能 | ✅ 90% | LLM統合・表情変更は実装済み |
| 🎤 音声機能 | ✅ 90% | VOICEVOX統合済み、非同期再生実装済み |
| ⚙️ 物理演算 | ⚠️ 50% | エンジン実装済み、AliceAppへの統合は未完了 |
| 🎨 アニメーション | ❌ 0% | 未実装 |
| 🔍 コード品質解析 | ❌ 0% | 未実装 |
| 🛠️ セットアップ | ❌ 0% | library_manager.py未実装 |

---

# 第1部：実装済み機能の詳細

## ✅ 1. スプライト管理（`parts/image/sprite_manager.py`）

### 📈 実装状況: 90%
**総合評価**: ⭐⭐⭐⭐⭐ (プロフェッショナルレベルの画像処理)

### ✅ 実装済み機能

#### 1.1 スプライトシート読み込み
- ✅ 1024x1024px スプライトシート対応
- ✅ 2x2 / 4x4 グリッド自動検出
- ✅ 左上セル切り出し機能（neutralのみ）
- ✅ 単一画像としての処理にも対応

#### 1.2 高度な背景除去（⭐⭐⭐⭐⭐）
**実装技術**:
- **背景色自動推定**: 外周ピクセルサンプリング（中央値+平均の組み合わせ）
- **距離計算**: ユークリッド距離 × 0.8 + マンハッタン距離 × 0.2
- **適応的閾値**: 画像統計に基づく動的閾値（90パーセンタイル + 20）
- **赤色ハロー除去**: 
  - 赤色マスク: `(R > 150) & (G < 100) & (B < 100)`
  - エッジ領域の赤色も積極的に検出・除去
- **NaN/Inf処理**: 安全な数値計算（`np.nan_to_num`使用）

**コード例**:
```python
# 背景色との距離を計算
diff = rgb - bg_color[None, None, :]
dist_euclidean = np.sqrt(np.sum(diff ** 2, axis=-1))
dist_manhattan = np.sum(np.abs(diff), axis=-1)
dist_combined = dist_euclidean * 0.8 + (dist_manhattan / 3.0) * 0.2

# 赤色を積極的に検出
red_mask = (r > 150) & (g < 100) & (b < 100)
bg_mask = (dist_combined < bg_threshold) | red_mask
```

#### 1.3 ノイズ除去（⭐⭐⭐⭐⭐）
**実装技術**:
- **モルフォロジー演算**: 
  - 収縮（MinFilter × 5回） → 外側のノイズ除去
  - 膨張（MaxFilter × 5回） → キャラ輪郭を復元
- **連結成分解析**（scipy使用時）:
  - 最小サイズ100px未満のコンポーネントを除去
  - scipyなしでも代替処理で動作
- **メディアンフィルタ**: サイズ5（より大きなノイズも除去）
- **ガウシアンブラー**: radius=1.2（エッジを保ちながら平滑化）
- **アルファチャンネル最適化**:
  - コントラスト強化（3.0倍）
  - 最終調整（1.3倍）

#### 1.4 エッジ平滑化（⭐⭐⭐⭐⭐）
**実装技術**:
- **エッジ領域自動検出**: `(alpha > 0.05) & (alpha < 0.95)`
- **RGB色補正**: エッジ領域の赤色を背景色に近づける
- **ガウシアンブラー**: sigma=0.8（scipyありの場合）
- **段階的平滑化**: SMOOTH_MORE × 2回（最適化された回数）
- **ソフト閾値処理**: Otsuの方法ベースの適応的閾値

#### 1.5 正方形トリミング
**実装技術**:
- アルファチャンネルからバウンディングボックス自動検出
- パディング付きトリミング（デフォルト20px）
- 高品質リサイズ（LANCZOS、reducing_gap=3.0）
- 1024x1024px キャンバスへの中央配置
- **リサイズ後のクリーニング**:
  - メディアンフィルタでノイズ除去
  - エッジの軽いガウシアンブラー
  - 透明部分のRGBを0に設定

#### 1.6 キャッシュ機能（⭐⭐⭐⭐⭐）
**実装機能**:
- 処理済み画像の自動保存（`processed_*.png`）
- 更新時刻の比較による自動スキップ
  ```python
  if processed_mtime >= original_mtime:
      # キャッシュを読み込むだけ
  ```
- `clear_cache(force_reload=True)` - 特定キャッシュ削除+再読み込み
- `clear_all_image_cache()` - 全キャッシュ削除
- パフォーマンス最適化が秀逸

#### 1.7 外部API
- `add_sprite(name, image_path)` - 新規スプライト追加
- `remove_background_from_image()` - 単一画像の背景除去
- `get_current_sprite()` - 現在の表情取得
- `set_expression(expr)` - 表情変更
- `reset_expression()` - neutralに戻す

### ⚠️ 致命的な制限事項

#### 🔴 1体のみ対応（最優先修正項目）
**現状**:
```python
# 左上のセル（neutral）だけを切り出し
img = full_sheet.crop((0, 0, cell_w, cell_h))
self.sprites["neutral"] = img  # 1つだけ
```

**影響**:
- 16表情のうち1つ（neutral）しか使えない
- 表情変更機能が事実上無効
- スプライトシートの大半が未使用

**修正コード**:
```python
# 4x4グリッド全体をループ
for i, expr in enumerate(Config.EXPRESSIONS):
    if i >= 16:
        break
    
    # グリッド位置を計算
    col = i % 4
    row = i // 4
    left, top = col * cell_w, row * cell_h
    right, bottom = left + cell_w, top + cell_h
    
    # 各セルを処理
    cell_img = full_sheet.crop((left, top, right, bottom))
    
    # 背景除去・ノイズ除去などの処理
    processed_img = self._advanced_background_removal(cell_img)
    processed_img = self._smooth_edges(processed_img)
    processed_img = self._crop_to_square(processed_img, self.sprite_size)
    processed_img = self._remove_noise(processed_img)
    processed_img = self._smooth_edges(processed_img)
    
    self.sprites[expr] = processed_img

print(f"✅ {len(self.sprites)}個のスプライトをロードしました")
```

#### ⚠️ Config のセルサイズプリセット未使用
- `Config.CELL_SIZE` を更新しているが、プリセット機能は活用されていない
- 異なるサイズのスプライトシートに柔軟に対応できない

### 🔧 依存関係
**必須**: `PIL`, `numpy`, `pathlib`  
**推奨**: `scipy` (連結成分解析用、なくても代替処理で動作)

---

## ✅ 2. 線画抽出（`parts/image/lineart_extractor.py`）

### 📈 実装状況: 100%
**総合評価**: ⭐⭐⭐⭐⭐ (修正不要、完全実装)

### ✅ 実装済み機能

#### 2.1 2つの抽出方法
- **basic**: Cannyエッジ検出 + 膨張処理
- **advanced**: 適応的閾値処理（アニメ調に最適）

#### 2.2 パラメータ調整
- Canny閾値: `canny_low`, `canny_high`
- ガウシアンブラー: `blur_size`
- 適応的閾値: `adaptive_block_size`, `adaptive_c`
- 透明化閾値: `transparency_threshold`
- 膨張処理: `dilation_iterations`

#### 2.3 エラーハンドリング
- ファイル存在確認: `FileNotFoundError`
- 画像読み込みエラー: `ValueError`
- OpenCVエラー: `cv2.error`
- メモリエラー: `MemoryError`

#### 2.4 その他
- Path オブジェクトサポート
- 透明化処理（白背景を自動で透明に）
- 反転処理（白背景に黒線）

### 📝 使用例
```python
from parts.image.lineart_extractor import LineartExtractor

# 高度な線画抽出
lineart = LineartExtractor.extract(
    "input.png",
    method="advanced",
    blur_size=5,
    adaptive_block_size=11
)
```

---

## ✅ 3. ローカルLLM統合（`parts/conversation/local_llm_engine.py`）

### 📈 実装状況: 90%
**総合評価**: ⭐⭐⭐⭐⭐ (ほぼ完全実装)

### ✅ 実装済み機能

#### 3.1 Ollama API 統合
- エンドポイント: `http://localhost:11434/api/generate`
- デフォルトモデル: `elyza:jp8b`
- タイムアウト: 30秒

#### 3.2 表情タグ抽出
- 正規表現パターン: `\[(.*?)\]`
- Config.EXPRESSIONS からバリデーション
- 本文からタグを自動削除

**システムプロンプト**:
```python
system_inst = (
    "あなたはAliceという名前の学習サポートAIです。"
    "回答の冒頭に、今の感情をConfig.EXPRESSIONSにある単語から選び、"
    "[happy]のようにブラケットで囲んで1つだけ付けてください。"
    f"利用可能な表情: {', '.join(Config.EXPRESSIONS)}\n\n"
)
```

#### 3.3 コンテキスト管理
- 会話履歴の保持: `self.context: List[int]`
- コンテキスト長制限: 4096トークン（デフォルト）
- 古い履歴の自動削除: 後半2/3を保持
- `clear_context()` - 会話履歴リセット
- `get_context_length()` - コンテキスト長取得

#### 3.4 ストリーミング対応
- `stream_callback` によるリアルタイム出力
- 非ストリーミングモードもサポート
- トークン単位でコールバック実行

#### 3.5 エラーハンドリング
- 接続エラー: Ollama未起動時
- タイムアウト: 30秒
- レスポンス解析エラー
- 初回接続エラーのみ警告表示

### 🔧 軽微な改善点

#### モデル切り替え機能（未実装）
**推奨追加**:
```python
def change_model(self, model_name: str):
    self.model = model_name
    self.clear_context()
    print(f"🔄 モデルを変更しました: {model_name}")
```

---

## ✅ 4. VOICEVOX統合（`parts/audio/voicevox_manager.py`）

### 📈 実装状況: 90%
**総合評価**: ⭐⭐⭐⭐⭐ (リップシンク以外は完全)

### ✅ 実装済み機能

#### 4.1 VOICEVOX API 統合
- エンドポイント: `http://localhost:50021`
- デフォルト話者ID: 3
- 2段階処理:
  1. `/audio_query` - 音声クエリ作成
  2. `/synthesis` - 音声合成

#### 4.2 非同期再生
- スレッドによる非ブロッキング再生
- `async_mode=True` (デフォルト)
- `sd.play()` + `sd.wait()`

#### 4.3 同期再生
- `async_mode=False` でブロッキング再生

#### 4.4 停止機能
- `stop()` - 再生中の音声を停止
- `sd.stop()` 使用
- 再生中フラグの管理

#### 4.5 音量調整
- `set_volume(volume: float)` - 0.0〜1.0 の範囲
- 音声データに直接乗算

#### 4.6 リトライ機能
- 最大3回まで自動リトライ
- 1秒間隔でリトライ
- 静かにリトライ（ログ出力なし）

#### 4.7 エラーハンドリング
- 接続エラー: VOICEVOX未起動時（初回のみ警告）
- タイムアウト: 音声クエリ10秒、合成30秒
- 音声再生エラー

#### 4.8 便利メソッド
- `get_speakers()` - 話者リスト取得（デバッグ用）

### ❌ 未実装機能

#### リップシンク
- **現状**: 音声と口の動きが同期しない
- **影響**: 視覚的なリアリティが低い
- **修正必須度**: 🟡 中

---

## ✅ 5. 物理演算エンジン（`parts/physics/physics_engine.py`）

### 📈 実装状況: 100%（単体では完成）
**総合評価**: ⭐⭐⭐⭐⭐ (完全実装、統合が未完)

### ✅ 実装済み機能

#### 5.1 Pymunk 統合
- `pymunk.Space()` による物理空間
- `Config.GRAVITY` からの重力設定

#### 5.2 境界設定
- ウィンドウの上下左右に境界線
- `pymunk.Segment` 使用
- 弾性係数: 0.5、摩擦係数: 0.5

#### 5.3 キャラクター設定
- `pymunk.Body` - 動的ボディ
- `pymunk.Poly.create_box` - ボックス形状
- サイズ: `CHARACTER_DISPLAY_SIZE` の70%
- 質量: 1.0
- 弾性係数: 0.3、摩擦係数: 0.6

#### 5.4 ドラッグ＆ドロップ
- `start_dragging(x, y)` - 掴む
- `update_drag_pos(x, y)` - 移動
- `stop_dragging()` - 離す
- `pymunk.PivotJoint` 使用（最大力1000000）

#### 5.5 物理演算ステップ
- `step()` - 60FPS で更新 (`1.0 / PHYSICS_FPS`)
- `get_character_transform()` - 位置(x, y)・角度取得

#### 5.6 衝撃付与
- `apply_impulse(fx, fy)` - 力を加える

### ⚠️ 統合の問題
- **現状**: `AliceApp.py` で使用されていない
- **影響**: ドラッグ＆ドロップ、重力などが動作しない
- **修正必須度**: 🟡 高

---

## ✅ 6. メインアプリ（`AliceApp.py`）

### 📈 実装状況: 70%
**総合評価**: ⭐⭐⭐⭐ (基本機能は完成、統合が不完全)

### ✅ 実装済み機能

#### 6.1 Tkinter GUI
- **透過ウィンドウ**:
  - `overrideredirect(True)` - 枠なし
  - `transparentcolor='#abcdef'` - 透過色
  - `topmost=True` - 最前面表示
- **ウィンドウサイズ**: 800x600px
- **初期位置**: x=500, y=200

#### 6.2 スプライト表示
- `sprite_manager` からの画像取得
- 400x400px にリサイズ（LANCZOS）
- 中央配置（x=400, y=300）
- ガベージコレクション防止（`self.tk_img`保持）

#### 6.3 吹き出し表示
- 丸みのある吹き出し描画
- 三角形の尾っぽ
- メッセージ長に応じた表示時間調整:
  ```python
  display_time = max(3000, min(len(text) * 100, 10000))
  ```
- 改行対応（`width=180`）

#### 6.4 LLM 対話統合
- `local_llm_engine` 使用
- 非同期処理（スレッド）
- 表情タグによる自動表情変更
- エラーハンドリング
- 処理中フラグ

#### 6.5 音声合成統合
- `voicevox_manager` 使用
- 非同期再生
- LLM応答と連動

#### 6.6 入力フォーム
- ドラッグ可能（`cursor="fleur"`）
- Enter キー対応
- 送信ボタン
- 処理中は入力無効化

#### 6.7 Ctrl+C ハンドリング
- `signal.signal(signal.SIGINT, ...)` 使用
- 安全な終了処理
- ポーリング（500ms間隔）

### ❌ 未実装機能

#### 6.8 物理演算の統合
**現状**: `physics_engine` が初期化されていない

**必要な実装**:
```python
def __init__(self, root):
    # ... (既存のコード) ...
    
    # 物理エンジンの初期化
    from parts.physics.physics_engine import PhysicsEngine
    self.physics_engine = PhysicsEngine()
    self.is_dragging = False

def _setup_ui(self, root):
    # ... (既存のコード) ...
    
    # キャラクターキャンバスにドラッグイベントをバインド
    self.char_canvas.bind("<Button-1>", self._on_char_press)
    self.char_canvas.bind("<B1-Motion>", self._on_char_drag)
    self.char_canvas.bind("<ButtonRelease-1>", self._on_char_release)

def _on_char_press(self, event):
    self.is_dragging = True
    self.physics_engine.start_dragging(event.x, event.y)

def _on_char_drag(self, event):
    if self.is_dragging:
        self.physics_engine.update_drag_pos(event.x, event.y)

def _on_char_release(self, event):
    self.is_dragging = False
    self.physics_engine.stop_dragging()

def _update_loop(self):
    # 物理演算の更新
    self.physics_engine.step()
    x, y, angle = self.physics_engine.get_character_transform()
    
    # ... (既存の描画コード) ...
    
    # 位置と角度を適用
    if abs(angle) > 0.01:
        resized = resized.rotate(-math.degrees(angle), expand=True)
    self.char_canvas.create_image(x, y, image=self.tk_img, anchor=tk.CENTER)
```

#### 6.9 右クリックメニュー
**現状**: 設定変更の UI がない

**必要な実装**:
```python
def _setup_context_menu(self):
    self.context_menu = tk.Menu(self.root, tearoff=0)
    self.context_menu.add_command(label="会話履歴をクリア", command=self._clear_context)
    self.context_menu.add_command(label="表情をリセット", command=self._reset_expression)
    self.context_menu.add_separator()
    self.context_menu.add_command(label="終了", command=self._safe_quit)
    
    self.char_canvas.bind("<Button-3>", self._show_context_menu)

def _show_context_menu(self, event):
    self.context_menu.tk_popup(event.x_root, event.y_root)

def _clear_context(self):
    if self.llm_engine:
        self.llm_engine.clear_context()
        self.msg = "会話履歴をクリアしました"
        self.root.after(2000, self._clear_bubble)

def _reset_expression(self):
    self.sprite_manager.reset_expression()
```

#### 6.10 アニメーション
- まばたき
- 表情遷移

---

# 第2部：未実装・不完全実装の詳細分析

## 🔴 最高優先度（致命的な問題）

### 1. sprite_manager.py - 16表情対応が必須

#### 問題の詳細
**現状**:
```python
# 左上のセル（neutral）だけを切り出し
if img_w >= 4 * 256 and img_h >= 4 * 256:
    cell_w = img_w // 4
    cell_h = img_h // 4
    img = full_sheet.crop((0, 0, cell_w, cell_h))  # ← ここが問題
    print(f"📦 4x4グリッドから左上のセル ({cell_w}x{cell_h}) を切り出しました")
```

**影響**:
- ✅ 画像処理品質は最高レベル
- ❌ しかし、16表情のうち1つしか使えない
- ❌ 表情変更機能が無意味になっている
- ❌ スプライトシートの93.75%が未使用

**修正の緊急度**: 🔴🔴🔴 最高優先

#### 修正方法

**ステップ1: 16表情すべてをロード**
```python
def load_spritesheet(self):
    raw_path = Config.IMAGES_DIR / "default_images.png"
    processed_path = Config.IMAGES_DIR / "processed_default_images.png"
    
    # キャッシュチェック（省略）
    
    if not raw_path.exists():
        print("Raw image not found.")
        return
    
    print(f"Processing spritesheet: {raw_path}")
    full_sheet = PILImage.open(raw_path).convert("RGBA")
    img_w, img_h = full_sheet.size
    
    # グリッドサイズを自動検出
    if img_w >= 4 * 256 and img_h >= 4 * 256:
        # 4x4グリッド
        cell_w = img_w // 4
        cell_h = img_h // 4
        grid_cols = 4
        grid_rows = 4
        print(f"📦 4x4グリッドを検出: {cell_w}x{cell_h}")
    elif img_w >= 2 * 512 and img_h >= 2 * 512:
        # 2x2グリッド（4表情のみ）
        cell_w = img_w // 2
        cell_h = img_h // 2
        grid_cols = 2
        grid_rows = 2
        print(f"📦 2x2グリッドを検出: {cell_w}x{cell_h}")
    else:
        # 単一画像
        cell_w, cell_h = img_w, img_h
        grid_cols = 1
        grid_rows = 1
        print(f"📦 単一画像として処理: {cell_w}x{cell_h}")
    
    # 各表情を処理
    for i, expr in enumerate(Config.EXPRESSIONS):
        if i >= grid_cols * grid_rows:
            break
        
        # グリッド位置を計算
        col = i % grid_cols
        row = i // grid_cols
        
        # クロップ範囲
        left = col * cell_w
        top = row * cell_h
        right = left + cell_w
        bottom = top + cell_h
        
        # セルを切り出し
        cell_img = full_sheet.crop((left, top, right, bottom))
        
        # 背景除去・ノイズ除去などの処理
        print(f"  処理中: {expr} ({i+1}/{len(Config.EXPRESSIONS)})")
        processed_img = self._advanced_background_removal(cell_img)
        processed_img = self._smooth_edges(processed_img)
        processed_img = self._crop_to_square(processed_img, self.sprite_size)
        processed_img = self._remove_noise(processed_img)
        processed_img = self._smooth_edges(processed_img)
        
        self.sprites[expr] = processed_img
    
    print(f"✅ {len(self.sprites)}個のスプライトをロードしました")
```

**ステップ2: キャッシュを表情ごとに保存**
```python
# load_spritesheet() の最後に追加
for expr, sprite_img in self.sprites.items():
    cache_path = Config.CACHE_DIR / f"processed_{expr}.png"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    sprite_img.save(cache_path)
    print(f"  💾 キャッシュ保存: {expr}")
```

**ステップ3: キャッシュ読み込みも修正**
```python
def load_spritesheet(self):
    # ... (前半省略) ...
    
    # 処理済みファイルが存在し、元の画像より新しい場合
    all_cached = True
    for expr in Config.EXPRESSIONS[:16]:  # 最大16表情
        cache_path = Config.CACHE_DIR / f"processed_{expr}.png"
        if not cache_path.exists():
            all_cached = False
            break
        if cache_path.stat().st_mtime < raw_path.stat().st_mtime:
            all_cached = False
            break
    
    if all_cached:
        print("Loading all sprites from cache...")
        for expr in Config.EXPRESSIONS[:16]:
            cache_path = Config.CACHE_DIR / f"processed_{expr}.png"
            self.sprites[expr] = PILImage.open(cache_path).convert("RGBA")
        print(f"✅ {len(self.sprites)}個のスプライトをキャッシュから読み込みました")
        return
    
    # 処理を実行...
```

#### 効果
- ✅ 16表情すべてが使用可能に
- ✅ 表情変更機能が正常に動作
- ✅ スプライトシートを100%活用
- ✅ キャッシュによる高速化

---

### 2. spritesheet_generator.py - 削除または改名が必須

#### 問題の詳細
**現状**:
- `sprite_manager.py` と `spritesheet_generator.py` の両方に `SpriteManager` クラス
- クラス名が重複
- 機能が重複（どちらを使うべきか不明確）

**比較**:
| 機能 | sprite_manager.py | spritesheet_generator.py |
|------|-------------------|--------------------------|
| 背景除去 | ✅ 高度（⭐⭐⭐⭐⭐） | ❌ なし |
| ノイズ除去 | ✅ あり（⭐⭐⭐⭐⭐） | ❌ なし |
| エッジ調整 | ✅ あり（⭐⭐⭐⭐⭐） | ❌ なし |
| キャッシュ | ✅ あり | ❌ なし |
| 16表情対応 | ⚠️ 未対応（要修正） | ✅ 対応 |
| ダミー生成 | ❌ なし | ✅ あり |
| コード行数 | 約600行 | 約100行 |

#### 推奨される対応

**オプション1: spritesheet_generator.py を削除（推奨）**
- `sprite_manager.py` を修正して16表情対応
- `spritesheet_generator.py` は削除
- ダミー生成機能は `sprite_manager.py` に移植

**オプション2: 用途を分ける**
- `spritesheet_generator.py` を `SimpleSpritesheetLoader` に改名
- 簡易的な読み込み専用クラスとして位置づけ
- `sprite_manager.py` は画像処理専用

**推奨**: オプション1（削除）

---

## 🟡 高優先度（機能不足）

### 3. AliceApp.py - 物理演算の統合

#### 問題の詳細
**現状**:
- `physics_engine.py` は完璧に実装されている
- しかし、`AliceApp.py` で一切使用されていない
- ドラッグ＆ドロップが動作しない

**修正必須度**: 🟡 高

#### 修正方法（前述のコード参照）

---

### 4. config.py - プリセット機能の実装

#### 問題の詳細
**現状**:
```python
@classmethod
def set_cell_preset(cls, preset_name: str):
    # 互換性のために残していますが、現在は自動取得を優先しています
    print(f"⚙️ Config: プリセット '{preset_name}' を適用しました")
```
→ 何もしていない（空実装）

**影響**:
- 異なるサイズのスプライトシートに対応できない
- README の仕様と実装が乖離

**修正必須度**: 🟡 中

#### 修正方法
```python
from typing import Tuple, Dict

class Config:
    # ... (既存のコード) ...
    
    # セルサイズプリセット定義
    CELL_PRESETS: Dict[str, Tuple[int, int]] = {
        "ultra_high": (512, 512),  # 2048x2048を4x4分割
        "high": (256, 256),        # 1024x1024を4x4分割（デフォルト）
        "standard": (128, 128),    # 512x512を4x4分割
        "compact": (64, 64),       # 256x256を4x4分割
        "dense": (32, 32)          # 128x128を4x4分割
    }
    
    @classmethod
    def set_cell_preset(cls, preset_name: str):
        if preset_name not in cls.CELL_PRESETS:
            available = ", ".join(cls.CELL_PRESETS.keys())
            print(f"❌ 不明なプリセット: {preset_name}")
            print(f"   利用可能なプリセット: {available}")
            return
        
        width, height = cls.CELL_PRESETS[preset_name]
        cls.CELL_SIZE = width
        print(f"✅ セルサイズプリセット '{preset_name}' を適用: {width}x{height}px")
    
    @classmethod
    def get_cell_position(cls, expression_index: int) -> Tuple[int, int]:
        """表情インデックスからグリッド上の位置（col, row）を取得"""
        if expression_index < 0 or expression_index >= cls.TOTAL_EXPRESSIONS:
            raise ValueError(f"表情インデックスは0-{cls.TOTAL_EXPRESSIONS-1}の範囲である必要があります")
        
        col = expression_index % cls.GRID_COLS
        row = expression_index // cls.GRID_COLS
        return col, row
    
    @classmethod
    def get_cell_rect(cls, expression_index: int) -> Tuple[int, int, int, int]:
        """表情インデックスから切り出し矩形（left, top, right, bottom）を取得"""
        col, row = cls.get_cell_position(expression_index)
        
        left = col * cls.CELL_SIZE
        top = row * cls.CELL_SIZE
        right = left + cls.CELL_SIZE
        bottom = top + cls.CELL_SIZE
        
        return left, top, right, bottom
    
    @classmethod
    def get_expression_name(cls, expression_index: int) -> str:
        """表情インデックスから表情名を取得"""
        if expression_index < 0 or expression_index >= len(cls.EXPRESSIONS):
            return "neutral"
        return cls.EXPRESSIONS[expression_index]
    
    @classmethod
    def get_expression_index(cls, expression_name: str) -> int:
        """表情名から表情インデックスを取得"""
        try:
            return cls.EXPRESSIONS.index(expression_name)
        except ValueError:
            return 0  # デフォルトは"neutral"
```

#### CACHE_DIR の追加
```python
class Config:
    BASE_DIR = Path(__file__).parent.parent
    IMAGES_DIR = BASE_DIR / "images"
    MODELS_DIR = BASE_DIR / "models"
    CACHE_DIR = BASE_DIR / "cache"  # ← 追加
    
    @classmethod
    def ensure_directories(cls):
        cls.IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        cls.MODELS_DIR.mkdir(parents=True, exist_ok=True)
        cls.CACHE_DIR.mkdir(parents=True, exist_ok=True)  # ← 追加
```

---

### 5. AliceApp.py - 右クリックメニュー

**修正必須度**: 🟡 中

#### 必要な機能
- 会話履歴をクリア
- 表情をリセット
- キャッシュをクリア
- 設定変更（音量、モデルなど）
- 終了

（修正コードは前述）

---

## 🟢 中優先度（改善）

### 6. local_llm_engine.py - モデル切り替え機能

**修正必須度**: 🟢 低

```python
def change_model(self, model_name: str):
    """使用するモデルを変更"""
    self.model = model_name
    self.clear_context()
    print(f"🔄 モデルを変更しました: {model_name}")
```

---

### 7. voicevox_manager.py - リップシンク

**修正必須度**: 🟡 中

#### 実装案
- 音声の音量を解析
- 音量に応じて口の開き具合を変える
- アニメーションと連動

---

## ⚪ 低優先度（オプション）

### 8. 未実装機能

#### セットアップ関連
- ❌ `library_manager.py` - ライブラリ自動管理
- ❌ `requirements.txt` - 依存関係定義
- ❌ `ollama_manager.py` - Ollamaモデル自動管理

#### アニメーション機能
- ❌ `parts/image/animation_controller.py`
- ❌ まばたきアニメーション
- ❌ 表情遷移アニメーション
- ❌ パーティクルエフェクト

#### コード品質解析
- ❌ `parts/quality/` ディレクトリ全体
- ❌ 静的解析
- ❌ セキュリティスキャン
- ❌ パフォーマンスプロファイリング

---

# 第3部：開発ロードマップ

## 📋 Phase 1: 致命的な問題の修正（1〜2日）

### 🔴 最優先
1. **sprite_manager.py の修正**
   - 16表情すべてをロード
   - キャッシュを表情ごとに保存
   - 推定作業時間: 2〜3時間

2. **spritesheet_generator.py の削除**
   - ファイル削除
   - インポート文の修正
   - 推定作業時間: 30分

### 🟡 高優先
3. **config.py のプリセット実装**
   - プリセット辞書の定義
   - ヘルパーメソッドの実装
   - CACHE_DIR の追加
   - 推定作業時間: 1時間

4. **AliceApp.py への物理演算統合**
   - 物理エンジンの初期化
   - ドラッグイベントのバインド
   - 描画処理の修正
   - 推定作業時間: 2〜3時間

---

## 📋 Phase 2: 機能拡張（1週間）

### 🟡 中優先
1. **右クリックメニュー**
   - メニューの実装
   - 各コマンドの実装
   - 推定作業時間: 2時間

2. **library_manager.py**
   - ライブラリチェック
   - 自動インストール
   - 推定作業時間: 3〜4時間

3. **ollama_manager.py**
   - モデル一覧取得
   - モデル自動ダウンロード
   - 推定作業時間: 3〜4時間

4. **requirements.txt**
   - 依存関係の整理
   - 推定作業時間: 30分

---

## 📋 Phase 3: 高度な機能（2〜4週間）

### 🟢 低優先
1. **アニメーション**
   - まばたき
   - 表情遷移
   - 推定作業時間: 1週間

2. **リップシンク**
   - 音声解析
   - 口の開閉アニメーション
   - 推定作業時間: 1週間

3. **学習サポート機能**
   - コンテキスト解析
   - 学習進捗管理
   - 推定作業時間: 2週間

---

# 第4部：技術的詳細

## 🔧 依存関係の整理

### 必須ライブラリ
```txt
Pillow>=10.0.0         # 画像処理
opencv-python>=4.8.0   # 線画抽出
numpy>=1.24.0          # 数値計算
requests>=2.31.0       # HTTP通信
sounddevice>=0.4.6     # 音声再生
soundfile>=0.12.1      # 音声ファイル処理
```

### 推奨ライブラリ
```txt
scipy>=1.11.0          # 連結成分解析（sprite_manager用）
pymunk>=6.5.0          # 物理演算
```

### オプションライブラリ
```txt
# 現在は使用していない
```

---

## 🐛 デバッグ・トラブルシューティング

### 1. スプライトが1つしか表示されない
**原因**: `sprite_manager.py` が左上のセルのみを処理  
**解決策**: 上記の修正を適用

### 2. 表情が変わらない
**原因**: スプライトが1つ（`neutral`）しかロードされていない  
**解決策**: 上記の修正を適用

### 3. 物理演算が動かない
**原因**: `AliceApp.py` で `physics_engine` が初期化されていない  
**解決策**: 物理エンジンを統合

### 4. キャッシュが残って更新されない
**解決策**:
```python
sprite_manager.clear_cache(force_reload=True)
# または
sprite_manager.clear_all_image_cache()
```

### 5. Ollama / VOICEVOX に接続できない
**確認事項**:
- Ollama: `http://localhost:11434` が起動しているか
- VOICEVOX: `http://localhost:50021` が起動しているか

---

## 📊 総括

### 実装品質の評価
- **画像処理**: ⭐⭐⭐⭐⭐ (プロフェッショナルレベル)
- **LLM 統合**: ⭐⭐⭐⭐⭐ (完全実装)
- **音声合成**: ⭐⭐⭐⭐⭐ (リップシンク以外は完全)
- **物理演算**: ⭐⭐⭐⭐⭐ (単体では完全、統合が未完)
- **統合**: ⭐⭐⭐ (不完全、優先修正が必要)

### 致命的な問題
🔴 **sprite_manager.py**: 16表情のうち1つしか使えない

### 推奨される修正順序
1. 🔴 sprite_manager.py を修正（最優先）
2. 🔴 spritesheet_generator.py を削除
3. 🟡 config.py のプリセット実装
4. 🟡 AliceApp.py に物理演算を統合
5. 🟡 右クリックメニューの追加
6. 🟢 library_manager.py / ollama_manager.py の作成
7. 🟢 アニメーション・リップシンクの実装

---

**最終更新**: 2024年（最新ファイルに基づく総合分析）
