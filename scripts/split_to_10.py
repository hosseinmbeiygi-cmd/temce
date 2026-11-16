import os
import traceback
from pathlib import Path


def collect_python_files(root_dir='.'):
    """جمع‌آوری مسیر تمام فایل‌های .py به جز پوشه‌های حذف‌شده"""
    skip_dirs = {
        # محیط‌های مجازی و پوشه‌های غیرضروری
        'venv', 'venve', '.venv', 'env', '.env',
        'virtualenv', 'codal_env',
        'nmp', 'node_modules', '__pycache__', '.git',
        'site-packages', 'dist-packages',
        # پوشه‌های جدید که باید نادیده گرفته شوند
        '.mimocode',
        'claw-code',
        'code_dump'
    }
    py_files = []

    for dirpath, dirnames, filenames in os.walk(root_dir):
        # حذف پوشه‌های غیرمجاز از لیست پیمایش
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]

        for filename in filenames:
            if filename.endswith('.py'):
                full_path = os.path.join(dirpath, filename)
                py_files.append(full_path)

    return sorted(py_files)


def split_into_chunks(files, num_chunks=10):
    """تقسیم لیست فایل‌ها به تعداد مشخص"""
    if not files:
        return [[] for _ in range(num_chunks)]

    chunk_size = max(1, len(files) // num_chunks)
    chunks = []

    for i in range(num_chunks):
        start = i * chunk_size
        end = len(files) if i == num_chunks - 1 else start + chunk_size
        chunks.append(files[start:end])

    return chunks


def write_chunks_to_files(chunks, output_dir='output_texts'):
    """نوشتن هر گروه از فایل‌ها در یک فایل متنی جداگانه"""
    output_path = Path(output_dir).resolve()
    output_path.mkdir(parents=True, exist_ok=True)

    for idx, chunk in enumerate(chunks, start=1):
        output_file = output_path / f'part_{idx:02d}.txt'

        with open(output_file, 'w', encoding='utf-8') as out:
            if not chunk:
                out.write("(این بخش خالی است - فایل پایتونی در این دسته وجود ندارد)\n")
                continue

            for py_file in chunk:
                folder = os.path.dirname(py_file)
                filename = os.path.basename(py_file)

                out.write(f"FOLDER: {folder}\n")
                out.write(f"FILE: {filename}\n")
                out.write(f"{'=' * 60}\n\n")

                try:
                    try:
                        with open(py_file, encoding='utf-8') as src:
                            content = src.read()
                    except UnicodeDecodeError:
                        with open(py_file, encoding='latin-1') as src:
                            content = src.read()
                    except Exception as e:
                        content = f"[Error reading file: {e}]"

                    out.write(content)
                except Exception as e:
                    out.write(f"[Error processing file: {e}]\n")

                out.write("\n\n")


def main():
    try:
        root = '.'
        print(f"مسیر جاری: {Path(root).resolve()}")

        py_files = collect_python_files(root)

        # نمایش پوشه‌های یکتا
        folders = sorted({os.path.dirname(f) for f in py_files})
        print("\nپوشه‌های پیدا شده:")
        for folder in folders:
            print(f"  - {folder}")

        print(f"\nتعداد فایل‌های پایتون: {len(py_files)}")

        chunks = split_into_chunks(py_files, num_chunks=10)
        write_chunks_to_files(chunks)

        # نمایش مسیر خروجی
        output_path = Path('output_texts').resolve()
        print("\nفایل‌های خروجی در پوشه زیر ساخته شدند:")
        print(f"  {output_path}")

        # نمایش لیست فایل‌های ساخته شده
        if output_path.exists():
            for txt_file in sorted(output_path.glob('*.txt')):
                size = txt_file.stat().st_size
                print(f"  - {txt_file.name} ({size} بایت)")
        else:
            print("پوشه خروجی یافت نشد!")

    except Exception:
        print("خطای غیرمنتظره رخ داد:")
        traceback.print_exc()


if __name__ == '__main__':
    main()
