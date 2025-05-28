"""
工具函数模块
提供数据处理脚本所需的辅助功能
"""

import json
from typing import List, Dict, Any
import os


def read_json_file(file_path: str) -> List[Dict[str, Any]]:
    """
    读取JSON文件内容
    
    Args:
        file_path: JSON文件路径
        
    Returns:
        JSON数据列表
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def write_json_file(data: List[Dict[str, Any]], file_path: str) -> None:
    """
    将数据写入JSON文件
    
    Args:
        data: 要写入的数据列表
        file_path: 目标文件路径
    """
    # 确保目录存在
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    # 写入文件
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)