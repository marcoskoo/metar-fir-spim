from flask import Flask, render_template, request, jsonify
import requests
from bs4 import BeautifulSoup
import re
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = Flask(__name__, template_folder=os.path.join(ROOT, "templates"), static_folder=os.path.join(ROOT, "static"))

CORPAC_URL = "https://meteorologia.corpac.gob.pe/app/Meteorologia/tiempo/manualMetar.php"

ALL_AIRPORTS = [
    "SPHY","SPHZ","SPQU","SPAY","SPHO","SPJR","SPPY","SPHI","SPEO",
    "SPZO","SPNC","SPLO","SPQT","SPJE","SPJJ","SPJI","SPJL","SPJC",
    "SPMF","SPZA","SPSO","SPUR","SPCL","SPTU","SPTN","SPYL","SPST",
    "SPJA","SPGM","SPRU","SPME","SPMS"
]

AIRPORT_NAMES = {
    "SPHY": "Andahuaylas", "SPHZ": "Anta-Huaraz", "SPQU": "Arequipa",
    "SPAY": "Atalaya", "SPHO": "Ayacucho", "SPJR": "Cajamarca",
    "SPPY": "Chachapoyas", "SPHI": "Chiclayo", "SPEO": "Chimbote",
    "SPZO": "Cuzco", "SPNC": "Huanuco", "SPLO": "Ilo",
    "SPQT": "Iquitos", "SPJE": "Jaen", "SPJJ": "Jauja",
    "SPJI": "Juanjui", "SPJL": "Juliaca", "SPJC": "Lima-Callao",
    "SPMF": "Mazamari", "SPZA": "Nazca", "SPSO": "Pisco",
    "SPUR": "Piura", "SPCL": "Pucallpa", "SPTU": "Puerto Maldonado",
    "SPTN": "Tacna", "SPYL": "Talara", "SPST": "Tarapoto",
    "SPJA": "Rioja", "SPGM": "Tingo Maria", "SPRU": "Trujillo",
    "SPME": "Tumbes", "SPMS": "Yurimaguas"
}

def parse_metar_response(html):
    soup = BeautifulSoup(html, "html.parser")
    content_div = soup.find("div", class_="taf")
    if not content_div:
        return []
    raw_html = str(content_div)
    blocks = re.split(r'<center>.*?</center>', raw_html, flags=re.DOTALL)
    results = []
    for block in blocks:
        block_soup = BeautifulSoup(block, "html.parser")
        text = block_soup.get_text("\n", strip=True)
        tokens = [re.sub(r'\s+', ' ', l).strip() for l in text.split("\n") if l.strip()]
        metar_text = ""
        taf_text = ""
        airport_code = ""
        i = 0
        while i < len(tokens):
            t = tokens[i]
            if t == "METAR:" and i + 1 < len(tokens):
                i += 1
                metar_text = tokens[i]
                m = re.match(r'(SP[A-Z]{2})', metar_text)
                if m:
                    airport_code = m.group(1)
            elif t == "TAF:" and i + 1 < len(tokens):
                i += 1
                taf_text = tokens[i]
                if not airport_code:
                    m = re.match(r'(SP[A-Z]{2})', taf_text)
                    if m:
                        airport_code = m.group(1)
            i += 1
        if airport_code:
            results.append({
                "code": airport_code,
                "name": AIRPORT_NAMES.get(airport_code, airport_code),
                "metar": metar_text,
                "taf": taf_text
            })
    return results

def fetch_batch(codes):
    payload = {"aeropT": ",".join(codes), "incTaf": "on"}
    try:
        resp = requests.post(CORPAC_URL, data=payload, timeout=25)
        resp.encoding = "iso-8859-1"
        if resp.status_code == 200:
            return parse_metar_response(resp.text)
    except requests.exceptions.RequestException:
        pass
    return []

def fetch_all_metar():
    batch_size = 4
    batches = [ALL_AIRPORTS[i:i+batch_size] for i in range(0, len(ALL_AIRPORTS), batch_size)]
    all_results = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = {ex.submit(fetch_batch, b): b for b in batches}
        for f in as_completed(futures):
            all_results.extend(f.result())
    all_results.sort(key=lambda r: ALL_AIRPORTS.index(r["code"]))
    return all_results

@app.route("/api/metar")
def api_metar():
    results = fetch_all_metar()
    return jsonify({"results": results, "count": len(results), "total": len(ALL_AIRPORTS)})

@app.route("/")
def index():
    return render_template("index.html", airport_count=len(ALL_AIRPORTS))
