import asyncio
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
import json
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
import time
import random
from bs4 import BeautifulSoup
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options as ChromeOptions
import sys

app = Flask(__name__)
socketio = SocketIO(app, async_mode='threading')

bot_status = "Idle"
total_symbols = 0
# Define a verification code
VERIFICATION_CODE = "slvrealpass"  # Replace with your actual code

def extract_text_from_html(html_content):
    html_content = html_content.replace('\xa0', ' ')
    html_content = html_content.replace(
        """<span class="token_unit  _clr"><span class="_enter"> </span><br></span>""",
        """<span class="token_unit  _clr">в</span>"""
    )
    soup = BeautifulSoup(html_content, 'html.parser')
    text = soup.get_text()
    print(f'non-fixed: {text}')
    text = text.replace('  ', ' ')
    text = text.replace('\xa0', ' ')
    text = text.replace('\u200B', '')
    text = text.strip()
    print(f'fixed: {text}')
    return text

class Typer:
    def __init__(self, cps=5):
        self.delay_min = 1 / cps + random.uniform((1 / cps) / 100, 1 / cps)
        self.delay_max = 1 / cps + random.uniform((1 / cps) / 100, 1 / cps)
        print(f'Delays set to: min={self.delay_min}, max={self.delay_max}')

    def type_text(self, text: str, driver):
        global bot_status, total_symbols
        symbols_typed = 0
        total_symbols = len(text)
        actions = ActionChains(driver)
        last_char = None

        for char in text:
            if char == " " and last_char == " ":
                continue

            if char == "в":
                actions.send_keys(Keys.ENTER)
            else:
                actions.send_keys(char)

            actions.perform()
            last_char = char
            symbols_typed += 1

            if symbols_typed % 30 == 0:
                socketio.emit('update', {'typed': symbols_typed, 'left': total_symbols - symbols_typed, 'status': bot_status})

            time.sleep(random.uniform(self.delay_min, self.delay_max))

def start_typing_task(task_url, cookies_file, req_cps):
    global bot_status
    driver = None
    html_file_path = f"output_{random.randint(1, 10000)}.html"

    try:
        bot_status = "Running... (Setting options)"
        socketio.emit('update', {'typed': 0, 'left': 0, 'status': bot_status})
        socketio.emit('extracted', {'text': 'not loaded yet'})

        chrome_options = ChromeOptions()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disk-cache-size=64")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--single-process")
        chrome_options.add_argument("--window-size=620,480")
        chrome_options.add_argument("--disable-application-cache")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--js-flags=--max_old_space_size=512")

        bot_status = "Running... (Running browser | options= --headless)"
        socketio.emit('update', {'typed': 0, 'left': 0, 'status': bot_status})

        driver = webdriver.Chrome(options=chrome_options)

        bot_status = "Running... (Opening page)"
        socketio.emit('update', {'typed': 0, 'left': 0, 'status': bot_status})
        driver.get(task_url)

        if os.path.exists(cookies_file):
            with open(cookies_file, 'r') as f:
                cookies = json.load(f)

            bot_status = "Running... (Loading cookies)"
            socketio.emit('update', {'typed': 0, 'left': 0, 'status': bot_status})
            for cookie in cookies:
                driver.add_cookie(cookie)

            driver.refresh()

        time.sleep(3)

        bot_status = "Running... (Extracting HTML)"
        socketio.emit('update', {'typed': 0, 'left': 0, 'status': bot_status})
        html_content = driver.page_source

        with open(html_file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        bot_status = "Running... (Extracting text)"
        socketio.emit('update', {'typed': 0, 'left': 0, 'status': bot_status})
        text_to_type = extract_text_from_html(html_content)

        bot_status = "Running... (Typing)"
        typer = Typer(req_cps)
        typer.type_text(text_to_type, driver)

    except Exception as e:
        print(f"Error: {e}")
        socketio.emit('error', {'message': str(e), 'status': 'Idle'})
    finally:
        if driver:
            driver.quit()
        bot_status = "Idle"
        socketio.emit('update', {'typed': total_symbols, 'left': 0, 'status': bot_status})

@app.route('/start', methods=['POST'])
def start_bot():
    global bot_status

    # Check if the bot is already running
    if bot_status != "Idle":
        socketio.emit('error', {'message': 'A typing task is already running. Please wait until it finishes. Maybe someone else is typing now?'})
        return jsonify({'message': 'A typing task is already running. Please wait until it finishes. Maybe someone else is typing now?'}), 400

    # Check if verification code is provided
    if 'verification_code' not in request.form:
        socketio.emit('error', {'message': 'Verification code is required!'})
        return jsonify({'message': 'Verification code is required!'}), 400

    # Validate the verification code
    if request.form['verification_code'] != VERIFICATION_CODE:
        socketio.emit('error', {'message': 'Invalid verification code! You may be not allowed to run this bot'})
        return jsonify({'message': 'Invalid verification code!'}), 403

    if 'cookies' not in request.files or 'task_link' not in request.form:
        return "Cookies file and task link are required!", 400

    cookies_file = request.files['cookies']
    task_link = request.form['task_link']
    req_cps = int(request.form['cps'])

    cookies_file_path = os.path.join('cookies.json')
    cookies_file.save(cookies_file_path)

    # Start the typing task in the background
    socketio.start_background_task(start_typing_task, task_link, cookies_file_path, req_cps)
    return jsonify({'message': 'Bot started successfully!'})

if __name__ == '__main__':
    socketio.run(app, debug=True, port=int(sys.argv[1]), host='0.0.0.0')
