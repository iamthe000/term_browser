import sys
import io
import time
import shutil
import urllib.parse
from PIL import Image
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def get_terminal_size():
    size = shutil.get_terminal_size()
    return size.columns, size.lines

def pixels_to_ansi(image):
    pixels = image.load()
    width, height = image.size
    output = []
    for y in range(0, height - 1, 2):
        line = []
        for x in range(width):
            r1, g1, b1 = pixels[x, y]
            r2, g2, b2 = pixels[x, y + 1]
            line.append(f"\x1b[38;2;{r1};{g1};{b1}m\x1b[48;2;{r2};{g2};{b2}m▀")
        line.append("\x1b[0m")
        output.append("".join(line))
    return "\n".join(output)

def fetch_page(driver, url):
    term_width, term_height = get_terminal_size()
    elements = []
    
    try:
        driver.get(url)
        is_ddg_serp = "duckduckgo.com" in driver.current_url and "q=" in driver.current_url

        with open("debug.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        soup = BeautifulSoup(driver.page_source, 'html.parser')

        # 1. Find input boxes and textareas
        for inp in soup.find_all(['input', 'textarea']):
            if inp.get('type') != 'hidden':
                name = inp.get('name') or inp.get('id') or "input"
                elements.append({"type": "INPUT", "name": name, "label": f"入力: [{name}]"})

        # 2. Find links
        links_found = 0
        if is_ddg_serp:
            # Use a more specific selector for search result pages
            link_containers = soup.select('li[data-layout="organic"]')
            for container in link_containers:
                if links_found >= 15: break
                link_tag = container.select_one("h2 a[data-testid=\"result-title-a\"]")
                if not link_tag: continue

                href = link_tag.get('href')
                text = link_tag.get_text(strip=True)

                if href and text:
                    elements.append({"type": "LINK", "url": href, "label": text})
                    links_found += 1
        else:
            # Generic link finding for other pages
            for a in soup.find_all('a', href=True):
                if links_found >= 15: break
                text = a.get_text(strip=True)
                href = a.get('href')
                if text and href and len(text) > 2 and not href.startswith(('javascript:', '#')):
                    full_url = urllib.parse.urljoin(driver.current_url, href)
                    elements.append({"type": "LINK", "url": full_url, "label": text})
                    links_found += 1

    except Exception as e:
        print(f"解析エラー: {e}")

    # Get screenshot directly from Selenium
    img_ansi = ""
    try:
        driver.set_window_size(term_width * 8, (term_height - 12) * 32)
        png_data = driver.get_screenshot_as_png()
        img = Image.open(io.BytesIO(png_data)).convert("RGB")
        pixel_h = int(term_width / 1.2) * 2
        max_h = (term_height - 12) * 2
        img_resized = img.resize((term_width, min(pixel_h, max_h)), Image.Resampling.LANCZOS)
        img_ansi = pixels_to_ansi(img_resized)
    except Exception as e:
        img_ansi = f"\n(画像取得エラー: {e})\n"

    print("\x1b[2J\x1b[H", end="")
    print(img_ansi)
    print(f"\x1b[1;34m--- 操作パネル ({driver.current_url[:40]}...) ---\x1b[0m")
    
    for i, el in enumerate(elements[:12]):
        color = "\033[1;33m" if el['type'] == "INPUT" else "\033[1;32m"
        print(f"{color}[{i+1}] {el['label']}\033[0m")
        
    return elements

def main():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    driver = None
    try:
        driver = webdriver.Chrome(options=chrome_options)

        # If a command-line argument is provided, use it as a search query
        if len(sys.argv) > 1:
            search_query = ' '.join(sys.argv[1:])
            driver.get("https://duckduckgo.com")
            try:
                search_box = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "searchbox_input"))
                )
                search_box.clear()
                search_box.send_keys(search_query)
                search_box.send_keys(Keys.RETURN)
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'li[data-layout="organic"]'))
                )
                fetch_page(driver, driver.current_url)
            except Exception as e:
                print(f"検索エラー: {e}")
            return # Exit after performing the search

        # Interactive mode
        curr_url = "https://duckduckgo.com"
        curr_elements = fetch_page(driver, curr_url)
        
        while True:
            cmd = input("\n🔎 番号/検索/URL (exitで終了): ").strip()
            if cmd.lower() == 'exit': break
            
            if cmd.isdigit():
                idx = int(cmd) - 1
                if 0 <= idx < len(curr_elements):
                    el = curr_elements[idx]
                    
                    if el['type'] == "INPUT":
                        val = input(f"📝 {el['name']} への入力値: ")
                        try:
                            # Use WebDriverWait to ensure the input is interactable
                            input_element = WebDriverWait(driver, 10).until(
                                EC.presence_of_element_located((By.NAME, el['name']))
                            )
                            input_element.clear()
                            input_element.send_keys(val)
                            input_element.send_keys(Keys.RETURN)
                            curr_elements = fetch_page(driver, driver.current_url)
                        except Exception as e:
                            print(f"入力エラー: {e}")
                    else: # LINK
                        curr_elements = fetch_page(driver, el['url'])
            elif cmd.startswith('http'):
                curr_elements = fetch_page(driver, cmd)
            else: # Search
                # Go to DDG home and search from there to be more robust
                driver.get("https://duckduckgo.com")
                try:
                    search_box = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.ID, "searchbox_input"))
                    )
                    search_box.clear()
                    search_box.send_keys(cmd)
                    search_box.send_keys(Keys.RETURN)
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, 'li[data-layout="organic"]'))
                    )
                    curr_elements = fetch_page(driver, driver.current_url)
                except Exception as e:
                    print(f"検索エラー: {e}")
                
    except (KeyboardInterrupt, EOFError):
        print("\n終了します。")
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    main()
