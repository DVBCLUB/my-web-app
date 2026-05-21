"""
AI_CHAT_UI - Widget UI cho Gemini AI Chat
Cung cấp giao diện chat tích hợp trong ứng dụng
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import threading
from typing import Optional, Callable

from modules.multi_ai_service import get_multi_ai_service
from modules.ai_context import AGENT_MODES, AIContextBuilder
from modules.ai_data_assistant import AccountingDataAssistant
from modules.ai_code_assistant import AICodeAssistant
import config


class AIChatWidget(tk.Frame):
    """Widget chat AI tích hợp"""

    def __init__(self, parent, theme=None, context_provider=None, **kwargs):
        super().__init__(parent, **kwargs)

        self.ai_service = get_multi_ai_service()
        self.context_builder = AIContextBuilder(context_provider)
        self.compare_mode = tk.BooleanVar(value=False)
        self.provider_var = tk.StringVar(value=self.ai_service.get_active_name())
        self.mode_var = tk.StringVar(value="ask")
        self.theme = theme or {
            'bg': '#f0f4f8',
            'panel': '#ffffff',
            'primary': '#1a56a5',
            'success': '#27ae60',
            'danger': '#e74c3c',
            'text': '#2c3e50',
            'muted': '#7f8c8d',
            'line': '#e0e0e0',
        }

        self.configure(bg=self.theme['bg'])
        self._build_ui()

    def _build_ui(self):
        """Xây dựng giao diện chat"""

        # ── HEADER ──────────────────────────────────────────
        header = tk.Frame(self, bg=self.theme['panel'], highlightbackground=self.theme['line'], highlightthickness=1)
        header.pack(fill='x', padx=16, pady=(16, 0))

        tk.Label(header, text="🤖 Trợ lý kế toán AI", font=('Arial', 14, 'bold'),
                bg=self.theme['panel'], fg=self.theme['text']).pack(anchor='w', padx=12, pady=(12, 4))

        provider_bar = tk.Frame(header, bg=self.theme['panel'])
        provider_bar.pack(fill='x', padx=12, pady=(0, 8))
        self.provider_buttons = {}
        for provider in self.ai_service.list_providers():
            btn = tk.Radiobutton(
                provider_bar,
                text=provider.label,
                value=provider.name,
                variable=self.provider_var,
                indicatoron=False,
                command=self._switch_provider,
                bg=self.theme['bg'],
                fg=self.theme['text'],
                selectcolor=self.theme['primary'],
                activebackground=self.theme['primary'],
                activeforeground='white',
                font=('Arial', 9, 'bold'),
                padx=10,
                pady=4,
                relief='flat',
            )
            btn.pack(side='left', padx=(0, 6))
            self.provider_buttons[provider.name] = btn
        tk.Checkbutton(
            provider_bar,
            text="So sánh 4 AI",
            variable=self.compare_mode,
            bg=self.theme['panel'],
            fg=self.theme['muted'],
            selectcolor=self.theme['panel'],
            activebackground=self.theme['panel'],
            font=('Arial', 9),
        ).pack(side='left', padx=(8, 0))

        mode_bar = tk.Frame(header, bg=self.theme['panel'])
        mode_bar.pack(fill='x', padx=12, pady=(0, 8))
        tk.Label(mode_bar, text="Chế độ", bg=self.theme['panel'], fg=self.theme['muted'],
                 font=('Arial', 9, 'bold')).pack(side='left', padx=(0, 6))
        mode_combo = ttk.Combobox(
            mode_bar,
            textvariable=self.mode_var,
            values=list(AGENT_MODES.keys()),
            state='readonly',
            width=10,
        )
        mode_combo.pack(side='left', padx=(0, 10))
        self.context_label = tk.Label(mode_bar, text="", bg=self.theme['panel'],
                                      fg=self.theme['muted'], font=('Arial', 8))
        self.context_label.pack(side='left', fill='x', expand=True, anchor='w')

        # Status indicator
        self.status_label = tk.Label(header, text="● Sẵn sàng", font=('Arial', 9),
                                     bg=self.theme['panel'], fg=self.theme['success'])
        self.status_label.pack(anchor='w', padx=12, pady=(0, 12))

        # Update status
        self._update_status()

        # ── CHAT AREA ───────────────────────────────────────
        chat_frame = tk.Frame(self, bg=self.theme['panel'], highlightbackground=self.theme['line'], highlightthickness=1)
        chat_frame.pack(fill='both', expand=True, padx=16, pady=(8, 0))

        # Chat messages display
        self.chat_display = scrolledtext.ScrolledText(
            chat_frame,
            height=15,
            width=60,
            wrap=tk.WORD,
            bg='#f8f9fa',
            fg=self.theme['text'],
            font=('Arial', 10),
            bd=0,
            padx=8,
            pady=8
        )
        self.chat_display.pack(fill='both', expand=True, padx=8, pady=8)
        self.chat_display.config(state='disabled')

        # Configure tags for styling
        self.chat_display.tag_config('user', foreground=self.theme['primary'], font=('Arial', 10, 'bold'))
        self.chat_display.tag_config('assistant', foreground=self.theme['success'], font=('Arial', 10, 'bold'))
        self.chat_display.tag_config('error', foreground=self.theme['danger'], font=('Arial', 10))
        self.chat_display.tag_config('timestamp', foreground=self.theme['muted'], font=('Arial', 8))

        # ── INPUT AREA ──────────────────────────────────────
        input_frame = tk.Frame(self, bg=self.theme['panel'], highlightbackground=self.theme['line'], highlightthickness=1)
        input_frame.pack(fill='x', padx=16, pady=(0, 16))

        # Message input
        self.message_input = tk.Text(
            input_frame,
            height=3,
            width=60,
            wrap=tk.WORD,
            bg='white',
            fg=self.theme['text'],
            font=('Arial', 10),
            bd=1,
            relief='solid'
        )
        self.message_input.pack(fill='both', expand=True, padx=8, pady=8)
        self.message_input.bind('<Control-Return>', self._on_send)
        self.message_input.bind('<KeyRelease>', lambda _e: self._refresh_context_label())

        # Button frame
        button_frame = tk.Frame(input_frame, bg=self.theme['panel'])
        button_frame.pack(fill='x', padx=8, pady=(0, 8))

        quick_frame = tk.Frame(input_frame, bg=self.theme['panel'])
        quick_frame.pack(fill='x', padx=8, pady=(0, 8))
        quick_actions = [
            ("Ask", "/ask "),
            ("Data", "/data #schema "),
            ("Plan", "/plan "),
            ("Fix", "/fix "),
            ("Review", "/review "),
        ]
        for label, prefix in quick_actions:
            tk.Button(
                quick_frame,
                text=label,
                command=lambda p=prefix: self._insert_prompt_prefix(p),
                bg=self.theme['bg'],
                fg=self.theme['text'],
                font=('Arial', 8, 'bold'),
                padx=8,
                pady=3,
                relief='flat',
                cursor='hand2',
            ).pack(side='left', padx=(0, 5))

        # Send button
        self.send_btn = tk.Button(
            button_frame,
            text="Gửi (Ctrl+Enter)",
            command=self._send_message,
            bg=self.theme['primary'],
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=16,
            pady=6,
            relief='flat',
            cursor='hand2'
        )
        self.send_btn.pack(side='right', padx=4)

        # Clear button
        clear_btn = tk.Button(
            button_frame,
            text="Xóa lịch sử",
            command=self._clear_chat,
            bg=self.theme['muted'],
            fg='white',
            font=('Arial', 9),
            padx=12,
            pady=6,
            relief='flat',
            cursor='hand2'
        )
        clear_btn.pack(side='right', padx=4)

        code_btn = tk.Button(
            button_frame,
            text="AI rà lỗi code",
            command=self._start_code_review,
            bg=self.theme['success'],
            fg='white',
            font=('Arial', 9, 'bold'),
            padx=12,
            pady=6,
            relief='flat',
            cursor='hand2'
        )
        code_btn.pack(side='right', padx=4)
        self.code_review_btn = code_btn

        review_btn = tk.Button(
            button_frame,
            text="Duyệt bản vá",
            command=self._show_code_reviews,
            bg=self.theme['muted'],
            fg='white',
            font=('Arial', 9),
            padx=12,
            pady=6,
            relief='flat',
            cursor='hand2'
        )
        review_btn.pack(side='right', padx=4)

        # API Key setup button
        setup_btn = tk.Button(
            button_frame,
            text="⚙ Cấu hình API",
            command=self._show_api_setup,
            bg=self.theme['muted'],
            fg='white',
            font=('Arial', 9),
            padx=12,
            pady=6,
            relief='flat',
            cursor='hand2'
        )
        setup_btn.pack(side='right', padx=4)

        # Display welcome message
        self._display_welcome()
        self._refresh_context_label()

    def _switch_provider(self):
        """Switch the active AI provider without rebuilding the widget."""
        self.ai_service.set_active_provider(self.provider_var.get())
        self._update_status()

    def _insert_prompt_prefix(self, prefix):
        self.message_input.insert('insert', prefix)
        mode = prefix.strip('/ ').split(' ', 1)[0]
        if mode in AGENT_MODES:
            self.mode_var.set(mode)
        self.message_input.focus_set()
        self._refresh_context_label()

    def _refresh_context_label(self):
        message = self.message_input.get('1.0', tk.END).strip() if hasattr(self, 'message_input') else ''
        labels = self.context_builder.context_labels(message, self.mode_var.get())
        self.context_label.config(text="Context: " + ", ".join(labels))

    def _update_status(self):
        """Cập nhật trạng thái kết nối"""
        active = self.ai_service.get_active_provider()
        if self.ai_service.is_ready():
            self.status_label.config(text=f"● {active.label} sẵn sàng", fg=self.theme['success'])
        elif self.ai_service.is_initialized:
            self.status_label.config(text=f"● {active.label} đang chờ", fg=self.theme['primary'])
        else:
            self.status_label.config(text=f"● {active.label} chưa cấu hình API", fg=self.theme['danger'])

        self._refresh_context_label()

        # Schedule next update
        self.after(500, self._update_status)

    def _display_welcome(self):
        """Hiển thị tin nhắn chào mừng"""
        self.chat_display.config(state='normal')
        self.chat_display.insert(tk.END, "🤖 Trợ lý kế toán AI\n", 'assistant')
        self.chat_display.insert(tk.END, "-" * 40 + "\n\n")

        if self.ai_service.is_initialized:
            msg = """Xin chào! Tôi là trợ lý kế toán AI của bạn.

Tôi có thể giúp bạn:
• Tư vấn về kế toán & thuế
• Phân tích dữ liệu tài chính
• Tóm tắt và giải thích báo cáo
• Trả lời các câu hỏi về hạch toán

Chọn Gemini, ChatGPT, Claude hoặc Copilot ở phía trên rồi nhấn Ctrl+Enter để gửi.
"""
        else:
            msg = """⚠️  Chưa cấu hình API cho AI đang chọn.

Để sử dụng tính năng này:
1. Nhấp nút "⚙ Cấu hình API"
2. Chọn nhà cung cấp và nhập API Key
3. Nhấp "Kết nối"
"""

        self.chat_display.insert(tk.END, msg, 'timestamp')
        self.chat_display.config(state='disabled')
        self.chat_display.see(tk.END)

    def _on_send(self, event):
        """Xử lý phím Ctrl+Enter"""
        self._send_message()
        return 'break'

    def _send_message(self):
        """Gửi tin nhắn tới AI hoặc trợ lý dữ liệu nội bộ."""
        message = self.message_input.get('1.0', tk.END).strip()
        if not message:
            messagebox.showwarning("Trống", "Vui lòng nhập tin nhắn")
            return

        self.chat_display.config(state='normal')
        self.chat_display.insert(tk.END, "\nBạn: ", 'user')
        self.chat_display.insert(tk.END, message + "\n")
        self.chat_display.config(state='disabled')
        self.message_input.delete('1.0', tk.END)
        self.send_btn.config(state='disabled', text="Đang chờ...")
        self._send_async(message)

    def _send_async(self, message: str):
        """Gửi tin nhắn không đồng bộ."""
        def callback(response: str):
            response = response or "Không nhận được phản hồi."
            self.after(0, lambda: self._append_async_response(response))

        def worker():
            try:
                if self.mode_var.get() == "data" or self._looks_like_data_question(message):
                    assistant = AccountingDataAssistant()
                    try:
                        callback(assistant.answer(message))
                    finally:
                        assistant.conn.close()
                    return
                prompt = self.context_builder.build_prompt(message, self.mode_var.get())
                if self.compare_mode.get():
                    answers = self.ai_service.compare(prompt)
                    callback("\n\n".join(
                        f"[{self.ai_service.providers[name].label}]\n{answer}"
                        for name, answer in answers.items()
                    ))
                    return
                if not self.ai_service.is_initialized:
                    active = self.ai_service.get_active_provider()
                    callback(f"Chưa cấu hình API key cho {active.label}. Bạn vẫn có thể hỏi số liệu, ví dụ: 'Chi phí vật liệu tháng này là bao nhiêu?'")
                    return
                response = self.ai_service.send_message(prompt)
                callback(response or self.ai_service.last_error or "AI không trả lời. Vui lòng kiểm tra API key, model, quota hoặc mạng.")
            except Exception as exc:
                callback(f"Lỗi truy vấn dữ liệu: {exc}")

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    def _append_async_response(self, response):
        self.chat_display.config(state='normal')
        self.chat_display.insert(tk.END, "\nAI: ", 'assistant')
        self.chat_display.insert(tk.END, response + "\n")
        self.chat_display.config(state='disabled')
        self.chat_display.see(tk.END)
        self.send_btn.config(state='normal', text="Gửi (Ctrl+Enter)")

    def _start_code_review(self):
        if not self.ai_service.is_initialized:
            messagebox.showwarning("Chưa cấu hình AI", "Vui lòng cấu hình API cho AI đang chọn trước khi dùng AI rà lỗi code.")
            return
        request = self.message_input.get('1.0', tk.END).strip() or (
            "Rà soát lỗi giao diện Tkinter bị che khuất, thanh cuộn, tiếng Việt lỗi dấu, "
            "và đề xuất bản vá an toàn cho phần mềm."
        )
        self.code_review_btn.config(state='disabled', text="Đang rà...")
        self._append_async_response("Đang gửi mã nguồn liên quan cho AI đang chọn để rà lỗi. Kết quả sẽ được lưu thành file review/bản vá đề xuất.")

        def worker():
            try:
                assistant = AICodeAssistant()
                prompt = assistant.build_prompt(request)
                response = self.ai_service.send_message(prompt) or self.ai_service.last_error or "Không nhận được phản hồi."
                path = assistant.save_review(request, response)
                msg = f"Đã lưu đề xuất sửa lỗi tại:\n{path}\n\nBạn có thể mở file này để duyệt phần unified diff trước khi áp dụng."
            except Exception as exc:
                msg = f"Lỗi AI rà code: {exc}"
            self.after(0, lambda: self._finish_code_review(msg))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_code_review(self, message):
        self._append_async_response(message)
        self.code_review_btn.config(state='normal', text="AI rà lỗi code")

    def _show_code_reviews(self):
        assistant = AICodeAssistant()
        reviews = assistant.list_reviews()
        win = tk.Toplevel(self)
        win.title("Duyệt bản vá AI")
        win.geometry("980x680")
        win.configure(bg=self.theme['bg'])

        left = tk.Frame(win, bg=self.theme['panel'], width=260)
        left.pack(side='left', fill='y', padx=(12, 6), pady=12)
        left.pack_propagate(False)
        right = tk.Frame(win, bg=self.theme['panel'])
        right.pack(side='right', fill='both', expand=True, padx=(6, 12), pady=12)

        tk.Label(left, text="Bản review đã lưu", bg=self.theme['panel'], fg=self.theme['text'],
                 font=('Arial', 11, 'bold')).pack(anchor='w', padx=10, pady=(10, 6))
        review_list = tk.Listbox(left, font=('Consolas', 9), activestyle='none')
        review_list.pack(fill='both', expand=True, padx=10, pady=(0, 10))
        for path in reviews:
            review_list.insert(tk.END, path.name)

        text = scrolledtext.ScrolledText(right, wrap=tk.WORD, font=('Consolas', 10), bg='white')
        text.pack(fill='both', expand=True, padx=10, pady=(10, 8))
        text.insert(tk.END, "Chọn một bản review bên trái để xem nội dung.")
        text.configure(state='disabled')

        selected_path = {'path': None, 'content': ''}

        def load_selected(_event=None):
            selection = review_list.curselection()
            if not selection:
                return
            path = reviews[selection[0]]
            content = assistant.read_review(path)
            selected_path['path'] = path
            selected_path['content'] = content
            text.configure(state='normal')
            text.delete('1.0', tk.END)
            text.insert(tk.END, content)
            text.configure(state='disabled')

        def export_patch():
            if not selected_path['content']:
                messagebox.showwarning("Duyệt bản vá", "Vui lòng chọn bản review trước.")
                return
            diff = assistant.extract_unified_diff(selected_path['content'])
            if not diff:
                messagebox.showinfo("Duyệt bản vá", "Bản review này chưa có khối unified diff để xuất.")
                return
            target = filedialog.asksaveasfilename(
                title="Lưu file patch",
                defaultextension=".patch",
                filetypes=[("Patch files", "*.patch"), ("All files", "*.*")],
                initialfile=selected_path['path'].with_suffix('.patch').name,
            )
            if not target:
                return
            with open(target, 'w', encoding='utf-8') as handle:
                handle.write(diff)
            messagebox.showinfo("Duyệt bản vá", f"Đã xuất patch:\n{target}")

        review_list.bind('<<ListboxSelect>>', load_selected)

        buttons = tk.Frame(right, bg=self.theme['panel'])
        buttons.pack(fill='x', padx=10, pady=(0, 10))
        tk.Button(buttons, text="Xuất unified diff thành .patch", command=export_patch,
                  bg=self.theme['primary'], fg='white', relief='flat', padx=12, pady=7).pack(side='left')
        tk.Button(buttons, text="Đóng", command=win.destroy,
                  bg=self.theme['muted'], fg='white', relief='flat', padx=12, pady=7).pack(side='right')

    def _looks_like_data_question(self, message):
        text = message.lower()
        markers = [
            'chi phi', 'chi phí', 'doanh thu', 'ton kho', 'tồn kho', 'vat tu', 'vật tư',
            'hop dong', 'hợp đồng', 'cong no', 'công nợ', 'top', 'thang nay', 'tháng này',
            'quy nay', 'quý này', 'bao nhieu', 'bao nhiêu',
        ]
        return any(marker in text for marker in markers)
    def _clear_chat(self):
        """Xóa lịch sử chat"""
        if messagebox.askyesno("Xác nhận", "Xóa toàn bộ lịch sử chat?"):
            self.ai_service.clear_history()
            self.chat_display.config(state='normal')
            self.chat_display.delete('1.0', tk.END)
            self.chat_display.config(state='disabled')
            self._display_welcome()

    def _show_api_setup(self):
        """Hiển thị dialog cấu hình API"""
        setup_window = tk.Toplevel(self)
        setup_window.title("Cấu hình AI API")
        setup_window.geometry("520x360")
        setup_window.resizable(False, False)

        # Bring to front
        setup_window.attributes('-topmost', True)

        # Content
        frame = tk.Frame(setup_window, bg=self.theme['bg'])
        frame.pack(fill='both', expand=True, padx=16, pady=16)

        tk.Label(frame, text="Cấu hình nhà cung cấp AI", font=('Arial', 12, 'bold'),
                bg=self.theme['bg'], fg=self.theme['text']).pack(anchor='w', pady=(0, 8))

        tk.Label(frame, text="Có thể dùng Gemini, OpenAI/ChatGPT, Anthropic/Claude hoặc endpoint Copilot tương thích.",
                font=('Arial', 9), bg=self.theme['bg'], fg=self.theme['muted']).pack(anchor='w', pady=(0, 12))

        provider_var = tk.StringVar(value=self.provider_var.get())
        provider_combo = ttk.Combobox(
            frame,
            textvariable=provider_var,
            values=[p.name for p in self.ai_service.list_providers()],
            state='readonly',
            width=24,
        )
        provider_combo.pack(fill='x', pady=(0, 12))

        # API Key input
        tk.Label(frame, text="API Key:", font=('Arial', 10),
                bg=self.theme['bg'], fg=self.theme['text']).pack(anchor='w', pady=(0, 4))

        api_key_input = tk.Entry(frame, width=50, font=('Arial', 10), show='*')
        api_key_input.pack(fill='x', pady=(0, 16))

        # Test button
        def test_connection():
            api_key = api_key_input.get().strip()
            if not api_key:
                messagebox.showwarning("Trống", "Vui lòng nhập API Key")
                return

            # Show loading
            test_btn.config(state='disabled', text="Đang kiểm tra...")
            setup_window.update()

            # Test in thread
            def test_in_thread():
                success, result_message = self.ai_service.validate_api_key(provider_var.get(), api_key)

                def on_result():
                    if success:
                        self.ai_service.set_active_provider(provider_var.get())
                        self.provider_var.set(provider_var.get())
                        messagebox.showinfo("Thành công", result_message)
                        setup_window.destroy()
                    else:
                        error = result_message or self.ai_service.last_error or "Lỗi không xác định"
                        messagebox.showerror("Lỗi", f"Kết nối thất bại:\n{error}")
                        test_btn.config(state='normal', text="Kết nối & Lưu")

                self.after(0, on_result)

            thread = threading.Thread(target=test_in_thread, daemon=True)
            thread.start()

        test_btn = tk.Button(frame, text="Kết nối & Lưu", command=test_connection,
                            bg=self.theme['primary'], fg='white', font=('Arial', 10, 'bold'),
                            padx=16, pady=8, relief='flat', cursor='hand2')
        test_btn.pack(fill='x', pady=(0, 8))

        # Cancel button
        tk.Button(frame, text="Hủy", command=setup_window.destroy,
                 bg=self.theme['muted'], fg='white', font=('Arial', 10),
                 padx=16, pady=8, relief='flat', cursor='hand2').pack(fill='x')


class AIChatDialog(tk.Toplevel):
    """Dialog độc lập cho AI Chat"""

    def __init__(self, parent=None, theme=None, **kwargs):
        super().__init__(parent, **kwargs)

        self.title("Trợ lý kế toán AI")
        self.geometry("650x700")
        self.resizable(True, True)

        # Chat widget
        self.chat_widget = AIChatWidget(self, theme=theme, bg='#f0f4f8')
        self.chat_widget.pack(fill='both', expand=True)

