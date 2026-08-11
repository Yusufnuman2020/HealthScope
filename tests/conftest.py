# -*- coding: utf-8 -*-
"""Test oturumu ayarları.

Testler GPU kullanmaz — modeller sahte (stub) pipeline ile değiştirilir.
Ancak `torch` içe aktarıldığında CUDA bağlamı yine de kurulur ve arka planda
çalışan bir sunucu GPU'yu tutuyorsa süreç sert şekilde çöker (C stack dump).

Bu yüzden testler açıkça CPU'ya sabitlenir. Ayar `torch` import edilmeden
ÖNCE yapılmalıdır; conftest.py bu iş için en erken çalışan yerdir.
"""
import os

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
os.environ.setdefault("HEALTHSCOPE_EAGER_LOAD", "0")
#: Testler üretken katmanı kullanmaz; yanlışlıkla 6 GB model yüklenmesin.
os.environ["HEALTHSCOPE_LLM_PROVIDER"] = "none"
