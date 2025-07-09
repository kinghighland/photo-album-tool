from translations import tr, get_language
from PIL import Image, UnidentifiedImageError
from multiprocessing import Pool, cpu_count
import signal
import sys
import os
import re
import time
import shutil
import psutil
import hashlib
import logging
from pathlib import Path

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
# LANG = 'zh'
# TEXTS = {
#     'zh': {
#         'log_config': '日志配置',
#         'hash_desc': '计算图片文件的哈希值，支持 md5/sha1。',
#         'img_collect': '递归收集文件夹下所有图片文件路径、大小、尺寸。',
#         'img_collect_ret': '返回：[{path, size, shape}...]',
#         'img_found': '共发现图片文件 {count} 张',
#         'img_meta': '成功读取元数据图片数: {count}',
#         'img_size_fail': '无法读取图片尺寸, 错误: {err}',
#         'img_size_fail2': '无法读取图片尺寸: {path}, 错误: {err}',
#         'file_size_fail': '无法读取文件大小: {path}, 错误: {err}',
#         'vid_collect': '递归收集文件夹下所有视频文件路径、大小、文件名。',
#         'vid_collect_ret': '返回：[{path, size, name}...]',
#         'vid_found': '共发现视频文件 {count} 个',
#         'vid_meta': '成功读取元数据视频数: {count}',
#         'vid_info_fail': '无法读取视频文件信息: {path}, 错误: {err}',
#         'hash_fail': '哈希计算失败: {path}, 错误: {err}',
#         'dedup_desc': '去重模式主流程：查找重复图片和视频并输出报告。',
#         'dry_run': '[DRY-RUN] 当前为只读模式，不会对任何文件做写入操作。',
#         'group_count': '分组后需进一步比对的组数: {count}',
#         'group_processing': '正在处理分组: 大小={size}, 尺寸={shape}, 文件数={count}',
#         'dedup_done': '去重完成，报告已保存到: {path}',
#         'supp_desc': '增补模式主流程：补充图片和视频并输出报告。',
#         'main_img_count': '主文件夹图片数: {main}, 补充文件夹图片数: {supp}',
#         'main_hash_done': '主文件夹哈希集合构建完成，唯一图片数: {count}',
#         'supp_dir': '补充图片_{timestamp}',
#         'supp_hash_fail': '补充图片哈希失败，跳过: {path',
#         'supp_exists': '已存在，未增补: {path}',
#         'disk_space': '增补图片总大小: {size:.2f} MB, 目标磁盘剩余空间: {free:.2f} MB',
#         'disk_full': '磁盘空间不足，操作中止！',
#         'disk_full_exc': '磁盘空间不足，无法完成增补操作！',
#         'dry_run_supp': '[DRY-RUN] 预演增补: {src} -> {dst}',
#         'supp_copy': '增补图片: {src} -> {dst}',
#         'supp_copy_fail': '复制图片失败: {src} -> {dst}, 错误: {err}',
#         'vid_supp_exists': '已存在视频，未增补: {path}',
#         'dry_run_vid': '[DRY-RUN] 预演增补视频: {src} -> {dst}',
#         'vid_supp_copy': '增补视频: {src} -> {dst}',
#         'vid_supp_copy_fail': '复制视频失败: {src} -> {dst}, 错误: {err}',
#         'dedup_img_group': '重复图片组{group_id} (哈希: {h}):',
#         'dedup_vid_header': '\n重复视频文件：\n',
#         'dedup_vid_group': '视频重复组{idx}:',
#         'supp_report': '增补图片报告',
#         'supp_img_success': '成功增补 {count} 张图片到: {dir}',
#         'supp_img_exists': '已存在（未增补）{count} 张图片：',
#         'supp_vid_success': '成功增补 {count} 个视频到: {dir}',
#         'supp_vid_exists': '已存在（未增补）{count} 个视频：',
#         'en_dash': '：',
#         'scanning_images': '正在扫描图片文件...',
#         'images_found': '发现图片文件 {count} 张',
#         'scanning_videos': '正在扫描视频文件...',
#         'videos_found': '发现视频文件 {count} 个',
#         'analyzing_duplicates': '正在分析重复文件，共 {count} 组待处理...',
#         'analysis_complete': '分析完成',
#     },
#     'en': {
#         'log_config': 'Log config',
#         'hash_desc': 'Calculate image file hash, supports md5/sha1.',
#         'img_collect': 'Recursively collect all image file paths, sizes, and shapes in folder.',
#         'img_collect_ret': 'Return: [{path, size, shape}...]',
#         'img_found': 'Found {count} image files',
#         'img_meta': 'Successfully read metadata for {count} images',
#         'img_size_fail': 'Failed to read image size, error: {err}',
#         'img_size_fail2': 'Failed to read image size: {path}, error: {err}',
#         'file_size_fail': 'Failed to read file size: {path}, error: {err}',
#         'vid_collect': 'Recursively collect all video file paths, sizes, and names in folder.',
#         'vid_collect_ret': 'Return: [{path, size, name}...]',
#         'vid_found': 'Found {count} video files',
#         'vid_meta': 'Successfully read metadata for {count} videos',
#         'vid_info_fail': 'Failed to read video file info: {path}, error: {err}',
#         'hash_fail': 'Hash calculation failed: {path}, error: {err}',
#         'dedup_desc': 'Deduplication main flow: find duplicate images/videos and output report.',
#         'dry_run': '[DRY-RUN] Readonly mode, no actual file operation.',
#         'group_count': 'Groups to further compare: {count}',
#         'group_processing': 'Processing group: size={size}, shape={shape}, count={count}',
#         'dedup_done': 'Deduplication done, report saved to: {path}',
#         'supp_desc': 'Supplement main flow: supplement images/videos and output report.',
#         'main_img_count': 'Main folder images: {main}, supplement folder images: {supp}',
#         'main_hash_done': 'Main folder hash set built, unique images: {count}',
#         'supp_dir': 'supplement_{timestamp}',
#         'supp_hash_fail': 'Supplement image hash failed, skip: {path}',
#         'supp_exists': 'Already exists, not supplemented: {path}',
#         'disk_space': 'Supplement images total size: {size:.2f} MB, target disk free: {free:.2f} MB',
#         'disk_full': 'Disk space not enough, abort!',
#         'disk_full_exc': 'Disk space not enough, cannot complete supplement!',
#         'dry_run_supp': '[DRY-RUN] Simulate supplement: {src} -> {dst}',
#         'supp_copy': 'Supplement image: {src} -> {dst}',
#         'supp_copy_fail': 'Copy image failed: {src} -> {dst}, error: {err}',
#         'vid_supp_exists': 'Video already exists, not supplemented: {path}',
#         'dry_run_vid': '[DRY-RUN] Simulate supplement video: {src} -> {dst}',
#         'vid_supp_copy': 'Supplement video: {src} -> {dst}',
#         'vid_supp_copy_fail': 'Copy video failed: {src} -> {dst}, error: {err}',
#         'dedup_img_group': 'Duplicate Image Group {group_id} (hash: {h}):',
#         'dedup_vid_header': '\nDuplicate Videos:\n',
#         'dedup_vid_group': 'Duplicate Video Group {idx}:',
#         'supp_report': 'Supplement Report',
#         'supp_img_success': 'Supplemented {count} images to: {dir}',
#         'supp_img_exists': 'Already exists (not supplemented) {count} images:',
#         'supp_vid_success': 'Supplemented {count} videos to: {dir}',
#         'supp_vid_exists': 'Already exists (not supplemented) {count} videos:',
#         'en_dash': ':',
#         'scanning_images': 'Scanning image files...',
#         'images_found': 'Found {count} image files',
#         'scanning_videos': 'Scanning video files...',
#         'videos_found': 'Found {count} video files',
#         'analyzing_duplicates': 'Analyzing duplicates, {count} groups to process...',
#         'analysis_complete': 'Analysis complete',
#     }
# }
# def get_text(lang, key, **kwargs):
#     s = TEXTS.get(lang, TEXTS['zh']).get(key, key)
#     return s.format(**kwargs) if kwargs else s
def get_optimal_chunk_size(file_size):
    """
    根据文件大小计算最优的读取块大小
    """
    if file_size < 1024 * 1024:  # < 1MB
        return 8192  # 8KB
    elif file_size < 10 * 1024 * 1024:  # < 10MB
        return 65536  # 64KB
    elif file_size < 100 * 1024 * 1024:  # < 100MB
        return 262144  # 256KB
    else:  # >= 100MB
        return 1048576  # 1MB
    
def get_image_hash(image_path, method='md5', max_size=500*1024*1024):
    """
    改进的哈希计算函数，优化大文件处理
    """
    try:
        normalized_path = normalize_path(image_path)
        
        if not safe_file_exists(normalized_path):
            logger.warning(f"文件不存在: {image_path}")
            return None
        
        file_size = safe_file_size(normalized_path)
        if file_size == 0:
            logger.warning(f"文件为空: {image_path}")
            return None
        
        if file_size > max_size:
            logger.warning(f"文件过大，跳过哈希计算: {image_path} ({file_size/1024/1024:.1f}MB)")
            return None
        
        # 根据文件大小选择最优块大小
        chunk_size = get_optimal_chunk_size(file_size)
        
        # 选择哈希算法
        if method == 'md5':
            hash_func = hashlib.md5()
        elif method == 'sha1':
            hash_func = hashlib.sha1()
        elif method == 'sha256':
            hash_func = hashlib.sha256()
        else:
            hash_func = hashlib.md5()
        
        bytes_processed = 0
        with open(normalized_path, 'rb') as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                hash_func.update(chunk)
                bytes_processed += len(chunk)
                
                # 对于超大文件，可以考虑只计算部分内容的哈希
                if file_size > 200 * 1024 * 1024 and bytes_processed > 50 * 1024 * 1024:
                    logger.info(f"大文件采用部分哈希: {image_path}")
                    break
        
        return hash_func.hexdigest()
        
    except (IOError, OSError) as e:
        logger.error(f"读取文件失败: {image_path}, 错误: {e}")
        return None
    except MemoryError:
        logger.error(f"内存不足，无法处理文件: {image_path}")
        return None
    except Exception as e:
        logger.error(f"哈希计算时发生未知错误: {image_path}, 错误: {e}")
        return None
def get_image_size(image_path):
    """优化的图片尺寸获取函数，处理大文件"""
    try:
        normalized_path = normalize_path(image_path)
        
        if not safe_file_exists(normalized_path):
            return None
        
        # 检查文件大小，避免加载超大文件
        file_size = safe_file_size(normalized_path)
        if file_size > 200 * 1024 * 1024:  # 200MB
            logger.warning(f"图片文件过大，跳过尺寸检测: {image_path} ({file_size/1024/1024:.1f}MB)")
            return None
            
        with Image.open(normalized_path) as img:
            size = img.size
            # 验证尺寸合理性
            if size[0] <= 0 or size[1] <= 0 or size[0] > 100000 or size[1] > 100000:
                logger.warning(f"图片尺寸异常: {image_path}, 尺寸: {size}")
                return None
            return size
            
    except (IOError, OSError, UnidentifiedImageError):
        return None
    except MemoryError:
        logger.error(f"内存不足，无法读取图片尺寸: {image_path}")
        return None
    except Exception as e:
        logger.warning(f"读取图片尺寸时发生未知错误: {image_path}, 错误: {e}")
        return None

def check_file_content_samples(files_info):
    """
    对小文件进行内容采样比较，检测哈希冲突
    """
    if len(files_info) < 2:
        return False
    
    try:
        # 读取第一个文件作为基准
        base_file = files_info[0]['path']
        if not safe_file_exists(base_file):
            return False
            
        with open(normalize_path(base_file), 'rb') as f:
            base_content = f.read()
        
        # 比较其他文件
        for file_info in files_info[1:]:
            file_path = file_info['path']
            if not safe_file_exists(file_path):
                continue
                
            try:
                with open(normalize_path(file_path), 'rb') as f:
                    content = f.read()
                
                if content != base_content:
                    return True  # 发现内容不同，确认哈希冲突
                    
            except Exception as e:
                logger.warning(f"读取文件用于冲突检测失败: {file_path}, 错误: {e}")
                continue
        
        return False  # 所有文件内容相同
        
    except Exception as e:
        logger.warning(f"哈希冲突检测失败: {e}")
        return False
def detect_potential_hash_collision(file_groups, sample_check=True):
    """
    检测潜在的哈希冲突
    sample_check: 是否对小文件进行内容采样比较
    """
    collision_suspects = []
    
    for group_files in file_groups:
        if len(group_files) < 2:
            continue
            
        # 按文件大小分组，大小不同的文件肯定不是重复的
        size_groups = {}
        for file_info in group_files:
            file_size = file_info.get('size', 0)
            if file_size not in size_groups:
                size_groups[file_size] = []
            size_groups[file_size].append(file_info)
        
        # 检查每个大小组
        for size, files_of_same_size in size_groups.items():
            if len(files_of_same_size) < 2:
                continue
                
            # 如果同一哈希值下有多个不同大小的文件，这很可能是哈希冲突
            if len(size_groups) > 1:
                logger.warning(f"发现可疑哈希冲突：相同哈希但不同文件大小")
                collision_suspects.extend(group_files)
                continue
            
            # 对于小文件（<5MB），进行内容采样比较
            if sample_check and size < 5 * 1024 * 1024 and len(files_of_same_size) > 1:
                if check_file_content_samples(files_of_same_size):
                    logger.warning(f"发现确认的哈希冲突：{[f['path'] for f in files_of_same_size]}")
                    collision_suspects.extend(files_of_same_size)
    
    return collision_suspects
def detect_supplement_hash_collision(added_images, skipped_images, main_hashes):
    """
    检测增补模式中的哈希冲突
    主要检测补充文件夹内部的哈希冲突
    """
    collision_suspects = []
    
    # 收集所有补充文件按哈希分组
    hash_groups = {}
    all_supplement_files = added_images + skipped_images
    
    for file_info in all_supplement_files:
        file_hash = file_info.get('hash')
        if file_hash:
            hash_groups.setdefault(file_hash, []).append(file_info)
    
    # 找出有多个文件的哈希组
    potential_collision_groups = []
    for hash_value, files in hash_groups.items():
        if len(files) > 1:
            potential_collision_groups.append(files)
    
    # 复用之前定义的检测函数
    if potential_collision_groups:
        collision_suspects = detect_potential_hash_collision(potential_collision_groups, sample_check=True)
    
    return collision_suspects

def safe_multiprocess_operation(func, items, max_workers=None):
    """
    安全的多进程操作，包含完善的错误处理和资源管理
    """
    if not items:
        return []
    
    if max_workers is None:
        max_workers = min(cpu_count(), len(items), 8)  # 限制最大进程数避免资源过度消耗
    
    # 如果任务数量很少，直接单进程处理
    if len(items) < max_workers * 2:
        logger.info("任务数量较少，使用单进程处理")
        return [func(item) for item in items]
    
    pool = None
    try:
        logger.info(f"使用 {max_workers} 个进程处理 {len(items)} 个任务")
        
        # 创建进程池
        pool = Pool(max_workers)
        
        # 使用map_async以便可以设置超时和更好的错误处理
        result = pool.map_async(func, items)
        
        # 等待结果，设置一个合理的超时时间
        timeout = max(300, len(items) * 2)  # 最少5分钟，或每个任务2秒
        results = result.get(timeout=timeout)
        
        return results
        
    except KeyboardInterrupt:
        logger.warning("用户中断了多进程操作")
        if pool:
            pool.terminate()
            pool.join()
        raise
    except Exception as e:
        logger.error(f"多进程操作失败: {e}")
        if pool:
            pool.terminate()
            pool.join()
        
        # 回退到单进程处理
        logger.info("回退到单进程处理")
        results = []
        for i, item in enumerate(items):
            try:
                result = func(item)
                results.append(result)
                
                # 每处理100个项目报告一次进度
                if (i + 1) % 100 == 0:
                    logger.info(f"单进程处理进度: {i+1}/{len(items)}")
                    
            except Exception as item_error:
                logger.error(f"处理项目失败: {item}, 错误: {item_error}")
                results.append(None)
        
        return results
    finally:
        # 确保进程池被正确关闭
        if pool:
            try:
                pool.close()
                pool.join()
            except Exception as e:
                logger.error(f"关闭进程池时发生错误: {e}")

def normalize_path(path):
    """
    标准化路径处理，解决Unicode等编码问题
    """
    try:
        # 首先尝试转换为字符串（处理Path对象）
        if isinstance(path, Path):
            path = str(path)
        # 处理Unicode路径
        if isinstance(path, bytes):
            # 如果是字节串，尝试解码
            try:
                path = path.decode('utf-8')
            except UnicodeDecodeError:
                path = path.decode('gbk', errors='ignore')  # Windows中文系统备选
        
        # 标准化路径
        normalized = os.path.normpath(os.path.abspath(path))
        
        # 在Windows上处理长路径问题
        if sys.platform == 'win32' and len(normalized) > 260:
            if not normalized.startswith('\\\\?\\'):
                normalized = '\\\\?\\' + normalized
        
        return normalized
        
    except (UnicodeError, TypeError, OSError) as e:
        logger.warning(f"路径标准化失败: {path}, 错误: {e}")
        # 回退到原始路径
        return str(path) if path else ''

def safe_file_exists(path):
    """安全的文件存在性检查，处理Unicode路径"""
    try:
        normalized_path = normalize_path(path)
        return os.path.exists(normalized_path)
    except (OSError, UnicodeError, TypeError):
        # 如果标准化失败，尝试直接检查原路径
        try:
            return os.path.exists(path)
        except:
            return False
def safe_file_size(path):
    """安全的文件大小获取，处理Unicode路径"""
    try:
        normalized_path = normalize_path(path)
        return os.path.getsize(normalized_path)
    except (OSError, UnicodeError, TypeError):
        try:
            return os.path.getsize(path)
        except:
            return 0
def safe_walk_directory(folder):
    """安全的目录遍历，处理Unicode文件名"""
    files_found = []
    folder = normalize_path(folder)
    try:
        for root, dirs, files in os.walk(folder):
            # 处理文件名编码问题
            for file in files:
                try:
                    file_path = os.path.join(root, file)
                    # 验证路径是否可用
                    if safe_file_exists(file_path):
                        files_found.append(normalize_path(file_path))
                except (UnicodeError, OSError) as e:
                    logger.warning(f"跳过有问题的文件: {file}, 错误: {e}")
                    continue
    except (OSError, UnicodeError) as e:
        logger.error(f"遍历目录失败: {folder}, 错误: {e}")
    
    return files_found

# 添加信号处理器来优雅地处理中断
def signal_handler(signum, frame):
    logger.info("接收到中断信号，正在清理资源...")
    sys.exit(0)

# 在模块加载时注册信号处理器
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def collect_images(folder, exts=None):
    """
    递归收集文件夹下所有图片文件路径、大小、尺寸。
    返回：[{path, size, shape}...]
    使用改进的多进程处理来收集图片
    使用安全路径处理的图片收集函数
    """
    if exts is None:
        exts = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.avif'}
    # 使用安全的目录遍历
    all_files = safe_walk_directory(folder)
    # 过滤图片文件
    image_files = []
    for file_path in all_files:
        try:
            ext = os.path.splitext(file_path)[1].lower()
            if ext in exts:
                image_files.append(file_path)
        except Exception as e:
            logger.warning(f"处理文件扩展名失败: {file_path}, 错误: {e}")
            continue
    
    logger.info(f"共发现图片文件 {len(image_files)} 张")

    # 使用安全的多进程操作
    sizes = safe_multiprocess_operation(get_image_size, image_files)
    
    image_meta = []
    for path, shape in zip(image_files, sizes):
        try:
            size = safe_file_size(path)
            if size > 0:  # 只包含有效大小的文件
                image_meta.append({'path': path, 'size': size, 'shape': shape})
        except Exception as e:
            logger.warning(f"处理图片元数据失败: {path}, 错误: {e}")
            continue
    
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

def is_valid_image(image_path):
    """
    改进的图片验证方法，使用load()代替verify()
    """
    try:
        with Image.open(image_path) as img:
            img.load()  # 使用load()代替verify()，不会破坏Image对象
            # 检查图片基本属性
            if img.size[0] <= 0 or img.size[1] <= 0:
                return False
            return True
    except (IOError, OSError, UnidentifiedImageError):
        return False
    except Exception as e:
        logger.warning(f"图片验证时发生未知错误: {image_path}, 错误: {e}")
        return False
    
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
        log_emit(tr('dry_run'))
    
    # 收集图片信息
    log_emit(tr('scanning_images'))
    image_meta = collect_images(folder)
    total_images_scanned = len(image_meta)
    log_emit(tr('images_found', count=total_images_scanned))
    progress_emit(0.1)
    
    # 按大小和尺寸分组
    group_map = {}
    for meta in image_meta:
        if meta['shape'] is None:  # 跳过无法读取尺寸的图片
            continue
        key = (meta['size'], meta['shape'])
        group_map.setdefault(key, []).append(meta)
    
    groups_to_process = sum(1 for files in group_map.values() if len(files) >= 2)
    if groups_to_process > 0:
        log_emit(tr('analyzing_duplicates', count=groups_to_process))
    progress_emit(0.2)
    
    # 计算哈希值并找出重复组
    img_groups = []
    processed_groups = 0
    
    for idx, (key, files) in enumerate(group_map.items()):
        if len(files) < 2:
            processed_groups += 1
            continue
            
        file_details = []
        for meta in files:
            try:
                file_hash = get_image_hash(meta['path'], hash_method)
                if file_hash is None:
                    corrupt_files.append(meta['path'])
                    continue
                    
                file_info = {
                    'path': meta['path'],
                    'size': meta['size'],
                    'shape': meta['shape'],
                    'hash': file_hash,
                    'mtime': os.path.getmtime(meta['path']) if os.path.exists(meta['path']) else 0,
                    'is_corrupt': False
                }
                
                # 使用改进的图片验证方法
                if not is_valid_image(meta['path']):
                    file_info['is_corrupt'] = True
                    corrupt_files.append(meta['path'])
                
                file_details.append(file_info)
                
            except Exception as e:
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
        # progress_emit(progress)
    
    # 🔥 在这里添加哈希冲突检测 🔥
    if img_groups:  # 只有当有重复组时才检测
        log_emit("正在检测潜在的哈希冲突...")
        collision_suspects = detect_potential_hash_collision(img_groups)
        if collision_suspects:
            logger.warning(f"发现 {len(collision_suspects)} 个可疑的哈希冲突文件")
            log_emit(f"⚠️ 发现 {len(collision_suspects)} 个可疑的哈希冲突文件，建议手动检查")

    progress_emit(0.7)
    
    # 处理视频文件
    log_emit(tr('scanning_videos'))
    video_meta = collect_videos(folder)
    total_videos_scanned = len(video_meta)
    log_emit(tr('videos_found', count=total_videos_scanned))
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
        'total_images_scanned': total_images_scanned,
        'total_videos_scanned': total_videos_scanned,
        'corrupt_files_count': len(corrupt_files),
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
    
    log_emit(tr('analysis_complete'))
    progress_emit(1.0)
    
    return {
        'img_groups': img_groups,
        'vid_groups': vid_groups,
        'stats': stats,
        'log': log,
        'progress': 1.0,
        'corrupt_files': corrupt_files
    }

def supplement_duplicates(main_folder, supplement_folder, report_path, hash_method='md5', dry_run=False, log_callback=None, progress_callback=None):
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
        log_emit(tr('dry_run'))
    
    # 扫描主文件夹
    main_meta = collect_images(main_folder)
    progress_emit(0.2)
    
    # 扫描补充文件夹  
    supplement_meta = collect_images(supplement_folder)
    progress_emit(0.3)
    
    log_emit(tr('main_img_count', main=len(main_meta), supp=len(supplement_meta)))
    
    # 构建主文件夹哈希集合
    main_hashes = set()
    for idx, meta in enumerate(main_meta):
        try:
            file_hash = get_image_hash(meta['path'], hash_method)
            if file_hash:
                main_hashes.add(file_hash)
        except Exception as e:
            log_emit(tr('hash_fail', path=meta['path'], err=e))
        
        # 🔥 优化进度更新：确保即使文件少也有进度反馈
        if len(main_meta) > 0:
            progress = 0.3 + 0.3 * ((idx + 1) / len(main_meta))
            progress_emit(progress)
    
    log_emit(tr('main_hash_done', count=len(main_hashes)))
    progress_emit(0.6)
    
    # 处理补充文件夹的图片
    added_images = []
    skipped_images = []
    
    timestamp = time.strftime('%Y%m%d_%H%M%S')
    supplement_dir = os.path.join(main_folder, tr('supp_dir', timestamp=timestamp))
    
    for idx, meta in enumerate(supplement_meta):
        try:
            file_hash = get_image_hash(meta['path'], hash_method)
            if not file_hash:
                log_emit(tr('supp_hash_fail', path=meta['path']))
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
                log_emit(tr('supp_exists', path=meta['path']))
            else:
                added_images.append(file_info)
        
        except Exception as e:
            log_emit(tr('hash_fail', path=meta['path'], err=e))
            corrupt_files.append(meta['path'])
        
        # 🔥 优化进度更新：每个文件都更新进度
        if len(supplement_meta) > 0:
            progress = 0.6 + 0.15 * ((idx + 1) / len(supplement_meta))  # 给后续步骤留出进度空间
            # progress_emit(progress)
    
    # 🔥 在这里添加增补模式的哈希冲突检测 🔥
    log_emit("正在检测补充文件的哈希冲突...")
    progress_emit(0.75)  # 补充文件处理完成
    collision_suspects = detect_supplement_hash_collision(added_images, skipped_images, main_hashes)
    if collision_suspects:
        logger.warning(f"在补充文件中发现 {len(collision_suspects)} 个可疑的哈希冲突文件")
        log_emit(f"⚠️ 在补充文件中发现 {len(collision_suspects)} 个可疑的哈希冲突文件，建议手动检查")

    progress_emit(0.80)
    
    # 处理视频文件
    log_emit("正在处理视频文件...")
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
            log_emit(tr('vid_supp_exists', path=meta['path']))
        else:
            added_videos.append(video_info)
        # 🔥 为视频处理添加进度更新
        if len(supplement_videos) > 0:
            progress = 0.80 + 0.1 * ((idx + 1) / len(supplement_videos))
            # progress_emit(progress)

    progress_emit(0.90)  # 视频处理完成
    
    # 统计信息
    total_add_size = sum(img['size'] for img in added_images) + sum(vid['size'] for vid in added_videos)
    # 🔥 报告写入阶段
    log_emit("正在生成报告...")
    progress_emit(0.95)

    stats = {
        'main_scanned': len(main_meta) + len(main_videos),  # 🔥 加上视频数量
        'supplement_scanned': len(supplement_meta) + len(supplement_videos),  # 🔥 加上视频数量
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
    _write_supplement_report(report_path, added_images, skipped_images, added_videos, skipped_videos, target_dirs, stats, dry_run, corrupt_files)
    
    log_emit(tr('dedup_done', path=report_path))
    progress_emit(1.0)  # 最终完成
    
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

def _write_supplement_report(report_path, added_images, skipped_images, added_videos, skipped_videos, target_dirs, stats, dry_run, corrupt_files=None):
    """写入增补报告文件"""
    with open(report_path, 'w', encoding='utf-8') as f:
        if dry_run:
            f.write(tr('dry_run') + '\n\n')
        f.write(tr('supp_report') + '\n\n')
        f.write(tr('supp_img_success', count=len(added_images), dir=target_dirs['supplement_dir']) + '\n')
        
        for img in added_images:
            f.write(f"    {img['path']}\n")
        
        f.write(tr('supp_img_exists', count=len(skipped_images)) + '\n')
        for img in skipped_images:
            f.write(f"    {img['path']}\n")
        
        f.write(tr('supp_vid_success', count=len(added_videos), dir=target_dirs['mp4_dir']) + '\n')
        for vid in added_videos:
            f.write(f"    {vid['path']}\n")
        
        f.write(tr('supp_vid_exists', count=len(skipped_videos)) + '\n')
        for vid in skipped_videos:
            f.write(f"    {vid['path']}\n")
        
                # 🔥 添加损坏文件详细信息
        if corrupt_files and len(corrupt_files) > 0:
            f.write(f"\n❌ 发现 {len(corrupt_files)} 个损坏或无法处理的文件：\n")
            f.write("=" * 60 + "\n")
            for idx, corrupt_file in enumerate(corrupt_files, 1):
                f.write(f"{idx:3d}. {corrupt_file}\n")
            f.write("\n建议：请检查这些文件是否确实损坏，如果确认损坏请删除或修复。\n\n")