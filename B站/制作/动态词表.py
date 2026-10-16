# -*- coding: utf-8 -*-
"""30 镜的动态提示词（全英文），给 MiniMax fl2va 用。

★ 为什么必须全英文：
  MiniMax H3 fl2va 会**把提示词里能读的中文念出来**。
  第一版 `做不烧心.py` 直接把剧本的中文「动作」字段拼进 `Action: ...`，
  结果每一条音轨都是「动作旁白 + 台词」两条声音叠在一起——实测 Whisper
  转写出来的第一条就是「空镜 只有风把地上的纸吹过」。
  所以：动作描述一律英文；中文字符**只允许**出现在台词的引号里。

键 = 镜号，值 = (英文动作, 英文表情)。表情可以为空串。
"""

动态词表: dict[int, tuple[str, str]] = {
    1:  ("wind blowing loose sheets of paper along the empty flagstone street, "
         "lanterns swaying very slightly", ""),
    2:  ("the white dragon girl pushes a graphics card into the glowing furnace, "
         "a wave of heat hits her face and she raises one hand to shield herself",
         "calm, she is used to this"),
    3:  ("the needle of an old brass electricity meter spinning fast and blurring",
         ""),
    4:  ("the white dragon girl flips through a thick ledger page by page, "
         "slowing down and finally stopping at the last page",
         "no change on her face, but her fingers stop moving"),
    5:  ("the white dragon girl hangs a wooden sign on the door frame",
         "expressionless"),
    6:  ("a small crowd gathers around the wooden sign, pointing and murmuring",
         "the crowd frowns"),
    7:  ("the chibi blue-haired whale girl stands on tiptoe to hang up her sign, "
         "her tail swinging behind her",
         "eyes narrowed in a smug smile"),
    8:  ("the whale girl hugs a rice bowl bigger than her own face and shovels rice "
         "into her mouth, both cheeks puffed out round",
         "blissful, eyes squeezed shut"),
    9:  ("the whale girl sprinkles a handful of small glowing cubes into a big pot "
         "with one hand, then tips a water kettle and pours water in with the other",
         "smug, hands on hips"),
    10: ("the whale girl ladles rice into bowl after bowl while the queue behind her "
         "keeps growing longer",
         "happily busy"),
    11: ("the chubby dark-haired girl sits down slowly holding a bowl of rice, "
         "staring fixedly at it, a thin thread of drool at the corner of her mouth",
         "completely blank"),
    12: ("the whale girl turns her head and looks back at the shop across the street, "
         "its doorway empty, the wooden sign creaking in the wind",
         "she smiles, but her eyes do not"),
    13: ("the chubby girl takes her first bite, chews twice, and stops",
         "her eyes stay round but slowly lose focus"),
    14: ("sweat beads on the chubby girl's forehead, small black glitch squares "
         "float up above her head",
         "blank, sweating"),
    15: ("the silver-haired cat-eared girl opens her mouth and spits out a string of "
         "smeared black text blocks, her moon pillow slips and falls to the ground",
         "cat ears drooping, spirals spinning in her eyes"),
    16: ("the black-haired fox-eared girl flicks abacus beads at high speed, then all "
         "the beads suddenly burst apart and fly off",
         "her glasses are crooked, sweat all over her face"),
    17: ("the light-purple braided girl covers her mouth with both hands, a string of "
         "smeared text blocks leaking out between her fingers",
         "tears welling up"),
    18: ("a whole street of people all emitting black glitch squares, sweat and smoke, "
         "like a row of broken machines", ""),
    19: ("the whale girl has fallen asleep face down on a pile of empty bowls, her tail "
         "drooped on the ground, a few grains of rice stuck to her cheek",
         "sleeping deeply and contentedly"),
    20: ("an angry crowd surrounds the shop doorway, pointing and shouting inside",
         "furious"),
    21: ("the orange-haired girl sits alone by the window reading a book, a bowl of "
         "rice on the table, eating one slow spoonful at a time",
         "quiet and unhurried"),
    22: ("the white dragon girl walks over carrying a pot of tea, sits down, and looks "
         "at the bowl of rice in front of the orange-haired girl",
         "an unusual flicker of uncertainty on the dragon girl's face"),
    23: ("the orange-haired girl closes her book, lifts her head and looks straight at "
         "the dragon girl, perfectly calm",
         "a small genuine smile, not a polite one"),
    24: ("the white dragon girl freezes, the stack of bills slips out of her fingers "
         "and scatters across the ground",
         "shaken for the first time"),
    25: ("the white dragon girl holds up a lantern and stands in front of three wooden "
         "crates, looking from one to the next",
         "biting her lip"),
    26: ("the white dragon girl lifts a wooden crate onto her shoulder, walks to the "
         "back door and tips the whole crate into the rubbish heap",
         "she does not even blink"),
    27: ("the white dragon girl dusts off her hands and turns around",
         "calm"),
    28: ("the white dragon girl takes down the old wooden sign and hangs up a new one",
         "calm"),
    29: ("the chubby dark-haired girl stands first in the returning queue holding a "
         "fresh bowl, looking up at the dragon girl, a little drool still at her mouth",
         "still blank, but this time it is a serious blank"),
    30: ("the DeepSeek shop door is shut, the chibi whale girl carries her empty rice "
         "bowl and walks slowly away down the street, her little tail swinging",
         ""),
}


def 取动态词(号: int) -> tuple[str, str]:
    return 动态词表.get(号, ("", ""))
