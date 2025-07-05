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
        logger.info("[DRY-RUN] 当前为只读模式，不会对任何文件做写入操作。")
    image_meta = collect_images(folder)
    # 1. 按 (文件大小, 尺寸) 分组
    group_map = {}
    for meta in image_meta:
        key = (meta['size'], meta['shape'])
        group_map.setdefault(key, []).append(meta['path'])
    logger.info(f"分组后需进一步比对的组数: {len(group_map)}")
    # 2. 对每组做哈希分组
    hash_map = {}
    for key, files in group_map.items():
        if len(files) < 2:
            continue
        logger.info(f"正在处理分组: 大小={key[0]}, 尺寸={key[1]}, 文件数={len(files)}")
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
            f.write('[DRY-RUN] 只读模式，未做任何实际写入操作\n\n')
        group_id = 1
        for h, imgs in hash_map.items():
            f.write(f"重复图片组{group_id} (哈希: {h}):\n")
            for img in imgs:
                f.write(f"    {img}\n")
            f.write("\n")
            group_id += 1
        if video_duplicates:
            f.write(f"\n重复视频文件：\n")
            for idx, paths in enumerate(video_duplicates, 1):
                f.write(f"视频重复组{idx}:\n")
                for p in paths:
                    f.write(f"    {p}\n")
                f.write("\n")
    logger.info(f"去重完成，报告已保存到: {report_path}")


def supplement_images(main_folder, supplement_folder, report_path, hash_method='md5', dry_run=False):
    """
    增补模式主流程：补充图片和视频并输出报告。
    """
    if dry_run:
        logger.info("[DRY-RUN] 当前为只读模式，不会对任何文件做写入操作。")
    # 图片增补（原逻辑不变）
    main_meta = collect_images(main_folder)
    supplement_meta = collect_images(supplement_folder)
    logger.info(f"主文件夹图片数: {len(main_meta)}，补充文件夹图片数: {len(supplement_meta)}")
    with Pool(cpu_count()) as pool:
        main_hash_results = pool.map(_hash_worker, [(m['path'], hash_method) for m in main_meta])
    main_hashes = set(h for _, h in main_hash_results if h)
    logger.info(f"主文件夹哈希集合构建完成，唯一图片数: {len(main_hashes)}")
    with Pool(cpu_count()) as pool:
        supplement_hash_results = pool.map(_hash_worker, [(m['path'], hash_method) for m in supplement_meta])
    # 时间戳目录
    timestamp = time.strftime('%Y%m%d_%H%M%S')
    supplement_dir = os.path.join(main_folder, f'补充图片_{timestamp}')
    added = []
    skipped = []
    to_add = []
    for meta, (_, h) in zip(supplement_meta, supplement_hash_results):
        if not h:
            logger.warning(f"补充图片哈希失败，跳过: {meta['path']}")
            continue
        if h in main_hashes:
            skipped.append(meta['path'])
            logger.info(f"已存在，未增补: {meta['path']}")
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
    logger.info(f"增补图片总大小: {total_size/1024/1024:.2f} MB, 目标磁盘剩余空间: {free_space/1024/1024:.2f} MB")
    if total_size > free_space:
        logger.error("磁盘空间不足，操作中止！")
        if not dry_run:
            raise RuntimeError("磁盘空间不足，无法完成增补操作！")
    # 执行复制
    if to_add and not dry_run:
        os.makedirs(supplement_dir, exist_ok=True)
    for src, dst, _ in to_add:
        if dry_run:
            logger.info(f"[DRY-RUN] 预演增补: {src} -> {dst}")
            added.append(src)  # 记录源路径
        else:
            try:
                shutil.copy2(src, dst)
                added.append(src)  # 记录源路径
                logger.info(f"增补图片: {src} -> {dst}")
            except Exception as e:
                logger.error(f"复制图片失败: {src} -> {dst}, 错误: {e}")
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
            logger.info(f"已存在视频，未增补: {meta['path']}")
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
            logger.info(f"[DRY-RUN] 预演增补视频: {src} -> {dst}")
            video_added.append(src)  # 记录源路径
        else:
            try:
                shutil.copy2(src, dst)
                video_added.append(src)  # 记录源路径
                logger.info(f"增补视频: {src} -> {dst}")
            except Exception as e:
                logger.error(f"复制视频失败: {src} -> {dst}, 错误: {e}")
    # 若无增补视频且文件夹已创建，删除空文件夹
    if not video_added and not dry_run and os.path.exists(mp4_dir) and not os.listdir(mp4_dir):
        os.rmdir(mp4_dir)
    # 3. 输出报告
    with open(report_path, 'w', encoding='utf-8') as f:
        if dry_run:
            f.write('[DRY-RUN] 只读模式，未做任何实际写入操作\n\n')
        f.write(f"增补图片报告\n\n")
        f.write(f"成功增补 {len(added)} 张图片到: {supplement_dir}\n")
        for src in added:
            f.write(f"    {src}\n")
        f.write(f"\n已存在（未增补）{len(skipped)} 张图片：\n")
        for img in skipped:
            f.write(f"    {img}\n")
        f.write(f"\n成功增补 {len(video_added)} 个视频到: {mp4_dir}\n")
        for v in video_added:
            f.write(f"    {v}\n")
        f.write(f"\n已存在（未增补）{len(video_skipped)} 个视频：\n")
        for v in video_skipped:
            f.write(f"    {v}\n")
    logger.info(f"增补完成，报告已保存到: {report_path}")

