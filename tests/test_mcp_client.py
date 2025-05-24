"""
MCP客户端单元测试
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.mcp_client.amap_client import AmapMCPClient
from src.mcp_client.claude_handler import ClaudeHandler
from src.core.exceptions import MCPConnectionError, ClaudeAPIError
from src.utils.helpers import validate_address, parse_coordinates, format_amap_response


class TestAmapMCPClient:
    """高德MCP客户端测试"""
    
    @pytest.fixture
    async def mock_amap_client(self):
        """创建模拟的高德MCP客户端"""
        client = AmapMCPClient()
        
        # 模拟连接状态
        client.is_connected = True
        client.session = AsyncMock()
        client._available_tools = [
            {
                "name": "geocode",
                "description": "地理编码",
                "input_schema": {"type": "object"}
            }
        ]
        
        return client
    
    @pytest.mark.asyncio
    async def test_connect_success(self):
        """测试成功连接"""
        with patch.object(AmapMCPClient, '_start_amap_server') as mock_start, \
             patch.object(AmapMCPClient, '_establish_mcp_connection') as mock_establish, \
             patch.object(AmapMCPClient, '_initialize_session') as mock_init, \
             patch.object(AmapMCPClient, '_load_available_tools') as mock_load:
            
            mock_start.return_value = None
            mock_establish.return_value = None
            mock_init.return_value = None
            mock_load.return_value = None
            
            client = AmapMCPClient()
            await client.connect()
            
            assert client.is_connected is True
            mock_start.assert_called_once()
            mock_establish.assert_called_once()
            mock_init.assert_called_once()
            mock_load.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_connect_failure(self):
        """测试连接失败"""
        with patch.object(AmapMCPClient, '_start_amap_server') as mock_start:
            mock_start.side_effect = Exception("启动失败")
            
            client = AmapMCPClient()
            
            with pytest.raises(MCPConnectionError):
                await client.connect()
            
            assert client.is_connected is False
    
    @pytest.mark.asyncio
    async def test_call_tool_success(self, mock_amap_client):
        """测试成功调用工具"""
        # 模拟工具调用结果
        mock_result = Mock()
        mock_result.content = {"location": "116.397428,39.90923"}
        mock_amap_client.session.call_tool.return_value = mock_result
        
        result = await mock_amap_client.call_tool("geocode", {"address": "北京"})
        
        assert result == {"location": "116.397428,39.90923"}
        mock_amap_client.session.call_tool.assert_called_once_with(
            "geocode", {"address": "北京"}
        )
    
    @pytest.mark.asyncio
    async def test_call_tool_not_connected(self):
        """测试未连接时调用工具"""
        client = AmapMCPClient()
        client.is_connected = False
        
        with pytest.raises(MCPConnectionError):
            await client.call_tool("geocode", {"address": "北京"})
    
    @pytest.mark.asyncio
    async def test_health_check_success(self, mock_amap_client):
        """测试健康检查成功"""
        mock_amap_client.session.list_tools.return_value = Mock()
        
        result = await mock_amap_client.health_check()
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_health_check_failure(self, mock_amap_client):
        """测试健康检查失败"""
        mock_amap_client.session.list_tools.side_effect = Exception("连接失败")
        
        result = await mock_amap_client.health_check()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_list_available_tools(self, mock_amap_client):
        """测试获取可用工具列表"""
        tools = await mock_amap_client.list_available_tools()
        
        assert len(tools) == 1
        assert tools[0]["name"] == "geocode"
        assert tools[0]["description"] == "地理编码"


class TestClaudeHandler:
    """Claude处理器测试"""
    
    @pytest.fixture
    def mock_claude_handler(self):
        """创建模拟的Claude处理器"""
        mock_amap_client = Mock()
        mock_amap_client.list_available_tools.return_value = [
            {
                "name": "geocode",
                "description": "地理编码",
                "input_schema": {"type": "object"}
            }
        ]
        
        handler = ClaudeHandler(mock_amap_client)
        handler.anthropic = AsyncMock()
        
        return handler
    
    @pytest.mark.asyncio
    async def test_process_query_success(self, mock_claude_handler):
        """测试成功处理查询"""
        # 模拟Claude响应
        mock_response = Mock()
        mock_content = Mock()
        mock_content.type = 'text'
        mock_content.text = "地址解析结果"
        mock_response.content = [mock_content]
        
        mock_claude_handler.anthropic.messages.create.return_value = mock_response
        
        result = await mock_claude_handler.process_query("北京市朝阳区")
        
        assert result["success"] is True
        assert "地址解析结果" in result["response"]
    
    @pytest.mark.asyncio
    async def test_process_query_with_tool_call(self, mock_claude_handler):
        """测试带工具调用的查询处理"""
        # 模拟工具调用
        mock_tool_call = Mock()
        mock_tool_call.type = 'tool_use'
        mock_tool_call.name = 'geocode'
        mock_tool_call.input = {'address': '北京'}
        mock_tool_call.id = 'tool_123'
        
        # 模拟第一次响应（包含工具调用）
        mock_response1 = Mock()
        mock_response1.content = [mock_tool_call]
        
        # 模拟第二次响应（工具调用后）
        mock_response2 = Mock()
        mock_content = Mock()
        mock_content.type = 'text'
        mock_content.text = "根据工具调用结果，地址解析完成"
        mock_response2.content = [mock_content]
        
        mock_claude_handler.anthropic.messages.create.side_effect = [
            mock_response1, mock_response2
        ]
        
        # 模拟工具调用结果
        mock_claude_handler.amap_client.call_tool.return_value = {
            "location": "116.397428,39.90923"
        }
        
        result = await mock_claude_handler.process_query("北京市朝阳区")
        
        assert result["success"] is True
        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["tool_name"] == "geocode"
    
    @pytest.mark.asyncio
    async def test_process_query_failure(self, mock_claude_handler):
        """测试查询处理失败"""
        mock_claude_handler.anthropic.messages.create.side_effect = Exception("API错误")
        
        with pytest.raises(ClaudeAPIError):
            await mock_claude_handler.process_query("测试查询")


class TestHelpers:
    """工具函数测试"""
    
    def test_validate_address_valid(self):
        """测试有效地址验证"""
        assert validate_address("北京市朝阳区三里屯") is True
        assert validate_address("上海市浦东新区陆家嘴金融中心") is True
        assert validate_address("广州市天河区珠江新城") is True
    
    def test_validate_address_invalid(self):
        """测试无效地址验证"""
        assert validate_address("") is False
        assert validate_address(None) is False
        assert validate_address("a") is False
        assert validate_address("x" * 201) is False
    
    def test_parse_coordinates_valid(self):
        """测试有效坐标解析"""
        lng, lat = parse_coordinates("116.397428,39.90923")
        assert lng == 116.397428
        assert lat == 39.90923
        
        lng, lat = parse_coordinates("116.397428, 39.90923")
        assert lng == 116.397428
        assert lat == 39.90923
    
    def test_parse_coordinates_invalid(self):
        """测试无效坐标解析"""
        assert parse_coordinates("") == (None, None)
        assert parse_coordinates("invalid") == (None, None)
        assert parse_coordinates("116.397428") == (None, None)
        assert parse_coordinates("200,100") == (None, None)
    
    def test_format_amap_response_geocode(self):
        """测试格式化地理编码响应"""
        response = {
            "status": "1",
            "geocodes": [
                {
                    "formatted_address": "北京市朝阳区三里屯太古里",
                    "province": "北京市",
                    "city": "北京市",
                    "district": "朝阳区",
                    "location": "116.397428,39.90923"
                }
            ]
        }
        
        formatted = format_amap_response(response)
        
        assert formatted["success"] is True
        assert formatted["data"]["formatted_address"] == "北京市朝阳区三里屯太古里"
        assert formatted["data"]["province"] == "北京市"
        assert formatted["data"]["location"] == "116.397428,39.90923"
    
    def test_format_amap_response_error(self):
        """测试格式化错误响应"""
        response = {
            "status": "0",
            "info": "INVALID_USER_KEY",
            "infocode": "10001"
        }
        
        formatted = format_amap_response(response)
        
        assert formatted["success"] is False
        assert formatted["error"]["code"] == "10001"
        assert formatted["error"]["message"] == "INVALID_USER_KEY"


class TestIntegration:
    """集成测试"""
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_full_workflow(self):
        """测试完整工作流程（需要真实API密钥）"""
        # 这个测试需要真实的API密钥，通常在CI/CD中跳过
        pytest.skip("需要真实API密钥的集成测试")
        
        # 如果有API密钥，可以进行真实测试
        # client = AmapMCPClient()
        # await client.connect()
        # 
        # handler = ClaudeHandler(client)
        # result = await handler.process_query("北京市朝阳区")
        # 
        # assert result["success"] is True
        # await client.disconnect()


# 测试配置
@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# 运行测试的主函数
if __name__ == "__main__":
    pytest.main([__file__, "-v"])