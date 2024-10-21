import asyncio
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
import json
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
import random
from bs4 import BeautifulSoup
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.options import Options as ChromeOptions
import sys, time
import requests, threading

app = Flask(__name__)
socketio = SocketIO(app, async_mode='threading')  # Change async_mode to 'eventlet' for asyncio support

bot_status = "Idle"
total_symbols = 0
url = 'https://lcp.rosettastone.com/api/v3/session/heartbeat'

def extract_text_from_html(html_content):
    # Replace non-breaking spaces in the raw HTML first
    html_content = html_content.replace('\xa0', ' ')

    # Handle any specific span replacements
    html_content = html_content.replace(
        """<span class="token_unit  _clr"><span class="_enter">&nbsp;</span><br></span>""",
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
        self.cps = cps
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
            if symbols_typed % (self.cps // 2) == 0:
                socketio.emit('update', {'typed': symbols_typed, 'left': total_symbols - symbols_typed, 'status': bot_status})

            # Introduce delay between keystrokes
            time.sleep(random.uniform(self.delay_min, self.delay_max))

def start_typing_task(task_url, cookies_file, req_cps):
    global bot_status
    driver = None
    html_file_path = f"output_{random.randint(1, 10000)}.html"  # Path to save the HTML file

    try:
        bot_status = "Running... (Setting options)"
        socketio.emit('update', {'typed': 0, 'left': 0, 'status': bot_status})
        socketio.emit('extracted', {'text': 'not loaded yet'})
        
        chrome_options = ChromeOptions()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disk-cache-size=128")
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

        # Load cookies if provided
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
        
        # Extract the text from the located div
        target_div = driver.find_element(By.CLASS_NAME, "typable")  # Replace "typable" with the correct selector if needed.
        html_content = target_div.get_attribute('outerHTML')
        text_to_type = extract_text_from_html(html_content)
        socketio.emit('extracted', {'text': text_to_type.replace('в', '\n')})
        bot_status = "Running... (Typing!)"
        socketio.emit('update', {'typed': 0, 'left': len(text_to_type), 'status': bot_status})

        # Start typing using the Typer class
        typer = Typer(req_cps)
        typer.type_text(text_to_type, driver)  # Call type_text with the driver

    except Exception as e:
        print(f"Error in typing task: {e}")
        bot_status = "Error"
        socketio.emit('error', {'message': str(e), 'status': bot_status})
    finally:
        if driver:
            for i in range(10):
                bot_status = f"Waiting for results ({10-i} seconds)..."
                time.sleep(1)
            # Save the HTML content to a file
            with open(html_file_path, 'w', encoding='utf-8') as f:
                try:
                    f.write(driver.page_source)
                except Exception as e:
                    print(f"Error saving HTML: {e}")
            driver.quit()

            # Emit the download link and final status update
            socketio.emit('update', {'typed': total_symbols, 'left': 0, 'status': 'Finished'})
            bot_status = "Idle"
        else:
            socketio.emit('error', {'message': 'NO DRIVER!', 'status': 'Error'})

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/whyicreatedthat')
def whypage():
    return render_template('why.html')

@app.route('/postman')
def postman():
    return render_template('postman.html')

@app.route('/api/resource/<int:item_id>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD'])
def resource(item_id):
    if request.method == 'GET':
        # Retrieve an item
        item = data_store.get(item_id)
        if item is None:
            return jsonify({"error": "Item not found"}), 404
        return jsonify({"id": item_id, "data": item}), 200

    elif request.method == 'POST':
        # Create a new item
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        # Store the data in the in-memory store
        data_store[item_id] = data
        return jsonify({"status": "success", "id": item_id, "data": data}), 201

    elif request.method == 'PUT':
        # Update an existing item
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        if item_id not in data_store:
            return jsonify({"error": "Item not found"}), 404
        
        data_store[item_id] = data
        return jsonify({"status": "success", "id": item_id, "data": data}), 200

    elif request.method == 'DELETE':
        # Delete an item
        if item_id in data_store:
            del data_store[item_id]
            return jsonify({"status": "success", "id": item_id}), 204
        else:
            return jsonify({"error": "Item not found"}), 404

    elif request.method == 'PATCH':
        # Partially update an existing item
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        if item_id not in data_store:
            return jsonify({"error": "Item not found"}), 404
        
        # Update the existing item with the new data
        data_store[item_id].update(data)
        return jsonify({"status": "success", "id": item_id, "data": data_store[item_id]}), 200

    elif request.method == 'OPTIONS':
        # Return allowed methods for the resource
        return jsonify({"allowed_methods": ["GET", "POST", "PUT", "DELETE", "PATCH"]}), 200

    elif request.method == 'HEAD':
        # Return headers for the resource
        if item_id in data_store:
            return jsonify(), 200
        else:
            return jsonify({"error": "Item not found"}), 404

    return jsonify({"error": "Method not allowed"}), 405

@app.route('/start', methods=['POST'])
def start_bot():
    global bot_status

    # Check if the bot is already running
    if bot_status != "Idle":
        socketio.emit('error', {'message': 'A typing task is already running. Please wait until it finishes. Maybe someone else is typing now?'})
        return jsonify({'message': 'A typing task is already running. Please wait until it finishes. Maybe someone else is typing now?'}), 400

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
    
def send_requests(duration, cookies, url):
    url2 = 'https://tracking.rosettastone.com/ee/ce/lausd8264/users/4258406/path_step_scores?course=SK-ENG-L5-NA-PE-NA-NA-Y-3&unit_index=0&lesson_index=3&path_type=general&occurrence=1&method=get'
    url3 = 'https://tracking.rosettastone.com/ee/ce/lausd8264/users/4258406/path_step_scores?course=SK-ENG-L5-NA-PE-NA-NA-Y-3&unit_index=0&lesson_index=3&path_type=general&occurrence=1&path_step_media_id=PATHSTEP_160529222&_method=put'
    url4 = 'https://tracking.rosettastone.com/ee/ce/lausd8264/users/4258406/lag_alarms'
    url5 = 'https://tracking.rosettastone.com/ee/ce/lausd8264/users/4258406/path_scores?course=SK-ENG-L5-NA-PE-NA-NA-Y-3&unit_index=0&lesson_index=3&path_type=general&occurrence=1&_method=put'
    time_left = duration
    successful_requests = 0  # Counter for successful requests
    unsuccessful_requests = 0  # Counter for unsuccessful requests

    while time_left >= 0:
        # Send OPTIONS request with cookies
        try:
            options_response = requests.options(url, cookies=cookies)
            print('OPTIONS Response Status Code:', options_response.status_code)
            socketio.emit('update', {'message': 'OPTIONS request sent (#1)', 'status_code': options_response.status_code})

            # Check response status and update the counter
            if options_response.status_code == 200:
                successful_requests += 1
            else:
                unsuccessful_requests += 1

        except Exception as e:
            print(f'Error sending OPTIONS request: {e}')
            socketio.emit('error', {'message': f'Error sending OPTIONS request: {e}'})
            unsuccessful_requests += 1  # Increment unsuccessful counter

        try:
            params = {
                'course': 'SK-ENG-L5-NA-PE-NA-NA-Y-3',
                'unit_index': '0',
                'lesson_index': '3',
                'path_type': 'general',
                'occurrence': '1',
                'method': 'get'
            }
            options_response = requests.options(url2, cookies=cookies, params=params)
            print('OPTIONS Response Status Code:', options_response.status_code)
            socketio.emit('update', {'message': 'OPTIONS request sent (#2)', 'status_code': options_response.status_code})

            # Check response status and update the counter
            if options_response.status_code == 200:
                successful_requests += 1
            else:
                unsuccessful_requests += 1

        except Exception as e:
            print(f'Error sending OPTIONS request: {e}')
            socketio.emit('error', {'message': f'Error sending OPTIONS request: {e}'})
            unsuccessful_requests += 1  # Increment unsuccessful counter

        try:
            params = {
                'course': 'SK-ENG-L5-NA-PE-NA-NA-Y-3',
                'unit_index': '0',
                'lesson_index': '3',
                'path_type': 'general',
                'occurrence': '1',
                'path_step_media_id': 'PATHSTEP_160529222',
                'method': 'get'
            }
            options_response = requests.options(url3, cookies=cookies, params=params)
            print('OPTIONS Response Status Code:', options_response.status_code)
            socketio.emit('update', {'message': 'OPTIONS request sent (#3)', 'status_code': options_response.status_code})

            # Check response status and update the counter
            if options_response.status_code == 200:
                successful_requests += 1
            else:
                unsuccessful_requests += 1

        except Exception as e:
            print(f'Error sending OPTIONS request: {e}')
            socketio.emit('error', {'message': f'Error sending OPTIONS request: {e}'})
            unsuccessful_requests += 1  # Increment unsuccessful counter

        try:
            options_response = requests.options(url4, cookies=cookies)
            print('OPTIONS Response Status Code:', options_response.status_code)
            socketio.emit('update', {'message': 'OPTIONS request sent (#4)', 'status_code': options_response.status_code})

            # Check response status and update the counter
            if options_response.status_code == 200:
                successful_requests += 1
            else:
                unsuccessful_requests += 1

        except Exception as e:
            print(f'Error sending OPTIONS request: {e}')
            socketio.emit('error', {'message': f'Error sending OPTIONS request: {e}'})
            unsuccessful_requests += 1  # Increment unsuccessful counter

        try:
            params = {
                'course': 'SK-ENG-L5-NA-PE-NA-NA-Y-3',
                'unit_index': '0',
                'lesson_index': '3',
                'path_type': 'general',
                'occurrence': '1',
                'method': 'get'
            }
            options_response = requests.options(url5, cookies=cookies, params=params)
            print('OPTIONS Response Status Code:', options_response.status_code)
            socketio.emit('update', {'message': 'OPTIONS request sent (#5)', 'status_code': options_response.status_code})

            # Check response status and update the counter
            if options_response.status_code == 200:
                successful_requests += 1
            else:
                unsuccessful_requests += 1

        except Exception as e:
            print(f'Error sending OPTIONS request: {e}')
            socketio.emit('error', {'message': f'Error sending OPTIONS request: {e}'})
            unsuccessful_requests += 1  # Increment unsuccessful counter

        # Emit the counts of successful and unsuccessful requests
        socketio.emit('update', {
            'message': f'Time remaining: {time_left} seconds',
            'successful_requests': successful_requests,
            'unsuccessful_requests': unsuccessful_requests,
            'req_status': 'Useless for now'
        })

        time.sleep(5)  # Wait for 5 seconds before the next request
        time_left -= 5
        print(f'Time remaining: {time_left} seconds')

@app.route('/rs')
def rs_page():
    return render_template('rs.html')
    
@app.route('/startrs', methods=['POST'])
def start_rs_bot():
    global url
    duration = int(request.form.get('duration', 0))  # Get duration from form
    cookie_file = request.files['cookies']  # Get the uploaded cookie file

    if duration <= 0:
        return jsonify({'message': 'Invalid duration'}), 400

    # Read cookies from the uploaded JSON file
    cookies = {}
    if cookie_file:
        try:
            cookie_data = json.load(cookie_file)  # Load the JSON data
            for cookie in cookie_data:
                name = cookie['name']
                value = cookie['value']
                cookies[name] = value
        except json.JSONDecodeError as e:
            return jsonify({'message': 'Invalid cookie file format', 'error': str(e)}), 400

    # Start the send_requests function as a background task
    socketio.start_background_task(send_requests, duration, cookies, url)

    # Emit that the bot has started
    socketio.emit('update', {'message': f'Bot started, duration: {duration} seconds'})
    
    return jsonify({'message': 'Bot started', 'duration': duration})

@app.route('/status', methods=['GET'])
def get_status():
    global bot_status
    return jsonify({'status': bot_status})

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(directory='.', path=filename, as_attachment=True)

if __name__ == '__main__':
    socketio.run(app, port=int(sys.argv[1]), host='0.0.0.0')
