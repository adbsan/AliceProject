"""
local_llm_engine.py - ローカルLLM通信モジュール
Ollama APIを使用して対話生成および感情解析を担当
"""

import requests
import json
import re
from typing import Tuple, List, Dict, Optional, Callable
from parts.config import Config

class LocalLLMEngine:
    def __init__(self, model_name: str = "elyza:jp8b", max_context_length: int = 4096):
        self.url = "http://localhost:11434/api/generate"
        self.model = model_name
        self.context: List[int] = []  # Ollamaの対話コンテキスト保持用
        self.max_context_length = max_context_length  # コンテキストの最大長
        
        # 表情抽出用の正規表現パターン
        self.expression_pattern = re.compile(r"\[(.*?)\]")

    def generate_response(self, prompt: str, stream_callback: Optional[Callable[[str], None]] = None) -> Tuple[str, str]:
        """
        ユーザーの入力に対してAIの回答と表情タグを返す
        
        Args:
            prompt: ユーザーの入力テキスト
            stream_callback: ストリーミング時のコールバック関数（オプション）
        
        Returns: (回答テキスト, 表情名)
        """
        # コンテキストが長すぎる場合は古い部分を削除
        self._trim_context_if_needed()
        
        # システムプロンプトを含めた指示（初回や文脈に応じて調整可能）
        system_inst = (
            "あなたはAliceという名前の学習サポートAIです。"
            "回答の冒頭に、今の感情をConfig.EXPRESSIONSにある単語から選び、"
            "[happy]のようにブラケットで囲んで1つだけ付けてください。"
            f"利用可能な表情: {', '.join(Config.EXPRESSIONS)}\n\n"
        )

        use_streaming = stream_callback is not None
        
        payload = {
            "model": self.model,
            "prompt": system_inst + prompt,
            "context": self.context,
            "stream": use_streaming
        }

        try:
            if use_streaming:
                return self._generate_streaming(payload, stream_callback)
            else:
                return self._generate_non_streaming(payload)

        except requests.exceptions.ConnectionError:
            # 接続エラーの場合は簡潔なメッセージのみ（初回のみ）
            if not hasattr(self, '_connection_error_shown'):
                print("⚠️ Ollamaが起動していません（LLM機能は無効です）")
                self._connection_error_shown = True
            return "Ollamaが起動していません。LLM機能を使用するにはOllamaを起動してください。", "sad"
        except requests.exceptions.RequestException as e:
            print(f"❌ LLM通信エラー: {e}")
            return "申し訳ありません。ローカルLLMとの接続に失敗しました。", "sad"
        except Exception as e:
            print(f"❌ LLM予期しないエラー: {e}")
            return "申し訳ありません。エラーが発生しました。", "sad"
    
    def _generate_non_streaming(self, payload: Dict) -> Tuple[str, str]:
        """非ストリーミングモードで応答を生成"""
        response = requests.post(self.url, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        full_text = data.get("response", "")
        self.context = data.get("context", [])  # コンテキストを更新して会話を継続
        
        # テキストから表情と本文を分離
        expression, clean_text = self._extract_emotion(full_text)
        
        print(f"🤖 LLM Response: [{expression}] {clean_text[:30]}...")
        return clean_text, expression
    
    def _generate_streaming(self, payload: Dict, callback: Callable[[str], None]) -> Tuple[str, str]:
        """ストリーミングモードで応答を生成"""
        full_text = ""
        
        response = requests.post(self.url, json=payload, stream=True, timeout=30)
        response.raise_for_status()
        
        for line in response.iter_lines():
            if line:
                try:
                    data = json.loads(line)
                    token = data.get("response", "")
                    if token:
                        full_text += token
                        callback(token)  # ストリーミングコールバック
                    
                    # 最終的なコンテキストを取得
                    if "context" in data:
                        self.context = data["context"]
                except json.JSONDecodeError:
                    continue
        
        # テキストから表情と本文を分離
        expression, clean_text = self._extract_emotion(full_text)
        
        print(f"🤖 LLM Response (streaming): [{expression}] {clean_text[:30]}...")
        return clean_text, expression
    
    def _trim_context_if_needed(self):
        """コンテキストが長すぎる場合は古い部分を削除"""
        # 簡易的な実装：コンテキストの長さをチェック
        # 実際のトークン数を正確に計算するには、トークナイザーが必要
        if len(self.context) > self.max_context_length:
            # 古い部分を削除（後半の2/3を保持）
            keep_length = int(self.max_context_length * 2 / 3)
            self.context = self.context[-keep_length:]
            print(f"⚠️ コンテキストが長すぎるため、古い部分を削除しました")

    def _extract_emotion(self, text: str) -> Tuple[str, str]:
        """テキストから[expression]タグを抽出し、本文と分離する"""
        match = self.expression_pattern.search(text)
        
        if match:
            expression = match.group(1).lower()
            # 抽出したタグを本文から除去
            clean_text = self.expression_pattern.sub("", text).strip()
            
            # 定義外の表情が来た場合のバリデーション
            if expression not in Config.EXPRESSIONS:
                expression = "neutral"
        else:
            expression = "neutral"
            clean_text = text.strip()
            
        return expression, clean_text

    def clear_context(self):
        """会話の履歴をリセットする"""
        self.context = []
        print("🗑️ 会話履歴をリセットしました")
    
    def get_context_length(self) -> int:
        """現在のコンテキストの長さを返す"""
        return len(self.context)