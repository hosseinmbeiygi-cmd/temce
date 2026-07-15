import argparse
import base64
import os
from datetime import datetime

# ── تنظیمات ──────────────────────────────────────────
EXCLUDE_DIRS = [
    "node_modules", ".next", "venv", ".venv", "__pycache__",
    ".git", ".idea", ".vscode", "dist", "build", "out", "coverage",
    "bower_components", "jspm_packages", "packages"
]
EXCLUDE_FILES = [
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "combined_output.txt", "all_files.txt", "files_part_*.txt"
]
EXCLUDE_DIR_NAMES = [
    "node_modules", ".next", "venv", ".venv", "__pycache__",
    ".git", ".idea", ".vscode", "dist", "build", "out", "coverage"
]
MAX_FILE_SIZE = 50 * 1024 * 1024
SPLIT_COUNT = 5

def should_exclude(path: str, is_dir: bool = False) -> bool:
    """بررسی استثنا بودن پوشه یا فایل"""
    basename = os.path.basename(path)
    if is_dir:
        # بررسی نام پوشه
        if basename in EXCLUDE_DIR_NAMES:
            return True
        # بررسی مسیر کامل برای node_modules (هرجا که باشد)
        if "node_modules" in path.split(os.sep):
            return True
        return basename in EXCLUDE_DIRS
    else:
        return basename in EXCLUDE_FILES

def is_binary_file(file_path: str) -> bool:
    try:
        with open(file_path, 'rb') as f:
            chunk = f.read(1024)
        text_chars = bytearray({7,8,9,10,12,13,27} | set(range(0x20, 0x100)))
        return bool(chunk.translate(None, text_chars))
    except:
        return True

def read_file_content(file_path: str) -> tuple[str, str]:
    file_size = os.path.getsize(file_path)

    if file_size > MAX_FILE_SIZE:
        return "info", f"⚠️ فایل خیلی بزرگ است ({file_size / 1024 / 1024:.1f} MB) - فقط نام نمایش داده شده است."

    if is_binary_file(file_path):
        try:
            with open(file_path, 'rb') as f:
                binary_data = f.read()
            encoded = base64.b64encode(binary_data).decode('ascii')
            return "binary", f"[BASE64 ENCODED]\n{encoded}"
        except Exception as e:
            return "error", f"⚠️ خطا در خواندن فایل باینری: {e}"

    encodings = ['utf-8', 'cp1256', 'iso-8859-1', 'ascii']
    for enc in encodings:
        try:
            with open(file_path, encoding=enc, errors='ignore') as f:
                content = f.read()
            return "text", content
        except (UnicodeDecodeError, PermissionError):
            continue

    return "error", "⚠️ خطا: encoding نامشخص یا دسترسی محدود"

def collect_all_files(root_dir: str) -> list:
    """جمع‌آوری لیست تمام فایل‌ها به جز node_modules"""
    result = []
    excluded_count = 0

    for dirpath, dirnames, filenames in os.walk(root_dir):
        # حذف پوشه‌های استثنا (با چک کامل)
        original_count = len(dirnames)
        dirnames[:] = [d for d in dirnames if not should_exclude(os.path.join(dirpath, d), is_dir=True)]
        excluded_count += original_count - len(dirnames)

        for filename in filenames:
            file_path = os.path.join(dirpath, filename)
            if should_exclude(file_path, is_dir=False):
                continue
            result.append(file_path)

    if excluded_count > 0:
        print(f"🔇 {excluded_count} پوشه (شامل node_modules) از اسکن حذف شدند.")

    return sorted(result)

def split_files_into_parts(file_list: list, parts: int) -> list:
    if parts <= 1:
        return [file_list]

    total_size = sum(os.path.getsize(f) for f in file_list)
    target_size_per_part = total_size / parts

    result = []
    current_part = []
    current_size = 0

    for file_path in file_list:
        file_size = os.path.getsize(file_path)
        if file_size > target_size_per_part * 1.5:
            if current_part:
                result.append(current_part)
                current_part = []
                current_size = 0
            result.append([file_path])
            continue

        current_part.append(file_path)
        current_size += file_size

        if current_size >= target_size_per_part:
            result.append(current_part)
            current_part = []
            current_size = 0

    if current_part:
        result.append(current_part)

    return result

def generate_split_files(root_dir: str, output_prefix: str, parts: int = 5):
    files = collect_all_files(root_dir)
    total_files = len(files)

    if total_files == 0:
        print("⚠️ هیچ فایلی پیدا نشد.")
        return

    print(f"📂 پوشه: {root_dir}")
    print(f"📄 تعداد فایل‌های متنی: {total_files}")
    print(f"📦 تعداد بخش‌ها: {parts}")
    print("-" * 50)

    file_groups = split_files_into_parts(files, parts)
    actual_parts = len(file_groups)

    text_count = 0
    binary_count = 0
    error_count = 0

    for part_idx, group in enumerate(file_groups, 1):
        output_file = f"{output_prefix}_{part_idx}_of_{actual_parts}.txt"

        with open(output_file, 'w', encoding='utf-8') as out:
            out.write("# ================================================\n")
            out.write(f"#  ترکیب فایل‌های پوشه: {root_dir}\n")
            out.write(f"#  بخش {part_idx} از {actual_parts}\n")
            out.write(f"#  تعداد فایل‌های این بخش: {len(group)}\n")
            out.write(f"#  تاریخ ایجاد: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            out.write("# ================================================\n\n")

            for idx, file_path in enumerate(group, 1):
                rel_path = os.path.relpath(file_path, root_dir)
                ext = os.path.splitext(file_path)[1] or "بدون پسوند"
                file_size = os.path.getsize(file_path)

                out.write(f"\n{'=' * 70}\n")
                out.write(f"📄 فایل [{idx}/{len(group)}]: {rel_path}\n")
                out.write(f"   مسیر کامل: {file_path}\n")
                out.write(f"   پسوند: {ext}\n")
                out.write(f"   حجم: {file_size:,} بایت ({file_size / 1024:.1f} KB)\n")
                out.write(f"{'=' * 70}\n\n")

                content_type, content = read_file_content(file_path)

                if content_type == "text":
                    out.write(content)
                    text_count += 1
                    status = "📝"
                elif content_type == "binary":
                    out.write(content)
                    binary_count += 1
                    status = "🔷"
                elif content_type == "info":
                    out.write(content)
                    status = "ℹ️"
                else:
                    out.write(content)
                    error_count += 1
                    status = "❌"

                out.write("\n\n")
                print(f"{status} بخش {part_idx}/{actual_parts} [{idx:3d}/{len(group)}]  {rel_path}  ({file_size / 1024:.1f} KB)")

        size_mb = os.path.getsize(output_file) / 1024 / 1024
        print(f"✅ بخش {part_idx} ذخیره شد: {output_file} ({size_mb:.2f} MB)")
        print("-" * 50)

    print(f"\n✅ همه بخش‌ها ذخیره شدند! ({actual_parts} فایل)")
    print("📊 خلاصه کلی:")
    print(f"   📝 فایل‌های متنی: {text_count}")
    print(f"   🔷 فایل‌های باینری (Base64): {binary_count}")
    if error_count > 0:
        print(f"   ❌ خطا: {error_count}")

def main():
    parser = argparse.ArgumentParser(
        description="تبدیل تمام فایل‌های یک پوشه به چند فایل متنی (بدون node_modules)"
    )
    parser.add_argument(
        "folder",
        help="مسیر پوشه‌ی مورد نظر"
    )
    parser.add_argument(
        "-o", "--output-prefix",
        default="files_part",
        help="پیشوند نام فایل‌های خروجی (پیش‌فرض: files_part)"
    )
    parser.add_argument(
        "-n", "--parts",
        type=int,
        default=5,
        help="تعداد بخش‌ها (پیش‌فرض: 5)"
    )
    parser.add_argument(
        "--max-size",
        type=int,
        default=50,
        help="حداکثر حجم فایل بر حسب مگابایت (پیش‌فرض: 50)"
    )

    args = parser.parse_args()

    global EXCLUDE_DIRS, MAX_FILE_SIZE, SPLIT_COUNT
    EXCLUDE_DIRS = args.exclude_dirs if hasattr(args, 'exclude_dirs') else EXCLUDE_DIRS
    MAX_FILE_SIZE = args.max_size * 1024 * 1024
    SPLIT_COUNT = args.parts

    if not os.path.isdir(args.folder):
        print(f"❌ پوشه‌ی '{args.folder}' وجود ندارد.")
        return

    generate_split_files(args.folder, args.output_prefix, args.parts)

if __name__ == "__main__":
    main()
