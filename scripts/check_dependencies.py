#!/usr/bin/env python3
"""
依赖一致性检查脚本
验证environment.yml和requirements.txt之间的依赖版本同步
"""

import yaml
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple


def parse_requirements_txt(file_path: Path) -> Dict[str, str]:
    """解析requirements.txt文件"""
    dependencies = {}
    
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                # 解析包名和版本约束
                match = re.match(r'^([^>=<!\s]+)([>=<!\s].*)?$', line)
                if match:
                    package = match.group(1)
                    version = match.group(2) or ""
                    dependencies[package] = version.strip()
    
    return dependencies


def parse_environment_yml(file_path: Path) -> Tuple[Dict[str, str], Dict[str, str]]:
    """解析environment.yml文件，返回conda依赖和pip依赖"""
    conda_deps = {}
    pip_deps = {}
    
    with open(file_path, 'r', encoding='utf-8') as f:
        env_data = yaml.safe_load(f)
    
    for dep in env_data.get('dependencies', []):
        if isinstance(dep, str):
            # conda依赖
            match = re.match(r'^([^>=<!\s]+)([>=<!\s].*)?$', dep)
            if match:
                package = match.group(1)
                version = match.group(2) or ""
                conda_deps[package] = version.strip()
        elif isinstance(dep, dict) and 'pip' in dep:
            # pip依赖
            for pip_dep in dep['pip']:
                match = re.match(r'^([^>=<!\s]+)([>=<!\s].*)?$', pip_dep)
                if match:
                    package = match.group(1)
                    version = match.group(2) or ""
                    pip_deps[package] = version.strip()
    
    return conda_deps, pip_deps


def compare_dependencies(req_deps: Dict[str, str], env_pip_deps: Dict[str, str], 
                        env_conda_deps: Dict[str, str]) -> Dict[str, List[str]]:
    """比较依赖版本差异"""
    issues = {
        'missing_in_env': [],
        'missing_in_req': [],
        'version_mismatch': [],
        'ok': []
    }
    
    # 检查requirements.txt中的包是否在environment.yml中
    for package, req_version in req_deps.items():
        if package in env_pip_deps:
            env_version = env_pip_deps[package]
            if req_version != env_version:
                issues['version_mismatch'].append(
                    f"{package}: req.txt({req_version}) vs env.yml({env_version})"
                )
            else:
                issues['ok'].append(f"{package}{req_version}")
        elif package in env_conda_deps:
            env_version = env_conda_deps[package]
            # conda和pip版本格式可能不同，记录为注意事项
            issues['ok'].append(f"{package}: req.txt({req_version}) -> conda({env_version})")
        else:
            issues['missing_in_env'].append(f"{package}{req_version}")
    
    # 检查environment.yml中的pip包是否在requirements.txt中
    for package, env_version in env_pip_deps.items():
        if package not in req_deps:
            issues['missing_in_req'].append(f"{package}{env_version}")
    
    return issues


def main():
    """主函数"""
    print("🔍 检查依赖一致性...")
    print("=" * 50)
    
    # 文件路径
    req_file = Path("requirements.txt")
    env_file = Path("environment.yml")
    
    # 检查文件是否存在
    if not req_file.exists():
        print("❌ requirements.txt文件不存在")
        return
    
    if not env_file.exists():
        print("❌ environment.yml文件不存在")
        return
    
    # 解析文件
    req_deps = parse_requirements_txt(req_file)
    env_conda_deps, env_pip_deps = parse_environment_yml(env_file)
    
    print(f"📋 Requirements.txt包数量: {len(req_deps)}")
    print(f"📋 Environment.yml conda包数量: {len(env_conda_deps)}")
    print(f"📋 Environment.yml pip包数量: {len(env_pip_deps)}")
    print()
    
    # 比较依赖
    issues = compare_dependencies(req_deps, env_pip_deps, env_conda_deps)
    
    # 报告结果
    if issues['ok']:
        print("✅ 一致的依赖:")
        for item in issues['ok']:
            print(f"   {item}")
        print()
    
    if issues['version_mismatch']:
        print("⚠️  版本不匹配:")
        for item in issues['version_mismatch']:
            print(f"   {item}")
        print()
    
    if issues['missing_in_env']:
        print("❌ environment.yml中缺失:")
        for item in issues['missing_in_env']:
            print(f"   {item}")
        print()
    
    if issues['missing_in_req']:
        print("❌ requirements.txt中缺失:")
        for item in issues['missing_in_req']:
            print(f"   {item}")
        print()
    
    # 总结
    total_issues = len(issues['version_mismatch']) + len(issues['missing_in_env']) + len(issues['missing_in_req'])
    
    if total_issues == 0:
        print("🎉 依赖文件一致性检查通过！")
    else:
        print(f"📊 发现 {total_issues} 个问题需要解决")
        print("\n💡 建议:")
        print("1. 确保两个文件中的包版本保持一致")
        print("2. 优先使用conda安装的包可以放在conda依赖中")
        print("3. MCP相关包建议使用pip安装")


if __name__ == "__main__":
    main() 