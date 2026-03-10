# 🚀 Руководство по деплою Quiz Bot

Этот документ описывает процесс развертывания бота на облачных платформах Render.com или Railway.com с базой данных на Neon.

## 📋 Предварительные требования

1. **Telegram Bot Token** - получите у [@BotFather](https://t.me/botfather)
2. **OpenAI API Key** или **Anthropic API Key** - для работы AI-функционала
3. **Git репозиторий** - код должен быть в GitHub/GitLab/Bitbucket

## 🗄️ Шаг 1: Настройка базы данных на Neon

1. Зарегистрируйтесь на [Neon.tech](https://neon.tech)
2. Создайте новый проект
3. Скопируйте **Connection String** (формат: `postgresql://user:password@host/database`)
4. Сохраните его - он понадобится для настройки переменных окружения

## 🎯 Вариант A: Деплой на Render.com

### Шаги:

1. **Создайте аккаунт** на [Render.com](https://render.com)

2. **Подключите репозиторий:**
   - Dashboard → New → Blueprint
   - Подключите ваш Git-репозиторий
   - Render автоматически обнаружит `render.yaml`

3. **Настройте переменные окружения:**

   Render автоматически подставит большинство переменных из `render.yaml`, но нужно добавить секретные:

   - `BOT__TOKEN` - ваш Telegram bot token
   - `LLM__OPENAI_API_KEY` - ключ OpenAI (если используете OpenAI)
   - `LLM__ANTHROPIC_API_KEY` - ключ Anthropic (если используете Claude)
   - `DB__URL` - будет автоматически подставлен из подключенной БД

4. **Разверните проект:**
   - Нажмите "Apply" в Blueprint
   - Render создаст сервис и базу данных
   - Дождитесь завершения деплоя

### Примечания для Render:

- **Free tier** доступен, но сервис засыпает после 15 минут неактивности
- PostgreSQL БД на Render также доступна бесплатно (с ограничениями)
- Можно использовать Neon вместо Render PostgreSQL

## 🚂 Вариант B: Деплой на Railway.com

### Шаги:

1. **Создайте аккаунт** на [Railway.app](https://railway.app)

2. **Создайте новый проект:**
   - Dashboard → New Project
   - Deploy from GitHub repo
   - Выберите ваш репозиторий

3. **Настройте переменные окружения:**

   В разделе Variables добавьте:

   ```bash
   BOT__TOKEN=your-bot-token-here
   BOT__ADMIN_IDS=[123456789]

   DB__URL=postgresql://user:password@host/database  # Из Neon

   LLM__PROVIDER=openai
   LLM__OPENAI_API_KEY=sk-...
   LLM__OPENAI_MODEL=gpt-4o-mini

   # Или для Anthropic:
   # LLM__PROVIDER=anthropic
   # LLM__ANTHROPIC_API_KEY=sk-ant-...
   # LLM__ANTHROPIC_MODEL=claude-sonnet-4-20250514

   ANALYSIS__MESSAGE_THRESHOLD=10
   ANALYSIS__CONFIDENCE_THRESHOLD=0.7
   ANALYSIS__BUFFER_SIZE=100

   RATE_LIMIT__PROACTIVE_COOLDOWN_SECONDS=120
   RATE_LIMIT__BUCKET_RATE=0.008
   RATE_LIMIT__BUCKET_CAPACITY=5
   RATE_LIMIT__DAILY_PROACTIVE_CAP=20
   RATE_LIMIT__COMMAND_COOLDOWN_SECONDS=5

   QUIZ__INACTIVITY_THRESHOLD_MINUTES=120
   QUIZ__QUESTION_TIMEOUT_SECONDS=30

   DB__MESSAGE_RETENTION_DAYS=90
   ```

4. **Разверните:**
   - Railway автоматически обнаружит `Dockerfile` и `railway.toml`
   - Нажмите Deploy
   - Дождитесь завершения сборки

### Примечания для Railway:

- **$5 бесплатных кредитов** каждый месяц на Hobby план
- Сервис не засыпает (в отличие от Render free tier)
- Отличная интеграция с GitHub (auto-deploy при push)

## 🔧 Переменные окружения

### Обязательные:

| Переменная | Описание | Пример |
|------------|----------|--------|
| `BOT__TOKEN` | Telegram Bot Token от BotFather | `1234567890:ABCdef...` |
| `DB__URL` | PostgreSQL connection string | `postgresql://user:pass@host/db` |
| `LLM__PROVIDER` | AI провайдер (openai/anthropic) | `openai` |
| `LLM__OPENAI_API_KEY` | OpenAI API ключ | `sk-proj-...` |

### Опциональные (со значениями по умолчанию):

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `BOT__ADMIN_IDS` | `[]` | Список ID администраторов |
| `LLM__OPENAI_MODEL` | `gpt-4o-mini` | Модель OpenAI |
| `LLM__ANTHROPIC_MODEL` | `claude-sonnet-4-20250514` | Модель Anthropic |
| `ANALYSIS__MESSAGE_THRESHOLD` | `10` | Порог сообщений для анализа |
| `RATE_LIMIT__DAILY_PROACTIVE_CAP` | `20` | Дневной лимит проактивных сообщений |

## 🔍 Проверка деплоя

После успешного деплоя:

1. Откройте логи на платформе (Render/Railway)
2. Проверьте, что бот запустился: `Bot starting...`
3. Убедитесь, что БД инициализирована: `Database schema initialized`
4. Попробуйте отправить команду боту в Telegram

## 🐛 Troubleshooting

### Бот не отвечает:

- Проверьте логи на наличие ошибок
- Убедитесь, что `BOT__TOKEN` правильный
- Проверьте, что сервис запущен (не в статусе sleep)

### Ошибки подключения к БД:

- Проверьте `DB__URL` - должен начинаться с `postgresql://` или `postgres://`
- Убедитесь, что БД на Neon активна и доступна
- Проверьте, что IP вашего сервиса не заблокирован в Neon

### Ошибки AI:

- Проверьте корректность API ключей
- Убедитесь, что `LLM__PROVIDER` соответствует используемому ключу
- Проверьте баланс на аккаунте OpenAI/Anthropic

## 📊 Мониторинг

- **Render**: Dashboard → Logs/Metrics
- **Railway**: Dashboard → Deployments → View Logs
- **Neon**: Console → Database → Monitoring

## 🔄 Обновление

### Render:
- Push в GitHub → автоматический деплой (если настроен)
- Или вручную: Dashboard → Manual Deploy

### Railway:
- Push в GitHub → автоматический деплой
- Или вручную: Dashboard → Deployments → Deploy

## 💡 Рекомендации

1. **Используйте Neon для БД** - бесплатный tier более щедрый, чем у Render
2. **Railway для бота** - не засыпает, отличная DX
3. **Настройте алерты** - следите за использованием лимитов
4. **Регулярно проверяйте логи** - отслеживайте ошибки и производительность
5. **Backup БД** - Neon автоматически делает бэкапы, но можно настроить дополнительные

## 📚 Дополнительные ресурсы

- [Документация Render](https://render.com/docs)
- [Документация Railway](https://docs.railway.app)
- [Документация Neon](https://neon.tech/docs)
- [Telegram Bot API](https://core.telegram.org/bots/api)

## 🆘 Поддержка

Если возникли проблемы, проверьте:
1. Логи приложения
2. Статус сервисов (Render/Railway/Neon)
3. Корректность переменных окружения
4. Доступность API эндпоинтов (Telegram, OpenAI, Anthropic)
