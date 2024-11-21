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
from flask import after_this_request

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
    def __init__(self, cps=5, session_filename=None):
        self.delay_min = 1 / cps + random.uniform((1 / cps) / 100, 1 / cps)
        self.delay_max = 1 / cps + random.uniform((1 / cps) / 100, 1 / cps)
        self.cps = cps
        self.session_filename = session_filename  # File to log each typed symbol and delay
        print(f'Delays set to: min={self.delay_min}, max={self.delay_max}')

    def type_text(self, text: str, driver):
        global bot_status, total_symbols
        symbols_typed = 0
        total_symbols = len(text)

        # Initialize ActionChains to send keys to the whole page
        actions = ActionChains(driver)

        # Track the last character to avoid typing two spaces consecutively
        last_char = None

        # Open the session log file for writing
        with open(self.session_filename, 'a', encoding='utf-8') as log_file:
            start_time = time.time()
            log_file.write(f"Typing Session Started: {time.ctime(start_time)}\n\n")

            for char in text:
                # Only type a space if it's not following another space
                if char == " " and last_char == " ":
                    continue  # Skip duplicate spaces

                # Send the key to the page
                if char == "в":
                    actions.send_keys(Keys.ENTER)
                    log_file.write(f"Symbol: ENTER\n")  # Log ENTER
                else:
                    actions.send_keys(char)
                    log_file.write(f"Symbol: {char}\n")  # Log the character

                actions.perform()  # Perform the action on the page

                last_char = char  # Update last character
                symbols_typed += 1

                # Introduce delay between keystrokes and log it
                delay = random.uniform(self.delay_min, self.delay_max)
                log_file.write(f"Delay before next symbol: {delay:.3f} seconds\n\n")
                time.sleep(delay)

                # Emit an update every 30 characters
                if symbols_typed % (self.cps // 2) == 0:
                    socketio.emit('update', {'typed': symbols_typed, 'left': total_symbols - symbols_typed, 'status': bot_status})

            end_time = time.time()
            time_spent = end_time - start_time
            log_file.write(f"Typing Session Ended: {time.ctime(end_time)}\n")
            log_file.write(f"Total Time Spent Typing: {time_spent:.2f} seconds\n")

def start_typing_task(task_url, cookies_file, req_cps):
    global bot_status
    driver = None
    session_id = random.randint(1, 10000)
    session_filename = f"typing_session_{session_id}.txt"  # Path to save the log file
    html_file_path = f"output_{session_id}.html"  # Path to save the HTML file

    try:
        bot_status = "Running... (Setting options)"
        socketio.emit('update', {'typed': 0, 'left': 0, 'status': bot_status})
        socketio.emit('extracted', {'text': 'not loaded yet'})
        
        chrome_options = ChromeOptions()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disk-cache-size=512")
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

        # Start typing using the Typer class and log each typed character
        typer = Typer(req_cps, session_filename)  # Pass the session filename to the Typer class
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

            # Emit the final status update and the link to download the session log
            socketio.emit('update', {
                'typed': total_symbols,
                'left': 0,
                'status': f'Finished /download/{session_filename}'
            })
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

@app.route('/api/send', methods=['POST'])
def send_request():
    """ Endpoint to send a request to another API server-side """
    api_url = request.json.get('url')
    method = request.json.get('method', 'GET')
    body = request.json.get('body')

    # Forward the request to the external API
    try:
        if method == 'POST':
            response = requests.post(api_url, json=body)
        elif method == 'GET':
            response = requests.get(api_url)
        elif method == 'PUT':
            response = requests.put(api_url, json=body)
        elif method == 'DELETE':
            response = requests.delete(api_url)
        elif method == 'PATCH':
            response = requests.patch(api_url, json=body)
        else:
            return jsonify({"error": "Unsupported method"}), 400

        # Check response type
        try:
            response_json = response.json()
            return jsonify(response_json), response.status_code
        except ValueError:
            # If response is not JSON, return it as text
            return response.text, response.status_code

    except Exception as e:
        return jsonify({"error": str(e)}), 500

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
    global bot_status
    url2 = 'https://tracking.rosettastone.com/ee/ce/lausd8264/users/4258406/path_step_scores?course=SK-ENG-L5-NA-PE-NA-NA-Y-3&unit_index=0&lesson_index=3&path_type=general&occurrence=1&method=get'
    url3 = 'https://tracking.rosettastone.com/ee/ce/lausd8264/users/4258406/path_step_scores?course=SK-ENG-L5-NA-PE-NA-NA-Y-3&unit_index=0&lesson_index=3&path_type=general&occurrence=1&path_step_media_id=PATHSTEP_160529222&_method=put'
    url4 = 'https://tracking.rosettastone.com/ee/ce/lausd8264/users/4258406/lag_alarms'
    url5 = 'https://tracking.rosettastone.com/ee/ce/lausd8264/users/4258406/path_scores?course=SK-ENG-L5-NA-PE-NA-NA-Y-3&unit_index=0&lesson_index=3&path_type=general&occurrence=1&_method=put'
    time_left = duration
    successful_requests = 0  # Counter for successful requests
    unsuccessful_requests = 0  # Counter for unsuccessful requests

    # Create a unique filename for each session
    session_id = random.randint(1, 10000)
    session_filename = f"session_{session_id}.txt"
    session_filepath = os.path.join('.', session_filename)

    # Open the file to log responses
    with open(session_filepath, 'w', encoding='utf-8') as log_file:
        log_file.write(f"Session ID: {session_id}\n")
        log_file.write(f"Duration: {duration} seconds\n")
        log_file.write(f"Start Time: {time.ctime()}\n\n")

        while time_left >= 0:
            # Send OPTIONS request with cookies
            try:
                options_response = requests.options(url, cookies=cookies)
                response_text = options_response.text  # Capture the response text
                log_file.write(f"URL: {url}\n")
                log_file.write(f"Response Status: {options_response.status_code}\n")
                log_file.write(f"Response Time: {time.ctime()}\n")
                log_file.write(f"Response Text: {response_text}\n\n")  # Write the response text

                # Emit updates to the client
                socketio.emit('update', {'message': 'OPTIONS request sent (#1)', 'status_code': options_response.status_code})

                # Check response status and update the counter
                if options_response.status_code == 200:
                    successful_requests += 1
                else:
                    unsuccessful_requests += 1

            except Exception as e:
                log_file.write(f"Error sending OPTIONS request: {e}\n")
                socketio.emit('error', {'message': f'Error sending OPTIONS request: {e}'})
                unsuccessful_requests += 1  # Increment unsuccessful counter

            # Repeat for other URLs (url2, url3, url4, url5)
            urls = [url2, url3, url4, url5]
            for i, request_url in enumerate(urls, start=2):
                try:
                    options_response = requests.options(request_url, cookies=cookies)
                    response_text = options_response.text  # Capture the response text
                    log_file.write(f"URL: {request_url}\n")
                    log_file.write(f"Response Status: {options_response.status_code}\n")
                    log_file.write(f"Response Time: {time.ctime()}\n")
                    log_file.write(f"Response Text: {response_text}\n\n")  # Write the response text

                    # Emit updates to the client
                    socketio.emit('update', {'message': f'OPTIONS request sent (#{i})', 'status_code': options_response.status_code})

                    # Check response status and update the counter
                    if options_response.status_code == 200:
                        successful_requests += 1
                    else:
                        unsuccessful_requests += 1

                except Exception as e:
                    log_file.write(f"Error sending OPTIONS request to {request_url}: {e}\n")
                    socketio.emit('error', {'message': f'Error sending OPTIONS request: {e}'})
                    unsuccessful_requests += 1

            # Emit the counts of successful and unsuccessful requests
            socketio.emit('update', {
                'message': f'Time remaining: {time_left} seconds',
                'successful_requests': successful_requests,
                'unsuccessful_requests': unsuccessful_requests,
                'req_status': 'Running'
            })

            time.sleep(5)  # Wait for 5 seconds before the next request
            time_left -= 5
            print(f'Time remaining: {time_left} seconds')

        # Emit the completion of the session
        socketio.emit('update', {'message': 'Session finished', 'status_code': 200})
        log_file.write(f"Session Completed at: {time.ctime()}\n")
        log_file.write(f"Total Successful Requests: {successful_requests}\n")
        log_file.write(f"Total Unsuccessful Requests: {unsuccessful_requests}\n")

    # Emit the link for the download of the session file
    socketio.emit('update', {
        'message': f'Session completed. Download the session log: /download/{session_filename}'
    })


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

from flask import after_this_request

@app.route('/download/<filename>')
def download_file(filename):
    file_path = os.path.join('.', filename)

    # Check if the file is a log file for either typing or rs logs
    if (filename.startswith('typing_session_') or filename.startswith('session_')) and filename.endswith('.txt'):
        
        @after_this_request
        def remove_file(response):
            try:
                os.remove(file_path)  # Remove the file after the response is sent
                print(f"Deleted file: {file_path}")
            except Exception as e:
                print(f"Error deleting file: {e}")
            return response

    # Send the file to the client for download
    return send_from_directory(directory='.', path=filename, as_attachment=True)


if __name__ == '__main__':
    socketio.run(app, port=int(sys.argv[1]), host='0.0.0.0')
