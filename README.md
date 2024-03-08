# Бот для учета заказов в компании друзей на вечеринке

За общим столом бывает нелегко посчитать кто сколько заказал/потратил/оплатил. Этот бот помогает подбить итоги вечеринки.

## Подготовка к запуску, настройка окружения

Для запуска бота вам потребуется Python 3.10

Скачайте код бота, затем установите зависимости командой
```sh
pip install -r requirements.txt
```

## <a id="configure">Настройка параметров</a>

Получите все токены/ключи для заполнения `.env` файла.

```.env
TG_BOT_TOKEN=<получите у [**BotFather**](https://telegram.me/BotFather)>
TG_ADMIN_CHAT=<Необхожимо завести чат для админов заранее и указать его ID. Так же после запуска бота, его нужно добавить в этот чат, как участника>
LOG_LEVEL=[NOTSET|DEBUG|(INFO)|WARN|ERROR|CRITICAL] необязательный параметр. По умолчанию - INFO.

REDIS_HOST=адрес сервера redis
REDIS_PORT=порт сервера
REDIS_PASSWORD=пароль для подключения к серверу redis
```

## Запуск бота

Для запуска телеграм бота используйте следующую команду:

```sh
python party-billing-bot.py
```

## Запуск с использованием Docker

Вы можете запустить проект в докер-контейнере (docker должен быть установлен на Вашей машине)

Не забудьте перед запуском указать ваш токен бота как указано в разделе [Настройка параметров](#configure)

Сначала соберите образ контейнера командой:

```sh
docker build -t party_billing_bot .
```

Затем запустите собранный образ командой:

```sh
docker run --env-file .env -d --restart  always party_billing_bot:prod
```
