import sys

from openai import OpenAI

# ---------------------------------------------------------------------------
# کلید API و تنظیمات اتصال به سرویس AvalAI
# ---------------------------------------------------------------------------
API_KEY = "aa-cwf9gL3WJ73ISkDP0cZCOwPMsefdYJsNcssmhhOZ4StLrs9B"
BASE_URL = "https://api.avalai.ir/v1"
MODEL_NAME = "gpt-4o-mini"

# تعریف نقش و رفتار دستیار هوش مصنوعی
SYSTEM_PROMPT = (
    "تو یک دستیار هوش مصنوعی هوشمند، حرفه‌ای و دقیق هستی. "
    "به تمام سوالات با دقت، به زبان فارسی روان و با توضیحات کامل پاسخ بده."
)


class AIAssistant:
    def __init__(self, api_key: str, base_url: str, model: str, system_prompt: str):
        self.client = OpenAI(api_key=api_key.strip(), base_url=base_url)
        self.model = model
        self.system_prompt = system_prompt
        self.history = [{"role": "system", "content": self.system_prompt}]

    def reset_memory(self):
        """پاک کردن حافظه گفتگو برای شروع بحث جدید"""
        self.history = [{"role": "system", "content": self.system_prompt}]
        print("\n🔄 [حافظه دستیار ریست شد]\n")

    def chat(self, user_message: str):
        """ارسال پیام به مدل و نمایش پاسخ به صورت زنده (Stream)"""
        self.history.append({"role": "user", "content": user_message})

        try:
            response = self.client.chat.completions.create(model=self.model, messages=self.history, stream=True)

            print("\n🤖 دستیار: ", end="", flush=True)
            bot_reply_chunks = []

            for chunk in response:
                content = chunk.choices[0].delta.content
                if content:
                    print(content, end="", flush=True)
                    bot_reply_chunks.append(content)
            print("\n")

            bot_reply = "".join(bot_reply_chunks)
            self.history.append({"role": "assistant", "content": bot_reply})

        except Exception as error:
            print(f"\n❌ خطا در برقراری ارتباط: {error}\n")
            # حذف آخرین پیام کاربر در صورت بروز خطا تا تاریخچه به هم نخورد
            self.history.pop()


# ---------------------------------------------------------------------------
# اجرای محیط چت در کنسول / ترمینال
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    assistant = AIAssistant(api_key=API_KEY, base_url=BASE_URL, model=MODEL_NAME, system_prompt=SYSTEM_PROMPT)

    print("=" * 55)
    print("   🤖 دستیار هوش مصنوعی فعال شد")
    print("   • برای پاک کردن حافظه: کلمه 'clear' یا 'پاکسازی'")
    print("   • برای خروج از برنامه: کلمه 'exit' یا 'خروج'")
    print("=" * 55)

    while True:
        try:
            user_input = input("👤 شما: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ["exit", "خروج", "quit"]:
                print("خداحافظ!")
                break

            if user_input.lower() in ["clear", "پاکسازی", "reset"]:
                assistant.reset_memory()
                continue

            assistant.chat(user_input)

        except KeyboardInterrupt:
            print("\nبرنامه بسته شد.")
            sys.exit(0)
