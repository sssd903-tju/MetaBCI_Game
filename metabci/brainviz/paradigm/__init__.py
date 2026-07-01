# -*- coding: utf-8 -*-
"""
范式定义 — 每种 BCI 范式的元数据、电极配置、处理管线
"""

from metabci.brainviz.paradigm.base import BaseParadigm
from metabci.brainviz.paradigm.focus import FocusParadigm
from metabci.brainviz.paradigm.ssvep import SSVEPParadigm
from metabci.brainviz.paradigm.p300 import P300Paradigm
from metabci.brainviz.paradigm.mi import MIParadigm

# 注册表
PARADIGMS: dict[str, BaseParadigm] = {
    "focus": FocusParadigm(),
    "ssvep": SSVEPParadigm(),
    "p300": P300Paradigm(),
    "mi": MIParadigm(),
}

PARADIGM_LIST = list(PARADIGMS.values())
