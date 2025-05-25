# 高德地址解析服务

基于Claude AI和高德地图MCP的智能地址解析服务，提供强大的地址解析、地理编码和位置信息查询功能。

## 🚀 功能特性

- **智能地址解析**: 使用Claude AI理解自然语言地址查询
- **高德地图集成**: 通过MCP协议集成高德地图API
- **多种查询方式**: 支持地址转坐标、坐标转地址、POI搜索等
- **RESTful API**: 提供完整的HTTP API接口
- **异步处理**: 高性能异步架构，支持并发请求
- **健康监控**: 完善的健康检查和监控机制
- **错误处理**: 完善的异常处理和错误恢复机制

## 📋 系统要求

- Python 3.10+
- Node.js 16+ (用于高德MCP服务器)
- 高德地图API密钥
- Claude API密钥

## 🛠️ 安装配置

### 1. 克隆项目

```bash
git clone <repository-url>
cd address-parser-service
```

### 2. 创建Python环境

#### 方式一：使用pip（推荐）

```bash
# 创建虚拟环境
python -m venv address-parser-env

# 激活虚拟环境
# Windows:
address-parser-env\Scripts\activate
# macOS/Linux:
source address-parser-env/bin/activate

# 安装依赖
pip install -r requirements.txt
```

#### 方式二：使用conda

```bash
# 方法1: 使用environment.yml文件（推荐）
conda env create -f environment.yml
conda activate address-parser

# 方法2: 手动创建环境
conda create -n address-parser python=3.11
conda activate address-parser

# 安装依赖
pip install -r requirements.txt

# 或者使用conda安装部分依赖
conda install fastapi uvicorn pydantic
pip install mcp anthropic structlog pydantic-settings
```

### 3. 配置环境变量

复制环境变量模板：

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入你的API密钥：

```env
# Claude API配置
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# 高德地图API配置  
AMAP_MAPS_API_KEY=your_amap_api_key_here

# 其他配置保持默认即可
```

### 4. 获取API密钥

#### 高德地图API密钥
1. 访问 [高德开放平台](https://lbs.amap.com/)
2. 注册账号并创建应用
3. 获取Web服务API密钥

#### Claude API密钥
1. 访问 [Anthropic Console](https://console.anthropic.com/)
2. 创建账号并获取API密钥

## 🚀 快速开始

### 方式一：使用示例脚本

```bash
# 激活环境（如果使用虚拟环境）
# pip环境:
source address-parser-env/bin/activate  # macOS/Linux
# 或
address-parser-env\Scripts\activate     # Windows

# conda环境:
conda activate address-parser

# 运行基础使用示例
python examples/basic_usage.py
```

### 方式二：启动API服务

```bash
# 启动FastAPI服务
python api/main.py
```

服务启动后访问：
- API文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/api/v1/health

### 方式三：直接使用MCP客户端

```python
import asyncio
from src.mcp_client import AmapMCPClient, ClaudeHandler

async def main():
    # 创建MCP客户端
    async with AmapMCPClient() as amap_client:
        # 创建Claude处理器
        claude_handler = ClaudeHandler(amap_client)
        
        # 处理查询
        result = await claude_handler.process_query(
            "请帮我解析这个地址：北京市朝阳区三里屯太古里"
        )
        
        print(result["final_answer"])

asyncio.run(main())
```

## 📖 API文档

### 地址解析接口

**POST** `/api/v1/address/parse`

请求体：
```json
{
    "address": "北京市朝阳区三里屯太古里",
    "context": {
        "city": "北京",
        "preferences": "详细地址信息"
    },
    "system_prompt": "请提供详细的地址解析结果"
}
```

响应：
```json
{
    "success": true,
    "request_id": "1642123456789_abc12345",
    "data": {
        "formatted_address": "北京市朝阳区三里屯太古里",
        "location": "116.397428,39.90923",
        "province": "北京市",
        "city": "北京市",
        "district": "朝阳区"
    },
    "response": "根据您提供的地址，我已经成功解析出详细信息...",
    "tool_calls": [...],
    "processing_time": 2.5
}
```

### 健康检查接口

**GET** `/api/v1/health`

响应：
```json
{
    "status": "healthy",
    "mcp_connected": true,
    "claude_available": true,
    "tools_count": 5,
    "uptime": 3600.0
}
```

### 工具列表接口

**GET** `/api/v1/tools`

响应：
```json
{
    "success": true,
    "tools": [
        {
            "name": "geocode",
            "description": "地理编码，将地址转换为坐标",
            "input_schema": {...}
        }
    ],
    "count": 1
}
```

## 🔧 高级配置

### MCP服务器管理

使用内置的服务器管理脚本：

```bash
# 启动高德MCP服务器
python scripts/start_amap_server.py start

# 停止服务器
python scripts/start_amap_server.py stop

# 重启服务器
python scripts/start_amap_server.py restart

# 查看状态
python scripts/start_amap_server.py status

# 监控模式（自动重启）
python scripts/start_amap_server.py monitor
```

### 配置参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `MCP_SERVER_TIMEOUT` | 30 | MCP服务器超时时间（秒） |
| `MCP_RETRY_COUNT` | 3 | 重试次数 |
| `MCP_RETRY_DELAY` | 1.0 | 重试延迟（秒） |
| `LOG_LEVEL` | INFO | 日志级别 |
| `API_HOST` | 127.0.0.1 | API服务主机 |
| `API_PORT` | 8000 | API服务端口 |

## 🧪 测试

### 运行单元测试

```bash
# 运行所有测试
pytest tests/

# 运行特定测试文件
pytest tests/test_mcp_client.py -v

# 运行集成测试（需要API密钥）
pytest tests/ -m integration
```

### 测试覆盖率

```bash
# 生成测试覆盖率报告
pytest --cov=src tests/
```

## 📁 项目结构

```
address-parser-service/
├── src/                    # 核心源代码
│   ├── mcp_client/        # MCP客户端模块
│   │   ├── amap_client.py # 高德MCP客户端
│   │   └── claude_handler.py # Claude处理器
│   ├── core/              # 核心模块
│   │   ├── config.py      # 配置管理
│   │   ├── logger.py      # 日志配置
│   │   └── exceptions.py  # 异常定义
│   └── utils/             # 工具函数
│       └── helpers.py     # 辅助函数
├── api/                   # API服务模块
│   ├── main.py           # FastAPI主应用
│   ├── routes/           # API路由
│   └── schemas/          # 数据模型
├── tests/                # 测试代码
├── scripts/              # 脚本文件
├── examples/             # 使用示例
├── logs/                 # 日志文件
├── requirements.txt      # Python依赖
├── .env.example         # 环境变量模板
└── README.md            # 项目文档
```

## 🔍 使用示例

### 基础地址解析

```python
# 地址转坐标
query = "北京市朝阳区三里屯太古里"
result = await claude_handler.process_query(query)

# 坐标转地址
query = "116.397428,39.90923 这个坐标对应的地址是什么？"
result = await claude_handler.process_query(query)

# POI搜索
query = "帮我查找北京大学的地理坐标"
result = await claude_handler.process_query(query)
```

### 批量处理

```bash
curl -X POST "http://localhost:8000/api/v1/address/batch" \
     -H "Content-Type: application/json" \
     -d '[
       {"address": "北京市朝阳区三里屯"},
       {"address": "上海市浦东新区陆家嘴"},
       {"address": "广州市天河区珠江新城"}
     ]'
```

## 🐛 故障排除

### 常见问题

1. **MCP连接失败**
   - 检查 `AMAP_MAPS_API_KEY` 是否正确设置
   - 确认网络连接正常
   - 查看日志文件获取详细错误信息

2. **Claude API调用失败**
   - 检查 `ANTHROPIC_API_KEY` 是否正确设置
   - 确认API密钥有足够的配额
   - 检查网络连接

3. **工具调用超时**
   - 增加 `MCP_SERVER_TIMEOUT` 配置值
   - 检查高德地图API服务状态

4. **依赖包冲突**
   - 使用虚拟环境隔离依赖：`python -m venv address-parser-env`
   - 或使用conda环境：`conda create -n address-parser python=3.11`
   - 清理pip缓存：`pip cache purge`

5. **conda环境问题**
   - 确保激活了正确的环境：`conda activate address-parser`
   - 如果遇到依赖冲突，尝试混合安装：
     ```bash
     conda install fastapi uvicorn pydantic
     pip install mcp anthropic structlog pydantic-settings
     ```

### 日志查看

```bash
# 查看应用日志
tail -f logs/app.log

# 查看API访问日志
tail -f logs/api.log
```

## 🤝 贡献指南

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🙏 致谢

- [Anthropic](https://www.anthropic.com/) - Claude AI API
- [高德地图](https://lbs.amap.com/) - 地图服务API
- [Model Context Protocol](https://modelcontextprotocol.io/) - MCP协议
- [FastAPI](https://fastapi.tiangolo.com/) - Web框架

## 📞 支持

如果你遇到问题或有建议，请：

1. 查看 [FAQ](#-故障排除)
2. 搜索现有的 [Issues](../../issues)
3. 创建新的 [Issue](../../issues/new)

---

**注意**: 本项目仅供学习和研究使用，请遵守相关API服务的使用条款。