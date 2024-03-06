import datetime
import logging
import os
from enum import Enum

from dotenv import load_dotenv
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (CommandHandler, ConversationHandler, Filters,
                          MessageHandler, Updater)

logger = logging.getLogger(__file__)


class Status(Enum):
    GET_ITEM = 0
    GET_COST = 1
    GET_CHECK = 2


def start(update, context):
    logger.debug(f'Enter cmd_start: {update=}')

    text = 'Привет!\n' \
           'Я учитываю заказы нашей компании на вечеринке ' \
           f'{datetime.date.today():%d %B %Y} ' \
           'в <party-place>\nНапиши мне примерное название того что ты ' \
           'хочешь заказать'
    context.bot.send_message(chat_id=update.effective_chat.id, text=text,
                             reply_markup=ReplyKeyboardRemove(), )
    return Status.GET_ITEM


def get_item(update, context):
    logger.debug(f'Enter save_item: {update=}')

    item = update.message.text
    context.user_data['item'] = item
    text = f'Ты заказал:\n{item}\nНапиши стоимость, ' \
           'чтобы мы потом правильно раделили итоговый счет на всех.'
    context.bot.send_message(chat_id=update.effective_chat.id, text=text)
    return Status.GET_COST


def get_cost(update, context):
    logger.debug(f'Enter save_cost: {update=}')

    item = context.user_data['item']
    cost = update.message.text
    context.user_data['cost'] = cost
    text = f'Ок. Ты заказал:\n{item}\nСтоимость:\n{cost}\n' \
           'Нажми "Да", если все верно, или "Нет", если хочешь прислать ' \
           'заказ заново'
    keyboard = [['Да', 'Нет'],]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    context.bot.send_message(chat_id=update.effective_chat.id, text=text,
                             reply_markup=reply_markup, )
    return Status.GET_CHECK


def confirm_choice(update, context):
    logger.debug(f'Enter confirm_choice: {update=}')

    cost = context.user_data['cost']
    item = context.user_data['item']
    text = f'Спасибо, что ты заказал:\n{item}\nСтоимость:\n{cost}\n' \
           'Я записал заказ в общий список и учту его при разделе счета.\n' \
           'Если захочешь добавить что-то еще, то опять присылай название.'
    context.bot.send_message(chat_id=update.effective_chat.id, text=text,
                             reply_markup=ReplyKeyboardRemove(), )
    return Status.GET_ITEM


def decline_choice(update, context):
    logger.debug(f'Enter decline_choice: {update=}')

    text = 'Ок. Отменяем. Попробуй ввести название заново.'
    context.bot.send_message(chat_id=update.effective_chat.id, text=text,
                             reply_markup=ReplyKeyboardRemove(), )
    return Status.GET_ITEM


if __name__ == '__main__':
    load_dotenv()
    tg_token = os.getenv('TELEGRAM_BOT_TOKEN')
    loglevel = os.getenv('LOG_LEVEL', default='INFO')
    logger.debug('Start logging')

    updater = Updater(tg_token)
    dispatcher = updater.dispatcher
    conversation = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            Status.GET_ITEM: [
                MessageHandler(Filters.text, get_item),
            ],
            Status.GET_COST: [
                MessageHandler(Filters.text, get_cost),
            ],
            Status.GET_CHECK: [
                MessageHandler(Filters.text('Да'), confirm_choice),
                MessageHandler(Filters.text('Нет'), decline_choice),
            ],
        },
        fallbacks=[],
        name='party_billing_conversation',
        # persistent=True,
    )
    dispatcher.add_handler(conversation)
    updater.start_polling()
    updater.idle()
