"""AI-assisted code repair workflow with reviewable patch output."""

from datetime import datetime
from pathlib import Path


class AICodeAssistant:
    """Collects local code context and asks the selected AI for a safe repair proposal."""

    DEFAULT_FILES = [
        "ui/main_window.py",
        "ui/dialogs.py",
        "ui/expense_table.py",
        "ui/ai_chat_widget.py",
        "ui/theme.py",
        "modules/utilities.py",
        "modules/ai_service.py",
        "modules/multi_ai_service.py",
        "modules/ai_context.py",
    ]

    def __init__(self, base_dir=None, output_dir=None):
        self.base_dir = Path(base_dir or Path(__file__).resolve().parent.parent)
        self.output_dir = Path(output_dir or self.base_dir / "reports" / "ai_code_reviews")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def build_prompt(self, user_request):
        context_parts = []
        for rel_path in self.DEFAULT_FILES:
            path = self.base_dir / rel_path
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if len(text) > 22000:
                text = text[:22000] + "\n# ... file truncated for review ..."
            context_parts.append(f"### {rel_path}\n```python\n{text}\n```")

        return (
            "Bạn là kỹ sư Python/Tkinter senior đang hỗ trợ sửa phần mềm kế toán nội bộ.\n"
            "Nhiệm vụ: rà lỗi giao diện bị che khuất, lỗi cuộn, lỗi tiếng Việt, lỗi dữ liệu và đề xuất bản vá an toàn.\n"
            "Yêu cầu bắt buộc:\n"
            "- Không xóa dữ liệu kế toán.\n"
            "- Không tự ý đổi schema database nếu không nêu migration rõ ràng.\n"
            "- Trả về theo 3 phần: Tóm tắt lỗi, Bản vá đề xuất dạng unified diff, Các bước kiểm thử.\n"
            "- Nếu chưa đủ dữ liệu, ghi rõ file cần xem thêm.\n\n"
            f"Yêu cầu người dùng:\n{user_request}\n\n"
            "Mã nguồn liên quan:\n\n"
            + "\n\n".join(context_parts)
        )

    def save_review(self, request_text, response_text):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = self.output_dir / f"ai_code_review_{timestamp}.md"
        output_path.write_text(
            "# AI Code Review / Repair Proposal\n\n"
            "## Yêu cầu\n\n"
            f"{request_text}\n\n"
            "## Phản hồi Gemini\n\n"
            f"{response_text}\n",
            encoding="utf-8",
        )
        return output_path

    def list_reviews(self):
        return sorted(
            list(self.output_dir.glob("ai_code_review_*.md"))
            + list(self.output_dir.glob("gemini_code_review_*.md")),
            reverse=True,
        )

    def read_review(self, path):
        path = Path(path)
        if not path.is_absolute():
            path = self.output_dir / path.name
        if self.output_dir.resolve() not in path.resolve().parents:
            raise ValueError("File review nằm ngoài thư mục AI code review.")
        return path.read_text(encoding="utf-8", errors="replace")

    def extract_unified_diff(self, review_text):
        lines = review_text.splitlines()
        blocks = []
        in_block = False
        current = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("```") and ("diff" in stripped or "patch" in stripped):
                in_block = True
                current = []
                continue
            if stripped.startswith("```") and in_block:
                in_block = False
                if current:
                    blocks.append("\n".join(current))
                continue
            if in_block:
                current.append(line)
        return "\n\n".join(blocks)
