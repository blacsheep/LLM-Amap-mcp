"""
数据处理器模块
处理JSON数据并调用大模型进行处理
"""

import asyncio
import json
from typing import List, Dict, Any, Optional
import tqdm

from src.core.prompt_manager import get_system_prompt
from src.mcp_client.amap_client import AmapMCPClient
from src.mcp_client.llm_factory import create_llm_handler
from src.core.logger import get_logger


def extract_valid_json(text: str) -> Optional[Dict[str, Any]]:
    """
    从文本中提取有效的JSON对象，确保包含所需字段
    
    Args:
        text: 包含JSON的文本
    
    Returns:
        解析后的JSON字典，如果没有找到符合条件的JSON则返回None
    """
    # 所需的字段
    required_fields = ["standardized_address", "latitude", "longitude"]
    
    # 检查提取的JSON是否有效且包含所需字段
    def is_valid_json(json_obj: Dict[str, Any]) -> bool:
        return all(field in json_obj for field in required_fields)
    
    # 提取所有可能的JSON对象
    i = 0
    while i < len(text):
        # 查找开始括号
        start_idx = text.find('{', i)
        if start_idx == -1:
            break
        
        # 尝试找到匹配的结束括号
        bracket_count = 1
        end_idx = start_idx + 1
        
        while end_idx < len(text) and bracket_count > 0:
            if text[end_idx] == '{':
                bracket_count += 1
            elif text[end_idx] == '}':
                bracket_count -= 1
            end_idx += 1
        
        if bracket_count == 0:  # 找到匹配的括号
            json_str = text[start_idx:end_idx]
            try:
                json_obj = json.loads(json_str)
                if isinstance(json_obj, dict) and is_valid_json(json_obj):
                    return json_obj
            except json.JSONDecodeError:
                pass  # 继续寻找下一个可能的JSON
        
        # 继续从当前开始括号的下一个位置查找
        i = start_idx + 1
    
    return None


class DataProcessor:
    """数据处理器类"""
    
    def __init__(self):
        """初始化数据处理器"""
        self.logger = get_logger("data_processor")
        self.amap_client = None
        self.llm_handler = None
    
    async def connect(self) -> None:
        """
        连接到MCP客户端和LLM处理器
        
        Raises:
            Exception: 连接失败时抛出异常
        """
        try:
            self.logger.info("正在连接到MCP客户端和LLM处理器")
            self.amap_client = AmapMCPClient()
            await self.amap_client.connect()
            self.llm_handler = create_llm_handler(self.amap_client)
            self.logger.info("连接成功")
        except Exception as e:
            self.logger.error(f"连接失败: {e}")
            raise
    
    async def disconnect(self) -> None:
        """断开连接"""
        if self.amap_client:
            await self.amap_client.disconnect()
            self.logger.info("已断开MCP客户端连接")
    
    async def process_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理单个数据项
        
        Args:
            item: 要处理的数据项
            
        Returns:
            处理后的数据项
        """
        try:
            # 将数据项转换为JSON字符串
            item_json = json.dumps(item, ensure_ascii=False)
            
            # 获取系统提示词
            system_prompt = get_system_prompt()
            
            # 调用LLM处理
            result = await self.llm_handler.process_query(
                query=item_json,
                system_prompt=system_prompt
            )
            
            # 提取处理后的数据
            response_text = result.get("response", "")
            
            # 使用改进的JSON提取方法
            processed_item = extract_valid_json(response_text)
            
            if processed_item:
                self.logger.info("成功从响应中提取到有效JSON数据")
                return processed_item
            
            # 如果响应中没有找到有效的JSON，检查其他结果字段
            if "data" in result and isinstance(result["data"], dict) and all(
                field in result["data"] for field in ["standardized_address", "latitude", "longitude"]
            ):
                self.logger.info("从result.data中提取到有效JSON数据")
                return result["data"]
            
            # 尝试直接解析完整响应文本作为JSON
            try:
                full_json = json.loads(response_text)
                if isinstance(full_json, dict) and all(
                    field in full_json for field in ["standardized_address", "latitude", "longitude"]
                ):
                    self.logger.info("成功将完整响应解析为有效JSON")
                    return full_json
            except json.JSONDecodeError:
                pass
            
            # 如果无法找到有效的JSON，记录警告并返回原始数据
            self.logger.warning(f"无法从响应中提取包含所需字段的有效JSON数据")
            return item
            
        except Exception as e:
            self.logger.error(f"处理数据项时出错: {e}")
            return item  # 返回原始数据
    
    async def process_batch(self, items: List[Dict[str, Any]], batch_size: int = 1) -> List[Dict[str, Any]]:
        """
        批量处理数据项
        
        Args:
            items: 要处理的数据项列表
            batch_size: 批处理大小
            
        Returns:
            处理后的数据项列表
        """
        self.logger.info(f"开始处理 {len(items)} 个数据项")
        results = []
        
        # 处理每个批次
        for i in range(0, len(items), batch_size):
            batch = items[i:i+batch_size]
            batch_tasks = [self.process_item(item) for item in batch]
            batch_results = await asyncio.gather(*batch_tasks)
            results.extend(batch_results)
            self.logger.info(f"已处理 {min(i+batch_size, len(items))}/{len(items)} 个数据项")
        
        return results