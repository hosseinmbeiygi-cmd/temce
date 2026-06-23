import json
import os
from pathlib import Path


def get_frontend_structure(project_root: str = ".") -> dict[str, object]:
    """
    اسکن کامل پوشه‌ی فرانت‌اند و استخراج اطلاعات ساختاری.
    """
    frontend_path = Path(project_root) / "frontend"

    if not frontend_path.exists():
        return {"error": "پوشه‌ی frontend یافت نشد!"}

    result: dict[str, object] = {
        "path": str(frontend_path),
        "folders": [],
        "files": {
            "total": 0,
            "by_extension": {},
            "details": [],
        },
        "package_json": None,
        "next_config": None,
        "components": [],
        "pages": [],
        "api_routes": [],
        "styles": [],
        "public_assets": [],
        "hooks": [],
        "utils": [],
        "types": [],
    }

    for root, dirs, files in os.walk(frontend_path):
        # حذف پوشه‌های سیستمی و کش
        dirs[:] = [d for d in dirs if not d.startswith((".", "_", "node_modules", ".next", "out", "dist"))]

        rel_path = Path(root).relative_to(frontend_path)
        if str(rel_path) != ".":
            result["folders"].append(str(rel_path))

        for file in files:
            # حذف فایل‌های سیستمی و کش
            if file.startswith((".", "_")):
                continue

            file_path = Path(root) / file
            rel_file_path = file_path.relative_to(frontend_path)
            ext = file_path.suffix or "no_extension"

            # دسته‌بندی فایل‌ها
            result["files"]["total"] += 1
            result["files"]["by_extension"][ext] = result["files"]["by_extension"].get(ext, 0) + 1
            result["files"]["details"].append(str(rel_file_path))

            # بررسی فایل‌های خاص
            if file == "package.json":
                try:
                    with open(file_path, encoding="utf-8") as f:
                        result["package_json"] = json.load(f)
                except Exception:
                    result["package_json"] = {"error": "نمی‌توان فایل را خواند"}

            elif file in ("next.config.js", "next.config.ts"):
                result["next_config"] = str(rel_file_path)

            # دسته‌بندی بر اساس مسیر
            str_rel = str(rel_file_path)
            if "components" in str_rel and ext in (".tsx", ".jsx", ".ts", ".js"):
                result["components"].append(str_rel)
            elif "app" in str_rel and ext in (".tsx", ".jsx") and "page" in file:
                result["pages"].append(str_rel)
            elif "api" in str_rel and ext in (".ts", ".js"):
                result["api_routes"].append(str_rel)
            elif "styles" in str_rel and ext in (".css", ".scss", ".sass", ".less"):
                result["styles"].append(str_rel)
            elif "public" in str_rel:
                result["public_assets"].append(str_rel)
            elif "hooks" in str_rel and ext in (".ts", ".tsx", ".js", ".jsx"):
                result["hooks"].append(str_rel)
            elif "utils" in str_rel and ext in (".ts", ".js"):
                result["utils"].append(str_rel)
            elif "types" in str_rel and ext in (".ts", ".d.ts"):
                result["types"].append(str_rel)

    return result


def print_tree(structure: dict[str, object], indent: int = 0) -> None:
    """نمایش ساختار درختی فرانت‌اند."""
    print(" " * indent + "📁 frontend/")

    # نمایش پوشه‌ها
    folders = sorted(set(structure.get("folders", [])))  # type: ignore
    for folder in folders:
        depth = folder.count("/")
        print(" " * (indent + 2 + depth * 2) + f"📁 {folder.split('/')[-1]}/")

    # نمایش فایل‌ها بر اساس پسوند
    ext_colors = {
        ".tsx": "🔵",
        ".jsx": "🔷",
        ".ts": "🟦",
        ".js": "🟨",
        ".css": "🟩",
        ".scss": "🟢",
        ".json": "📄",
        ".html": "🌐",
    }

    by_ext = structure.get("files", {}).get("by_extension", {})
    for ext, count in sorted(by_ext.items()):  # type: ignore
        color = ext_colors.get(ext, "📄")
        print(f"   {color} {ext}: {count} فایل")

    print("\n📊 خلاصه:")
    files_total = structure.get("files", {}).get("total", 0)
    folders_count = len(structure.get("folders", []))  # type: ignore
    print(f"   مجموع فایل‌ها: {files_total}")
    print(f"   تعداد پوشه‌ها: {folders_count}")

    # اطلاعات package.json
    pkg = structure.get("package_json")
    if pkg and isinstance(pkg, dict):
        deps = pkg.get("dependencies", {})
        dev_deps = pkg.get("devDependencies", {})
        print("\n📦 وابستگی‌ها:")
        print(f"   اصلی: {len(deps)} مورد")
        for pkg_name, ver in list(deps.items())[:5]:
            print(f"     • {pkg_name}: {ver}")
        if len(deps) > 5:
            print(f"     ... و {len(deps) - 5} مورد دیگر")
        print(f"   توسعه: {len(dev_deps)} مورد")

    # بخش‌های اصلی
    print("\n🗂️ بخش‌های اصلی:")
    print(f"   📄 صفحات (Pages): {len(structure.get('pages', []))}")  # type: ignore
    print(f"   🧩 کامپوننت‌ها: {len(structure.get('components', []))}")  # type: ignore
    print(f"   🔌 API Routes: {len(structure.get('api_routes', []))}")  # type: ignore
    print(f"   🎨 استایل‌ها: {len(structure.get('styles', []))}")  # type: ignore
    print(f"   🖼️ Assets عمومی: {len(structure.get('public_assets', []))}")  # type: ignore
    print(f"   🪝 Hooks: {len(structure.get('hooks', []))}")  # type: ignore
    print(f"   🛠️ Utils: {len(structure.get('utils', []))}")  # type: ignore
    print(f"   📋 Types: {len(structure.get('types', []))}")  # type: ignore


def save_report(structure: dict[str, object], output_file: str = "frontend_report.json") -> None:
    """ذخیره‌ی گزارش به‌صورت فایل JSON."""
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(structure, f, indent=2, ensure_ascii=False)
    print(f"\n✅ گزارش کامل در فایل {output_file} ذخیره شد.")


if __name__ == "__main__":
    # اجرای اسکریپت
    structure = get_frontend_structure(".")

    if "error" in structure:
        print(f"❌ {structure['error']}")
    else:
        print_tree(structure)
        save_report(structure)
