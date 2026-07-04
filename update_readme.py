#!/usr/bin/env python
import os
import shutil

os.chdir('E:\\桌面\\简历投递agent\\RESUME_SKILL')

# 替换文件
if os.path.exists('README_NEW.md'):
    shutil.move('README_NEW.md', 'README.md')
    print('✅ README.md 已成功更新!')
    with open('README.md', 'r', encoding='utf-8') as f:
        lines = len(f.readlines())
    print(f'✅ 文件行数: {lines}')
else:
    print('❌ README_NEW.md 不存在')
