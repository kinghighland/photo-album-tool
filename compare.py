import os
import hashlib
import logging
from PIL import Image
from multiprocessing import Pool, cpu_count
import time
import shutil
import psutil
import re
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
        'supp_hash_fail': '补充图片哈希失败，跳过: {path',
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
        path_norm = os.path.normcase(os.path.normpath(str(image_path)))
        err_str = str(e)
        match = re.search(r"['\"](.+?)['\"]", err_str)
        if match:
            err_path = os.path.normcase(os.path.normpath(match.group(1)))
            if path_norm == err_path:
                logger.warning(f"无法读取图片尺寸, 错误: {e}")
                return None
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

def find_duplicates(folder, report_path, hash_method='md5', dry_run=False, log_callback=None, progress_callback=None):
    """
    去重模式主流程：查找重复图片和视频并输出报告。
    """
    log = []
    corrupt_files = []
    
    def log_emit(msg):
        log.append(msg)
        if log_callback:
            log_callback(msg)
    
    def progress_emit(value):
        if progress_callback:
            progress_callback(value)
    
    if dry_run:
        log_emit(get_text(LANG, 'dry_run'))
    
    # 收集图片信息
    image_meta = collect_images(folder)
    total_images_scanned = len(image_meta)  # 添加这行
    progress_emit(0.1)
    
    # 按大小和尺寸分组
    group_map = {}
    for meta in image_meta:
        if meta['shape'] is None:  # 跳过无法读取尺寸的图片
            continue
        key = (meta['size'], meta['shape'])
        group_map.setdefault(key, []).append(meta)
    
    log_emit(get_text(LANG, 'group_count', count=len(group_map)))
    progress_emit(0.2)
    
    # 计算哈希值并找出重复组
    img_groups = []
    processed_groups = 0
    
    for idx, (key, files) in enumerate(group_map.items()):
        if len(files) < 2:
            processed_groups += 1
            continue
            
        log_emit(get_text(LANG, 'group_processing', size=key[0], shape=key[1], count=len(files)))
        
        # 计算每个文件的哈希值和详细信息
        file_details = []
        for meta in files:
            try:
                file_hash = get_image_hash(meta['path'], hash_method)
                if file_hash is None:
                    corrupt_files.append(meta['path'])
                    continue
                    
                # 获取文件详细信息
                file_info = {
                    'path': meta['path'],
                    'size': meta['size'],
                    'shape': meta['shape'],
                    'hash': file_hash,
                    'mtime': os.path.getmtime(meta['path']) if os.path.exists(meta['path']) else 0,
                    'is_corrupt': False
                }
                
                # 简化的图片验证
                try:
                    with Image.open(meta['path']) as img:
                        img.load()
                except Exception:
                    file_info['is_corrupt'] = True
                    corrupt_files.append(meta['path'])
                
                file_details.append(file_info)
                
            except Exception as e:
                log_emit(get_text(LANG, 'hash_fail', path=meta['path'], err=e))
                corrupt_files.append(meta['path'])
        
        # 按哈希值分组
        hash_groups = {}
        for file_info in file_details:
            hash_groups.setdefault(file_info['hash'], []).append(file_info)
        
        # 只保留有重复的组
        for hash_val, group in hash_groups.items():
            if len(group) > 1:
                img_groups.append(group)
        
        processed_groups += 1
        progress = 0.2 + 0.5 * (processed_groups / len(group_map))
        progress_emit(progress)
    
    progress_emit(0.7)
    
    # 处理视频文件
    video_meta = collect_videos(folder)
    total_videos_scanned = len(video_meta)  # 添加这行
    vid_groups = []
    
    if video_meta:
        # 按文件名和大小分组
        video_group_map = {}
        for meta in video_meta:
            key = (meta['name'], meta['size'])
            video_group_map.setdefault(key, []).append(meta)
        
        for group in video_group_map.values():
            if len(group) > 1:
                # 构建视频文件详细信息
                video_group = []
                for meta in group:
                    video_info = {
                        'path': meta['path'],
                        'name': meta['name'],
                        'size': meta['size'],
                        'mtime': os.path.getmtime(meta['path']) if os.path.exists(meta['path']) else 0,
                        'is_corrupt': False
                    }
                    video_group.append(video_info)
                vid_groups.append(video_group)
    
    progress_emit(0.9)
    
    # 生成统计信息
    total_img_files = sum(len(group) for group in img_groups)
    total_vid_files = sum(len(group) for group in vid_groups)
    
    stats = {
        'total_img_groups': len(img_groups),
        'total_img_files': total_img_files,
        'total_vid_groups': len(vid_groups), 
        'total_vid_files': total_vid_files,
        'corrupt_files_count': len(corrupt_files),
        'total_images_scanned': total_images_scanned,  # 添加这行
        'total_videos_scanned': total_videos_scanned,  # 添加这行
        'potential_space_saved': sum(
            sum(file_info['size'] for file_info in group[1:]) 
            for group in img_groups
        ) + sum(
            sum(file_info['size'] for file_info in group[1:])
            for group in vid_groups
        )
    }
    
    # 写报告文件 (保持兼容性)
    _write_dedup_report(report_path, img_groups, vid_groups, stats)
    
    log_emit(get_text(LANG, 'dedup_done', path=report_path))
    progress_emit(1.0)
    
    return {
        'img_groups': img_groups,
        'vid_groups': vid_groups,
        'stats': stats,
        'log': log,
        'progress': 1.0,
        'corrupt_files': corrupt_files
    }


def supplement_images(main_folder, supplement_folder, report_path, hash_method='md5', dry_run=False, log_callback=None, progress_callback=None):
    """
    增补模式主流程：补充图片和视频并输出报告。
    返回dict: {
        'added_images': List[dict],  # 需要增补的图片详细信息
        'skipped_images': List[dict],  # 已存在的图片
        'added_videos': List[dict],  # 需要增补的视频
        'skipped_videos': List[dict],  # 已存在的视频
        'target_dirs': dict,  # 目标目录
        'stats': dict,  # 统计信息
        'log': List[str],
        'progress': float,
        'corrupt_files': List[str]
    }
    """
    log = []
    corrupt_files = []
    def log_emit(msg):
        log.append(msg)
        if log_callback:
            log_callback(msg)
    
    def progress_emit(value):
        if progress_callback:
            progress_callback(value)
    
    if dry_run:
        log_emit(get_text(LANG, 'dry_run'))
    
    # 扫描主文件夹
    main_meta = collect_images(main_folder)
    progress_emit(0.2)
    
    # 扫描补充文件夹  
    supplement_meta = collect_images(supplement_folder)
    progress_emit(0.3)
    
    log_emit(get_text(LANG, 'main_img_count', main=len(main_meta), supp=len(supplement_meta)))
    
    # 构建主文件夹哈希集合
    main_hashes = set()
    for idx, meta in enumerate(main_meta):
        try:
            file_hash = get_image_hash(meta['path'], hash_method)
            if file_hash:
                main_hashes.add(file_hash)
        except Exception as e:
            log_emit(get_text(LANG, 'hash_fail', path=meta['path'], err=e))
        
        if idx % 100 == 0:  # 每100个文件更新一次进度
            progress = 0.3 + 0.3 * (idx / len(main_meta)) if main_meta else 0.3
            progress_emit(progress)
    
    log_emit(get_text(LANG, 'main_hash_done', count=len(main_hashes)))
    progress_emit(0.6)
    
    # 处理补充文件夹的图片
    added_images = []
    skipped_images = []
    
    timestamp = time.strftime('%Y%m%d_%H%M%S')
    supplement_dir = os.path.join(main_folder, get_text(LANG, 'supp_dir', timestamp=timestamp))
    
    for idx, meta in enumerate(supplement_meta):
        try:
            file_hash = get_image_hash(meta['path'], hash_method)
            if not file_hash:
                log_emit(get_text(LANG, 'supp_hash_fail', path=meta['path']))
                corrupt_files.append(meta['path'])
                continue
            
            # 验证图片是否损坏
            is_corrupt = False
            try:
                with Image.open(meta['path']) as img:
                    img.verify()
            except Exception:
                is_corrupt = True
                corrupt_files.append(meta['path'])
            
            base_name = os.path.basename(meta['path'])
            target_path = os.path.join(supplement_dir, base_name)
            
            file_info = {
                'path': meta['path'],
                'target_path': target_path,
                'size': meta['size'],
                'shape': meta['shape'],
                'hash': file_hash,
                'mtime': os.path.getmtime(meta['path']) if os.path.exists(meta['path']) else 0,
                'is_corrupt': is_corrupt
            }
            
            if file_hash in main_hashes:
                skipped_images.append(file_info)
                log_emit(get_text(LANG, 'supp_exists', path=meta['path']))
            else:
                added_images.append(file_info)
        
        except Exception as e:
            log_emit(get_text(LANG, 'hash_fail', path=meta['path'], err=e))
            corrupt_files.append(meta['path'])
        
        if idx % 50 == 0:  # 每50个文件更新一次进度
            progress = 0.6 + 0.2 * (idx / len(supplement_meta)) if supplement_meta else 0.6
            progress_emit(progress)
    
    progress_emit(0.8)
    
    # 处理视频文件
    main_videos = collect_videos(main_folder)
    supplement_videos = collect_videos(supplement_folder)
    
    main_video_keys = set((v['name'], v['size']) for v in main_videos)
    mp4_dir = os.path.join(main_folder, f'MP4_{timestamp}')
    
    added_videos = []
    skipped_videos = []
    
    for meta in supplement_videos:
        key = (meta['name'], meta['size'])
        target_path = os.path.join(mp4_dir, meta['name'])
        
        video_info = {
            'path': meta['path'],
            'target_path': target_path,
            'name': meta['name'],
            'size': meta['size'],
            'mtime': os.path.getmtime(meta['path']) if os.path.exists(meta['path']) else 0,
            'is_corrupt': False
        }
        
        if key in main_video_keys:
            skipped_videos.append(video_info)
            log_emit(get_text(LANG, 'vid_supp_exists', path=meta['path']))
        else:
            added_videos.append(video_info)
    
    progress_emit(0.9)
    
    # 统计信息
    total_add_size = sum(img['size'] for img in added_images) + sum(vid['size'] for vid in added_videos)
    
    stats = {
        'main_scanned': len(main_meta),
        'supplement_scanned': len(supplement_meta),
        'images_to_add': len(added_images),
        'images_skipped': len(skipped_images),
        'videos_to_add': len(added_videos),
        'videos_skipped': len(skipped_videos),
        'total_add_size': total_add_size,
        'corrupt_files_count': len(corrupt_files)
    }
    
    target_dirs = {
        'supplement_dir': supplement_dir,
        'mp4_dir': mp4_dir
    }
    
    # 写报告文件 (保持兼容性)
    _write_supplement_report(report_path, added_images, skipped_images, added_videos, skipped_videos, target_dirs, stats, dry_run)
    
    log_emit(get_text(LANG, 'dedup_done', path=report_path))
    progress_emit(1.0)
    
    return {
        'added_images': added_images,
        'skipped_images': skipped_images,
        'added_videos': added_videos,
        'skipped_videos': skipped_videos,
        'target_dirs': target_dirs,
        'stats': stats,
        'log': log,
        'progress': 1.0,
        'corrupt_files': corrupt_files
    }


def _write_dedup_report(report_path, img_groups, vid_groups, stats):
    """写入去重报告文件"""
    with open(report_path, 'w', encoding='utf-8') as f:
        if LANG == 'zh':
            f.write('去重图片报告\n\n')
            f.write(f'共检测到{stats["total_img_groups"]}组重复图片，共{stats["total_img_files"]}张图片\n\n')
        else:
            f.write('Deduplication Report\n\n')
            f.write(f'{stats["total_img_groups"]} duplicate image groups, {stats["total_img_files"]} images in total\n\n')
        
        if img_groups:
            for group_id, group in enumerate(img_groups, 1):
                f.write(f'重复图片组{group_id} (哈希: {group[0]["hash"]}):\n' if LANG == 'zh' else f'Duplicate Image Group {group_id} (hash: {group[0]["hash"]}):\n')
                for file_info in group:
                    f.write(f"    {file_info['path']}\n")
                f.write("\n")
        else:
            f.write('未发现重复图片\n\n' if LANG == 'zh' else 'No duplicate images found\n\n')
        
        if LANG == 'zh':
            f.write(f'共检测到{stats["total_vid_groups"]}组重复视频，共{stats["total_vid_files"]}个视频\n\n')
        else:
            f.write(f'{stats["total_vid_groups"]} duplicate video groups, {stats["total_vid_files"]} videos in total\n\n')
        
        if vid_groups:
            for idx, group in enumerate(vid_groups, 1):
                f.write(f'视频重复组{idx}:\n' if LANG == 'zh' else f'Duplicate Video Group {idx}:\n')
                for file_info in group:
                    f.write(f"    {file_info['path']}\n")
                f.write("\n")
        else:
            f.write('未发现重复视频\n' if LANG == 'zh' else 'No duplicate videos found\n')


def _write_supplement_report(report_path, added_images, skipped_images, added_videos, skipped_videos, target_dirs, stats, dry_run):
    """写入增补报告文件"""
    with open(report_path, 'w', encoding='utf-8') as f:
        if dry_run:
            f.write(get_text(LANG, 'dry_run') + '\n\n')
        f.write(get_text(LANG, 'supp_report') + '\n\n')
        f.write(get_text(LANG, 'supp_img_success', count=len(added_images), dir=target_dirs['supplement_dir']) + '\n')
        
        for img in added_images:
            f.write(f"    {img['path']}\n")
        
        f.write(get_text(LANG, 'supp_img_exists', count=len(skipped_images)) + '\n')
        for img in skipped_images:
            f.write(f"    {img['path']}\n")
        
        f.write(get_text(LANG, 'supp_vid_success', count=len(added_videos), dir=target_dirs['mp4_dir']) + '\n')
        for vid in added_videos:
            f.write(f"    {vid['path']}\n")
        
        f.write(get_text(LANG, 'supp_vid_exists', count=len(skipped_videos)) + '\n')
        for vid in skipped_videos:
            f.write(f"    {vid['path']}\n")