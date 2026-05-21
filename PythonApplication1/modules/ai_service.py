"""
AI_SERVICE - Dá»‹ch vá»¥ tĂ­ch há»£p Google Gemini API
Cung cáº¥p kháº£ nÄƒng chat thĂ´ng minh cho á»©ng dá»¥ng ERP
"""

import os
import json
import threading
from datetime import datetime
from typing import Optional, List, Dict, Callable
from collections import deque

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except Exception:
    # Gemini API integration is optional; náº¿u khĂ´ng thá»ƒ import thĂ¬ á»©ng dá»¥ng váº«n cháº¡y.
    GEMINI_AVAILABLE = False
    genai = None

import config


GEMINI_MODEL_FALLBACKS = [
    'gemini-2.0-flash',
    'gemini-2.0-flash-lite',
    'gemini-2.5-flash',
    'gemini-2.5-pro',
]


class ChatMessage:
    """Lá»›p Ä‘áº¡i diá»‡n cho má»™t tin nháº¯n trong cuá»™c há»™i thoáº¡i"""

    def __init__(self, role: str, content: str):
        self.role = role  # 'user' hoáº·c 'assistant'
        self.content = content
        self.timestamp = datetime.now()

    def to_dict(self) -> Dict:
        return {
            'role': self.role,
            'content': self.content,
            'timestamp': self.timestamp.isoformat()
        }


class GeminiAIService:
    """
    Dá»‹ch vá»¥ tĂ­ch há»£p Google Gemini API
    Quáº£n lĂ½ chat, lá»‹ch sá»­ cuá»™c trĂ² chuyá»‡n, vĂ  tÆ°Æ¡ng tĂ¡c vá»›i Gemini
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Khá»Ÿi táº¡o dá»‹ch vá»¥ AI

        Args:
            api_key: Google API key (náº¿u khĂ´ng cĂ³ sáº½ láº¥y tá»« config hoáº·c environment)
        """
        self.api_key = api_key or config.GEMINI_API_KEY
        self.model_name = config.GEMINI_MODEL
        self.system_prompt = config.AI_SYSTEM_PROMPT
        self.max_history = config.AI_MAX_HISTORY
        self.response_timeout = config.AI_RESPONSE_TIMEOUT

        # Lá»‹ch sá»­ chat
        self.chat_history: deque = deque(maxlen=self.max_history)

        # Callback cho sá»± kiá»‡n
        self.on_response_received: Optional[Callable] = None
        self.on_error_occurred: Optional[Callable] = None

        # Tráº¡ng thĂ¡i
        self.is_initialized = False
        self.is_waiting_response = False
        self.last_error: Optional[str] = None
        self.model = None

        # Khá»Ÿi táº¡o Gemini náº¿u API key cĂ³ sáºµn
        if self.api_key:
            self._initialize()

    def _make_model(self, model_name: str):
        try:
            return genai.GenerativeModel(
                model_name=model_name,
                system_instruction=self.system_prompt
            )
        except TypeError:
            return genai.GenerativeModel(model_name=model_name)

    def _available_generate_models(self) -> List[str]:
        if not genai or not hasattr(genai, 'list_models'):
            return []
        try:
            names = []
            for model in genai.list_models():
                methods = getattr(model, 'supported_generation_methods', []) or []
                name = getattr(model, 'name', '') or ''
                if 'generateContent' not in methods or not name:
                    continue
                if name.startswith('models/'):
                    name = name.split('/', 1)[1]
                names.append(name)
            return names
        except Exception:
            return []

    def _candidate_model_names(self) -> List[str]:
        available = self._available_generate_models()
        preferred = [self.model_name] + GEMINI_MODEL_FALLBACKS
        candidates = []
        for name in preferred + available:
            if name and name not in candidates:
                candidates.append(name)
        if available:
            allowed = set(available)
            matched = [name for name in candidates if name in allowed]
            return matched or available
        return candidates

    def _configure_first_working_model(self) -> None:
        last_error = None
        for model_name in self._candidate_model_names():
            try:
                self.model = self._make_model(model_name)
                self.model_name = model_name
                return
            except Exception as exc:
                last_error = exc
        if last_error:
            raise last_error
        raise RuntimeError("Khong tim thay model Gemini kha dung.")

    def _is_model_not_found_error(self, text: str) -> bool:
        lowered = str(text or '').lower()
        return 'not found' in lowered and 'model' in lowered

    def _friendly_error(self, exc: Exception) -> str:
        text = str(exc)
        lowered = text.lower()
        if self._is_model_not_found_error(text):
            return (
                "Gemini: model dang cau hinh khong kha dung voi API key nay. "
                "Phan mem da tu dong thu cac model thay the nhung chua thanh cong."
            )
        if 'api_key' in lowered or 'permission' in lowered or 'unauthenticated' in lowered:
            return "Gemini: API key khong hop le hoac khong co quyen truy cap model."
        if 'quota' in lowered or '429' in lowered:
            return "Gemini: tai khoan/API key da het quota hoac bi gioi han toc do."
        return f"Loi Gemini: {text}"

    def _initialize(self) -> bool:
        """Khá»Ÿi táº¡o Gemini API"""
        if not GEMINI_AVAILABLE:
            self.last_error = "ThÆ° viá»‡n google-generativeai chÆ°a Ä‘Æ°á»£c cĂ i Ä‘áº·t.\nCháº¡y: pip install google-generativeai"
            if self.on_error_occurred:
                self.on_error_occurred(self.last_error)
            return False

        if not self.api_key:
            self.last_error = "ChÆ°a cáº¥u hĂ¬nh GEMINI_API_KEY"
            return False

        try:
            genai.configure(api_key=self.api_key)
            self._configure_first_working_model()
            self.is_initialized = True
            self.last_error = None
            return True
        except Exception as e:
            self.last_error = self._friendly_error(e)
            if self.on_error_occurred:
                self.on_error_occurred(self.last_error)
            return False

    def set_api_key(self, api_key: str) -> bool:
        """
        Thiáº¿t láº­p API key má»›i

        Args:
            api_key: Google API key

        Returns:
            True náº¿u thĂ nh cĂ´ng, False náº¿u tháº¥t báº¡i
        """
        self.api_key = api_key
        self.chat_history.clear()  # XĂ³a lá»‹ch sá»­ khi Ä‘á»•i API key
        return self._initialize()

    def is_ready(self) -> bool:
        """Kiá»ƒm tra dá»‹ch vá»¥ AI cĂ³ sáºµn sĂ ng khĂ´ng"""
        return self.is_initialized and not self.is_waiting_response

    def add_message(self, role: str, content: str) -> None:
        """
        ThĂªm tin nháº¯n vĂ o lá»‹ch sá»­

        Args:
            role: 'user' hoáº·c 'assistant'
            content: Ná»™i dung tin nháº¯n
        """
        message = ChatMessage(role, content)
        self.chat_history.append(message)

    def get_history(self) -> List[Dict]:
        """Láº¥y lá»‹ch sá»­ chat dÆ°á»›i dáº¡ng dict"""
        return [msg.to_dict() for msg in self.chat_history]

    def clear_history(self) -> None:
        """XĂ³a lá»‹ch sá»­ chat"""
        self.chat_history.clear()

    def send_message(self, user_message: str, callback: Optional[Callable] = None) -> Optional[str]:
        """
        Gá»­i tin nháº¯n tá»›i Gemini vĂ  nháº­n response (Ä‘á»“ng bá»™)

        Args:
            user_message: Ná»™i dung tin nháº¯n tá»« ngÆ°á»i dĂ¹ng
            callback: HĂ m callback khi nháº­n Ä‘Æ°á»£c response

        Returns:
            Response tá»« Gemini hoáº·c None náº¿u cĂ³ lá»—i
        """
        if not self.is_ready():
            error_msg = "Dá»‹ch vá»¥ AI chÆ°a sáºµn sĂ ng"
            if self.on_error_occurred:
                self.on_error_occurred(error_msg)
            return None

        # ThĂªm tin nháº¯n cá»§a ngÆ°á»i dĂ¹ng vĂ o lá»‹ch sá»­
        self.add_message('user', user_message)
        self.is_waiting_response = True

        try:
            # Chuáº©n bá»‹ lá»‹ch sá»­ chat cho API
            conversation_history = [
                {
                    'role': msg.role if msg.role == 'user' else 'model',
                    'parts': [msg.content]
                }
                for msg in self.chat_history
            ]
            if self.system_prompt and conversation_history:
                conversation_history[0]['parts'][0] = (
                    f"{self.system_prompt}\n\nYeu cau nguoi dung:\n"
                    f"{conversation_history[0]['parts'][0]}"
                )

            # Gá»­i yĂªu cáº§u tá»›i Gemini
            if not genai or not hasattr(genai, 'types'):
                raise RuntimeError("Google Generative AI khĂ´ng kháº£ dá»¥ng")

            try:
                response = self.model.generate_content(
                    conversation_history,
                    generation_config=genai.types.GenerationConfig(
                        max_output_tokens=2000,
                    )
                )
            except Exception as model_exc:
                if self._is_model_not_found_error(str(model_exc)):
                    bad_model = self.model_name
                    response = None
                    last_exc = model_exc
                    for candidate in self._candidate_model_names():
                        if candidate == bad_model:
                            continue
                        try:
                            self.model = self._make_model(candidate)
                            self.model_name = candidate
                            response = self.model.generate_content(
                                conversation_history,
                                generation_config=genai.types.GenerationConfig(
                                    max_output_tokens=2000,
                                )
                            )
                            break
                        except Exception as retry_exc:
                            last_exc = retry_exc
                    if response is None:
                        raise last_exc
                else:
                    raise

            assistant_response = response.text

            # ThĂªm response vĂ o lá»‹ch sá»­
            self.add_message('assistant', assistant_response)

            # Gá»i callback náº¿u cĂ³
            if callback:
                callback(assistant_response)

            if self.on_response_received:
                self.on_response_received(assistant_response)

            return assistant_response

        except Exception as e:
            error_msg = self._friendly_error(e)
            self.last_error = error_msg

            if self.on_error_occurred:
                self.on_error_occurred(error_msg)

            return None
        finally:
            self.is_waiting_response = False

    def send_message_async(self, user_message: str, callback: Callable) -> None:
        """
        Gá»­i tin nháº¯n tá»›i Gemini khĂ´ng Ä‘á»“ng bá»™ (trong thread riĂªng)

        Args:
            user_message: Ná»™i dung tin nháº¯n
            callback: HĂ m callback khi nháº­n Ä‘Æ°á»£c response
        """
        def send_in_thread():
            self.send_message(user_message, callback)

        thread = threading.Thread(target=send_in_thread, daemon=True)
        thread.start()

    def get_summary(self, data: str = "") -> Optional[str]:
        """
        Láº¥y tĂ³m táº¯t cá»§a má»™t dá»¯ liá»‡u tĂ i chĂ­nh

        Args:
            data: Dá»¯ liá»‡u cáº§n tĂ³m táº¯t

        Returns:
            TĂ³m táº¯t tá»« Gemini
        """
        if not self.is_ready():
            return None

        prompt = f"HĂ£y tĂ³m táº¯t ngáº¯n gá»n dá»¯ liá»‡u káº¿ toĂ¡n sau:\n\n{data}"
        return self.send_message(prompt)

    def analyze_data(self, data: str = "") -> Optional[str]:
        """
        PhĂ¢n tĂ­ch dá»¯ liá»‡u tĂ i chĂ­nh

        Args:
            data: Dá»¯ liá»‡u cáº§n phĂ¢n tĂ­ch

        Returns:
            PhĂ¢n tĂ­ch tá»« Gemini
        """
        if not self.is_ready():
            return None

        prompt = f"Vui lĂ²ng phĂ¢n tĂ­ch dá»¯ liá»‡u káº¿ toĂ¡n sau vĂ  Ä‘Æ°a ra nháº­n xĂ©t:\n\n{data}"
        return self.send_message(prompt)

    def get_advice(self, question: str) -> Optional[str]:
        """
        Láº¥y tÆ° váº¥n vá» káº¿ toĂ¡n

        Args:
            question: CĂ¢u há»i vá» káº¿ toĂ¡n

        Returns:
            TÆ° váº¥n tá»« Gemini
        """
        return self.send_message(question)

    def export_history(self, filepath: str) -> bool:
        """
        Xuáº¥t lá»‹ch sá»­ chat ra file JSON

        Args:
            filepath: ÄÆ°á»ng dáº«n file

        Returns:
            True náº¿u thĂ nh cĂ´ng, False náº¿u tháº¥t báº¡i
        """
        try:
            history_data = {
                'timestamp': datetime.now().isoformat(),
                'messages': self.get_history()
            }

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(history_data, f, ensure_ascii=False, indent=2)

            return True
        except Exception as e:
            self.last_error = f"Lá»—i xuáº¥t lá»‹ch sá»­: {str(e)}"
            return False


# Instance toĂ n cá»¥c
_ai_service: Optional[GeminiAIService] = None


def get_ai_service() -> GeminiAIService:
    """Láº¥y instance toĂ n cá»¥c cá»§a GeminiAIService"""
    global _ai_service

    if _ai_service is None:
        _ai_service = GeminiAIService()

    return _ai_service


def initialize_ai_service(api_key: Optional[str] = None) -> bool:
    """
    Khá»Ÿi táº¡o dá»‹ch vá»¥ AI toĂ n cá»¥c

    Args:
        api_key: Google API key (tĂ¹y chá»n)

    Returns:
        True náº¿u thĂ nh cĂ´ng, False náº¿u tháº¥t báº¡i
    """
    service = get_ai_service()

    if api_key:
        return service.set_api_key(api_key)

    return service.is_ready()


