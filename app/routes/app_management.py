import os
import json
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse

# 导入 loguru
from loguru import logger

router = APIRouter()

# ========== 路径配置 ==========
# APP 文件存放的物理路径
PACKAGE_DIRECTORY = "/var/local/jobobo-backend/app/app_packages"
# 安卓配置
APK_NAME = "jabobo.apk"
APK_MEDIA_TYPE = "application/vnd.android.package-archive"
# iOS 配置
IPA_NAME = "jabobo.ipa"
IPA_MEDIA_TYPE = "application/octet-stream"
# 服务器域名（替换成你的实际域名）
SERVER_DOMAIN = "https://jabobo.com"

# ========== 固定版本配置（无需数据库） ==========
# 安卓固定版本
ANDROID_CONFIG = {
    "version_name": "1.1",
    "version_code": 2,  # 版本号建议比1.0高，这里设为2
    "update_log": "初始版本发布",
    "download_url": f"{SERVER_DOMAIN}/api/app/download?platform=android"
}

# iOS固定版本
IOS_CONFIG = {
    "version_name": "1.0",
    "version_code": 1,
    "update_log": "初始版本发布",
    "download_url": f"{SERVER_DOMAIN}/api/app/download?platform=ios",
    "plist_url": f"{SERVER_DOMAIN}/api/app/ios-plist",
    "bundle_id": "com.gn.Jabobo",  # 替换成你实际的Bundle ID
    "version_build": 1
}

# ========== 1. 获取最新版本信息（支持安卓/iOS，无数据库查询） ==========
@router.get("/app/latest-version")
async def get_latest_version(platform: str = Query("android", enum=["android", "ios"])):
    """
    获取最新版本信息
    :param platform: 平台类型 android/ios
    """
    try:
        # 直接返回固定配置，无需数据库
        if platform == "android":
            version_data = ANDROID_CONFIG
            logger.info(f"🔍 [APP VERSION] {platform} | Latest Version: {version_data['version_name']} (固定配置)")
        else:
            version_data = IOS_CONFIG
            logger.info(f"🔍 [APP VERSION] {platform} | Latest Version: {version_data['version_name']} (固定配置)")
        
        return {
            "success": True,
            "data": version_data
        }
    except Exception as e:
        logger.exception(f"🔥 [VERSION ERROR] 获取{platform}版本信息时发生异常: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取{platform}版本信息失败")

# ========== 2. APP 下载接口（支持安卓/iOS） ==========
@router.get("/app/download")
async def download_app(platform: str = Query("android", enum=["android", "ios"])):
    """
    下载安装包
    :param platform: 平台类型 android/ios
    """
    # 根据平台选择文件和配置
    if platform == "android":
        file_name = APK_NAME
        file_path = os.path.join(PACKAGE_DIRECTORY, file_name)
        media_type = APK_MEDIA_TYPE
        download_filename = "Jabobo_Latest.apk"
    else:
        file_name = IPA_NAME
        file_path = os.path.join(PACKAGE_DIRECTORY, file_name)
        media_type = IPA_MEDIA_TYPE
        download_filename = "Jabobo_Latest.ipa"

    # 检查文件是否存在
    if not os.path.exists(file_path):
        logger.error(f"❌ [DOWNLOAD ERROR] {platform}文件不存在: {file_path}")
        raise HTTPException(status_code=404, detail=f"{platform}安装包文件不存在，请联系管理员")

    logger.success(f"🚀 [APP DOWNLOAD] Serving {platform.upper()}: {file_name}")
    
    return FileResponse(
        path=file_path,
        filename=download_filename,
        media_type=media_type
    )

# ========== 3. iOS plist 描述文件接口（无数据库查询） ==========
@router.get("/app/ios-plist", response_class=PlainTextResponse)
async def get_ios_plist():
    """
    生成iOS安装所需的plist文件（关键！）
    """
    try:
        # 直接使用iOS固定配置，无需数据库查询
        bundle_id = IOS_CONFIG["bundle_id"]
        version_name = IOS_CONFIG["version_name"]
        
        # 构造plist内容（苹果要求的固定格式）
        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>items</key>
    <array>
        <dict>
            <key>assets</key>
            <array>
                <dict>
                    <key>kind</key>
                    <string>software-package</string>
                    <key>url</key>
                    <string>{IOS_CONFIG['download_url']}</string>
                </dict>
            </array>
            <key>metadata</key>
            <dict>
                <key>bundle-identifier</key>
                <string>{bundle_id}</string>
                <key>bundle-version</key>
                <string>{version_name}</string>
                <key>kind</key>
                <string>software</string>
                <key>title</key>
                <string>Jabobo</string>
            </dict>
        </dict>
    </array>
</dict>
</plist>"""
        
        logger.success(f"✅ [IOS PLIST] 生成plist文件成功 | Bundle ID: {bundle_id} (固定配置)")
        return PlainTextResponse(content=plist_content, media_type="application/xml")
    
    except Exception as e:
        logger.exception(f"🔥 [IOS PLIST ERROR] 生成plist文件失败: {str(e)}")
        raise HTTPException(status_code=500, detail="生成iOS安装配置文件失败")