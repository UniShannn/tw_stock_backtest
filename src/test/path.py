# 注意!!! 凡是在test資料夾底下的py檔案 
# 記得要先打 import path 才 import config
# 為了把 src/ 加到路徑中，才能順利 import src/ 底下的模組
import os
import sys

# 取得 src/ 資料夾的絕對路徑並加到路徑中
src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)