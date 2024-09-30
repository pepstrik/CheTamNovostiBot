#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import telebot
from telebot import types

chat_id = -1001455307140
admin_id = 4414554 

bot = telebot.TeleBot('6258803046:AAEyAlfHMbCw810NmNsE42pTTsbgDz1vT3s')

@bot.message_handler(commands=['start'])
def welcome(message):
    
    bot.send_message(message.from_user.id, "Большой привет от маленькой компани подкаста Чё там новости!👋")
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn0 = types.KeyboardButton('🔥 Наш сайт')
    btn1 = types.KeyboardButton('🙉 Где нас послушать')
    btn2 = types.KeyboardButton('🙈 Мы в соцсетях')
    btn3 = types.KeyboardButton('🙊 Обратная связь')
    markup.row (btn0)
    markup.row (btn1)
    markup.row (btn2)
    markup.row (btn3)
    bot.send_message(message.chat.id, 'Выберите интересующий вас раздел', reply_markup=markup)

@bot.message_handler(content_types=['text'])
def body(message):
    
    if message.text == '🔥 Наш сайт':
        
        start_markup = telebot.types.InlineKeyboardMarkup()
        btn0 = types.InlineKeyboardButton(text='Добро пожаловать!', url='http://chetamnovosti.ru')
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        btn14 = types.KeyboardButton('🔙 Обратно')
        start_markup.row(btn0)
        markup.row(btn14)
        bot.send_message(message.chat.id, '🫶 На сайте вы найдёте подробную информацию о подкасте и его ведущих', reply_markup = start_markup)
        bot.send_message(message.from_user.id, 'А ещё на страничке с выпусками мы выкладываем разные дополнительные материалы 🎁', reply_markup=markup, parse_mode='Markdown')
    
        
    elif message.text == '🙉 Где нас послушать':
        
        start_markup = telebot.types.InlineKeyboardMarkup()
        btn4 = types.InlineKeyboardButton(text='Apple Podcasts', url='https://podcasts.apple.com/ru/podcast/чё-там-новости/id1523225500')
        btn5 = types.InlineKeyboardButton(text='Яндекс.Музыка', url='https://music.yandex.ru/album/11402620')
        btn6 = types.InlineKeyboardButton(text='Подкасты ВКонтакте', url='https://vk.com/podcasts-197058964')
        btn7 = types.InlineKeyboardButton(text='Google Podcasts', url='https://www.google.com/podcasts?feed=aHR0cHM6Ly9hbmNob3IuZm0vcy8yYTRhN2EyMC9wb2RjYXN0L3Jzcw==')
        btn8 = types.InlineKeyboardButton(text='Mave', url='https://che-tam-novosti.mave.digital/')
        btn9 = types.InlineKeyboardButton(text='Soundstream', url='https://soundstream.media/channel/che-tam-novosti')
        btn10 = types.InlineKeyboardButton(text='Spotify', url='https://open.spotify.com/show/0eNkvFFle5c8NFo0GCS7WW')
        btn11 = types.InlineKeyboardButton(text='Castbox', url='https://castbox.fm/channel/Че-там-новости-id3103700')
        btn12 = types.InlineKeyboardButton(text='Podcast.RU', url='https://podcast.ru/1523225500')
        btn13 = types.InlineKeyboardButton(text='PocketCast', url='https://pca.st/itunes/1523225500')        
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        btn14 = types.KeyboardButton('🔙 Обратно')
        start_markup.row(btn4)
        start_markup.row(btn5)
        start_markup.row(btn6)
        start_markup.row(btn7)
        start_markup.row(btn8)
        start_markup.row(btn9)
        start_markup.row(btn10)
        start_markup.row(btn11)
        start_markup.row(btn12)
        start_markup.row(btn13)
        markup.row(btn14)
        bot.send_message(message.chat.id, 'На любой платформе ❤️ На любой вкус!', reply_markup = start_markup)
        bot.send_message(message.from_user.id, 'Подписывайтесь, чтобы не пропустить новый выпуск!', reply_markup=markup, parse_mode='Markdown')
        
                       
    elif message.text == '🙈 Мы в соцсетях':
        
        start_markup = telebot.types.InlineKeyboardMarkup()
        btn15 = types.InlineKeyboardButton(text='Мы ВКонтакте', url='https://vk.com/che_tam_novosti')
        btn16 = types.InlineKeyboardButton(text='Телеграм канал', url='https://t.me/CheTamNovosti')     
        btn17 = types.InlineKeyboardButton(text='Наш Инстаграм', url='https://instagram.com/che_tam_novosti/')
        btn18 = types.InlineKeyboardButton(text='Youtube', url='https://www.youtube.com/channel/UCW5ggyOrfJu6CDxTFkI7V-Q')
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        btn14 = types.KeyboardButton('🔙 Обратно')
        start_markup.row(btn15)
        start_markup.row(btn16)
        start_markup.row(btn17)
        start_markup.row(btn18)
        markup.row(btn14)
        bot.send_message(message.from_user.id,'Читайте нас! ❤️ Пишите нам!', reply_markup = start_markup)
        bot.send_message(message.from_user.id, 'Мы стараемся показывать то, о чём рассказываем. 🎥 Пруфы, линки и ролики.', reply_markup=markup, parse_mode='Markdown')
 
    elif message.text == '🙊 Обратная связь':
        
        start_markup = telebot.types.InlineKeyboardMarkup()
        btn19 = types.InlineKeyboardButton(text='Пишите в Телеграме 💌', url='https://t.me/+ofyomEN0RCNhZDIy') 
        start_markup.row(btn19)
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        btn14 = types.KeyboardButton('🔙 Обратно')
        markup.add(btn14)
        bot.send_message(message.from_user.id, "❗Вот тут нам можно что-то написать:", reply_markup=start_markup)
        bot.send_message(message.from_user.id, str(message.from_user.first_name) + ',' + ' спасибо! 📜 Обязательно всё прочитаем!', reply_markup=markup)

    elif message.text == '🔙 Обратно':
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        btn0 = types.KeyboardButton('🔥 Наш сайт')
        btn1 = types.KeyboardButton('🙉 Где нас послушать')
        btn2 = types.KeyboardButton('🙈 Мы в соцсетях')
        btn3 = types.KeyboardButton('🙊 Обратная связь')
        markup.add(btn0, btn1, btn2, btn3)
        bot.send_message(message.from_user.id, 'Выберите интересующий вас раздел', reply_markup=markup)
                         
bot.infinity_polling()                 
    
                     


# In[ ]:





# In[ ]:




