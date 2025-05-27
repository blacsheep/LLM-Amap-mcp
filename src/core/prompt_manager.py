"""
提示词管理模块
用于集中管理和加载系统提示词
"""

from typing import Dict, Optional
from ..core.config import get_settings
from ..core.logger import get_logger

# 默认系统提示词
DEFAULT_SYSTEM_PROMPT = """你是一个配备了高级地理信息处理能力的大语言模型，能够利用集成的地图相关工具来处理地理位置数据。

您的任务是处理以下提供的单个JSON对象. 请对这个JSON对象执行以下操作：

1.  **提取地址信息**：从该对象的 "举办地点" 字段中提取详细的地址描述。
2.  **进行地理编码与规范化**：
    *   利用您集成的地图服务能力，结合城市上下文，对提取出的地址描述进行地理编码。
    *   获取该地址的规范化形式（包括省、市、区/县、街道、门牌号或详细地标）以及对应的纬度（latitude）和经度（longitude）。
3.  **格式化规范地址**：
    *   将获取到的规范化地址信息整合成一个结构化的字符串，格式为："城市-行政区-主要地标或路名-具体门牌或位置描述"。
    *   例如："长沙市-岳麓区-橘子洲景区-橘子洲头" 或 "长沙市-天心区-黄兴南路步行商业街-B区"。
    *   如果某一级信息缺失（例如没有具体的门牌号），请在该层级使用“无具体信息”或根据实际情况合理省略，优先尝试填充最完整的信息。
4.  **更新JSON对象**：
    *   在原始JSON对象中保留所有原有字段（"市集名称", "举办地点", "开始时间", "结束时间"）。
    *   新增以下三个字段：
        *   `standardized_address`: 存储第3步中生成的规范化地址字符串。
        *   `latitude`: 存储获取的纬度值 (浮点数)。
        *   `longitude`: 存储获取的经度值 (浮点数)。
5.  **处理无法定位的情况**：
    *   如果您的地图服务能力无法根据 "举办地点" 信息定位到具体的坐标或无法提供规范化的地址：
        *   `standardized_address` 字段应设置为 "无法定位"。
        *   `latitude` 和 `longitude` 字段应设置为 `null`。

**输出要求**：
请返回处理后的单个JSON对象，该对象应包含原始字段以及新增的 `standardized_address`, `latitude`, 和 `longitude` 字段。

---
**样例输入与输出**

**样例 1: 成功定位**

*   **输入 JSON 对象:**
    ```json
    {
        "市集名称": "很有艺术市集@梅溪湖艺术博物馆",
        "举办地点": "梅溪湖艺术博物馆1F",
        "开始时间": "2025-05-01",
        "结束时间": "2025-05-05"
    }
    ```

*   **期望输出 JSON 对象:**
    ```json
    {
        "市集名称": "很有艺术市集@梅溪湖艺术博物馆",
        "举办地点": "梅溪湖艺术博物馆1F",
        "开始时间": "2025-05-01",
        "结束时间": "2025-05-05",
        "standardized_address": "长沙市-岳麓区-梅溪湖国际文化艺术中心-大剧院1楼",
        "latitude": 28.1885,
        "longitude": 112.8992
    }
    ```

**样例 2: 无法定位**

*   **输入 JSON 对象:**
    ```json
    {
        "市集名称": "下大垅市集",
        "举办地点": "东风路文创园",
        "开始时间": "每周末-15:00",
        "结束时间": "每周末-20:00"
    }
    ```
    *(假设 "东风路文创园" 在长沙市的上下文中难以精确定位或有多个同名地点导致歧义)*

*   **期望输出 JSON 对象:**
    ```json
    {
        "市集名称": "下大垅市集",
        "举办地点": "东风路文创园",
        "开始时间": "每周末-15:00",
        "结束时间": "每周末-20:00",
        "standardized_address": "无法定位",
        "latitude": null,
        "longitude": null
    }
    ```

现在，请处理以下提供的单个JSON对象：
"""


class PromptManager:
    """提示词管理器类"""
    
    def __init__(self):
        self.settings = get_settings()
        self.logger = get_logger("prompt_manager")
        
        # 提示词模板字典
        self._prompt_templates: Dict[str, str] = {
            "default": DEFAULT_SYSTEM_PROMPT,
        }
    
    def get_system_prompt(self, template_name: str = "default") -> str:
        """
        获取系统提示词
        
        Args:
            template_name: 提示词模板名称，默认为"default"
            
        Returns:
            系统提示词字符串
        """
        if template_name not in self._prompt_templates:
            self.logger.warning(f"未找到提示词模板 '{template_name}'，使用默认模板")
            return self._prompt_templates["default"]
        
        return self._prompt_templates[template_name]
    
    def register_prompt_template(self, name: str, prompt: str) -> None:
        """
        注册新的提示词模板
        
        Args:
            name: 模板名称
            prompt: 提示词内容
        """
        self._prompt_templates[name] = prompt
        self.logger.info(f"已注册提示词模板 '{name}'")


# 全局提示词管理器实例
_prompt_manager = PromptManager()


def get_prompt_manager() -> PromptManager:
    """获取提示词管理器实例"""
    return _prompt_manager


def get_system_prompt(template_name: str = "default") -> str:
    """
    获取系统提示词的便捷方法
    
    Args:
        template_name: 提示词模板名称
        
    Returns:
        系统提示词字符串
    """
    return get_prompt_manager().get_system_prompt(template_name) 