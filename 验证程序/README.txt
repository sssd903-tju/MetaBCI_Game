验证脚本说明
============

环境:
  SSVEP:  Python 3.10+, pip install numpy
  MI:     Python 3.10+, pip install numpy scipy mne scikit-learn

脚本:
  03_itcca_validate.py       — SSVEP ItCCA 模板匹配验证 (96.2%, 133试次)
  01_train_and_validate.py   — MI 离线训练 + LOO 验证 (SVM-rbf 79.6%, 49试次)
  02_online_test.py          — MI 在线测试验证 (30试次 Session 16)

数据目录:
  默认 ../验证数据 (SSVEP 会话) 和 ../验证数据/MI (MI BDF+JSONL)
  若不存在则回退至 ~/MetaBCI_Training_Data

运行:
  cd 验证程序
  PYTHONPATH=.. python 03_itcca_validate.py
  PYTHONPATH=.. python 01_train_and_validate.py
  PYTHONPATH=.. python 02_online_test.py
