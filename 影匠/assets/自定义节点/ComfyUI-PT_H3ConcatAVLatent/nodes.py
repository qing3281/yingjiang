import torch
import comfy
from comfy import nested_tensor

class PT_H3ConcatAVLatent:
    """
    将独立的视频 Latent 和音频 Latent 合并为 H3 模型所需的 NestedTensor。
    输入：
        video_latent: 标准 LATENT 字典，包含 "samples" (视频张量)
        audio_latent: 标准 LATENT 字典，包含 "samples" (音频张量)
    输出：
        合并后的 LATENT 字典，其 "samples" 是一个 NestedTensor 对象。
    """
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "video_latent": ("LATENT",),
                "audio_latent": ("LATENT",),
            }
        }

    RETURN_TYPES = ("LATENT",)
    FUNCTION = "merge"
    CATEGORY = "H3/PT"

    def merge(self, video_latent, audio_latent):
        # 1. 提取张量
        video_tensor = video_latent["samples"]
        audio_tensor = audio_latent["samples"]

        # 2. 基本的类型与形状校验（可选但推荐）
        if not isinstance(video_tensor, torch.Tensor) or not isinstance(audio_tensor, torch.Tensor):
            raise ValueError("Both video and audio latents must be torch.Tensor.")
        
        # 这里可以添加更详细的形状检查，例如：
        # H3 视频预期形状: [B, 24, T, H/16, W/16]
        # H3 音频预期形状: [B, 32, 2, T_audio]
        # 但为了通用性，我们只做简单断言
        if video_tensor.ndim != 5:
            raise ValueError(f"Video latent expects 5D tensor, got {video_tensor.ndim}D.")
        if audio_tensor.ndim != 4:
            raise ValueError(f"Audio latent expects 4D tensor, got {audio_tensor.ndim}D.")

        # 3. 创建 NestedTensor（最关键的一步）
        #    注意：NestedTensor 接受一个张量列表，顺序为 [video, audio]
        nested_latent = nested_tensor.NestedTensor([video_tensor, audio_tensor])

        # 4. 返回符合 ComfyUI 标准的 LATENT 字典
        return ({"samples": nested_latent},)