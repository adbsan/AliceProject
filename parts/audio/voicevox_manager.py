"""
voicevox_manager.py - VOICEVOX音声合成管理モジュール
ローカルVOICEVOX Engineを使用した音声生成および再生を担当
"""

import requests
import json
import io
import threading
import sounddevice as sd
import soundfile as sf
from parts.config import Config

class VoicevoxManager:
    def __init__(self):
        self.base_url = Config.VOICEVOX_ENGINE_URL
        self.speaker_id = Config.VOICEVOX_SPEAKER_ID
        self.current_stream = None  # 現在再生中のストリーム
        self.is_playing = False  # 再生中フラグ
        self.volume = 1.0  # 音量（0.0-1.0）

    def speak(self, text: str, async_mode: bool = True) -> bool:
        """
        テキストを音声に変換して再生する（メインメソッド）
        
        Args:
            text: 読み上げるテキスト
            async_mode: Trueの場合、非同期で再生（デフォルト）
        """
        print(f"🎤 音声合成中: {text[:20]}...")
        
        wav_data = self._generate_wav(text)
        if wav_data:
            if async_mode:
                # 非同期で再生
                thread = threading.Thread(target=self._play_wav, args=(wav_data,), daemon=True)
                thread.start()
                return True
            else:
                # 同期で再生（ブロッキング）
                return self._play_wav(wav_data)
        return False
    
    def stop(self):
        """現在再生中の音声を停止する"""
        if self.is_playing and self.current_stream:
            try:
                sd.stop()
                self.is_playing = False
                self.current_stream = None
                print("⏹️ 音声再生を停止しました")
            except Exception as e:
                print(f"❌ 音声停止エラー: {e}")
    
    def set_volume(self, volume: float):
        """
        音量を設定する
        
        Args:
            volume: 音量（0.0-1.0の範囲）
        """
        self.volume = max(0.0, min(1.0, volume))

    def _generate_wav(self, text: str, max_retries: int = 3) -> bytes:
        """
        VOICEVOX APIを叩いてWAVデータを生成する
        
        Args:
            text: 音声合成するテキスト
            max_retries: 最大リトライ回数
        """
        for attempt in range(max_retries):
            try:
                # 1. 音声クエリの作成
                query_res = requests.post(
                    f"{self.base_url}/audio_query",
                    params={"text": text, "speaker": self.speaker_id},
                    timeout=10
                )
                query_res.raise_for_status()
                query_data = query_res.json()

                # ここでピッチや速度の微調整が可能 (Configからの反映も検討可)
                # query_data["speedScale"] = 1.1 

                # 2. 音声合成の実行
                synthesis_res = requests.post(
                    f"{self.base_url}/synthesis",
                    params={"speaker": self.speaker_id},
                    json=query_data,
                    timeout=30
                )
                synthesis_res.raise_for_status()
                
                return synthesis_res.content

            except requests.exceptions.ConnectionError:
                # 接続エラーの場合は簡潔なメッセージのみ（初回のみ）
                if not hasattr(self, '_connection_error_shown'):
                    print("⚠️ VOICEVOX Engineが起動していません（音声機能は無効です）")
                    self._connection_error_shown = True
                return None
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    # リトライ時はログを出力しない（静かにリトライ）
                    import time
                    time.sleep(1)  # 1秒待ってからリトライ
                else:
                    print(f"❌ VOICEVOX通信エラー: {e}")
                    return None
            except Exception as e:
                print(f"❌ VOICEVOX予期しないエラー: {e}")
                return None
        
        return None

    def _play_wav(self, wav_data: bytes) -> bool:
        """WAVバイナリを読み込んで再生する"""
        try:
            # 既に再生中の場合は停止
            if self.is_playing:
                self.stop()
            
            # バイナリデータをファイルオブジェクトとして扱い、soundfileで読み込む
            with io.BytesIO(wav_data) as b_io:
                data, fs = sf.read(b_io)
                
                # 音量を適用
                if self.volume != 1.0:
                    data = data * self.volume
                
                self.is_playing = True
                # 非ブロッキング再生
                self.current_stream = sd.play(data, fs)
                
                # 再生完了を待つ
                sd.wait()
                
            self.is_playing = False
            self.current_stream = None
            return True
        except Exception as e:
            print(f"❌ 音声再生エラー: {e}")
            self.is_playing = False
            self.current_stream = None
            return False

    def get_speakers(self):
        """利用可能な話者リストを取得（デバッグ用）"""
        try:
            res = requests.get(f"{self.base_url}/speakers")
            return res.json()
        except:
            return []