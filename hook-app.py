from PyInstaller.utils.hooks import collect_submodules

hidden_imports = collect_submodules('app')
import os
from PyInstaller.utils.hooks import collect_submodules

plugins_dir = os.path.join(os.path.dirname(__file__), 'plugins')

plugins = ['atomic', 'emu', 'manx', 'sandcat', 'stockpile']  # Bạn có thể liệt kê tất cả các plugin

for plugin in plugins:
    app_dir = os.path.join(plugins_dir, plugin, 'app')

    if os.path.exists(app_dir):
        hidden_imports.extend(collect_submodules(f'plugins.{plugin}.app'))

hiddenimports = hidden_imports