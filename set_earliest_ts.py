# 设置文件创建时间的工具，实现如下要求：
# 递归遍历指定目录，包含所有子目录，查找每个文件的atime/mtime/ctime，找出最早时间；
# 支持两种模式：
#   --mode show ：只显示每个文件的时间信息，不修改
#   --mode exec ：执行实际的创建时间修改
# 通过命令行参数控制要处理的目录和模式

import os
import sys
import argparse
import datetime

# 仅在 Windows 下使用 pywin32
try:
    import pywintypes
    import win32file
    import win32con
except ImportError:
    pywintypes = None
    win32file = None
    win32con = None

def get_file_times(path):
    stat = os.stat(path)
    atime = datetime.datetime.fromtimestamp(stat.st_atime)
    mtime = datetime.datetime.fromtimestamp(stat.st_mtime)
    ctime = datetime.datetime.fromtimestamp(stat.st_ctime)
    return atime, mtime, ctime

def set_file_creation_time(path, new_ctime):
    try:
        handle = win32file.CreateFile(
            path,
            win32con.GENERIC_WRITE,
            0,
            None,
            win32con.OPEN_EXISTING,
            win32con.FILE_ATTRIBUTE_NORMAL,
            None)
        stat = os.stat(path)
        atime = pywintypes.Time(stat.st_atime)
        mtime = pywintypes.Time(stat.st_mtime)
        # 注意new_ctime必须是 pywintypes.Time 类型
        win32file.SetFileTime(handle, pywintypes.Time(new_ctime.timestamp()), atime, mtime)
        handle.close()
        return True, ""
    except Exception as e:
        return False, str(e)

def process_file(path, mode):
    try:
        atime, mtime, ctime = get_file_times(path)
        min_time = min(atime, mtime, ctime)
        print(f"{path}")
        print(f"  atime: {atime}")
        print(f"  mtime: {mtime}")
        print(f"  ctime: {ctime}")
        print(f"  earliest: {min_time}", end=' ')
        if min_time == ctime:
            print("[已最早，无需修改]")
            return

        if mode == "show":
            print("[需修改]")
        elif mode == "exec":
            # 修改 ctime（仅Windows）
            if win32file:
                ok, errmsg = set_file_creation_time(path, min_time)
                if ok:
                    print("[已修改]")
                else:
                    print(f"[修改失败: {errmsg}]")
            else:
                print("[exec模式仅支持Windows]")
        else:
            print("[未知模式]")
    except Exception as e:
        print(f"{path} [处理失败: {e}]")

def process_dir(root_dir, mode):
    for base, dirs, files in os.walk(root_dir):
        for fname in files:
            fpath = os.path.join(base, fname)
            process_file(fpath, mode)

def main():
    parser = argparse.ArgumentParser(description="批量查/改文件的创建时间为最早的时间")
    parser.add_argument("directory", metavar="DIR", help="要处理的根目录")
    parser.add_argument("--mode", choices=["show", "exec"], required=True, help="操作模式: show | exec")
    args = parser.parse_args()

    # 检查操作系统
    if sys.platform != "win32" and args.mode == "exec":
        print("exec模式仅支持Windows系统。")
        sys.exit(1)

    process_dir(args.directory, args.mode)

if __name__ == "__main__":
    main()