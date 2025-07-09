import argparse
import os
from compare import (collect_images,find_duplicates,supplement_duplicates)

TEXTS = {
    'zh': {
        'desc': '照片去重与增补工具',
        'folder1': '主文件夹路径（去重模式为待去重文件夹，增补模式为主文件夹）',
        'folder2': '补充文件夹路径（仅增补模式需要）',
        'report': '报告输出路径',
        'hash': '哈希算法',
        'execute': '真正执行写入操作（否则为只读预演模式）',
        'dedup_mode': '运行去重模式：目标文件夹={folder}',
        'supp_mode': '运行增补模式：主文件夹={main}，补充文件夹={supp}',
    },
    'en': {
        'desc': 'Photo Deduplication & Supplement Tool',
        'folder1': 'Main folder path (target folder for deduplication, main folder for supplement)',
        'folder2': 'Supplement folder path (only needed for supplement mode)',
        'report': 'Report output path',
        'hash': 'Hash algorithm',
        'execute': 'Actually perform file operations (otherwise dry-run mode)',
        'dedup_mode': 'Running deduplication mode: target folder={folder}',
        'supp_mode': 'Running supplement mode: main={main}, supplement={supp}',
    }
}
def get_text(lang, key, **kwargs):
    s = TEXTS.get(lang, TEXTS['zh']).get(key, key)
    return s.format(**kwargs) if kwargs else s


def main():
    import sys
    lang = 'zh'
    for i, arg in enumerate(sys.argv):
        if arg == '--lang' and i+1 < len(sys.argv):
            lang = sys.argv[i+1]
    parser = argparse.ArgumentParser(description=get_text(lang, 'desc'))
    parser.add_argument('folder1', help=get_text(lang, 'folder1'))
    parser.add_argument('folder2', nargs='?', default=None, help=get_text(lang, 'folder2'))
    parser.add_argument('--report', default='report.txt', help=get_text(lang, 'report'))
    parser.add_argument('--hash', default='md5', choices=['md5', 'sha1'], help=get_text(lang, 'hash'))
    parser.add_argument('--execute', action='store_true', help=get_text(lang, 'execute'))
    parser.add_argument('--lang', default=lang, choices=['zh', 'en'], help='Language: zh or en')
    args = parser.parse_args()
    lang = args.lang
    import compare
    compare.LANG = lang
    dry_run = not args.execute
    if args.folder2:
        print(get_text(lang, 'supp_mode', main=args.folder1, supp=args.folder2))
        compare.supplement_duplicates(args.folder1, args.folder2, args.report, args.hash, dry_run=dry_run)
    else:
        print(get_text(lang, 'dedup_mode', folder=args.folder1))
        compare.find_duplicates(args.folder1, args.report, args.hash, dry_run=dry_run)

if __name__ == '__main__':
    main()
