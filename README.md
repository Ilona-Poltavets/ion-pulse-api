# HalfStack API

FastAPI-бэкенд для Vue-фронтенда блога про игры и программирование.

## Требования

- `pyenv`
- `pyenv-virtualenv`
- Python `3.13.7`

Проверить установку:

```bash
pyenv --version
pyenv virtualenv --version
```

## Создание окружения

Из папки API:

```bash
cd /home/ip/Web/habr/habr-clone-api
pyenv install 3.13.7
pyenv virtualenv 3.13.7 habr-api
pyenv local habr-api
```

После `pyenv local` в папке должен использоваться virtualenv `habr-api`.
Проверить:

```bash
python --version
pyenv version
```

## Установка зависимостей

```bash
pip install -r requirements.txt
```

## Если зависимость pydantic-core не ставится

Если видишь ошибку вида:

```text
the configured Python interpreter version (3.14) is newer than PyO3's maximum supported version
```

значит окружение создано на Python `3.14`. Удали его и создай заново на Python `3.13.7`:

```bash
pyenv deactivate
pyenv virtualenv-delete habr-api
pyenv install 3.13.7
pyenv virtualenv 3.13.7 habr-api
pyenv local habr-api
pip install -r requirements.txt
```

## Запуск API

```bash
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

API будет доступен по адресу:

```text
http://127.0.0.1:8000
```

Swagger-документация:

```text
http://127.0.0.1:8000/docs
```

## Основные эндпоинты

```text
GET /
GET /health
GET /api/meta
GET /api/articles
GET /api/articles?section=games
GET /api/articles?section=programming
GET /api/articles?language=ru
GET /api/articles?language=en
GET /api/articles?featured=true
GET /api/articles/{slug}
GET /api/roles
POST /api/auth/register
POST /api/auth/login
GET /api/auth/me
GET /api/admin/overview
GET /api/admin/users
```

## Тестовый администратор

Для локальной разработки в API уже есть тестовый администратор:

```text
email: admin@halfstack.dev
password: admin12345
role: admin
```

Админские эндпоинты требуют заголовок:

```text
Authorization: Bearer <token>
```

## Запуск вместе с Vue

API:

```bash
cd /home/ip/Web/habr/habr-clone-api
pyenv local habr-api
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Фронтенд в другом терминале:

```bash
cd /home/ip/Web/habr/habr-clone-vue
source /home/ip/.nvm/nvm.sh
nvm use 25
npm run dev
```

Фронтенд ожидает API на:

```text
http://localhost:8000
```
