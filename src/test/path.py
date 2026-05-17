# 檔案位置：src/test/test_path.py
import os
import sys

# 取得 src/ 資料夾的絕對路徑並加到路徑中
src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)