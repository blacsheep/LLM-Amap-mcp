#!/usr/bin/env python3
"""
快速启动脚本
帮助用户快速配置和启动地址解析服务
"""

import os
import sys
import subprocess
from pathlib import Path


def check_requirements():
    """检查系统要求"""
    print("🔍 检查系统要求...")
    
    # 检查Python版本
    if sys.version_info < (3, 10):
        print("❌ Python版本需要3.10或更高")
        return False
    
    print(f"✅ Python版本: {sys.version}")
    
    # 检查Node.js
    try:
        result = subprocess.run(['node', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Node.js版本: {result.stdout.strip()}")
        else:
            print("❌ 未找到Node.js，请安装Node.js 16+")
            return False
    except FileNotFoundError:
        print("❌ 未找到Node.js，请安装Node.js 16+")
        return False
    
    return True


def check_conda():
    """检查是否在conda环境中"""
    try:
        result = subprocess.run(['conda', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            conda_env = os.environ.get('CONDA_DEFAULT_ENV')
            
            # 检查是否在推荐的address-parser环境中
            if conda_env == 'address-parser':
                print(f"✅ 检测到正确的Conda环境: {conda_env}")
                return True
            elif conda_env and conda_env != 'base':
                print(f"⚠️  检测到Conda环境: {conda_env}")
                print("💡 建议切换到address-parser环境:")
                print("   conda activate address-parser")
                return True
            else:
                print("💡 建议创建并激活conda环境:")
                print("   conda env create -f environment.yml")
                print("   conda activate address-parser")
                print("   或者手动创建:")
                print("   conda create -n address-parser python=3.11")
                print("   conda activate address-parser")
                return False
    except FileNotFoundError:
        pass
    return False


def install_dependencies():
    """安装依赖"""
    print("\n📦 安装Python依赖...")
    
    # 检查conda环境
    in_conda = check_conda()
    
    try:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'], 
                      check=True)
        print("✅ Python依赖安装完成")
        
        if in_conda:
            print("💡 如果遇到依赖冲突，可以尝试:")
            print("   conda install fastapi uvicorn pydantic")
            print("   pip install mcp anthropic structlog pydantic-settings")
            
    except subprocess.CalledProcessError:
        print("❌ Python依赖安装失败")
        if not in_conda:
            print("💡 建议使用虚拟环境:")
            print("   python -m venv address-parser-env")
            print("   source address-parser-env/bin/activate  # macOS/Linux")
            print("   address-parser-env\\Scripts\\activate    # Windows")
        return False
    
    return True


def setup_environment():
    """设置环境变量"""
    print("\n⚙️ 配置环境变量...")
    
    env_file = Path('.env')
    env_example = Path('.env.example')
    
    if not env_file.exists():
        if env_example.exists():
            # 复制示例文件
            with open(env_example, 'r', encoding='utf-8') as f:
                content = f.read()
            
            with open(env_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print("✅ 已创建.env文件")
        else:
            print("❌ 未找到.env.example文件")
            return False
    
    # 检查API密钥
    with open(env_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    needs_config = []
    
    # 检查高德地图API密钥（必需）
    if 'your_amap_api_key_here' in content:
        needs_config.append('AMAP_MAPS_API_KEY')
    
    # 检查LLM提供商配置
    llm_provider = "claude"  # 默认值
    for line in content.split('\n'):
        if line.startswith('LLM_PROVIDER=') and not line.startswith('#'):
            llm_provider = line.split('=', 1)[1].strip().lower()
            break
    
    print(f"🔧 检测到LLM提供商: {llm_provider.upper()}")
    
    # 根据LLM提供商检查相应的API密钥
    if llm_provider == "claude":
        if 'your_anthropic_api_key_here' in content:
            needs_config.append('ANTHROPIC_API_KEY')
    elif llm_provider == "openai":
        if 'your_openai_api_key_here' in content:
            needs_config.append('OPENAI_API_KEY')
    
    if needs_config:
        print(f"⚠️  请在.env文件中配置以下API密钥: {', '.join(needs_config)}")
        print("   API密钥获取地址:")
        if 'ANTHROPIC_API_KEY' in needs_config:
            print("   - ANTHROPIC_API_KEY: https://console.anthropic.com/")
        if 'OPENAI_API_KEY' in needs_config:
            print("   - OPENAI_API_KEY: https://platform.openai.com/")
        if 'AMAP_MAPS_API_KEY' in needs_config:
            print("   - AMAP_MAPS_API_KEY: https://lbs.amap.com/")
        print(f"\n💡 当前使用 {llm_provider.upper()} 作为LLM提供商")
        print("   可通过修改 .env 文件中的 LLM_PROVIDER 来切换 (claude/openai)")
        return False
    
    print("✅ 环境变量配置完成")
    return True


def test_basic_functionality():
    """测试基础功能"""
    print("\n🧪 测试基础功能...")
    
    try:
        # 运行简单的导入测试
        subprocess.run([
            sys.executable, '-c', 
            'from src.core.config import get_settings; print("配置模块正常")'
        ], check=True, capture_output=True)
        
        print("✅ 基础模块导入正常")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ 基础功能测试失败: {e}")
        return False


def show_next_steps():
    """显示后续步骤"""
    print("\n🎉 安装完成！后续步骤:")
    print("\n1. 配置API密钥:")
    print("   编辑 .env 文件，填入你的API密钥")
    
    print("\n2. 运行示例:")
    print("   python examples/basic_usage.py")
    
    print("\n3. 启动API服务:")
    print("   python api/main.py")
    print("   然后访问: http://localhost:8000/docs")
    
    print("\n4. 运行测试:")
    print("   pytest tests/")
    
    print("\n📖 更多信息请查看 README.md")


def main():
    """主函数"""
    print("🚀 高德地址解析服务 - 快速启动")
    print("=" * 50)
    
    # 检查系统要求
    if not check_requirements():
        print("\n❌ 系统要求检查失败，请解决上述问题后重试")
        return
    
    # 安装依赖
    if not install_dependencies():
        print("\n❌ 依赖安装失败")
        return
    
    # 设置环境
    if not setup_environment():
        print("\n⚠️  请配置API密钥后重新运行")
        return
    
    # 测试功能
    if not test_basic_functionality():
        print("\n❌ 基础功能测试失败")
        return
    
    # 显示后续步骤
    show_next_steps()


if __name__ == "__main__":
    main()