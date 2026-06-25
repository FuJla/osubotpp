import time
import threading
import requests
import irc.bot
from ossapi import Ossapi
from rosu_pp_py import Beatmap, Performance
from http.server import BaseHTTPRequestHandler, HTTPServer
import os

# --- НАСТРОЙКИ ---
IRC_PASSWORD = "ac576156"  # Ваш IRC-пароль с сайта osu!
USER_NAME = "showheart"             # Ваш токен-ник в игре (без пробелов, используйте _)
CLIENT_ID = 61392                         # Client ID из настроек OAuth
CLIENT_SECRET = "XdsyysAqQFZzVec4XadziznQ8HhBZ26bwYWovbcS" # Client Secret из настроек OAuth

class OsuRecentBot(irc.bot.SingleServerIRCBot):
    def __init__(self):
        # Подключаемся к Bancho под вашим именем
        super().__init__([("irc.ppy.sh", 6667, IRC_PASSWORD)], USER_NAME, USER_NAME)
        self.api = Ossapi(CLIENT_ID, CLIENT_SECRET)
        self.last_score_id = None
        self.user_id = self.api.user(USER_NAME).id

    def on_welcome(self, connection, event):
        print("Бот успешно зашел на Bancho! Мониторинг запущен.")
        # Запускаем бесконечный опрос API в отдельном потоке
        threading.Thread(target=self.track_recent_scores, daemon=True).start()

    def track_recent_scores(self):
        while True:
            try:
                # Берем самую последнюю сыгранную карту
                recent_scores = self.api.user_scores(self.user_id, type="recent", limit=1)
                
                if recent_scores:
                    score = recent_scores
                    
                    if score.id != self.last_score_id:
                        if self.last_score_id is not None:
                            self.process_and_send_score(score)
                        self.last_score_id = score.id
            except Exception as e:
                print(f"Ошибка API: {e}")
                
            time.sleep(12) # Безопасный интервал опроса API

    def process_and_send_score(self, score):
        acc = score.accuracy * 100
        c300 = score.statistics.count_300
        c100 = score.statistics.count_100
        c50 = score.statistics.count_50
        miss = score.statistics.count_miss

        if score.pp:
            pp_value = score.pp
        else:
            try:
                # Скачиваем .osu файл для точного просчета PP на unranked/loved
                map_file = requests.get(f"https://ppy.sh{score.beatmap.id}").content
                bmap = Beatmap(bytes=map_file)
                perf = Performance(accuracy=acc, misses=miss, n100=c100, n50=c50, combo=score.max_combo)
                
                if score.mods:
                    perf.set_mods(score.mods.value)
                    
                pp_value = perf.calculate(bmap).pp
            except Exception:
                pp_value = 0

        # Специфический тег [https://ppy.sh ID Текст] делает ссылку кликабельной в чате osu!
        message = (
            f" [https://ppy.sh{score.beatmap.id} {score.beatmapset.title} [{score.beatmap.version}]] "
            f"| Acc: {acc:.2f}% "
            f"| 300: {c300} | 100: {c100} | 50: {c50} | Miss: {miss} "
            f"| PP: {pp_value:.2f}pp"
        )

        try:
            # Отправка сообщения самому себе в ЛС внутри игры
            self.connection.privmsg(USER_NAME, message)
            print(f"Отправлен результат для {score.beatmapset.title}")
        except Exception as e:
            print(f"Не удалось отправить IRC сообщение: {e}")

# Создаем фейковый веб-сервер для Render, чтобы тариф Free не засыпал
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(b"Bot is running successfully!")

def run_web_server():
    # Render автоматически передает порт, берем его или ставим 8000
    port = int(os.environ.get("PORT", 8000))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    print(f"Фейковый веб-сервер запущен на порту {port}")
    server.serve_forever()

if __name__ == "__main__":
    # Запускаем фейковый веб-сайт в отдельном потоке для Render
    threading.Thread(target=run_web_server, daemon=True).start()
    
    # Запускаем нашего основного osu! бота
    bot = OsuRecentBot()
    bot.start()
