import os
import hashlib
import logging
from PIL import Image
from multiprocessing import Pool, cpu_count
import time
import shutil
import psutil

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('photo_tool.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

LANG = 'zh'
TEXTS = {
    'zh': {
        'log_config': '日志配置',
        'hash_desc': '计算图片文件的哈希值，支持 md5/sha1。',
        'img_collect': '递归收集文件夹下所有图片文件路径、大小、尺寸。',
        'img_collect_ret': '返回：[{path, size, shape}...]',
        'img_found': '共发现图片文件 {count} 张',
        'img_meta': '成功读取元数据图片数: {count}',
        'img_size_fail': '无法读取图片尺寸, 错误: {err}',
        'img_size_fail2': '无法读取图片尺寸: {path}, 错误: {err}',
        'file_size_fail': '无法读取文件大小: {path}, 错误: {err}',
        'vid_collect': '递归收集文件夹下所有视频文件路径、大小、文件名。',
        'vid_collect_ret': '返回：[{path, size, name}...]',
        'vid_found': '共发现视频文件 {count} 个',
        'vid_meta': '成功读取元数据视频数: {count}',
        'vid_info_fail': '无法读取视频文件信息: {path}, 错误: {err}',
        'hash_fail': '哈希计算失败: {path}, 错误: {err}',
        'dedup_desc': '去重模式主流程：查找重复图片和视频并输出报告。',
        'dry_run': '[DRY-RUN] 当前为只读模式，不会对任何文件做写入操作。',
        'group_count': '分组后需进一步比对的组数: {count}',
        'group_processing': '正在处理分组: 大小={size}, 尺寸={shape}, 文件数={count}',
        'dedup_done': '去重完成，报告已保存到: {path}',
        'supp_desc': '增补模式主流程：补充图片和视频并输出报告。',
        'main_img_count': '主文件夹图片数: {main}, 补充文件夹图片数: {supp}',
        'main_hash_done': '主文件夹哈希集合构建完成，唯一图片数: {count}',
        'supp_dir': '补充图片_{timestamp}',
        'supp_hash_fail': '补充图片哈希失败，跳过: {path}',
        'supp_exists': '已存在，未增补: {path}',
        'disk_space': '增补图片总大小: {size:.2f} MB, 目标磁盘剩余空间: {free:.2f} MB',
        'disk_full': '磁盘空间不足，操作中止！',
        'disk_full_exc': '磁盘空间不足，无法完成增补操作！',
        'dry_run_supp': '[DRY-RUN] 预演增补: {src} -> {dst}',
        'supp_copy': '增补图片: {src} -> {dst}',
        'supp_copy_fail': '复制图片失败: {src} -> {dst}, 错误: {err}',
        'vid_supp_exists': '已存在视频，未增补: {path}',
        'dry_run_vid': '[DRY-RUN] 预演增补视频: {src} -> {dst}',
        'vid_supp_copy': '增补视频: {src} -> {dst}',
        'vid_supp_copy_fail': '复制视频失败: {src} -> {dst}, 错误: {err}',
        'dedup_img_group': '重复图片组{group_id} (哈希: {h}):',
        'dedup_vid_header': '\n重复视频文件：\n',
        'dedup_vid_group': '视频重复组{idx}:',
        'supp_report': '增补图片报告',
        'supp_img_success': '成功增补 {count} 张图片到: {dir}',
        'supp_img_exists': '已存在（未增补）{count} 张图片：',
        'supp_vid_success': '成功增补 {count} 个视频到: {dir}',
        'supp_vid_exists': '已存在（未增补）{count} 个视频：',
        'en_dash': '：',
    },
    'en': {
        'log_config': 'Log config',
        'hash_desc': 'Calculate image file hash, supports md5/sha1.',
        'img_collect': 'Recursively collect all image file paths, sizes, and shapes in folder.',
        'img_collect_ret': 'Return: [{path, size, shape}...]',
        'img_found': 'Found {count} image files',
        'img_meta': 'Successfully read metadata for {count} images',
        'img_size_fail': 'Failed to read image size, error: {err}',
        'img_size_fail2': 'Failed to read image size: {path}, error: {err}',
        'file_size_fail': 'Failed to read file size: {path}, error: {err}',
        'vid_collect': 'Recursively collect all video file paths, sizes, and names in folder.',
        'vid_collect_ret': 'Return: [{path, size, name}...]',
        'vid_found': 'Found {count} video files',
        'vid_meta': 'Successfully read metadata for {count} videos',
        'vid_info_fail': 'Failed to read video file info: {path}, error: {err}',
        'hash_fail': 'Hash calculation failed: {path}, error: {err}',
        'dedup_desc': 'Deduplication main flow: find duplicate images/videos and output report.',
        'dry_run': '[DRY-RUN] Readonly mode, no actual file operation.',
        'group_count': 'Groups to further compare: {count}',
        'group_processing': 'Processing group: size={size}, shape={shape}, count={count}',
        'dedup_done': 'Deduplication done, report saved to: {path}',
        'supp_desc': 'Supplement main flow: supplement images/videos and output report.',
        'main_img_count': 'Main folder images: {main}, supplement folder images: {supp}',
        'main_hash_done': 'Main folder hash set built, unique images: {count}',
        'supp_dir': 'supplement_{timestamp}',
        'supp_hash_fail': 'Supplement image hash failed, skip: {path}',
        'supp_exists': 'Already exists, not supplemented: {path}',
        'disk_space': 'Supplement images total size: {size:.2f} MB, target disk free: {free:.2f} MB',
        'disk_full': 'Disk space not enough, abort!',
        'disk_full_exc': 'Disk space not enough, cannot complete supplement!',
        'dry_run_supp': '[DRY-RUN] Simulate supplement: {src} -> {dst}',
        'supp_copy': 'Supplement image: {src} -> {dst}',
        'supp_copy_fail': 'Copy image failed: {src} -> {dst}, error: {err}',
        'vid_supp_exists': 'Video already exists, not supplemented: {path}',
        'dry_run_vid': '[DRY-RUN] Simulate supplement video: {src} -> {dst}',
        'vid_supp_copy': 'Supplement video: {src} -> {dst}',
        'vid_supp_copy_fail': 'Copy video failed: {src} -> {dst}, error: {err}',
        'dedup_img_group': 'Duplicate Image Group {group_id} (hash: {h}):',
        'dedup_vid_header': '\nDuplicate Videos:\n',
        'dedup_vid_group': 'Duplicate Video Group {idx}:',
        'supp_report': 'Supplement Report',
        'supp_img_success': 'Supplemented {count} images to: {dir}',
        'supp_img_exists': 'Already exists (not supplemented) {count} images:',
        'supp_vid_success': 'Supplemented {count} videos to: {dir}',
        'supp_vid_exists': 'Already exists (not supplemented) {count} videos:',
        'en_dash': ':',
    }
}
def get_text(lang, key, **kwargs):
    s = TEXTS.get(lang, TEXTS['zh']).get(key, key)
    return s.format(**kwargs) if kwargs else s


def get_image_hash(image_path, method='md5'):
    """
    计算图片文件的哈希值，支持 md5/sha1。
    """
    hash_func = hashlib.md5() if method == 'md5' else hashlib.sha1()
    with open(image_path, 'rb') as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            hash_func.update(chunk)
    return hash_func.hexdigest()


def get_image_size(image_path):
    try:
        with Image.open(image_path) as img:
            return img.size
    except Exception as e:
        if os.path.normpath(str(image_path)) in str(e).replace('\\\\', '\\'):
            logger.warning(f"无法读取图片尺寸, 错误: {e}")
        else:
            logger.warning(f"无法读取图片尺寸: {image_path}, 错误: {e}")
        return None


def collect_images(folder, exts=None):
    """
    递归收集文件夹下所有图片文件路径、大小、尺寸。
    返回：[{path, size, shape}...]
    """
    if exts is None:
        exts = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff'}
    image_files = []
    for root, _, files in os.walk(folder):
        for file in files:
            if os.path.splitext(file)[1].lower() in exts:
                image_files.append(os.path.join(root, file))
    logger.info(f"共发现图片文件 {len(image_files)} 张")
    # 多进程读取图片尺寸
    with Pool(cpu_count()) as pool:
        sizes = pool.map(get_image_size, image_files)
    image_meta = []
    for path, shape in zip(image_files, sizes):
        try:
            size = os.path.getsize(path)
        except Exception as e:
            logger.warning(f"无法读取文件大小: {path}, 错误: {e}")
            continue
        image_meta.append({'path': path, 'size': size, 'shape': shape})
    logger.info(f"成功读取元数据图片数: {len(image_meta)}")
    return image_meta


def collect_videos(folder, exts=None):
    """
    递归收集文件夹下所有视频文件路径、大小、文件名。
    返回：[{path, size, name}...]
    """
    if exts is None:
        exts = {'.mp4', '.mov'}
    video_files = []
    for root, _, files in os.walk(folder):
        for file in files:
            if os.path.splitext(file)[1].lower() in exts:
                video_files.append(os.path.join(root, file))
    logger.info(f"共发现视频文件 {len(video_files)} 个")
    video_meta = []
    for path in video_files:
        try:
            size = os.path.getsize(path)
            name = os.path.basename(path)
        except Exception as e:
            logger.warning(f"无法读取视频文件信息: {path}, 错误: {e}")
            continue
        video_meta.append({'path': path, 'size': size, 'name': name})
    logger.info(f"成功读取元数据视频数: {len(video_meta)}")
    return video_meta


def _hash_worker(args):
    path, method = args
    try:
        return path, get_image_hash(path, method)
    except Exception as e:
        logger.error(f"哈希计算失败: {path}, 错误: {e}")
        return path, None


def find_duplicates(folder, report_path, hash_method='md5', dry_run=False):
    """
    去重模式主流程：查找重复图片和视频并输出报告。
    """
    if dry_run:
        logger.info(get_text(LANG, 'dry_run'))
    image_meta = collect_images(folder)
    # 1. 按 (文件大小, 尺寸) 分组
    group_map = {}
    for meta in image_meta:
        key = (meta['size'], meta['shape'])
        group_map.setdefault(key, []).append(meta['path'])
    logger.info(get_text(LANG, 'group_count', count=len(group_map)))
    # 2. 对每组做哈希分组
    hash_map = {}
    for key, files in group_map.items():
        if len(files) < 2:
            continue
        logger.info(get_text(LANG, 'group_processing', size=key[0], shape=key[1], count=len(files)))
        with Pool(cpu_count()) as pool:
            hash_results = pool.map(_hash_worker, [(f, hash_method) for f in files])
        group_hash = {}
        for path, h in hash_results:
            if h is None:
                continue
            group_hash.setdefault(h, []).append(path)
        for h, imgs in group_hash.items():
            if len(imgs) > 1:
                hash_map.setdefault(h, []).extend(imgs)
    # 视频去重
    video_meta = collect_videos(folder)
    video_group = {}
    for meta in video_meta:
        key = (meta['name'], meta['size'])
        video_group.setdefault(key, []).append(meta['path'])
    video_duplicates = [paths for paths in video_group.values() if len(paths) > 1]
    # 3. 输出报告
    with open(report_path, 'w', encoding='utf-8') as f:
        if dry_run:
            f.write(get_text(LANG, 'dry_run') + '\n\n')
        group_id = 1
        for h, imgs in hash_map.items():
            f.write(get_text(LANG, 'dedup_img_group', group_id=group_id, h=h) + '\n')
            for img in imgs:
                f.write(f"    {img}\n")
            f.write("\n")
            group_id += 1
        if video_duplicates:
            f.write(get_text(LANG, 'dedup_vid_header'))
            for idx, paths in enumerate(video_duplicates, 1):
                f.write(get_text(LANG, 'dedup_vid_group', idx=idx) + '\n')
                for p in paths:
                    f.write(f"    {p}\n")
                f.write("\n")
    logger.info(get_text(LANG, 'dedup_done', path=report_path))


def supplement_images(main_folder, supplement_folder, report_path, hash_method='md5', dry_run=False):
    """
    增补模式主流程：补充图片和视频并输出报告。
    """
    if dry_run:
        logger.info(get_text(LANG, 'dry_run'))
    # 图片增补（原逻辑不变）
    main_meta = collect_images(main_folder)
    supplement_meta = collect_images(supplement_folder)
    logger.info(get_text(LANG, 'main_img_count', main=len(main_meta), supp=len(supplement_meta)))
    with Pool(cpu_count()) as pool:
        main_hash_results = pool.map(_hash_worker, [(m['path'], hash_method) for m in main_meta])
    main_hashes = set(h for _, h in main_hash_results if h)
    logger.info(get_text(LANG, 'main_hash_done', count=len(main_hashes)))
    with Pool(cpu_count()) as pool:
        supplement_hash_results = pool.map(_hash_worker, [(m['path'], hash_method) for m in supplement_meta])
    # 时间戳目录
    timestamp = time.strftime('%Y%m%d_%H%M%S')
    supplement_dir = os.path.join(main_folder, get_text(LANG, 'supp_dir', timestamp=timestamp))
    added = []
    skipped = []
    to_add = []
    for meta, (_, h) in zip(supplement_meta, supplement_hash_results):
        if not h:
            logger.warning(get_text(LANG, 'supp_hash_fail', path=meta['path']))
            continue
        if h in main_hashes:
            skipped.append(meta['path'])
            logger.info(get_text(LANG, 'supp_exists', path=meta['path']))
            continue
        # 复制到补充图片目录，避免重名
        base = os.path.basename(meta['path'])
        target = os.path.join(supplement_dir, base)
        count = 1
        while os.path.exists(target) and not dry_run:
            name, ext = os.path.splitext(base)
            target = os.path.join(supplement_dir, f"{name}_{count}{ext}")
            count += 1
        to_add.append((meta['path'], target, meta['size']))
    # 磁盘空间检查
    total_size = sum(size for _, _, size in to_add)
    free_space = psutil.disk_usage(main_folder).free
    logger.info(get_text(LANG, 'disk_space', size=total_size/1024/1024, free=free_space/1024/1024))
    if total_size > free_space:
        logger.error(get_text(LANG, 'disk_full'))
        if not dry_run:
            raise RuntimeError(get_text(LANG, 'disk_full_exc'))
    # 执行复制
    if to_add and not dry_run:
        os.makedirs(supplement_dir, exist_ok=True)
    for src, dst, _ in to_add:
        if dry_run:
            logger.info(get_text(LANG, 'dry_run_supp', src=src, dst=dst))
            added.append(src)  # 记录源路径
        else:
            try:
                shutil.copy2(src, dst)
                added.append(src)  # 记录源路径
                logger.info(get_text(LANG, 'supp_copy', src=src, dst=dst))
            except Exception as e:
                logger.error(get_text(LANG, 'supp_copy_fail', src=src, dst=dst, err=e))
    # 若无增补图片且文件夹已创建，删除空文件夹
    if not added and not dry_run and os.path.exists(supplement_dir) and not os.listdir(supplement_dir):
        os.rmdir(supplement_dir)
    # 视频增补（修正：避免重复增补）
    main_videos = collect_videos(main_folder)
    supplement_videos = collect_videos(supplement_folder)
    main_video_keys = set((v['name'], v['size']) for v in main_videos)
    mp4_dir = os.path.join(main_folder, f'MP4_{timestamp}')
    video_added = []
    video_skipped = []
    to_add_vid = []
    for meta in supplement_videos:
        key = (meta['name'], meta['size'])
        if key in main_video_keys:
            video_skipped.append(meta['path'])
            logger.info(get_text(LANG, 'vid_supp_exists', path=meta['path']))
            continue
        base = meta['name']
        target = os.path.join(mp4_dir, base)
        count = 1
        while os.path.exists(target) and not dry_run:
            name, ext = os.path.splitext(base)
            target = os.path.join(mp4_dir, f"{name}_{count}{ext}")
            count += 1
        to_add_vid.append((meta['path'], target))
    if to_add_vid and not dry_run:
        os.makedirs(mp4_dir, exist_ok=True)
    for src, dst in to_add_vid:
        if dry_run:
            logger.info(get_text(LANG, 'dry_run_vid', src=src, dst=dst))
            video_added.append(src)  # 记录源路径
        else:
            try:
                shutil.copy2(src, dst)
                video_added.append(src)  # 记录源路径
                logger.info(get_text(LANG, 'vid_supp_copy', src=src, dst=dst))
            except Exception as e:
                logger.error(get_text(LANG, 'vid_supp_copy_fail', src=src, dst=dst, err=e))
    # 若无增补视频且文件夹已创建，删除空文件夹
    if not video_added and not dry_run and os.path.exists(mp4_dir) and not os.listdir(mp4_dir):
        os.rmdir(mp4_dir)
    # 3. 输出报告
    with open(report_path, 'w', encoding='utf-8') as f:
        if dry_run:
            f.write(get_text(LANG, 'dry_run') + '\n\n')
        f.write(get_text(LANG, 'supp_report') + '\n\n')
        f.write(get_text(LANG, 'supp_img_success', count=len(added), dir=supplement_dir) + '\n')
        for src in added:
            f.write(f"    {src}\n")
        f.write(get_text(LANG, 'supp_img_exists', count=len(skipped)) + '\n')
        for img in skipped:
            f.write(f"    {img}\n")
        f.write(get_text(LANG, 'supp_vid_success', count=len(video_added), dir=mp4_dir) + '\n')
        for v in video_added:
            f.write(f"    {v}\n")
        f.write(get_text(LANG, 'supp_vid_exists', count=len(video_skipped)) + '\n')
        for v in video_skipped:
            f.write(f"    {v}\n")
    logger.info(get_text(LANG, 'dedup_done', path=report_path))

