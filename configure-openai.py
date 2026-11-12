"""Local masked API-key setup. Người thực hiện: Đỗ Quốc An."""
from pathlib import Path
import os
import re
import tempfile
import tkinter as tk
from tkinter import ttk, messagebox

ROOT = Path(__file__).resolve().parent


def save_config(key, model, path=None):
    path = Path(path or ROOT / '.env')
    if not re.fullmatch(r'sk-[A-Za-z0-9_-]{20,}', key):
        raise ValueError('Key chưa đúng định dạng. Hãy kiểm tra lại key OpenAI.')
    if not re.fullmatch(r'[A-Za-z0-9._:-]{1,100}', model):
        raise ValueError('Tên model chưa hợp lệ.')
    values = {'BHYT_CHAT_AI': '1', 'BHYT_ENABLE_AI': '0', 'OPENAI_API_KEY': key,
              'OPENAI_MODEL': model, 'BHYT_AI_TIMEOUT': '15'}
    lines = path.read_text(encoding='utf-8-sig').splitlines() if path.exists() else []
    lines = [s for s in lines if s.split('=', 1)[0].strip() not in values]
    lines += [k + '=' + v for k, v in values.items()]
    # Atomic replacement; never write the secret to a log or command argument.
    fd, name = tempfile.mkstemp(prefix='.bhyt-key-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as f:
            f.write('\n'.join(lines) + '\n')
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def main():
    app = tk.Tk()
    app.title('Cẩm nang BHYT · Kết nối OpenAI')
    app.geometry('570x360')
    app.resizable(False, False)
    frame = ttk.Frame(app, padding=24)
    frame.pack(fill='both', expand=True)
    ttk.Label(frame, text='Kết nối trợ lý OpenAI', font=('Segoe UI', 17, 'bold')).pack(anchor='w')
    ttk.Label(frame, text='Key chỉ được lưu trong .env trên máy, không đưa lên GitHub.',
              wraplength=510).pack(anchor='w', pady=(8, 16))
    ttk.Label(frame, text='API key').pack(anchor='w')
    key = ttk.Entry(frame, show='•', width=65)
    key.pack(fill='x', pady=(4, 12))
    ttk.Label(frame, text='Model (có thể đổi theo quyền truy cập tài khoản)').pack(anchor='w')
    model = ttk.Entry(frame)
    model.insert(0, 'gpt-4.1-mini')
    model.pack(fill='x', pady=(4, 12))
    ttk.Label(frame, text='Khi bật, câu hỏi và trích đoạn liên quan được gửi tới OpenAI.\n'
              'Không nhập thông tin định danh người bệnh. API có thể phát sinh phí sử dụng.',
              wraplength=510).pack(anchor='w')

    def save():
        try:
            save_config(key.get().strip(), model.get().strip())
        except ValueError as e:
            messagebox.showerror('Chưa lưu được', str(e), parent=app)
            return
        except OSError:
            messagebox.showerror('Chưa lưu được', 'Không ghi được tệp cấu hình.', parent=app)
            return
        key.delete(0, 'end')
        messagebox.showinfo('Đã lưu', 'Đã lưu cấu hình. Khởi động lại chatbot để áp dụng.', parent=app)
        app.destroy()

    ttk.Button(frame, text='Lưu và bật hỗ trợ AI', command=save).pack(anchor='e', pady=18)
    key.focus()
    app.mainloop()


if __name__ == '__main__':
    main()
