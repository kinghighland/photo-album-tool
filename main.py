import argparse
import os
from compare import (
    collect_images,
    find_duplicates,
    supplement_images
)


def main():
    parser = argparse.ArgumentParser(description='照片去重与增补工具')
    parser.add_argument('folder1', help='主文件夹路径（去重模式为待去重文件夹，增补模式为主文件夹）')
    parser.add_argument('folder2', nargs='?', default=None, help='补充文件夹路径（仅增补模式需要）')
    parser.add_argument('--report', default='report.txt', help='报告输出路径')
    parser.add_argument('--hash', default='md5', choices=['md5', 'sha1'], help='哈希算法')
    parser.add_argument('--execute', action='store_true', help='真正执行写入操作（否则为只读预演模式）')
    args = parser.parse_args()

    dry_run = not args.execute

    if args.folder2:
        # 增补模式
        print(f"运行增补模式：主文件夹={args.folder1}，补充文件夹={args.folder2}")
        supplement_images(args.folder1, args.folder2, args.report, args.hash, dry_run=dry_run)
    else:
        # 去重模式
        print(f"运行去重模式：目标文件夹={args.folder1}")
        find_duplicates(args.folder1, args.report, args.hash, dry_run=dry_run)

if __name__ == '__main__':
    main()
