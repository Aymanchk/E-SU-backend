# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# PythonAnywhere WSGI configuration for E-SU Backend
#
# Скопируйте содержимое этого файла в конфигурацию WSGI на PythonAnywhere:
# /var/www/<your-username>_pythonanywhere_com_wsgi.py
# (ссылка на этот файл находится во вкладке "Web" -> "WSGI configuration file")
# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

import os
import sys

# 1. Путь к каталогу backend проекта на сервере PythonAnywhere
# Замените 'yourusername' на ваш реальный логин на PythonAnywhere!
# Пример, если вы загрузили zip в корень домашней директории:
path = '/home/yourusername/E-SU-backend'

# Или если вы склонировали репозиторий E-SU целиком:
# path = '/home/yourusername/E-SU/E-SU-backend'

if path not in sys.path:
    sys.path.insert(0, path)

# 2. Настройки Django для PythonAnywhere
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.pythonanywhere'

# 3. Инициализация WSGI приложения Django
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
