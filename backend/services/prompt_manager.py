# -*- coding: utf-8 -*-
"""
Prompt 版本管理器
将 Prompt 从代码中独立出来，存储在 YAML 文件中
支持版本切换、热加载、A/B 测试
"""
import yaml
import os
import random
import logging
from pathlib import Path
from typing import Optional
from config import settings

logger = logging.getLogger(__name__)


class PromptManager:
    """
    Prompt 版本管理器
    负责加载、缓存和切换 Prompt 版本

    设计原则：
    - Prompt 与代码解耦，修改 Prompt 不需要改代码
    - 修改 YAML 文件后自动检测并重新加载
    - 支持 A/B 测试按权重分配不同版本
    """

    def __init__(self, prompts_dir: Optional[Path] = None):
        self._prompts_dir = prompts_dir or settings.PROMPTS_DIR
        self._cache: dict[str, dict] = {}
        self._config: dict = {}
        self._config_mtime: float = 0

    def _load_config(self) -> dict:
        """
        加载全局配置
        通过检测文件修改时间实现热加载
        """
        config_path = self._prompts_dir / "config.yaml"
        if not config_path.exists():
            logger.warning(f"Prompt 配置文件不存在: {config_path}")
            return {"active_version": "v1.0"}

        mtime = os.path.getmtime(config_path)
        if mtime != self._config_mtime:
            with open(config_path, "r", encoding="utf-8") as f:
                self._config = yaml.safe_load(f) or {}
            self._config_mtime = mtime
            logger.info(
                f"Prompt 配置已加载 | 激活版本: {self._config.get('active_version', 'v1.0')}"
            )

        return self._config

    def _load_version(self, version: str) -> dict:
        """加载指定版本的 Prompt 文件"""
        if version in self._cache:
            return self._cache[version]

        path = self._prompts_dir / f"{version}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"Prompt 版本文件不存在: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        self._cache[version] = data
        logger.info(f"Prompt 版本 {version} 已加载")
        return data

    def get_active_prompt(self) -> tuple[dict, str]:
        """
        获取当前应使用的 Prompt

        A/B 测试模式下按权重随机选择版本，
        普通模式下返回激活版本

        返回: (prompt_data, version_id)
        """
        config = self._load_config()

        # A/B 测试模式
        ab_test = config.get("ab_test", {})
        if ab_test.get("enabled"):
            versions = ab_test.get("versions", [])
            if versions:
                weights = [v.get("weight", 1) for v in versions]
                chosen = random.choices(versions, weights=weights, k=1)[0]
                version = chosen["version"]
            else:
                version = config.get("active_version", "v1.0")
        else:
            version = config.get("active_version", "v1.0")

        prompt_data = self._load_version(version)
        return prompt_data, version

    def get_system_prompt(self) -> tuple[str, str]:
        """
        获取当前 System Prompt 文本和版本号
        这是排版接口最常用的方法

        返回: (system_prompt_text, version_id)
        """
        prompt_data, version = self.get_active_prompt()
        system_prompt = prompt_data.get("system_prompt", "")
        return system_prompt, version

    def get_model_params(self) -> dict:
        """获取当前版本的模型参数"""
        prompt_data, _ = self.get_active_prompt()
        return prompt_data.get("model_params", {
            "model": "glm-4-flash",
            "temperature": 0.3,
            "max_tokens": 4096,
        })

    def get_user_prompt(self, content: str) -> str:
        """
        构建 User Prompt
        将用户输入填充到模板中
        """
        prompt_data, _ = self.get_active_prompt()
        template = prompt_data.get("user_prompt_template", "请对以下文章进行排版：\n\n{content}")
        return template.replace("{content}", content)

    def list_versions(self) -> list[dict]:
        """列出所有可用的 Prompt 版本"""
        versions = []
        for f in self._prompts_dir.glob("v*.yaml"):
            with open(f, "r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
            if data:
                versions.append({
                    "version": data.get("version", f.stem),
                    "description": data.get("description", ""),
                    "created_at": data.get("created_at", ""),
                    "author": data.get("author", ""),
                })
        return sorted(versions, key=lambda x: x["version"], reverse=True)

    def switch_version(self, new_version: str) -> str:
        """
        切换激活版本
        修改 config.yaml 并清除缓存
        返回之前的版本号
        """
        # 先验证目标版本存在
        self._load_version(new_version)

        config_path = self._prompts_dir / "config.yaml"
        config = self._load_config()
        old_version = config.get("active_version", "v1.0")

        config["active_version"] = new_version
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False)

        self.reload()
        logger.info(f"Prompt 版本切换: {old_version} → {new_version}")
        return old_version

    def reload(self) -> None:
        """强制清除缓存，下次调用时重新加载"""
        self._cache.clear()
        self._config_mtime = 0
        logger.info("Prompt 缓存已清除")


# 全局单例
prompt_manager = PromptManager()
