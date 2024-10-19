import asyncio
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import json
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
import time
import random
from bs4 import BeautifulSoup
from selenium.webdriver.chrome.options import ChromiumOptions
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
import sys


app = Flask(__name__)
socketio = SocketIO(app, async_mode='threading')

bot_status = "Idle"
total_symbols = 0

from bs4 import BeautifulSoup


def extract_text_from_html(html_content):
    # Replace non-breaking spaces in the raw HTML first
    html_content = html_content.replace('\xa0', ' ')

    # Handle any specific span replacements
    html_content = html_content.replace(
        """<span class="token_unit  _clr"><span class="_enter"> </span><br></span>""",
        """<span class="token_unit  _clr">в</span>"""
    )

    # Parse the modified HTML with BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')

    # Extract text
    text = soup.get_text()

    # Log non-fixed text for debugging
    print(f'non-fixed: {text}')

    # Replace double spaces and any missed non-breaking spaces
    text = text.replace('  ', ' ')  # Replace double spaces with single space
    text = text.replace('\xa0', ' ')  # Replace non-breaking spaces
    text = text.replace('\u200B', '')  # Remove zero-width spaces
    text = text.strip()  # Remove leading and trailing spaces

    # Log fixed text for debugging
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

        # Initialize ActionChains to send keys to the whole page
        actions = ActionChains(driver)

        # Track the last character to avoid typing two spaces consecutively
        last_char = None

        for char in text:
            print(f'Typing character: "{char}"')  # Debugging

            # Only type a space if it's not following another space
            if char == " " and last_char == " ":
                continue  # Skip duplicate spaces

            # Send the key to the page
            if char == "в":
                actions.send_keys(Keys.ENTER)
            else:
                actions.send_keys(char)

            actions.perform()  # Perform the action on the page

            last_char = char  # Update last character
            symbols_typed += 1

            # Emit an update every 30 characters
            if symbols_typed % 30 == 0:
                socketio.emit('update', {'typed': symbols_typed, 'left': total_symbols - symbols_typed, 'status': bot_status})

            # Introduce delay between keystrokes
            time.sleep(random.uniform(self.delay_min, self.delay_max))

def start_typing_task(task_url, cookies_file, req_cps):
    global bot_status
    driver = None
    try:
        bot_status = "Running... (Setting options)"
        socketio.emit('update', {'typed': 0, 'left': 0, 'status': bot_status})
        socketio.emit('extracted', {'text': 'not loaded yet'})
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument("--headless")  # Ensure headless mode is enabled
        chrome_options.add_argument("--no-sandbox")  # Required to run in Docker
        #chrome_options.add_argument("--disable-dev-shm-usage")  # Overcome limited resource problems
        chrome_options.add_argument("--disable-gpu")
        #
        chrome_options.add_argument("--window-size=1920,1080")  # Set window size for headless mode
        bot_status = "Running... (Running browser | options= --headless)"
        socketio.emit('update', {'typed': 0, 'left': 0, 'status': bot_status})
        driver = webdriver.Chrome(options=chrome_options)  # Or specify the path: webdriver.Chrome('/path/to/chromedriver')

        bot_status = "Running... (Opening page)"
        socketio.emit('update', {'typed': 0, 'left': 0, 'status': bot_status})
        driver.get(task_url)

        if os.path.exists(cookies_file):
            with open(cookies_file, 'r') as f:
                cookies = json.load(f)
                for cookie in cookies:
                    if cookie.get('domain') and cookie['domain'] in task_url:
                        driver.add_cookie(cookie)
        driver.get(task_url)

        time.sleep(2)
        bot_status = "Running... (Extracting text)"
        socketio.emit('update', {'typed': 0, 'left': 0, 'status': bot_status})
        target_div = driver.find_element(By.CLASS_NAME, "typable")  # Replace "typable" with the correct selector if needed.
        html_content = target_div.get_attribute('outerHTML')
        text_to_type = extract_text_from_html(html_content)
        socketio.emit('extracted', {'text': text_to_type})

        bot_status = "Running... (Typing!)"
        socketio.emit('update', {'typed': 0, 'left': 0, 'status': bot_status})

        #driver.get('https://www.rapidtables.com/tools/notepad.html')

        typer = Typer(req_cps)
        typer.type_text(text_to_type, driver)  # Call type_text with the driver
    except Exception as e:
        print(f"Error in typing task: {e}")
        bot_status = "Error"
        socketio.emit('error', {'message': str(e), 'status': bot_status})
    finally:
        if driver:
            socketio.emit('update', {'typed': total_symbols, 'left': 0, 'status': 'Waiting for results...'})
            time.sleep(3)
            driver.quit()
            bot_status = "Finished"
            socketio.emit('update', {'typed': total_symbols, 'left': 0, 'status': bot_status})

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start', methods=['POST'])
def start_bot():
    global bot_status

    if 'cookies' not in request.files or 'task_link' not in request.form:
        return "Cookies file and task link are required!", 400

    cookies_file = request.files['cookies']
    task_link = request.form['task_link']
    req_cps = int(request.form['cps'])

    cookies_file_path = os.path.join('cookies.json')
    cookies_file.save(cookies_file_path)

    socketio.start_background_task(start_typing_task, task_link, cookies_file_path, req_cps) # Correct way to start
    return jsonify({'message': 'Bot started successfully!'})

@app.route('/status', methods=['GET'])
def get_status():
    global bot_status
    return jsonify({'status': bot_status})

if __name__ == '__main__':
    socketio.run(app, debug=True, port=int(sys.argv[1]), host='0.0.0.0')
