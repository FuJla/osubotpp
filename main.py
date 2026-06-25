import os
import threading
import requests
import irc.bot
from flask import Flask, request, jsonify
from rosu_pp_py import Beatmap, Performance

# --- НАСТРОЙКИ ---
IRC_PASSWORD = "ac576156"  # Ваш IRC-пароль с сайта osu.ppy.sh/p/irc
USER_NAME = "showheart"             # Ваш ник в игре (пробелы замените на _)

app = Flask(__name__)
irc_client = None

class OsuIRCClient(irc.bot.SingleServerIRCBot):
    def __init__(self):
        super().__init__([("irc.ppy.sh", 6667, IRC_PASSWORD)], USER_NAME, USER_NAME)

    def on_welcome(self, connection, event):
        print("Бот успешно подключился к Bancho IRC!")

    def send_osu_message(self, message):
        try:
            self.connection.privmsg(USER_NAME, message)
            print("Сообщение успешно отправлено в ЛС osu!")
        except Exception as e:
            print(f"Ошибка отправки IRC: {e}")

@app.route('/', methods=['GET'])
def health_check():
    return "Бот работает!", 200

@app.route('/webhook', methods=['POST'])
def osu_webhook():
    data = request.get_json()
    if not data or data.get("event") != "user.score.new":
        return jsonify({"status": "ignored"}), 200

    score_data = data.get("data", {})
    acc = score_data.get("accuracy", 0) * 100
    statistics = score_data.get("statistics", {})
    c300 = statistics.get("count_300", 0)
    c100 = statistics.get("count_100", 0)
    c50 = statistics.get("count_50", 0)
    miss = statistics.get("count_miss", 0)
    max_combo = score_data.get("max_combo", 0)
    
    beatmap = score_data.get("beatmap", {})
    beatmap_id = beatmap.get("id")
    beatmapset = score_data.get("beatmapset", {})

    if score_data.get("pp"):
        pp_value = score_data.get("pp")
    else:
        try:
            map_file = requests.get(f"https://ppy.sh{beatmap_id}").content
            bmap = Beatmap(bytes=map_file)
            perf = Performance(accuracy=acc, misses=miss, n100=c100, n50=c50, combo=max_combo)
            pp_value = perf.calculate(bmap).pp
        except:
            pp_value = 0

    message = (
        f" [https://ppy.sh{beatmap_id} {beatmapset.get('title', 'Map')} [{beatmap.get('version', 'Diff')}]] "
        f"| Acc: {acc:.2f}% | 300: {c300} | 100: {c100} | 50: {c50} | Miss: {miss} | PP: {pp_value:.2f}pp"
    )

    if irc_client and irc_client.connection.is_connected():
        irc_client.send_osu_message(message)

    return jsonify({"status": "success"}), 200

def start_irc():
    global irc_client
    irc_client = OsuIRCClient()
    irc_client.start()

if __name__ == "__main__":
    # Запускаем постоянное подключение IRC в фоне
    threading.Thread(target=start_irc, daemon=True).start()
    # Запускаем веб-сервер Flask для приема вебхуков от osu!
    port = int(os.environ.get("PORT", 7860))  # Папка Spaces слушает порт 7860
    app.run(host="0.0.0.0", port=port)
