import zipfile
import os

def zip_project_folder(source_dir=".", output_zip="project.zip", exclude_dirs=None, exclude_exts=None, exclude_files=None):
    exclude_dirs = exclude_dirs or ['.git', '.venv', '__pycache__']
    exclude_exts = exclude_exts or ['.pyc', '.log', ".zip", ".pfx"]
    exclude_files = exclude_files or ['combined_stock_data.csv']  # ✅ 新增：可排除特定檔名

    with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(source_dir):
            # 過濾隱藏資料夾與排除清單
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in exclude_dirs]

            for file in files:
                # 跳過隱藏檔與指定副檔名
                if (
                    file.startswith('.') or
                    any(file.endswith(ext) for ext in exclude_exts) or
                    file in exclude_files
                ):
                    continue

                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, start=source_dir)
                zipf.write(full_path, arcname=rel_path)

    print(f"✅ 壓縮完成：{output_zip}")

