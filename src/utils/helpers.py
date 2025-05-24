"""
工具函数和辅助方法
"""

import re
import asyncio
import functools
from typing import Tuple, Optional, Dict, Any, Callable, Union
from ..core.exceptions import ValidationError, TimeoutError


def validate_address(address: str) -> bool:
    """
    验证地址格式是否合理
    
    Args:
        address: 待验证的地址字符串
        
    Returns:
        bool: 地址格式是否有效
    """
    if not address or not isinstance(address, str):
        return False
    
    # 去除首尾空格
    address = address.strip()
    
    # 基本长度检查
    if len(address) < 2 or len(address) > 200:
        return False
    
    # 检查是否包含中文字符或常见地址关键词
    chinese_pattern = r'[\u4e00-\u9fff]'
    address_keywords = ['省', '市', '区', '县', '镇', '街道', '路', '号', '栋', '楼', '室']
    
    has_chinese = bool(re.search(chinese_pattern, address))
    has_address_keyword = any(keyword in address for keyword in address_keywords)
    
    return has_chinese or has_address_keyword


def parse_coordinates(coord_str: str) -> Tuple[Optional[float], Optional[float]]:
    """
    解析坐标字符串
    
    Args:
        coord_str: 坐标字符串，格式如 "116.397428,39.90923" 或 "116.397428, 39.90923"
        
    Returns:
        Tuple[Optional[float], Optional[float]]: (经度, 纬度)
    """
    if not coord_str or not isinstance(coord_str, str):
        return None, None
    
    try:
        # 清理字符串并分割
        coord_str = coord_str.strip().replace(' ', '')
        parts = coord_str.split(',')
        
        if len(parts) != 2:
            return None, None
        
        longitude = float(parts[0])
        latitude = float(parts[1])
        
        # 验证坐标范围（中国境内大致范围）
        if not (-180 <= longitude <= 180 and -90 <= latitude <= 90):
            return None, None
            
        return longitude, latitude
        
    except (ValueError, IndexError):
        return None, None


def format_amap_response(response: Dict[str, Any]) -> Dict[str, Any]:
    """
    格式化高德地图API响应
    
    Args:
        response: 高德地图API原始响应
        
    Returns:
        Dict[str, Any]: 格式化后的响应
    """
    if not isinstance(response, dict):
        return {"error": "无效的响应格式"}
    
    # 提取常用字段
    formatted = {
        "success": True,
        "data": {},
        "raw_response": response
    }
    
    # 处理地理编码响应
    if "geocodes" in response:
        geocodes = response.get("geocodes", [])
        if geocodes:
            geocode = geocodes[0]  # 取第一个结果
            formatted["data"] = {
                "formatted_address": geocode.get("formatted_address", ""),
                "province": geocode.get("province", ""),
                "city": geocode.get("city", ""),
                "district": geocode.get("district", ""),
                "township": geocode.get("township", ""),
                "street": geocode.get("street", ""),
                "number": geocode.get("number", ""),
                "location": geocode.get("location", ""),
                "level": geocode.get("level", ""),
                "confidence": geocode.get("confidence", "")
            }
    
    # 处理逆地理编码响应
    elif "regeocode" in response:
        regeocode = response.get("regeocode", {})
        formatted["data"] = {
            "formatted_address": regeocode.get("formatted_address", ""),
            "addressComponent": regeocode.get("addressComponent", {}),
            "pois": regeocode.get("pois", []),
            "roads": regeocode.get("roads", []),
            "roadinters": regeocode.get("roadinters", []),
            "aois": regeocode.get("aois", [])
        }
    
    # 处理错误响应
    elif "info" in response and response.get("status") != "1":
        formatted["success"] = False
        formatted["error"] = {
            "code": response.get("infocode", ""),
            "message": response.get("info", "未知错误")
        }
    
    return formatted


def retry_async(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: Tuple = (Exception,)
) -> Callable:
    """
    异步函数重试装饰器
    
    Args:
        max_retries: 最大重试次数
        delay: 初始延迟时间（秒）
        backoff_factor: 退避因子
        exceptions: 需要重试的异常类型
        
    Returns:
        装饰器函数
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        # 最后一次尝试失败，抛出异常
                        break
                    
                    # 等待后重试
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff_factor
            
            # 抛出最后一次的异常
            raise last_exception
        
        return wrapper
    return decorator


def safe_get(data: Dict[str, Any], key_path: str, default: Any = None) -> Any:
    """
    安全获取嵌套字典中的值
    
    Args:
        data: 字典数据
        key_path: 键路径，用点分隔，如 "a.b.c"
        default: 默认值
        
    Returns:
        获取到的值或默认值
    """
    if not isinstance(data, dict):
        return default
    
    keys = key_path.split('.')
    current = data
    
    try:
        for key in keys:
            current = current[key]
        return current
    except (KeyError, TypeError, IndexError):
        return default


def generate_request_id() -> str:
    """
    生成请求ID
    
    Returns:
        str: 唯一的请求ID
    """
    import uuid
    import time
    
    timestamp = int(time.time() * 1000)
    unique_id = str(uuid.uuid4()).replace('-', '')[:8]
    
    return f"{timestamp}_{unique_id}"


def validate_coordinates(longitude: float, latitude: float) -> bool:
    """
    验证坐标是否在合理范围内
    
    Args:
        longitude: 经度
        latitude: 纬度
        
    Returns:
        bool: 坐标是否有效
    """
    # 基本范围检查
    if not (-180 <= longitude <= 180 and -90 <= latitude <= 90):
        return False
    
    # 中国大陆范围大致检查（可选）
    # 经度范围：73°E - 135°E
    # 纬度范围：18°N - 54°N
    china_bounds = {
        "min_lng": 73.0,
        "max_lng": 135.0, 
        "min_lat": 18.0,
        "max_lat": 54.0
    }
    
    return (china_bounds["min_lng"] <= longitude <= china_bounds["max_lng"] and
            china_bounds["min_lat"] <= latitude <= china_bounds["max_lat"])