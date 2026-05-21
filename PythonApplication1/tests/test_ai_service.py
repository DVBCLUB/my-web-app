"""
TEST_AI_SERVICE - Script test cho tích hợp Gemini AI
"""

import sys
from pathlib import Path

# Add app root directory to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules.ai_service import get_ai_service, GeminiAIService
import config


def test_import():
    """Test import modules"""
    print("✓ Imports thành công")


def test_service_creation():
    """Test tạo service"""
    service = get_ai_service()
    assert service is not None, "Service không được tạo"
    print(f"✓ Service được tạo: {type(service).__name__}")


def test_config():
    """Test cấu hình"""
    print(f"✓ GEMINI_MODEL: {config.GEMINI_MODEL}")
    print(f"✓ AI_MAX_HISTORY: {config.AI_MAX_HISTORY}")
    print(f"✓ AI_RESPONSE_TIMEOUT: {config.AI_RESPONSE_TIMEOUT}")


def test_api_key_setup():
    """Test setup API Key"""
    service = get_ai_service()

    # Test key trống
    if not service.is_initialized:
        print("⚠️  API Key chưa được cấu hình (bình thường)")
        return

    print(f"✓ API Key được cấu hình")
    print(f"✓ Service ready: {service.is_ready()}")


def test_chat_message():
    """Test ChatMessage class"""
    from modules.ai_service import ChatMessage

    msg = ChatMessage('user', 'Xin chào!')
    assert msg.role == 'user'
    assert msg.content == 'Xin chào!'
    assert msg.to_dict()['role'] == 'user'
    print("✓ ChatMessage hoạt động")


def test_history():
    """Test history management"""
    service = GeminiAIService()
    service.add_message('user', 'Test 1')
    service.add_message('assistant', 'Reply 1')

    history = service.get_history()
    assert len(history) == 2
    assert history[0]['role'] == 'user'
    print(f"✓ History quản lý được: {len(history)} tin nhắn")


def main():
    """Run all tests"""
    print("\n" + "="*50)
    print("🧪 TEST TÍCH HỢP GEMINI AI")
    print("="*50 + "\n")

    tests = [
        ("Import modules", test_import),
        ("Tạo service", test_service_creation),
        ("Cấu hình", test_config),
        ("API Key setup", test_api_key_setup),
        ("ChatMessage", test_chat_message),
        ("History management", test_history),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            print(f"\n📝 Test: {name}")
            test_func()
            passed += 1
        except Exception as e:
            print(f"❌ Lỗi: {str(e)}")
            failed += 1

    print("\n" + "="*50)
    print(f"📊 Kết quả: {passed} thành công, {failed} thất bại")
    print("="*50 + "\n")

    if failed == 0:
        print("✅ Tất cả test thành công!\n")
        print("Bước tiếp theo:")
        print("1. Lấy API Key từ: https://aistudio.google.com/app/apikey")
        print("2. Chạy: python main.py")
        print("3. Menu → Trợ lý AI → Cấu hình API → Dán API Key")
        print()
        return 0
    else:
        print("❌ Có lỗi trong test\n")
        return 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
