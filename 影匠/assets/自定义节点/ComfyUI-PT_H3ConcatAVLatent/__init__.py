from .nodes import PT_H3ConcatAVLatent

# 必须定义的映射字典
NODE_CLASS_MAPPINGS = {
    "PT_H3ConcatAVLatent": PT_H3ConcatAVLatent,
}

# 可选：显示名称映射（用于 WebUI 友好名称）
NODE_DISPLAY_NAME_MAPPINGS = {
    "PT_H3ConcatAVLatent": "PT H3 Concat AV Latent",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]