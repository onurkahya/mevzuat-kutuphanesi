import json
import re
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

PROXY_URL = "https://mevzuat-proxy.onur-kahya.workers.dev/"

MEVZUATLAR = [
    {
        "id": "mesafeli-sozlesmeler",
        "ad": "MESAFELİ SÖZLEŞMELER YÖNETMELİĞİ",
        "no": "20237",
        "tur": "7",
        "tertip": "5",
    },
    {
        "id": "fiyat-etiketi",
        "ad": "FİYAT ETİKETİ YÖNETMELİĞİ",
        "no": "19819",
        "tur": "7",
        "tertip": "5",
    },
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140 Safari/537.36",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.mevzuat.gov.tr/",
}

def now_tr():
    return datetime.now(ZoneInfo("Europe/Istanbul")).isoformat(timespec="seconds")

def official_url(item):
    return (
        "https://www.mevzuat.gov.tr/mevzuat"
        f"?MevzuatNo={item['no']}"
        f"&MevzuatTur={item['tur']}"
        f"&MevzuatTertip={item['tertip']}"
    )

def detail_url(item):
    return (
        "https://www.mevzuat.gov.tr/anasayfa/MevzuatFihristDetayIframe"
        f"?MevzuatTur={item['tur']}"
        f"&MevzuatNo={item['no']}"
        f"&MevzuatTertip={item['tertip']}"
    )

def clean_text(text):
    text = text.replace("\xa0", " ").replace("\r", "\n")
    lines = []
    for line in text.split("\n"):
        line = re.sub(r"[ \t]+", " ", line).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)

def get_page(url):
    print("   Cloudflare proxy üzerinden bağlanılıyor...")
    response = requests.get(
        PROXY_URL,
        params={"url": url},
        headers={
            "User-Agent": HEADERS["User-Agent"],
            "Accept-Language": "tr-TR,tr;q=0.9",
        },
        timeout=60,
    )
    response.raise_for_status()
    if not response.content:
        raise RuntimeError("Cloudflare proxy boş cevap döndürdü.")
    return response

def preserve_superscripts(soup):
    for tag in soup.find_all("sup"):
        value = re.sub(r"\s+", "", tag.get_text(" ", strip=True))
        if value:
            tag.replace_with(f"[[SUP]]{value}[[/SUP]]")
        else:
            tag.decompose()

def fetch_mevzuat(item):
    print()
    print(item["ad"])
    print("Kaynak indiriliyor...")
    response = get_page(detail_url(item))
    if not response.encoding or response.encoding.lower() == "iso-8859-1":
        response.encoding = response.apparent_encoding or "utf-8"
    soup = BeautifulSoup(response.text, "html.parser")
    preserve_superscripts(soup)
    return soup

ARTICLE_RE = re.compile(r"^\s*MADDE\s+(\d+)\s*[-–—]", re.IGNORECASE)

SECTION_RE = re.compile(
    r"^(BİRİNCİ|İKİNCİ|ÜÇÜNCÜ|DÖRDÜNCÜ|BEŞİNCİ|ALTINCI|YEDİNCİ|SEKİZİNCİ|"
    r"DOKUZUNCU|ONUNCU|ON BİRİNCİ|ON İKİNCİ|ON ÜÇÜNCÜ|ON DÖRDÜNCÜ|"
    r"ON BEŞİNCİ|ON ALTINCI|ON YEDİNCİ|ON SEKİZİNCİ|ON DOKUZUNCU|YİRMİNCİ)\s+BÖLÜM$",
    re.IGNORECASE,
)

def is_possible_title(line):
    if not line or SECTION_RE.match(line) or ARTICLE_RE.match(line):
        return False
    if re.match(r"^\(\d+\)", line):
        return False
    if re.match(r"^[a-zçğıöşü]\)", line, re.IGNORECASE):
        return False
    if len(line) > 180 or line.endswith("."):
        return False
    return True

def format_article_text(text):
    text = clean_text(text)
    text = re.sub(r"\s*\n\s*", " ", text)
    text = re.sub(r"[ \t]+", " ", text).strip()
    text = re.sub(r"(?<=[.!?])\s+(?=\(\d+\)\s)", "\n", text)
    text = re.sub(r"\s+(?=[a-zçğıöşü]\)\s)", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+(?=\d+\)\s)", "\n", text)
    return text.strip()

def parse_articles(soup):
    for tag in soup(["script", "style", "noscript", "iframe"]):
        tag.decompose()

    text = soup.get_text("\n").replace("\xa0", " ").replace("\r", "\n")
    text = re.sub(r"\n[ \t]*\n+", "\n", text)
    lines = [re.sub(r"[ \t]+", " ", x).strip() for x in text.split("\n")]
    lines = [x for x in lines if x]

    articles = []
    current = None

    for index, line in enumerate(lines):
        match = ARTICLE_RE.match(line)

        if match:
            if current:
                current["metin"] = format_article_text("\n".join(current["body"]))
                del current["body"]
                articles.append(current)

            number = int(match.group(1))

            title_parts = []
            for back in range(1, 4):
                pos = index - back
                if pos < 0:
                    break
                candidate = lines[pos]
                if not is_possible_title(candidate):
                    break
                title_parts.insert(0, candidate)

            remainder = ARTICLE_RE.sub("", line, count=1).strip()

            current = {
                "madde": number,
                "baslik": " ".join(title_parts).strip(),
                "body": [],
            }

            if remainder:
                current["body"].append(remainder)
        else:
            if current:
                current["body"].append(line)

    if current:
        current["metin"] = format_article_text("\n".join(current["body"]))
        del current["body"]
        articles.append(current)

    return articles

def save_mevzuat(item):
    soup = fetch_mevzuat(item)
    articles = parse_articles(soup)

    if not articles:
        raise RuntimeError(f"{item['ad']} için hiçbir MADDE bulunamadı.")

    data = {
        "id": item["id"],
        "ad": item["ad"],
        "mevzuat_no": item["no"],
        "mevzuat_tur": item["tur"],
        "mevzuat_tertip": item["tertip"],
        "kaynak": official_url(item),
        "son_guncelleme": now_tr(),
        "madde_sayisi": len(articles),
        "maddeler": articles,
    }

    output = DATA_DIR / f"{item['id']}.json"
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"✓ {len(articles)} madde bulundu.")
    print(f"✓ Kaydedildi: {output.name}")

    return {
        "id": item["id"],
        "ad": item["ad"],
        "dosya": f"data/{item['id']}.json",
        "kaynak": official_url(item),
        "madde_sayisi": len(articles),
        "son_guncelleme": data["son_guncelleme"],
    }

def main():
    print("=" * 60)
    print("MEVZUAT KÜTÜPHANESİ")
    print("Güncelleme başladı:", now_tr())
    print("=" * 60)

    catalogue = []
    errors = []

    for item in MEVZUATLAR:
        try:
            catalogue.append(save_mevzuat(item))
        except Exception as exc:
            print(f"✗ HATA: {item['ad']}")
            print(exc)
            errors.append({
                "id": item["id"],
                "ad": item["ad"],
                "hata": str(exc),
            })

        time.sleep(2)

    catalogue_data = {
        "son_guncelleme": now_tr(),
        "mevzuatlar": catalogue,
        "hatalar": errors,
    }

    (DATA_DIR / "mevzuatlar.json").write_text(
        json.dumps(catalogue_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print()
    print("=" * 60)
    print("İŞLEM TAMAMLANDI")
    print(f"Başarılı: {len(catalogue)}")
    print(f"Hatalı: {len(errors)}")
    print("=" * 60)

    if not catalogue:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
