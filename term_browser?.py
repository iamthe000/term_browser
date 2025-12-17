import sys
import io
import shutil
import requests
import urllib.parse
from PIL import Image
from bs4 import BeautifulSoup

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

def fetch_page(url, is_search=False):
    term_width, term_height = get_terminal_size()
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36","Accept-Language": "ja,en-US;q=0.9,en;q=0.8"}
    elements = [] # リンクと入力ボックスを統合して管理
    
    try:
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 1. 入力ボックス (INPUT) を探す
        for i, inp in enumerate(soup.find_all(['input', 'textarea'])):
            if inp.get('type') != 'hidden':
                name = inp.get('name') or inp.get('id') or "input"
                elements.append({"type": "INPUT", "name": name, "label": f"入力: [{name}]"})

        # 2. リンク (A) を探す
        for i, a in enumerate(soup.find_all('a', href=True)):
            text = a.get_text(strip=True)
            if text and len(text) > 2:
                elements.append({"type": "LINK", "url": urllib.parse.urljoin(url, a['href']), "label": text})
                if len(elements) > 15: break # 画面に収まる程度に制限

    except Exception as e:
        print(f"解析エラー: {e}")

    # 画像取得（比率 1.2）
    api_url = f"https://s.wordpress.com/mshots/v1/{urllib.parse.quote(url)}?w=1280"
    img_ansi = ""
    try:
        img_res = requests.get(api_url, timeout=8)
        img = Image.open(io.BytesIO(img_res.content)).convert("RGB")
        pixel_h = int(term_width / 1.2) * 2
        max_h = (term_height - 12) * 2
        img_resized = img.resize((term_width, min(pixel_h, max_h)), Image.Resampling.LANCZOS)
        img_ansi = pixels_to_ansi(img_resized)
    except:
        img_ansi = "\n(画像取得中...)\n"

    print("\x1b[2J\x1b[H", end="")
    print(img_ansi)
    print(f"\x1b[1;34m--- 操作パネル ({url[:30]}...) ---\x1b[0m")
    
    for i, el in enumerate(elements[:12]):
        color = "\033[1;33m" if el['type'] == "INPUT" else "\033[1;32m"
        print(f"{color}[{i+1}] {el['label']}\033[0m")
        
    return elements

def main():
    curr_url = "https://html.duckduckgo.com/html/"
    curr_elements = fetch_page(curr_url)
    
    while True:
        try:
            cmd = input("\n🔎 番号/検索/URL (exitで終了): ").strip()
            if cmd.lower() == 'exit': break
            
            if cmd.isdigit():
                idx = int(cmd) - 1
                if 0 <= idx < len(curr_elements):
                    el = curr_elements[idx]
                    
                    if el['type'] == "INPUT":
                        val = input(f"📝 {el['name']} への入力値: ")
                        # 簡易的な検索実行（入力ボックスが1つのサイト用）
                        search_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(val)}"
                        curr_elements = fetch_page(search_url)
                    else:
                        curr_elements = fetch_page(el['url'])
            elif cmd.startswith('http'):
                curr_elements = fetch_page(cmd)
            else:
                search_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(cmd)}"
                curr_elements = fetch_page(search_url)
                
        except KeyboardInterrupt: break

if __name__ == "__main__":
    main()
