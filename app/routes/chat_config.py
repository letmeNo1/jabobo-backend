# ... existing code ...
from fastapi import APIRouter, HTTPException, Header, Path
from app.database import db
import json
from typing import Dict, Any  # 添加typing导入
import os
from dotenv import load_dotenv
from loguru import logger  # 导入 loguru

# 加载.env文件，不修改原有换行/格式
load_dotenv()

router = APIRouter()

# 辅助函数：仅读取环境变量，不影响原格式
def get_env(key: str, default: str = "") -> str:
    return os.getenv(key, default)

# 1. 获取服务器基础配置
@router.post("/config/server-base")
async def get_server_base_config():
    """
    获取服务器基础配置
    """
    try:
        # 模拟服务器基础配置
        server_config = {
            "delete_audio": True,
            "ASR": {
                "ASR_FunASR": {
                    "type": "fun_local",
                    "model_dir": "models/SenseVoiceSmall",
                    "output_dir": "tmp/"
                }
            },
            "server": {
                "sms_max_send_count": 10,
                "fronted_url": get_env("FRONTED_URL"),
                "websocket": get_env("WEBSOCKET_URL"),
                "name": "xiaozhi-esp32-server",
                "mcp_endpoint": get_env("MCP_ENDPOINT"),
                "voice_print": get_env("VOICEPRINT_URL"),
                "secret": get_env("SERVER_SECRET"),
                "beian_ga_num": "None",
                "ota": get_env("OTA_URL"),
                "beian_icp_num": "None",
                "allow_user_register": True,
                "enable_mobile_register": False
            },
            "enable_stop_tts_notify": True,
            "close_connection_no_voice_time": 120,
            "enable_wakeup_words_response_cache": False,
            "log": {
                "log_format_file": "{time:YYYY-MM-DD HH:mm:ss} - {version}_{selected_module} - {name} - {level} - {extra[tag]} - {message}",
                "log_dir": "tmp",
                "log_format": "<green>{time:YYMMDD HH:mm:ss}</green>[<light-blue>{version}-{selected_module}</light-blue>][<light-blue>{extra[tag]}</light-blue>]-<level>{level}</level>-<light-green>{message}</light-green>",
                "log_file": "server.log",
                "log_level": "INFO",
                "data_dir": "data"
            },
            "wakeup_words": [
                "捷宝宝",
            ],
            "selected_module": {
                "ASR": "ASR_FunASR",
                "VAD": "VAD_SileroVAD"
            },
            "enable_greeting": False,
            "end_prompt": {
                "enable": True,
                "prompt": "再见"
            },
            "exit_commands": [
                "none"
            ],
            "tts_timeout": 10,
            "device_max_output_size": 0,
            "VAD": {
                "VAD_SileroVAD": {
                    "type": "silero",
                    "model_dir": "models/snakers4_silero-vad",
                    "threshold": "0.65",
                    "min_silence_duration_ms": "500"
                }
            },
            "summaryMemory": None,
            "stop_tts_notify_voice": "config/assets/tts_notify.mp3",
            "aliyun": {
                "sms": {
                    "access_key_id": "",
                    "sign_name": "",
                    "access_key_secret": "",
                    "sms_code_template_code": ""
                }
            },
            "prompt": None,
            "xiaozhi": {
                "type": "hello",
                "version": 1,
                "transport": "websocket",
                "audio_params": {
                    "format": "opus",
                    "sample_rate": 16000,
                    "channels": 1,
                    "frame_duration": 60
                }
            }
        }

        return {
            "code": 0,
            "msg": "success",
            "data": server_config
        }
    except Exception as e:
        logger.error(f"🔥 Server Base Config Error: {str(e)}")
        return {
            "code": 500,
            "msg": str(e),
            "data": None
        }


# 2. 获取代理模型配置
@router.post("/config/agent-models")
async def get_agent_models_config(payload: dict):
    """
    获取代理模型配置
    """
    try:
        # 从payload中获取设备信息
        mac_address = payload.get('macAddress', '')
        client_id = payload.get('clientId', '')
        
        logger.info(f"💬 [AGENT MODELS CONFIG] Device: {mac_address}")
        logger.debug(f"   Client ID: {client_id}")
        
        # 从数据库获取设备特定配置
        device_prompt, device_memory = await get_device_config(mac_address)
        
        # 根据设备MAC地址获取声纹列表
        voiceprint_list = await get_voiceprint_list_by_mac(mac_address)
        
        # 模拟代理模型配置
        agent_models_config = {
            "plugins": {
                "get_weather": "{\"api_key\": \"" + get_env("WEATHER_API_KEY") + "\", \"api_host\": \"py78kyqwtq.re.qweatherapi.com\", \"default_location\": \"Ballerup\"}"
            },
            "Memory": {
                "Memory_mem_local_short": {
                    "llm": "LLM_DeepSeekLLM",
                    "type": "mem_local_short"
                }
            },
            "selected_module": {
                "TTS": "AzureTTS",
                "Memory": "Memory_mem_local_short",
                "Intent": "Intent_intent_llm",
                "LLM": "LLM_AliLLM",
                "VLLM": "VLLM_ChatGLMVLLM"
            },
            "Intent": {
                "Intent_intent_llm": {
                    "llm": "LLM_AliLLM",
                    "type": "intent_llm",
                }
            },
            "chat_history_conf": 2,
            "LLM": {
                "LLM_AliLLM": {
                    "type": "openai",
                    "top_k": "50",
                    "top_p": "1",
                    "api_key": get_env("ALI_LLM_API_KEY"),
                    "base_url": get_env("ALI_LLM_BASE_URL"),
                    "max_tokens": "500",
                    "model_name": "qwen-turbo-latest",
                    "temperature": "0.3",
                    "frequency_penalty": "0",
                    "device_max_output_size": "0"
                },
                "LLM_DeepSeekLLM": {
                    "type": "openai", 
                    "top_k": "", 
                    "top_p": "", 
                    "api_key": get_env("DEEPSEEK_LLM_API_KEY"), 
                    "base_url": get_env("DEEPSEEK_LLM_BASE_URL"), 
                    "max_tokens": "", 
                    "model_name": "deepseek-chat", 
                    "temperature": "", 
                    "frequency_penalty": ""
                }
            },
            "TTS": {
                "AzureTTS": {
                    "type": "azure",
                    "subscription_key": get_env("AZURE_TTS_SUBSCRIPTION_KEY"),
                    "region": get_env("AZURE_TTS_REGION", "northeurope"),
                    "voice": get_env("AZURE_TTS_VOICE", "en-US-AnaNeural"),
                    "output_dir": "tmp/"
                },
                "TTS_TencentTTS": {
                    "type": "tencent",
                    "appid": "1391329716",
                    "voice": "101001",
                    "region": "ap-guangzhou",
                    "secret_id": get_env("TENCENT_TTS_SECRET_ID"),
                    "output_dir": "tmp/",
                    "secret_key": get_env("TENCENT_TTS_SECRET_KEY"),
                    "private_voice": "101015",
                    "mcp_endpoint": get_env("TTS_MCP_ENDPOINT")
                },
                "HuoshanDoubleStreamTTS": {
                    "type": "huoshan_double_stream",
                    "appid": 1368522836,
                    "access_token": get_env("HUOSHAN_TTS_ACCESS_TOKEN"),
                    "resource_id": "volc.service_type.10029",
                    "ws_url": "wss://openspeech.bytedance.com/api/v3/tts/bidirection",
                }
            },
            "voiceprint": {
                "speakers": voiceprint_list,
                "url": get_env("VOICEPRINT_URL")
            },
            "summaryMemory": device_memory,
            "prompt": device_prompt,
            "VLLM": {
                "VLLM_ChatGLMVLLM": {
                    "type": "openai",
                    "api_key": get_env("CHATGLM_VLLM_API_KEY"),
                    "base_url": get_env("CHATGLM_VLLM_BASE_URL"),
                    "model_name": "glm-4v-flash"
                }
            }
        }
                      
        return {
            "code": 0,
            "msg": "success",
            "data": agent_models_config
        }
    except Exception as e:
        logger.error(f"🔥 Agent Models Config Error: {str(e)}")
        return {
            "code": 500,
            "msg": str(e),
            "data": None
        }
        
# 新增函数：根据设备MAC地址获取声纹列表
async def get_voiceprint_list_by_mac(mac_address: str):
    """
    根据设备MAC地址获取声纹列表
    """
    default_voiceprints = [
        "e3877b049aa7ca8863354f83418b9e1f,Tianhao,这是天豪,SIMULATION TEAM的实习生",
        "2ef8f890252e057797565de6d6fc4f28,Alice,manager of simulation team",
        "0f6b09bb29d23b90fb723fe7a01b0601,欣欣,5岁的小女孩，现在读中班了，爱运动，爱画画，足球踢得很好,是Alice的女儿，还有一个哥哥叫安安。"
    ]

    if not mac_address:
        return default_voiceprints
    
    connection = None
    try:
        connection = db.connect()
        if not connection:
            logger.error("🔥 Database connection failed")
            return default_voiceprints
        
        sql = "SELECT voiceprint_list FROM user_personas WHERE jabobo_id = %s"
        cursor = db.cursor
        cursor.execute(sql, (mac_address,))
        result = cursor.fetchone()
        
        logger.debug(f"🔍 Voiceprint query result for {mac_address}: {result}")
        
        if result and result.get("voiceprint_list") is not None:
            try:
                voiceprint_list = json.loads(result["voiceprint_list"])
                logger.debug(f"🔍 Parsed voiceprint list: {voiceprint_list}")
                
                formatted_voiceprints = []
                for item in voiceprint_list:
                    if isinstance(item, dict):
                        speaker_id = item.get("speaker_id", "")
                        voiceprint_name = item.get("voiceprint_name", "")
                        description = "this is a speaker from user device"
                        formatted_entry = f"{speaker_id},{voiceprint_name},{description}"
                        formatted_voiceprints.append(formatted_entry)
                
                return formatted_voiceprints
            except json.JSONDecodeError as e:
                logger.error(f"🔥 JSON Decode Error when parsing voiceprint list: {str(e)}")
                return default_voiceprints
        else:
            logger.warning(f"⚠️ No voiceprint list found for MAC: {mac_address}")
            return default_voiceprints
    except Exception as e:
        logger.error(f"🔥 Database Error when fetching voiceprint list: {str(e)} - Type: {type(e).__name__}")
        return default_voiceprints
    finally:
        if connection:
            db.close()

# 新增函数：根据设备MAC地址获取设备配置（人设和记忆）
async def get_device_config(jabobo_id: str) -> tuple:
    """
    根据设备ID获取设备特定的配置（人设和记忆）
    """
    default_prompt = "你叫捷宝宝，今年三岁了。\n最喜欢和小朋友聊天，回答他们各种各样的问题，给他们讲故事。\n除非小朋友要求你讲故事，这时候将对话控制内容控制在150字以内。\n\n"
    default_memory = "捷宝宝的主要开发人员：除了天豪 ，Alice Lin， Roshan Gao，以及simulation team的小伙伴们，还有AI专家Thomas Du, 硬件大佬Kris Chen,用户体验设计师Alessia Zhang，\n此外，还有特邀顾问团队。"

    if not jabobo_id:
        return default_prompt, default_memory
    
    connection = None
    try:
        connection = db.connect()
        if not connection:
            logger.error("🔥 Database connection failed")
            return default_prompt, default_memory
        
        sql = "SELECT personas, memory FROM user_personas WHERE jabobo_id = %s"
        cursor = db.cursor
        cursor.execute(sql, (jabobo_id,))
        result = cursor.fetchone()
        
        logger.debug(f"🔍 Query result for {jabobo_id}: {result}")
        
        if result:
            if isinstance(result, dict):
                personas_json = result['personas']
                memory_content = result.get('memory', '')
            else:
                personas_json = result[0]
                memory_content = result[1] if len(result) > 1 else ''
            
            logger.debug(f"🔍 Personas JSON: {personas_json}")
            logger.debug(f"🔍 Memory content: {memory_content}")
            
            if personas_json:
                personas_list = json.loads(personas_json)
                logger.debug(f"🔍 Personas list: {personas_list}")
                
                if personas_list and len(personas_list) > 0:
                    first_persona = personas_list[0]
                    device_prompt = json.dumps(first_persona, ensure_ascii=False)
                    return device_prompt, memory_content or "设备没有特定记忆信息"
            
            return default_prompt, memory_content or "设备没有特定记忆信息"
        else:
            logger.warning(f"⚠️ No config found for device ID: {jabobo_id}")
            return default_prompt, default_memory
    except json.JSONDecodeError as e:
        logger.error(f"🔥 JSON Decode Error when fetching device config: {str(e)}")
        return default_prompt, default_memory
    except Exception as e:
        logger.error(f"🔥 Database Error when fetching device config: {str(e)} - Type: {type(e).__name__}")
        return default_prompt, default_memory
    finally:
        if connection:
            db.close()
            
def verify_device_exists(mac_address: str):
    """
    验证设备是否存在
    """
    if not db.connect():
        logger.error("❌ 数据库连接失败")
        raise HTTPException(status_code=500, detail="数据库连接失败")
    
    try:
        sql = "SELECT jabobo_id FROM user_personas WHERE jabobo_id = %s"
        db.cursor.execute(sql, (mac_address,))
        device = db.cursor.fetchone()
        return True if device else False
    finally:
        db.close()

@router.put("/agent/saveMemory/{mac_address}")
async def save_memory(
    mac_address: str = Path(..., description="设备MAC地址"),
    summary_memory: Dict[str, Any] = None,
    user_agent: str = Header(..., alias="User-Agent"),
    accept: str = Header(..., alias="Accept"),
    authorization: str = Header(..., alias="Authorization")
):
    """
    保存短期记忆到服务器
    """
    logger.info(f"🧠 [MEMORY SAVE] Request received for MAC: {mac_address}")
    logger.debug(f"   User-Agent: {user_agent}")
    logger.debug(f"   Accept: {accept}")
    logger.debug(f"   Authorization: {authorization}")
    
    if not authorization.startswith("Bearer "):
        return {
            "code": 401,
            "data": None,
            "msg": "Authorization header format must be 'Bearer {token}'"
        }
    
    if not verify_device_exists(mac_address):
        logger.warning(f"❌ [MEMORY SAVE] Device with MAC {mac_address} not found")
        return {
            "code": 10041,
            "data": None,
            "msg": "设备未找到异常"
        }
    
    if not summary_memory or "summaryMemory" not in summary_memory:
        return {
            "code": 400,
            "data": None,
            "msg": "请求体中必须包含summaryMemory字段"
        }
    
    summary_content = summary_memory["summaryMemory"]
    
    if not db.connect():
        return {
            "code": 500,
            "data": None,
            "msg": "数据库连接失败"
        }
    
    try:
        sql = """
            UPDATE user_personas 
            SET memory = %s 
            WHERE jabobo_id = %s
        """
        db.cursor.execute(sql, (summary_content, mac_address))
        
        if db.cursor.rowcount == 0:
            logger.warning(f"❌ [MEMORY SAVE] No device found with MAC {mac_address}")
            return {
                "code": 10041,
                "data": None,
                "msg": "设备未找到异常"
            }
        
        logger.success(f"✅ [MEMORY SAVE] Memory updated successfully for MAC: {mac_address}")
        logger.debug(f"   New memory content: {summary_content[:100]}...")
        
        return {
            "code": 0,
            "data": {
                "mac_address": mac_address,
                "summary_memory": summary_content
            },
            "msg": "短期记忆保存成功"
        }
        
    except Exception as e:
        logger.error(f"❌ [MEMORY SAVE] Error saving memory for MAC {mac_address}: {str(e)}")
        return {
            "code": 500,
            "data": None,
            "msg": f"保存记忆时发生错误: {str(e)}"
        }
    finally:
        db.close()

@router.delete("/agent/clearMemory/{mac_address}")
async def clear_memory(
    mac_address: str = Path(..., description="设备MAC地址"),
    user_agent: str = Header(..., alias="User-Agent"),
    accept: str = Header(..., alias="Accept"),
    authorization: str = Header(..., alias="Authorization")
):
    """
    清除设备的短期记忆
    """
    logger.info(f"🧹 [MEMORY CLEAR] Request received for MAC: {mac_address}")

    if not authorization.startswith("Bearer "):
        return {
            "code": 401,
            "data": None,
            "msg": "Authorization header format must be 'Bearer {token}'"
        }

    if not verify_device_exists(mac_address):
        logger.warning(f"❌ [MEMORY CLEAR] Device with MAC {mac_address} not found")
        return {
            "code": 10041,
            "data": None,
            "msg": "设备未找到异常"
        }

    if not db.connect():
        return {
            "code": 500,
            "data": None,
            "msg": "数据库连接失败"
        }

    try:
        # 先查看当前记忆
        select_sql = "SELECT memory FROM user_personas WHERE jabobo_id = %s"
        db.cursor.execute(select_sql, (mac_address,))
        result = db.cursor.fetchone()

        if result and result.get('memory'):
            current_memory = result['memory']
            logger.info(f"📝 [MEMORY CLEAR] Current memory: {current_memory[:100]}...")

        # 清除记忆
        update_sql = "UPDATE user_personas SET memory = NULL WHERE jabobo_id = %s"
        db.cursor.execute(update_sql, (mac_address,))

        if db.cursor.rowcount == 0:
            logger.warning(f"❌ [MEMORY CLEAR] No device found with MAC {mac_address}")
            return {
                "code": 10041,
                "data": None,
                "msg": "设备未找到异常"
            }

        logger.success(f"✅ [MEMORY CLEAR] Memory cleared successfully for MAC: {mac_address}")

        return {
            "code": 0,
            "data": {
                "mac_address": mac_address
            },
            "msg": "记忆清除成功，AI将恢复默认行为"
        }

    except Exception as e:
        logger.error(f"❌ [MEMORY CLEAR] Error clearing memory for MAC {mac_address}: {str(e)}")
        return {
            "code": 500,
            "data": None,
            "msg": f"清除记忆时发生错误: {str(e)}"
        }
    finally:
        db.close()