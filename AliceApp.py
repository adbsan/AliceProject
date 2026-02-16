import tkinter as tk
from PIL import Image, ImageTk
import math, sys, signal
import threading

class AliceApp:
    def __init__(self, root):
        self.root = root
        # --- Ctrl+C 復旧：絶対に忘れない ---
        signal.signal(signal.SIGINT, lambda s, f: self._safe_quit())
        self._check_signal_poller()

        # 各マネージャーの初期化
        from parts.image.sprite_manager import SpriteManager
        self.sprite_manager = SpriteManager()
        
        # LLMエンジンと音声合成の初期化（オプション）
        self.llm_engine = None
        self.voicevox_manager = None
        self._init_ai_components()
        
        self.msg = None
        self.is_processing = False  # 処理中フラグ
        self.tk_img = None  # 画像参照を保持（ガベージコレクション防止）
        
        self._setup_window(root)
        self._setup_ui(root)
        self._update_loop()
    
    def _init_ai_components(self):
        """AIコンポーネント（LLM・音声合成）を初期化（エラー時は無効化）"""
        try:
            from parts.conversation.local_llm_engine import LocalLLMEngine
            from parts.config import Config
            self.llm_engine = LocalLLMEngine(Config.OLLAMA_MODEL)
            print("✅ LLMエンジンを初期化しました（Ollamaが起動していない場合は機能しません）")
        except Exception as e:
            print(f"⚠️ LLMエンジンの初期化に失敗しました: {e}")
            self.llm_engine = None
        
        try:
            from parts.audio.voicevox_manager import VoicevoxManager
            self.voicevox_manager = VoicevoxManager()
            print("✅ 音声合成マネージャーを初期化しました（VOICEVOX Engineが起動していない場合は機能しません）")
        except Exception as e:
            print(f"⚠️ 音声合成マネージャーの初期化に失敗しました: {e}")
            self.voicevox_manager = None

    def _check_signal_poller(self):
        self.root.after(500, self._check_signal_poller)

    def _safe_quit(self):
        print("\n[System] Alice closed safely via Ctrl+C.")
        self.root.destroy()
        sys.exit(0)

    def _setup_window(self, root):
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.geometry("800x600+500+200")
        root.config(bg='#abcdef')
        root.attributes("-transparentcolor", '#abcdef')

    def _setup_ui(self, root):
        # 階層：1. bubble_canvas (背面)
        self.bubble_canvas = tk.Canvas(root, highlightthickness=0, bd=0, bg='#abcdef')
        self.bubble_canvas.place(x=0, y=0, relwidth=1, relheight=1)
        # 階層：2. char_canvas (前面)
        self.char_canvas = tk.Canvas(root, highlightthickness=0, bd=0, bg='#abcdef')
        self.char_canvas.place(x=0, y=0, relwidth=1, relheight=1)
        
        # 階層：3. input_win (最前面・移動可能)
        self.input_win = tk.Frame(root, bg='#222', padx=5, pady=5, cursor="fleur")
        self.input_win.place(x=250, y=520, width=320)
        self.input_win.bind("<Button-1>", self._start_drag)
        self.input_win.bind("<B1-Motion>", self._do_drag)

        self.entry = tk.Entry(self.input_win, font=("Meiryo", 10))
        self.entry.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        self.entry.bind("<Return>", lambda e: self._on_send())
        tk.Button(self.input_win, text="送信", command=self._on_send, bg="#0078d7", fg="white").pack(side=tk.RIGHT)

    def _start_drag(self, e): self.dx, self.dy = e.x, e.y
    def _do_drag(self, e):
        self.input_win.place(x=self.input_win.winfo_x() + e.x - self.dx,
                             y=self.input_win.winfo_y() + e.y - self.dy)

    def _on_send(self):
        txt = self.entry.get()
        if not txt or self.is_processing:
            return
        
        self.entry.delete(0, tk.END)
        
        # LLMエンジンが利用可能な場合はAI応答を取得、そうでなければ固定メッセージ
        if self.llm_engine:
            self.is_processing = True
            # 非同期でLLM応答を取得
            threading.Thread(target=self._process_user_input, args=(txt,), daemon=True).start()
        else:
            # LLMが使えない場合は固定メッセージ
            self.msg = f"えへへ、{txt}！"
            self.root.after(4500, self._clear_bubble)
    
    def _process_user_input(self, user_input: str):
        """ユーザー入力を処理してAI応答を取得（非同期）"""
        try:
            # LLMから応答と表情を取得
            response_text, expression = self.llm_engine.generate_response(user_input)
            
            # UIスレッドで表情を変更
            self.root.after(0, lambda: self.sprite_manager.set_expression(expression))
            
            # UIスレッドでメッセージを表示
            self.root.after(0, lambda: self._show_message(response_text))
            
            # 音声合成が利用可能な場合は音声を再生（非ブロッキング）
            if self.voicevox_manager:
                threading.Thread(
                    target=self.voicevox_manager.speak,
                    args=(response_text,),
                    daemon=True
                ).start()
        
        except Exception as e:
            print(f"❌ 入力処理エラー: {e}")
            error_msg = "申し訳ありません。エラーが発生しました。"
            self.root.after(0, lambda: self._show_message(error_msg))
        finally:
            self.is_processing = False
    
    def _show_message(self, text: str):
        """メッセージを表示（UIスレッドから呼ばれる）"""
        self.msg = text
        # メッセージの長さに応じて表示時間を調整（1文字あたり約100ms）
        display_time = max(3000, min(len(text) * 100, 10000))
        self.root.after(display_time, self._clear_bubble)

    def _clear_bubble(self):
        self.msg = None
        self.bubble_canvas.delete("all")

    def _update_loop(self):
        # 1. キャラ描画 (前面キャンバス)
        from parts.config import Config
        img = self.sprite_manager.get_current_sprite()
        
        # スプライトがNoneの場合のフォールバック
        if img is None:
            print("⚠️ スプライトが読み込まれていません")
            self.char_canvas.delete("all")
        else:
            # 画像サイズを確認
            if img.size != Config.CHARACTER_DISPLAY_SIZE:
                resized = img.resize(Config.CHARACTER_DISPLAY_SIZE, Image.Resampling.LANCZOS)
            else:
                resized = img
            
            # 画像参照を保持（ガベージコレクション防止）
            self.tk_img = ImageTk.PhotoImage(resized)
            
            # キャンバスをクリアしてから描画
            self.char_canvas.delete("all")
            # 中央に1つだけ描画
            self.char_canvas.create_image(400, 300, image=self.tk_img, anchor=tk.CENTER)
        
        # 2. 吹き出し描画 (背面キャンバス)
        if self.msg:
            self.bubble_canvas.delete("all")
            pts = self._get_bubble_pts(130, 160, 350, 240, 25, 365, 275)
            self.bubble_canvas.create_polygon(pts, fill="white", outline="black", width=2, smooth=True)
            # メッセージが長い場合は改行を考慮
            self.bubble_canvas.create_text(240, 200, text=self.msg, font=("Meiryo", 10, "bold"), width=180, justify=tk.LEFT)
        
        # 処理中インジケーター（オプション）
        if self.is_processing:
            self.bubble_canvas.create_text(240, 160, text="考え中...", font=("Meiryo", 9), fill="gray")
        
        self.root.after(30, self._update_loop)

    def _get_bubble_pts(self, x1, y1, x2, y2, r, bx, by):
        p = []
        for i in range(11): p.extend([x1+r+r*math.cos(math.radians(180+90*i/10)), y1+r+r*math.sin(math.radians(180+90*i/10))])
        for i in range(11): p.extend([x2-r+r*math.cos(math.radians(270+90*i/10)), y1+r+r*math.sin(math.radians(270+90*i/10))])
        p.extend([x2, by-15, bx, by, x2-10, by+10])
        for i in range(11): p.extend([x2-r+r*math.cos(math.radians(0+90*i/10)), y2-r+r*math.sin(math.radians(0+90*i/10))])
        for i in range(11): p.extend([x1+r+r*math.cos(math.radians(90+90*i/10)), y2-r+r*math.sin(math.radians(90+90*i/10))])
        return p

if __name__ == "__main__":
    root = tk.Tk(); app = AliceApp(root); root.mainloop()