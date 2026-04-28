from fastapi import APIRouter, Form, File, UploadFile, Header, HTTPException, Query, Request
from app.database import db
import json
import os
import shutil
from typing import List, Optional
from datetime import datetime  # 处理时间戳
from app.utils.security import verify_user, get_valid_cursor
import base64
import asyncio
import aiohttp
import time
from dotenv import load_dotenv
# 仅导入loguru（使用项目统一配置）
from loguru import logger

# 移除了hashlib导入（因为不再使用MD5哈希）
# import hashlib  # 新增：用于生成hash

load_dotenv()

router = APIRouter()
ALLOWED_AUDIO_EXTENSIONS = {".wav"}  # 音频允许的后缀（修复NameError）
MAX_AUDIO_SIZE = 50 * 1024 * 1024    # 50MB 音频大小限制
# 辅助函数：仅读取环境变量，不影响原格式
def get_env(key: str) -> str:
    return os.getenv(key, "")

# 新增：通用文本截断函数（仅用于日志输出）
def truncate_log_text(text: str, max_len: int = 50) -> str:
    """截断日志文本，避免超长输出"""
    if text and isinstance(text, str) and len(text) > max_len:
        return text[:max_len] + "..."
    return text or ""


def sanitize_path_component(value: str, fallback: str = "unknown") -> str:
    text = str(value or fallback)
    invalid_chars = '<>:"/\\|?*'
    sanitized = "".join("_" if char in invalid_chars else char for char in text)
    sanitized = sanitized.strip().strip(".")
    return sanitized or fallback


def get_username_by_jabobo_id(jabobo_id: str):
    """根据设备ID查询对应的用户名，适配联合主键"""
    logger.debug(f"[用户查询] 开始通过设备ID查询用户名 - jabobo_id：{jabobo_id}")
    
    # 获取有效游标
    cursor = get_valid_cursor()
    
    # 执行查询（核心：通过jabobo_id查username）
    query_sql = "SELECT username FROM user_personas WHERE jabobo_id = %s LIMIT 1"
    logger.debug(f"[用户查询] 执行SQL：{query_sql} | 参数：({jabobo_id})")
    cursor.execute(query_sql, (jabobo_id,))
    result = cursor.fetchone()
    
    # 校验查询结果
    if not result or not result.get("username"):
        logger.error(f"[用户查询] 失败 - 未找到设备ID {jabobo_id} 对应的用户")
        raise HTTPException(status_code=404, detail=f"未找到设备ID {jabobo_id} 对应的用户记录")
    
    username = result.get("username")
    logger.info(f"[用户查询] 成功 - 设备ID {jabobo_id} 对应用户名：{username}")
    return username

# 新增辅助函数：生成speaker_id（核心修改：去掉hash，直接拼接）
def generate_speaker_id(jabobo_id: str, voiceprint_name: str) -> str:
    """
    通过jabobo_id + 声纹名称生成唯一的speaker_id
    直接拼接字符串，不再使用MD5 hash
    """
    # 直接拼接字符串，替代原有的MD5哈希逻辑
    speaker_id = f"{jabobo_id}_{voiceprint_name}"
    return speaker_id

# 新增辅助函数：查询并校验声纹数量
def check_voiceprint_limit(jabobo_id: str, max_limit: int = 10) -> List[dict]:
    """
    检查指定jabobo_id的声纹数量是否超过限制
    返回当前声纹列表，若超过限制则抛出异常
    """
    cursor = get_valid_cursor()
    
    # 查询该设备的声纹记录
    query_sql = "SELECT voiceprint_list FROM user_personas WHERE jabobo_id = %s LIMIT 1"
    cursor.execute(query_sql, (jabobo_id,))
    result = cursor.fetchone()
    
    # 解析声纹列表
    voiceprint_list = []
    if result and result.get("voiceprint_list") is not None:
        try:
            voiceprint_list = json.loads(result["voiceprint_list"])
            logger.debug(f"[声纹校验] 解析现有声纹列表成功 - 列表长度：{len(voiceprint_list)}")
        except json.JSONDecodeError:
            logger.warning(f"[声纹校验] 解析声纹列表JSON失败，重置为空列表")
            voiceprint_list = []
    
    # 检查数量限制
    if len(voiceprint_list) >= max_limit:
        raise HTTPException(
            status_code=400, 
            detail=f"该设备ID({jabobo_id})的声纹数量已达上限({max_limit}个)，无法新增"
        )
    
    return voiceprint_list

# 新增辅助函数：保存声纹记录到数据库
def save_voiceprint_record(jabobo_id: str, voiceprint_name: str, speaker_id: str, file_path: str):
    """
    将声纹名称、speaker_id、文件路径保存到数据库
    """
    # 先获取当前声纹列表并检查限制
    voiceprint_list = check_voiceprint_limit(jabobo_id)
    
    # 构建新的声纹记录
    new_voiceprint = {
        "voiceprint_name": voiceprint_name,
        "speaker_id": speaker_id,
        "file_path": file_path,
        "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "create_timestamp": datetime.now().timestamp()
    }
    
    # 检查是否已存在同名声纹
    for item in voiceprint_list:
        if item.get("voiceprint_name") == voiceprint_name:
            raise HTTPException(
                status_code=400,
                detail=f"该设备ID({jabobo_id})已存在名为{voiceprint_name}的声纹，请更换名称"
            )
    
    # 添加新记录
    voiceprint_list.append(new_voiceprint)
    
    # 更新数据库
    voiceprint_json = json.dumps(voiceprint_list, ensure_ascii=False)
    upsert_sql = """
        INSERT INTO user_personas (jabobo_id, voiceprint_list)
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE voiceprint_list = VALUES(voiceprint_list)
    """
    cursor = get_valid_cursor()
    cursor.execute(upsert_sql, (jabobo_id, voiceprint_json))
    db.connection.commit()
    
    logger.info(f"[声纹保存] 成功 - jabobo_id：{jabobo_id} | 声纹名称：{voiceprint_name} | speaker_id：{speaker_id}")
    return new_voiceprint

# 配置常量 - 音频文件相关
ALLOWED_EXTENSIONS = {".mp3", ".wav", ".ogg", ".flac", ".m4a"}  # 常见音频格式
MAX_FILE_SIZE = 100 * 1024 * 1024  # 增大到100MB（音频文件通常更大）
BASE_DATA_DIR = "./data"  # 音频专用存储目录

@router.post("/agent/chat-history/report")
async def report_chat_history(request: Request):
    logger.info("开始处理聊天历史报告请求")
    
    try:
        # 获取JSON请求体
        body = await request.json()
        # 精简请求数据日志，只打印关键字段
        req_summary = {
            "macAddress": body.get("macAddress"),
            "sessionId": body.get("sessionId"),
            "chatType": body.get("chatType"),
            "has_audio": bool(body.get("audioBase64"))
        }
        logger.debug(f"[请求信息] 收到请求数据: {req_summary}")
        
        # 提取请求参数
        macAddress = body.get("macAddress")
        sessionId = body.get("sessionId")
        chatType = body.get("chatType")
        content = body.get("content")
        reportTime = body.get("reportTime")
        audioBase64 = body.get("audioBase64")
        
        logger.debug(f"[请求信息] sessionId: {sessionId} | chatType: {chatType} | macAddress: {macAddress}")
        logger.debug(f"[请求信息] content: {truncate_log_text(content)}")
        logger.debug(f"[请求信息] reportTime: {reportTime}")
        
        # 通过macAddress或sessionId获取设备ID和用户名
        jabobo_id = macAddress if macAddress else sessionId
        
        # 通过设备ID查询对应的用户名
        username = get_username_by_jabobo_id(jabobo_id)
        safe_username = sanitize_path_component(username, "unknown_user")
        safe_jabobo_id = sanitize_path_component(jabobo_id, "unknown_device")
        
        # 如果有音频数据，进行处理
        if audioBase64:
            logger.info("[音频处理] 检测到base64音频数据，开始处理")
            
            # 解码base64音频数据
            try:
                # 解码base64字符串
                audio_bytes = base64.b64decode(audioBase64)
                logger.debug(f"[音频处理] 音频数据解码成功 - 原始大小: {len(audio_bytes)} 字节")
            except Exception as e:
                logger.error(f"[音频处理] 音频数据解码失败: {str(e)}")
                raise HTTPException(status_code=400, detail="音频数据base64解码失败")
            
            # 创建音频文件存储目录
            target_dir = os.path.join(BASE_DATA_DIR, safe_username, safe_jabobo_id, "audio_files")
            logger.debug(f"[目录创建] 音频目标目录：{target_dir}")
            os.makedirs(target_dir, exist_ok=True)
            
             # 解析content JSON，提取说话人信息
            # 解析content JSON，提取说话人信息
            try:
                content_data = json.loads(content)
                audio_content = content_data.get("content", "")
                speaker = content_data.get("speaker", "未知说话人")
                
                # 直接原位截断rag_error.response_text，限制≤100字符，不新增函数
                if "rag_error" in content_data and isinstance(content_data["rag_error"], dict):
                    resp_text = content_data["rag_error"].get("response_text", "")
                    if isinstance(resp_text, str) and len(resp_text) > 100:
                        # 直接截断，不调用任何外部函数
                        content_data["rag_error"]["response_text"] = resp_text[:100] + "..."
            except json.JSONDecodeError:
                logger.warning(f"[数据解析] content不是有效JSON格式，使用原始内容")
                audio_content = content
                speaker = "未知说话人"
            
            # 生成音频文件名（使用时间戳和sessionId确保唯一性）
            timestamp = datetime.fromtimestamp(reportTime).strftime("%Y%m%d_%H%M%S")
            safe_session_id = sanitize_path_component(sessionId, "unknown_session")
            safe_audio_content = sanitize_path_component(truncate_log_text(audio_content, 10), "audio")
            audio_filename = f"audio_{safe_session_id}_{timestamp}_{safe_audio_content}.wav"
            file_path = os.path.join(target_dir, audio_filename)
            file_path = os.path.abspath(file_path)
            
            logger.debug(f"[文件存储] 音频目标文件路径：{file_path}")
            
            try:
                # 数据库操作 - 获取现有音频记录
                logger.info("[数据库操作] 开始处理音频文件数据库逻辑")
                if not db.connect():
                    logger.error(f"[数据库操作] 失败 - 数据库连接失败")
                    raise HTTPException(status_code=500, detail="数据库连接失败")
                
                # 获取有效游标
                cursor = get_valid_cursor()
                
                # 查询现有音频记录
                query_sql = "SELECT audio_status FROM user_personas WHERE username = %s AND jabobo_id = %s"
                logger.debug(f"[数据库操作] 执行查询SQL：{query_sql} | 参数：({username}, {jabobo_id})")
                cursor.execute(query_sql, (username, jabobo_id))
                result = cursor.fetchone()
                
                # 解析现有音频路径列表
                if result and result.get("audio_status") is not None:
                    try:
                        audio_path_list = json.loads(result["audio_status"])
                        logger.debug(f"[数据库操作] 解析现有音频列表成功 - 列表长度：{len(audio_path_list)}")
                    except json.JSONDecodeError:
                        logger.warning(f"[数据库操作] 解析现有音频列表失败 - 重置为空列表")
                        audio_path_list = []
                else:
                    logger.debug(f"[数据库操作] 无现有音频记录 - 初始化空列表")
                    audio_path_list = []
                
                # 检查音频数量，如果超过10个，则删除最早的音频文件
                if len(audio_path_list) >= 10:
                    logger.info(f"[音频管理] 音频数量已达上限，开始删除最早的音频文件")
                    
                    # 按时间戳排序，找出最早的音频文件
                    sorted_audio_list = sorted(audio_path_list, key=lambda x: x.get('upload_timestamp', 0))
                    oldest_audio = sorted_audio_list[0]  # 最早的音频
                    
                    logger.debug(f"[音频管理] 确定最早的音频文件：{oldest_audio.get('file_path')}")
                    
                    # 删除最早的音频文件
                    oldest_file_path = oldest_audio.get('file_path')
                    if oldest_file_path and os.path.exists(oldest_file_path):
                        try:
                            os.remove(oldest_file_path)
                            logger.info(f"[音频管理] 最早的音频文件已删除：{oldest_file_path}")
                        except Exception as delete_e:
                            logger.error(f"[音频管理] 删除最早的音频文件失败：{str(delete_e)}")
                    
                    # 从列表中移除最早的音频记录
                    audio_path_list.remove(oldest_audio)
                    logger.debug(f"[音频管理] 最早的音频记录已从列表中移除")
                
                # 保存音频文件
                with open(file_path, "wb") as audio_file:
                    audio_file.write(audio_bytes)
                logger.debug(f"[文件存储] 音频文件写入完成 - 实际文件大小：{os.path.getsize(file_path)} 字节")
                
                # 获取文件信息
                file_size = os.path.getsize(file_path)
                file_size_mb = round(file_size / 1024 / 1024, 2)
                file_ext = os.path.splitext(audio_filename)[1][1:]  # 获取文件扩展名（不带点）
                
                # 构建音频文件信息
                audio_info = {
                    "file_path": file_path,
                    "file_name": audio_filename,
                    "file_size_bytes": file_size,
                    "file_size_mb": file_size_mb,
                    "audio_format": file_ext,
                    "audio_content": audio_content,
                    "speaker": speaker,
                    "upload_time": datetime.fromtimestamp(reportTime).strftime("%Y-%m-%d %H:%M:%S"),
                    "upload_timestamp": reportTime,
                    "sessionId": sessionId,
                    "chatType": chatType
                }
                
                # 将新的音频信息添加到列表
                audio_path_list.append(audio_info)
                logger.debug(f"[数据库操作] 音频文件信息追加完成 - 新列表长度：{len(audio_path_list)}")
                
                # 更新数据库
                audio_status_json = json.dumps(audio_path_list, ensure_ascii=False)
                upsert_sql = """
                    INSERT INTO user_personas (username, jabobo_id, audio_status)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE audio_status = VALUES(audio_status)
                """
                logger.debug(f"[数据库操作] 执行更新SQL：{upsert_sql} | 参数：({username}, {jabobo_id}, {truncate_log_text(audio_status_json, 100)})")
                cursor.execute(upsert_sql, (username, jabobo_id, audio_status_json))
                db.connection.commit()
                
            except Exception as e:
                logger.error(f"[音频存储异常] 失败 - 异常信息：{str(e)}", exc_info=True)
                if db.connection:
                    try:
                        logger.info(f"[数据库回滚] 开始回滚事务")
                        db.connection.rollback()
                        logger.info(f"[数据库回滚] 回滚完成")
                    except Exception as rollback_e:
                        logger.error(f"[数据库回滚] 失败 - 异常：{str(rollback_e)}")
                raise HTTPException(status_code=500, detail=f"音频文件保存异常: {str(e)}")
        else:
            logger.info(f"[音频处理] 未检测到音频数据，仅处理文本内容")
            # 如果没有音频数据，只处理文本内容
            # 构建仅文本的记录信息
            text_only_info = {
                "file_path": None,
                "file_name": None,
                "audio_content": content,
                "upload_time": datetime.fromtimestamp(reportTime).strftime("%Y-%m-%d %H:%M:%S"),
                "upload_timestamp": reportTime,
                "sessionId": sessionId,
                "chatType": chatType,
                "has_audio": False
            }
        
        logger.info(f"[处理完成] 聊天历史报告处理成功")
        
        return {
            "success": True,
            "message": "聊天历史报告处理成功",
            "sessionId": sessionId
        }
    
    except HTTPException:
        # 重新抛出已定义的HTTP异常
        raise
    except Exception as e:
        logger.error(f"[请求异常] 失败 - 异常信息：{str(e)}", exc_info=True)
        if db.connection:
            try:
                logger.info(f"[数据库回滚] 开始回滚事务")
                db.connection.rollback()
                logger.info(f"[数据库回滚] 回滚完成")
            except Exception as rollback_e:
                logger.error(f"[数据库回滚] 失败 - 异常：{str(rollback_e)}")
        raise HTTPException(status_code=500, detail=f"处理聊天历史报告请求失败: {str(e)}")
    finally:
        logger.debug(f"[资源释放] 关闭数据库连接")
        db.close()
        logger.debug(f"[资源释放] 数据库连接已关闭")
        
# --- 上传音频接口（修改：先查用户再写入）---
@router.post("/user/upload-audio")
async def upload_audio_file(
    jabobo_id: str = Form(...),  # 仅保留设备ID作为标识
    file: UploadFile = File(...),
    audio_content: Optional[str] = Form(None),  # 新增音频文本内容字段
):
    logger.info("开始处理音频文件上传请求")
    logger.debug(f"[请求信息] 设备ID：{jabobo_id} | 音频文件名：{file.filename}")
    if audio_content:
        logger.debug(f"[请求信息] 音频文本内容：{truncate_log_text(audio_content)}")
    
    # 第一步：通过设备ID查询对应的用户名（核心修改）
    username = get_username_by_jabobo_id(jabobo_id)
    
    # 1. 校验音频文件后缀
    logger.debug(f"[文件校验] 开始校验音频文件后缀 - 文件名：{file.filename}")
    file_ext = os.path.splitext(file.filename)[1].lower()
    logger.debug(f"[文件校验] 音频文件后缀：{file_ext} | 允许的后缀：{ALLOWED_EXTENSIONS}")
    if file_ext not in ALLOWED_EXTENSIONS:
        logger.error(f"[文件校验] 失败 - 不支持的音频格式：{file_ext}")
        raise HTTPException(status_code=400, detail="仅支持 MP3、WAV、OGG、FLAC、M4A 音频格式")
    logger.debug(f"[文件校验] 音频后缀校验通过")

    # 2. 校验音频文件大小
    logger.debug(f"[文件校验] 开始校验音频文件大小 - 文件名：{file.filename}")
    file.file.seek(0, os.SEEK_END)
    file_size = file.file.tell()
    file.file.seek(0)  # 重置文件指针
    file_size_mb = round(file_size / 1024 / 1024, 2)
    logger.debug(f"[文件校验] 音频文件大小：{file_size} 字节 ({file_size_mb} MB) | 最大允许：{MAX_FILE_SIZE / 1024 / 1024} MB")
    if file_size > MAX_FILE_SIZE:
        logger.error(f"[文件校验] 失败 - 音频文件大小超过限制")
        raise HTTPException(status_code=400, detail="音频文件大小超过 100MB 限制")
    logger.debug(f"[文件校验] 大小校验通过")

    # 3. 创建音频文件存储目录（仅基于设备ID，移除用户名层级）
    logger.debug(f"[目录创建] 开始创建音频存储目录")
    safe_username = sanitize_path_component(username, "unknown_user")
    safe_jabobo_id = sanitize_path_component(jabobo_id, "unknown_device")
    safe_file_name = sanitize_path_component(file.filename, "audio.wav")
    target_dir = os.path.join(BASE_DATA_DIR, safe_username, safe_jabobo_id, "audio_files")  # 仅保留设备ID目录
    logger.debug(f"[目录创建] 音频目标目录：{target_dir}")
    os.makedirs(target_dir, exist_ok=True)
    logger.debug(f"[目录创建] 音频目录创建完成（已存在则跳过）")
    
    # 4. 构建音频文件路径
    file_path = os.path.join(target_dir, safe_file_name)
    file_path = os.path.abspath(file_path)
    logger.debug(f"[文件存储] 音频目标文件路径：{file_path}")
    
    try:
        # 保存音频文件到本地
        logger.debug(f"[文件存储] 开始写入音频文件 - 文件名：{file.filename} | 路径：{file_path}")
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        logger.debug(f"[文件存储] 音频文件写入完成 - 实际文件大小：{os.path.getsize(file_path)} 字节")
        
        # 5. 数据库操作（存储音频文件信息，关联用户名+设备ID）
        logger.info("[数据库操作] 开始处理音频文件数据库逻辑")
        if not db.connect():
            logger.error(f"[数据库操作] 失败 - 数据库连接失败")
            raise HTTPException(status_code=500, detail="数据库连接失败")
        
        # 获取有效游标
        cursor = get_valid_cursor()
        
        # 查询现有音频记录（按 用户名+设备ID 查询，适配联合主键）
        query_sql = "SELECT audio_status FROM user_personas WHERE username = %s AND jabobo_id = %s"
        logger.debug(f"[数据库操作] 执行查询SQL：{query_sql} | 参数：({username}, {jabobo_id})")
        cursor.execute(query_sql, (username, jabobo_id))
        result = cursor.fetchone()
        logger.debug(f"[数据库操作] 查询结果：{result}")
        
        # 解析现有音频路径列表
        if result and result.get("audio_status") is not None:
            try:
                audio_path_list = json.loads(result["audio_status"])
                logger.debug(f"[数据库操作] 解析现有音频列表成功 - 列表长度：{len(audio_path_list)}")
            except json.JSONDecodeError:
                logger.warning(f"[数据库操作] 解析现有音频列表失败 - 重置为空列表")
                audio_path_list = []
        else:
            logger.debug(f"[数据库操作] 无现有音频记录 - 初始化空列表")
            audio_path_list = []
        
        # 构建音频文件信息（新增 audio_content 字段）
        audio_info = {
            "file_path": file_path,
            "file_name": file.filename,
            "file_size_bytes": file_size,
            "file_size_mb": file_size_mb,
            "audio_format": file_ext[1:],  # 音频格式
            "audio_content": audio_content or "",  # 音频文本内容，为空则存空字符串
            "upload_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "upload_timestamp": datetime.now().timestamp()
        }
        logger.debug(f"[数据库操作] 构建音频文件信息：{audio_info}")
        
        # 去重检查
        duplicate = any(item.get("file_path") == file_path for item in audio_path_list)
        if duplicate:
            logger.warning(f"[数据库操作] 音频文件已存在，跳过追加 - 路径：{file_path}")
        else:
            audio_path_list.append(audio_info)
            logger.debug(f"[数据库操作] 音频文件信息追加完成 - 新列表长度：{len(audio_path_list)}")
        
        # 插入/更新数据库（核心修改：补充username字段，适配联合主键）
        audio_status_json = json.dumps(audio_path_list, ensure_ascii=False)
        upsert_sql = """
            INSERT INTO user_personas (username, jabobo_id, audio_status)  -- 新增username字段
            VALUES (%s, %s, %s)  -- 三个参数：用户名、设备ID、音频信息
            ON DUPLICATE KEY UPDATE audio_status = VALUES(audio_status)
        """
        logger.debug(f"[数据库操作] 执行更新SQL：{upsert_sql} | 参数：({username}, {jabobo_id}, {truncate_log_text(audio_status_json, 100)})")
        cursor.execute(upsert_sql, (username, jabobo_id, audio_status_json))
        
        logger.info(f"[上传完成] 成功 - 音频文件路径：{file_path} | 用户名：{username}")
        return {
            "success": True,
            "current_audio_info": audio_info,
            "all_audio_paths": audio_path_list,
            "message": "音频文件上传成功"
        }
    
    except HTTPException:
        # 重新抛出已定义的HTTP异常（如用户未找到、文件格式错误等）
        raise
    except Exception as e:
        logger.error(f"[上传异常] 失败 - 异常信息：{str(e)}", exc_info=True)
        if db.connection:
            try:
                logger.info(f"[数据库回滚] 开始回滚事务")
                db.connection.rollback()
                logger.info(f"[数据库回滚] 回滚完成")
            except Exception as rollback_e:
                logger.error(f"[数据库回滚] 失败 - 异常：{str(rollback_e)}")
        raise HTTPException(status_code=500, detail=f"音频文件保存异常: {str(e)}")
    finally:
        logger.debug(f"[资源释放] 关闭数据库连接")
        db.close()
        logger.debug(f"[资源释放] 数据库连接已关闭")

# --- 查询音频列表接口（仍保留用户验证，若需调整可说明）---
@router.get("/user/list-audio")
async def list_audio_files(
    jabobo_id: str = Query(..., description="设备ID"),
    x_username: str = Header(...), 
    authorization: str = Header(...)
):
    logger.info("开始处理音频文件查询请求")
    logger.debug(f"[请求信息] 用户名：{x_username} | 设备ID：{jabobo_id}")
    
    # 身份验证
    verify_user(x_username, authorization)
    
    try:
        logger.info("[数据库操作] 开始查询音频文件列表")
        if not db.connect():
            logger.error(f"[数据库操作] 失败 - 数据库连接失败")
            raise HTTPException(status_code=500, detail="数据库连接失败")
        
        # 获取有效游标
        cursor = get_valid_cursor()
        
        # 执行查询（仅按设备ID查询）
        query_sql = "SELECT audio_status FROM user_personas WHERE jabobo_id = %s"
        logger.debug(f"[数据库操作] 执行查询SQL：{query_sql} | 参数：({jabobo_id})")
        cursor.execute(query_sql, (jabobo_id,))
        result = cursor.fetchone()
        logger.debug(f"[数据库操作] 查询结果：{result}")
        
        # 处理查询结果
        audio_detail_list = []
        if result and result.get("audio_status") is not None:
            try:
                audio_path_list = json.loads(result["audio_status"])
                logger.debug(f"[数据解析] 解析音频JSON成功 - 列表长度：{len(audio_path_list)}")
                
                for idx, item in enumerate(audio_path_list):
                    logger.debug(f"[数据处理] 处理第 {idx+1} 条音频记录：{item}")
                    if isinstance(item, dict):
                        file_path = item.get("file_path")
                        logger.debug(f"[文件检查] 检查音频文件是否存在：{file_path}")
                        if os.path.exists(file_path):
                            file_stat = os.stat(file_path)
                            item.update({
                                "current_modify_time": datetime.fromtimestamp(file_stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                                "status": "valid"
                            })
                            logger.debug(f"[文件检查] 存在 - 音频文件大小：{os.path.getsize(file_path)} 字节")
                        else:
                            item["status"] = "invalid (file not exists)"
                            logger.warning(f"[文件检查] 不存在")
                        audio_detail_list.append(item)
                    else:
                        # 兼容旧格式
                        file_path = item
                        logger.debug(f"[数据兼容] 旧格式音频路径：{file_path}")
                        if os.path.exists(file_path):
                            file_stat = os.stat(file_path)
                            audio_detail_list.append({
                                "file_path": file_path,
                                "file_name": os.path.basename(file_path),
                                "file_size_mb": round(file_stat.st_size / 1024 / 1024, 2),
                                "modify_time": f"{file_stat.st_mtime}",
                                "audio_format": os.path.splitext(file_path)[1][1:],
                                "audio_content": "",  # 旧格式无文本内容，置空
                                "status": "valid (old format)"
                            })
                        else:
                            audio_detail_list.append({
                                "file_path": file_path,
                                "file_name": os.path.basename(file_path),
                                "audio_format": os.path.splitext(file_path)[1][1:],
                                "audio_content": "",  # 旧格式无文本内容，置空
                                "status": "invalid (file not exists, old format)"
                            })
            except json.JSONDecodeError as e:
                logger.error(f"[数据解析] 失败 - JSON解析异常：{str(e)}")
                audio_detail_list = []
        else:
            logger.debug(f"[数据处理] 无音频文件记录")
            audio_detail_list = []
        
        logger.info(f"[查询完成] 成功 - 共查询到 {len(audio_detail_list)} 条音频记录")
        return {
            "success": True,
            "total_count": len(audio_detail_list),
            "audio_list": audio_detail_list,
            "message": "音频文件列表查询成功"
        }
    except Exception as e:
        logger.error(f"[查询异常] 失败 - 异常信息：{str(e)}", exc_info=True)
        if db.connection:
            try:
                db.connection.rollback()
            except:
                pass
        raise HTTPException(status_code=500, detail=f"查询音频文件列表失败：{str(e)}")
    finally:
        logger.debug(f"[资源释放] 关闭数据库连接")
        db.close()
        logger.debug(f"[资源释放] 数据库连接已关闭")

# --- 删除音频接口（仍保留用户验证，若需调整可说明）---
@router.post("/user/delete-audio")
async def delete_audio_file(
    jabobo_id: str = Query(..., description="设备ID"),
    file_path: str = Query(..., description="要删除的音频文件绝对路径"),
    x_username: str = Header(...), 
    authorization: str = Header(...)
):
    logger.info("开始处理音频文件删除请求")
    logger.debug(f"[请求信息] 用户名：{x_username} | 设备ID：{jabobo_id} | 要删除的音频文件路径：{file_path}")
    
    # 声明游标变量，避免未定义报错
    cursor = None
    
    try:
        # 1. 身份验证
        verify_user(x_username, authorization)
        
        # 2. 安全校验（检查设备ID是否在路径中）
        logger.debug(f"[权限校验] 检查音频文件是否属于当前设备ID")
        if jabobo_id not in file_path:
            logger.error(f"[权限校验] 失败 - 音频文件路径不含设备ID {jabobo_id}")
            raise HTTPException(status_code=403, detail="无权删除该音频文件（路径不属于当前设备）")
        logger.debug(f"[权限校验] 通过")
        
        # 3. 数据库连接
        logger.info("[数据库操作] 开始查询音频文件记录")
        if not db.connect():
            logger.error(f"[数据库操作] 失败 - 数据库连接失败")
            raise HTTPException(status_code=500, detail="数据库连接失败")
        
        # 4. 获取有效游标
        cursor = get_valid_cursor()
        
        # 5. 查询现有音频记录
        query_sql = "SELECT audio_status FROM user_personas WHERE jabobo_id = %s"
        logger.debug(f"[数据库操作] 执行查询SQL：{query_sql} | 参数：({jabobo_id})")
        cursor.execute(query_sql, (jabobo_id,))
        result = cursor.fetchone()
        logger.debug(f"[数据库操作] 查询结果：{result}")
        
        # 6. 解析音频列表
        audio_path_list = []
        if result and result.get("audio_status") is not None:
            try:
                audio_path_list = json.loads(result["audio_status"])
                logger.debug(f"[数据解析] 解析现有音频列表成功 - 列表长度：{len(audio_path_list)}")
            except json.JSONDecodeError:
                logger.warning(f"[数据解析] 失败 - 重置为空列表")
                audio_path_list = []
        else:
            logger.debug(f"[数据处理] 无现有音频记录")
        
        # 7. 检查音频文件是否存在于列表
        logger.debug(f"[存在性检查] 检查音频文件路径是否在列表中：{file_path}")
        file_exists = False
        if audio_path_list:
            if isinstance(audio_path_list[0], dict):
                file_exists = any(item.get("file_path") == file_path for item in audio_path_list)
            else:
                file_exists = file_path in audio_path_list
        
        if not file_exists:
            logger.error(f"[存在性检查] 失败 - 音频文件路径不在音频列表中")
            raise HTTPException(status_code=404, detail="音频文件路径不存在于音频列表中")
        logger.debug(f"[存在性检查] 通过")
        
        # 8. 删除本地音频文件
        logger.info(f"[文件删除] 开始删除本地音频文件：{file_path}")
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"[文件删除] 成功 - 本地音频文件已删除")
            except Exception as file_e:
                logger.error(f"[文件删除] 失败 - 异常：{str(file_e)}")
                raise HTTPException(status_code=500, detail=f"删除本地文件失败：{str(file_e)}")
        else:
            logger.warning(f"[文件删除] 跳过 - 本地音频文件不存在")
        
        # 9. 从列表移除音频路径
        logger.debug(f"[数据更新] 从音频列表移除文件路径")
        if audio_path_list:
            if isinstance(audio_path_list[0], dict):
                audio_path_list = [item for item in audio_path_list if item.get("file_path") != file_path]
            else:
                audio_path_list.remove(file_path)
        logger.debug(f"[数据更新] 移除完成 - 新音频列表长度：{len(audio_path_list)}")
        
        # 10. 更新数据库（核心修复：添加 username 字段）
        audio_status_json = json.dumps(audio_path_list, ensure_ascii=False)
        # 修复 UPSERT SQL，补充 username 字段
        upsert_sql = """
            INSERT INTO user_personas (jabobo_id, username, audio_status)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE 
                audio_status = VALUES(audio_status),
                username = VALUES(username)  # 可选：如需更新用户名则保留，否则删除该行
        """
        logger.debug(f"[数据库操作] 执行更新SQL：{upsert_sql} | 参数：({jabobo_id}, {x_username}, {truncate_log_text(audio_status_json, 100)})")
        # 传入 x_username 参数（从请求头获取的真实用户名）
        cursor.execute(upsert_sql, (jabobo_id, x_username, audio_status_json))
        # 提交事务（关键：确保数据写入）
        db.connection.commit()
        
        # 11. 返回成功结果
        logger.info(f"[删除完成] 成功 - 删除音频文件路径：{file_path} | 剩余音频记录数：{len(audio_path_list)}")
        return {
            "success": True,
            "deleted_path": file_path,
            "remaining_audio_paths": audio_path_list,
            "message": "音频文件删除成功"
        }
    
    # 捕获业务异常（HTTPException）
    except HTTPException:
        raise
    # 捕获其他所有异常
    except Exception as e:
        logger.error(f"[删除异常] 失败 - 异常信息：{str(e)}", exc_info=True)
        # 数据库回滚
        if db.connection:
            try:
                logger.info(f"[数据库回滚] 开始回滚事务")
                db.connection.rollback()
                logger.info(f"[数据库回滚] 回滚完成")
            except Exception as rollback_e:
                logger.error(f"[数据库回滚] 失败 - 异常：{str(rollback_e)}")
        # 关闭游标（避免资源泄漏）
        if cursor:
            try:
                cursor.close()
            except:
                pass
        raise HTTPException(status_code=500, detail=f"删除音频文件失败：{str(e)}")
    
    # 最终资源释放
    finally:
        logger.debug(f"[资源释放] 关闭数据库连接")
        db.close()
        logger.debug(f"[资源释放] 数据库连接已关闭")
        
@router.post("/voiceprint/register")
async def register_voiceprint(
    jabobo_id: str = Form(...),
    voiceprint_name: str = Form(...),
    file_path: str = Form(...),
    x_username: str = Header(...),  # 从请求头获取用户名（和知识库接口一致）
    authorization: str = Header(...)
):
    logger.info("开始处理声纹注册请求")
    logger.debug(f"[请求信息] 用户名：{x_username} | 设备ID：{jabobo_id} | 声纹名称：{voiceprint_name} | 音频文件路径：{file_path}")
    
    # 1. 身份验证（和知识库接口一致的权限校验）
    verify_user(x_username, authorization)
    
    # 2. 音频文件校验（对齐知识库接口的文件校验逻辑）
    logger.debug(f"[文件校验] 检查音频文件是否存在 - 路径：{file_path}")
    if not os.path.exists(file_path):
        logger.error(f"[文件校验] 失败 - 音频文件不存在")
        raise HTTPException(status_code=400, detail="音频文件不存在")
    
    # 2.1 校验文件后缀
    logger.debug(f"[文件校验] 开始校验音频文件后缀 - 文件名：{os.path.basename(file_path)}")
    file_ext = os.path.splitext(file_path)[1].lower()
    logger.debug(f"[文件校验] 音频文件后缀：{file_ext} | 允许的后缀：{ALLOWED_AUDIO_EXTENSIONS}")
    if file_ext not in ALLOWED_AUDIO_EXTENSIONS:
        logger.error(f"[文件校验] 失败 - 不支持的音频格式：{file_ext}")
        raise HTTPException(status_code=400, detail="仅支持 WAV 格式音频文件")
    logger.debug(f"[文件校验] 音频后缀校验通过")
    
    # 2.2 校验文件大小
    file_size = os.path.getsize(file_path)
    file_size_mb = round(file_size / 1024 / 1024, 2)
    logger.debug(f"[文件校验] 音频文件大小：{file_size} 字节 ({file_size_mb} MB) | 最大允许：{MAX_AUDIO_SIZE / 1024 / 1024} MB")
    if file_size > MAX_AUDIO_SIZE:
        logger.error(f"[文件校验] 失败 - 音频文件大小超过限制")
        raise HTTPException(status_code=400, detail="音频文件大小超过 50MB 限制")
    logger.debug(f"[文件校验] 大小校验通过")
    
    # 3. 生成SpeakerID（核心修改：去掉MD5，直接拼接）
    speaker_id = f"{jabobo_id}_{voiceprint_name}"  # 直接拼接，不再使用hash
    logger.info(f"[SpeakerID生成] 生成成功 - jabobo_id: {jabobo_id} | 声纹名称: {voiceprint_name} | speaker_id: {speaker_id}")
    
    db_connected = False
    try:
        # ===================== 新增：调用声纹服务器注册 =====================
        logger.info("[声纹服务器] 开始向 172.20.0.3:8005 发送注册请求")
        voiceprint_server_url = "http://localhost:8005/voiceprint/register"
        logger.debug(f"[声纹服务器] 请求地址：{voiceprint_server_url}")
        api_key = get_env("VOICEPRINT_API_KEY")
        
        # 读取音频文件内容
        with open(file_path, 'rb') as audio_file:
            file_content = audio_file.read()
        logger.debug(f"[声纹服务器] 音频文件内容读取完成 - 大小：{len(file_content)} 字节")
        
        # 准备请求参数
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Accept': 'application/json'
        }
        data = aiohttp.FormData()
        data.add_field('speaker_id', speaker_id)
        data.add_field('file', file_content, filename=os.path.basename(file_path), content_type='audio/wav')
        
        # 发送请求到声纹服务器
        api_start_time = time.monotonic()
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(voiceprint_server_url, headers=headers, data=data) as response:
                if response.status != 200:
                    error_msg = await response.text()
                    logger.error(f"[声纹服务器] 注册失败 - 状态码：{response.status} | 错误：{error_msg}")
                    raise HTTPException(status_code=response.status, detail=f"声纹服务器注册失败：{error_msg}")
                
                # 解析声纹服务器响应
                server_response = await response.json()
                total_elapsed_time = time.monotonic() - api_start_time
                logger.info(f"[声纹服务器] 注册成功 - 耗时：{total_elapsed_time:.3f}s | 响应：{server_response}")
        
        # ===================== 原有：数据库存储逻辑 =====================
        # 4. 数据库操作（对齐知识库接口的数据库逻辑）
        logger.info("[数据库操作] 检查声纹数量限制并保存记录")
        db_connected = db.connect()
        if not db_connected:
            logger.error(f"[数据库操作] 失败 - 数据库连接失败")
            raise HTTPException(status_code=500, detail="数据库连接失败")
        
        # 获取有效游标（和知识库接口一致）
        cursor = get_valid_cursor()
        
        # 4.1 查询现有声纹记录
        query_sql = "SELECT voiceprint_list FROM user_personas WHERE username = %s AND jabobo_id = %s"
        logger.debug(f"[数据库操作] 执行查询SQL：{query_sql} | 参数：({x_username}, {jabobo_id})")
        cursor.execute(query_sql, (x_username, jabobo_id))
        result = cursor.fetchone()
        logger.debug(f"[数据库操作] 查询结果：{result}")
        
        # 4.2 解析现有声纹列表（兼容空值/解析失败）
        voiceprint_list = []
        if result and result.get("voiceprint_list") is not None:
            try:
                voiceprint_list = json.loads(result["voiceprint_list"])
                logger.debug(f"[数据库操作] 解析现有声纹列表成功 - 列表长度：{len(voiceprint_list)}")
            except json.JSONDecodeError:
                logger.warning(f"[数据库操作] 解析现有声纹列表失败 - 重置为空列表")
                voiceprint_list = []
        else:
            logger.debug(f"[数据库操作] 无现有声纹记录 - 初始化空列表")
            voiceprint_list = []
        
        # 4.3 检查声纹数量限制（最多10个）
        if len(voiceprint_list) >= 10:
            logger.error(f"[数据库操作] 失败 - 声纹数量已达上限（10个）")
            raise HTTPException(status_code=400, detail="该设备声纹数量已达上限（最多10个）")
        
        # 4.4 检查同名声纹（避免重复）
        duplicate = any(item.get("voiceprint_name") == voiceprint_name for item in voiceprint_list)
        if duplicate:
            logger.error(f"[数据库操作] 失败 - 已存在名为{voiceprint_name}的声纹")
            raise HTTPException(status_code=400, detail=f"该设备已存在名为{voiceprint_name}的声纹")
        
        # 4.5 构建新声纹记录（对齐知识库接口的文件信息格式）
        voiceprint_info = {
            "voiceprint_name": voiceprint_name,
            "speaker_id": speaker_id,
            "file_path": file_path,
            "file_size_bytes": file_size,
            "file_size_mb": file_size_mb,
            "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "create_timestamp": datetime.now().timestamp()
        }
        logger.debug(f"[数据库操作] 构建声纹信息：{voiceprint_info}")
        
        # 4.6 追加新记录并更新数据库
        voiceprint_list.append(voiceprint_info)
        voiceprint_json = json.dumps(voiceprint_list, ensure_ascii=False)
        
        upsert_sql = """
            INSERT INTO user_personas (username, jabobo_id, voiceprint_list) 
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE voiceprint_list = VALUES(voiceprint_list)
        """
        logger.debug(f"[数据库操作] 执行更新SQL：{upsert_sql} | 参数：({x_username}, {jabobo_id}, {truncate_log_text(voiceprint_json, 100)})")
        cursor.execute(upsert_sql, (x_username, jabobo_id, voiceprint_json))
        
        # 核心：提交事务（和知识库接口一致）
        db.connection.commit()
        logger.info(f"[数据库操作] 事务提交成功")
        
        logger.info(f"[声纹注册] 成功 - speaker_id：{speaker_id}")
        return {
            "success": True,
            "speaker_id": speaker_id,
            "voiceprint_info": voiceprint_info,
            "total_voiceprints": len(voiceprint_list),
            "message": "声纹注册成功（声纹服务器+本地数据库）"
        }
    
    except Exception as e:
        logger.error("[声纹注册异常] 失败 - 异常信息：%s", str(e), exc_info=True)
        if db_connected and db.connection:
            try:
                logger.info(f"[数据库回滚] 开始回滚事务")
                db.connection.rollback()
                logger.info(f"[数据库回滚] 回滚完成")
            except Exception as rollback_e:
                logger.error(f"[数据库回滚] 失败 - 异常：{str(rollback_e)}")
        raise HTTPException(status_code=500, detail=f"声纹注册失败: {str(e)}")
    finally:
        # 资源释放（和知识库接口完全一致）
        logger.debug(f"[资源释放] 关闭数据库连接")
        if db_connected and db.connection:
            try:
                if hasattr(db, 'cursor') and db.cursor:
                    db.cursor.close()
                db.close()
            except Exception as close_e:
                logger.error(f"[资源释放] 关闭连接失败：{str(close_e)}")
        logger.debug(f"[资源释放] 数据库连接已关闭")

# --- 可选：声纹列表查询接口（对齐知识库list接口）---
@router.get("/voiceprint/list")
async def list_voiceprints(
    jabobo_id: str = Query(..., description="设备ID"),
    x_username: str = Header(...),
    authorization: str = Header(...)
):
    logger.info("开始处理声纹列表查询请求")
    logger.debug(f"[请求信息] 用户名：{x_username} | 设备ID：{jabobo_id}")
    
    # 身份验证
    verify_user(x_username, authorization)
    
    db_connected = False
    try:
        # 数据库连接
        db_connected = db.connect()
        if not db_connected:
            raise HTTPException(status_code=500, detail="数据库连接失败")
        
        cursor = get_valid_cursor()
        # 查询声纹列表
        query_sql = "SELECT voiceprint_list FROM user_personas WHERE username = %s AND jabobo_id = %s"
        logger.debug(f"[数据库操作] 执行查询SQL：{query_sql} | 参数：({x_username}, {jabobo_id})")
        cursor.execute(query_sql, (x_username, jabobo_id))
        result = cursor.fetchone()
        
        # 解析结果
        voiceprint_detail_list = []
        if result and result.get("voiceprint_list") is not None:
            try:
                voiceprint_list = json.loads(result["voiceprint_list"])
                logger.debug(f"[数据解析] 解析JSON成功 - 列表长度：{len(voiceprint_list)}")
                
                for idx, item in enumerate(voiceprint_list):
                    logger.debug(f"[数据处理] 处理第 {idx+1} 条声纹记录：{item}")
                    if isinstance(item, dict):
                        file_path = item.get("file_path")
                        # 检查音频文件是否存在
                        if os.path.exists(file_path):
                            item["file_status"] = "valid"
                        else:
                            item["file_status"] = "invalid (file not exists)"
                        voiceprint_detail_list.append(item)
            except json.JSONDecodeError as e:
                logger.error(f"[数据解析] 失败 - JSON解析异常：{str(e)}")
                voiceprint_detail_list = []
        
        logger.info(f"[查询完成] 成功 - 共查询到 {len(voiceprint_detail_list)} 条声纹记录")
        return {
            "success": True,
            "total_count": len(voiceprint_detail_list),
            "voiceprint_list": voiceprint_detail_list,
            "message": "声纹列表查询成功"
        }
    except Exception as e:
        logger.error(f"[查询异常] 失败 - 异常信息：{str(e)}", exc_info=True)
        if db_connected and db.connection:
            db.connection.rollback()
        raise HTTPException(status_code=500, detail=f"查询声纹列表失败：{str(e)}")
    finally:
        # 资源释放
        if db_connected and db.connection:
            try:
                if hasattr(db, 'cursor') and db.cursor:
                    db.cursor.close()
                db.close()
            except Exception as close_e:
                logger.error(f"[资源释放] 关闭连接失败：{str(close_e)}")
        logger.debug(f"[资源释放] 数据库连接已关闭")
        
@router.post("/voiceprint/delete") # 仅仅改这一行，把 delete 改成 post
async def delete_voiceprint(
    jabobo_id: str = Form(..., description="设备ID"),
    voiceprint_name: str = Form(..., description="声纹名称"),
    # 可选：也可以通过speaker_id删除
    speaker_id: Optional[str] = Form(None, description="说话人ID（可选，优先级高于声纹名称）")
):
    """
    删除声纹
    - 支持通过设备ID+声纹名称 或 speaker_id 删除
    - 删除时同时更新数据库中的声纹列表
    """
    logger.info("开始处理声纹删除请求")
    logger.debug(f"[请求信息] 设备ID：{jabobo_id} | 声纹名称：{voiceprint_name} | speaker_id：{speaker_id}")
    
    try:
        # 1. 数据库连接
        if not db.connect():
            logger.error(f"[数据库操作] 失败 - 数据库连接失败")
            raise HTTPException(status_code=500, detail="数据库连接失败")
        
        # 2. 生成speaker_id（如果未传入，直接拼接）
        if not speaker_id:
            speaker_id = f"{jabobo_id}_{voiceprint_name}"  # 核心修改：直接拼接
        logger.debug(f"[SpeakerID生成] 使用speaker_id：{speaker_id}")
        
        # 3. 查询并解析声纹列表
        cursor = get_valid_cursor()
        query_sql = "SELECT voiceprint_list FROM user_personas WHERE jabobo_id = %s LIMIT 1"
        cursor.execute(query_sql, (jabobo_id,))
        result = cursor.fetchone()
        
        if not result or not result.get("voiceprint_list"):
            raise HTTPException(status_code=404, detail=f"该设备ID({jabobo_id})暂无声纹记录")
        
        voiceprint_list = json.loads(result["voiceprint_list"])
        if not voiceprint_list:
            raise HTTPException(status_code=404, detail=f"该设备ID({jabobo_id})暂无声纹记录")
        
        # 4. 查找要删除的声纹记录
        delete_index = -1
        delete_item = None
        for idx, item in enumerate(voiceprint_list):
            if item.get("speaker_id") == speaker_id or item.get("voiceprint_name") == voiceprint_name:
                delete_index = idx
                delete_item = item
                break
        
        if delete_index == -1:
            raise HTTPException(status_code=404, detail=f"未找到声纹记录（名称：{voiceprint_name} | speaker_id：{speaker_id}）")
        
        # 5. 调用声纹服务器进行删除
        voiceprint_server_url = f"http://localhost:8005/voiceprint/{speaker_id}"
        api_key = get_env("VOICEPRINT_API_KEY")
        
        api_start_time = time.monotonic()
        timeout = aiohttp.ClientTimeout(total=30)
        
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Accept': 'application/json',
            'speaker_id': speaker_id
        }
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.delete(voiceprint_server_url, headers=headers) as response:
                
                if response.status == 200:
                    response_data = await response.json()
                    total_elapsed_time = time.monotonic() - api_start_time
                    
                    logger.info(f"[声纹删除] 耗时: {total_elapsed_time:.3f}s")
                    
                    # 6. 从列表中移除声纹记录
                    voiceprint_list.pop(delete_index)
                    voiceprint_json = json.dumps(voiceprint_list, ensure_ascii=False)
                    
                    # 7. 更新数据库
                    upsert_sql = """
                        UPDATE user_personas 
                        SET voiceprint_list = %s 
                        WHERE jabobo_id = %s
                    """
                    cursor.execute(upsert_sql, (voiceprint_json, jabobo_id))
                    db.connection.commit()
                    
                    # 8. 删除本地音频文件（可选）
                    file_path = delete_item.get("file_path")
                    if file_path and os.path.exists(file_path):
                        os.remove(file_path)
                        logger.info(f"[文件删除] 本地音频文件已删除：{file_path}")
                    
                    success = response_data.get("success", True)
                    msg = response_data.get("msg", "声纹删除成功")
                    
                    logger.debug(f"[声纹删除] 声纹服务器响应状态码：{response.status}")
                    logger.debug(f"[声纹删除] 声纹服务器响应内容：{response_data}")
                    
                    logger.info(f"[删除完成] 成功 - 设备ID：{jabobo_id} | 声纹名称：{voiceprint_name} | speaker_id：{speaker_id}")
                    return {
                        "success": success,
                        "msg": msg,
                        "jabobo_id": jabobo_id,
                        "voiceprint_name": voiceprint_name,
                        "speaker_id": speaker_id,
                        "deleted_voiceprint": delete_item,
                        "remaining_count": len(voiceprint_list)
                    }
                else:
                    logger.error(f"[声纹删除] 失败 - 声纹服务器返回非200状态码: {response.status}")
                    error_msg = await response.text()
                    logger.error(f"[声纹删除] 错误详情: {error_msg}")
                    raise HTTPException(status_code=response.status, detail=f"声纹服务器返回错误: {error_msg}")
                
    except HTTPException as e:
        logger.error(f"[声纹删除异常] HTTP异常 - {e.detail}")
        raise
    except ImportError:
        logger.error(f"[声纹删除异常] 缺少aiohttp模块，请安装: pip install aiohttp")
        raise HTTPException(status_code=500, detail="系统缺少aiohttp模块，请联系管理员")
    except asyncio.TimeoutError:
        elapsed = time.monotonic() - api_start_time if 'api_start_time' in locals() else 0
        logger.error(f"[声纹删除超时] 耗时: {elapsed:.3f}s")
        raise HTTPException(status_code=408, detail=f"声纹删除超时: {elapsed:.3f}s")
    except Exception as e:
        elapsed = time.monotonic() - api_start_time if 'api_start_time' in locals() else 0
        logger.error(f"[声纹删除异常] 失败 - 异常信息：{str(e)}", exc_info=True)
        if db.connection:
            db.connection.rollback()
        raise HTTPException(status_code=500, detail=f"声纹删除失败: {str(e)}")
    finally:
        if db.connection:
            db.close()
            logger.debug(f"[资源释放] 数据库连接已关闭")