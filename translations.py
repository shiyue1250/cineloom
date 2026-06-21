"""
Simplified-Chinese (zh_HANS / zh_CN) UI translations for Cineloom-specific labels.

Blender only auto-translates strings in its own dictionary (e.g. "File Path"),
so the add-on's custom labels stay English unless registered here via
``bpy.app.translations``. This covers the connect/configure flow, the Jobs panel,
and the most visible generation controls. Model ids are left untranslated.

Translations show only when the user has Interface translation enabled in
Blender preferences. Registered/unregistered from the add-on __init__.
"""

import bpy

_C = "*"  # default translation context

_ZH = {
    # --- Preferences: remote backend / connection ---
    (_C, "Remote Backend (Cineloom)"): "远端后端（Cineloom）",
    (_C, "Remote Backend URL"): "远端后端地址",
    (_C, "Remote API Key"): "远端 API 密钥",
    (_C, "Test Connection & Discover Models"): "测试连接并发现模型",
    (_C, "Control Backend URL"): "控制后端地址",
    (_C, "Video Model"): "视频模型",
    (_C, "Backend Model"): "后端模型",
    (_C, "Type"): "类型",
    (_C, "Model"): "模型",
    (_C, "Engine"): "引擎",
    (_C, "No remote model for this type"): "该类型暂无远端模型",
    (_C, "Show local models"): "显示本地模型",
    (_C, "Channel"): "渠道",
    (_C, "Add Channel"): "添加渠道",
    (_C, "Remove Channel"): "删除渠道",
    (_C, "Use This Channel"): "设为当前",
    (_C, "Test Active Channel"): "测试当前渠道",
    (_C, "Name"): "名称",
    (_C, "URL"): "地址",
    (_C, "API Key"): "API 密钥",
    (_C, "Remote Backends (Cineloom)"): "远端后端（Cineloom）",
    (_C, "(Backend default)"): "（后端默认）",
    (_C, "Image Model"): "图像模型",
    (_C, "Audio Model"): "音频模型",
    (_C, "Text Model"): "文本模型",
    (_C, "HuggingFace Cache"): "HuggingFace 缓存",
    (_C, "Notification"): "通知",
    (_C, "Use Local Files Only"): "仅使用本地文件",
    (_C, "Display System Console"): "显示系统控制台",
    (_C, "Install Dependencies"): "安装依赖",
    (_C, "Uninstall Dependencies"): "卸载依赖",
    (_C, "Export requirements.txt"): "导出 requirements.txt",

    # --- Main generation panel ---
    (_C, "Input"): "输入",
    (_C, "No Style"): "无风格",
    (_C, "Generate"): "生成",
    (_C, "Prompt"): "提示词",
    (_C, "Negative Prompt"): "反向提示词",
    (_C, "Seed"): "随机种子",
    (_C, "Frames"): "帧数",
    (_C, "Resolution"): "分辨率",
    (_C, "Strength"): "强度",

    # --- Jobs / task-history panel ---
    (_C, "Cineloom Jobs"): "Cineloom 任务",
    (_C, "Refresh Jobs"): "刷新任务",
    (_C, "No tasks — Refresh after generating."): "暂无任务 —— 生成后点刷新",
    (_C, "Result"): "结果",
    (_C, "Control map"): "控制图",
    (_C, "Download"): "下载",
    (_C, "Import"): "导入",
}

_TRANSLATIONS = {
    "zh_HANS": _ZH,   # Blender 4.x+ Simplified Chinese
    "zh_CN": _ZH,     # older locale id
}


def register_translations():
    try:
        bpy.app.translations.register(__name__, _TRANSLATIONS)
    except Exception:  # noqa: BLE001 — already registered / unsupported build
        pass


def unregister_translations():
    try:
        bpy.app.translations.unregister(__name__)
    except Exception:  # noqa: BLE001
        pass
