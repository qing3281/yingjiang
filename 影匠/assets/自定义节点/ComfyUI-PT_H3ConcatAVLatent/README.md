# ComfyUI-PT_H3ConcatAVLatent
Minimax video audio Concat AV Latent for any video into Minimax H3 sampler

Minimax H3 的采样器latent输入必须是同时带有音频和视频的latent,就像LTX那样,但是LTX节点组包含了类似的节点,而Minimax H3 似乎还没有这样的单独节点.

所以我制作了这个节点,它可以让 Minimax H3 直接对任何现有的视频进行权重重绘处理.得益于即将完善的加速Lora,可能是一种新的视频重绘方案.

希望这对你暂时有用, 因为未来也许会有人把这个功能整合到比较大的H3节点包内,就像LTX节点组那样.注意,我收到了提醒,表示LTX的ConcatAVLatent具有相同的功能,抱歉,我并不知情,如果你只是需要在H3使用这个功能,那这个节点至少为你省去了一个巨大的LTX节点包.:)
Note, I've been reminded that ConcatAVLatent in LTX has the same functionality. Sorry, I wasn't aware of this. If you only need to use this feature in H3, this node will at least save you from using a huge LTX node pack. :)



The sampler latent input for Minimax H3 must be a latent carrying both audio and video, just like LTX. However, the LTX node group includes comparable nodes, while Minimax H3 seemingly lacks such a standalone node.

Therefore, I have created this node, which enables Minimax H3 to directly perform‑weighted redrawing on any existing video. Thanks to the upcoming optimized acceleration LoRA, this could serve as a new video‑redrawing solution.

I hope this works for you for the time being, since this feature may eventually be integrated into a larger H3 node package in the future, similar to the LTX node group.

<img width="1689" height="1023" alt="QQ_1785998081435" src="https://github.com/user-attachments/assets/d668e679-d8c5-4da5-b51b-e35061640f8e" />

