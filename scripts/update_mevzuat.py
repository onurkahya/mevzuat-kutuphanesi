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
    {"id": '6502-tuketici-kanunu', "ad": '6502 SAYILI TÜKETİCİNİN KORUNMASI HAKKINDA KANUN', "no": '6502', "tur": '1', "tertip": '5'},
    {"id": 'abonelik-sozlesmeleri', "ad": 'ABONELİK SÖZLEŞMELERİ YÖNETMELİĞİ', "no": '20480', "tur": '7', "tertip": '5'},
    {"id": 'devre-tatil', "ad": 'DEVRE TATİL VE UZUN SÜRELİ TATİL HİZMETİ SÖZLEŞMELERİ YÖNETMELİĞİ', "no": '20442', "tur": '7', "tertip": '5'},
    {"id": 'dogrudan-satislar', "ad": 'DOĞRUDAN SATIŞLAR HAKKINDA YÖNETMELİK', "no": '42526', "tur": '7', "tertip": '5'},
    {"id": 'finansal-hizmetler-mesafeli', "ad": 'FİNANSAL HİZMETLERE İLİŞKİN MESAFELİ SÖZLEŞMELER YÖNETMELİĞİ', "no": '20495', "tur": '7', "tertip": '5'},
    {"id": 'fiyat-etiketi', "ad": 'FİYAT ETİKETİ YÖNETMELİĞİ', "no": '19819', "tur": '7', "tertip": '5'},
    {"id": 'garanti-belgesi', "ad": 'GARANTİ BELGESİ YÖNETMELİĞİ', "no": '19782', "tur": '7', "tertip": '5'},
    {"id": 'isyeri-disinda-kurulan', "ad": 'İŞ YERİ DIŞINDA KURULAN SÖZLEŞMELER YÖNETMELİĞİ', "no": '20444', "tur": '7', "tertip": '5'},
    {"id": 'konut-finansmani', "ad": 'KONUT FİNANSMANI SÖZLEŞMELERİ YÖNETMELİĞİ', "no": '20793', "tur": '7', "tertip": '5'},
    {"id": 'mesafeli-sozlesmeler', "ad": 'MESAFELİ SÖZLEŞMELER YÖNETMELİĞİ', "no": '20237', "tur": '7', "tertip": '5'},
    {"id": 'on-odemeli-konut', "ad": 'ÖN ÖDEMELİ KONUT SATIŞLARI HAKKINDA YÖNETMELİK', "no": '20238', "tur": '7', "tertip": '5'},
    {"id": 'paket-tur', "ad": 'PAKET TUR SÖZLEŞMELERİ YÖNETMELİĞİ', "no": '20446', "tur": '7', "tertip": '5'},
    {"id": 'satis-sonrasi-hizmetler', "ad": 'SATIŞ SONRASI HİZMETLER YÖNETMELİĞİ', "no": '19783', "tur": '7', "tertip": '5'},
    {"id": 'sureli-yayin-promosyon', "ad": 'SÜRELİ YAYIN KURULUŞLARINCA DÜZENLENEN PROMOSYON UYGULAMALARINA İLİŞKİN YÖNETMELİK', "no": '19800', "tur": '7', "tertip": '5'},
    {"id": 'taksitle-satis', "ad": 'TAKSİTLE SATIŞ SÖZLEŞMELERİ HAKKINDA YÖNETMELİK', "no": '20447', "tur": '7', "tertip": '5'},
    {"id": 'tanitma-kullanma-kilavuzu', "ad": 'TANITMA VE KULLANMA KILAVUZU YÖNETMELİĞİ', "no": '19784', "tur": '7', "tertip": '5'},
    {"id": 'ticari-reklam', "ad": 'TİCARİ REKLAM VE HAKSIZ TİCARİ UYGULAMALAR YÖNETMELİĞİ', "no": '20435', "tur": '7', "tertip": '5'},
    {"id": 'tuketici-kredisi', "ad": 'TÜKETİCİ KREDİSİ SÖZLEŞMELERİ YÖNETMELİĞİ', "no": '20767', "tur": '7', "tertip": '5'},
    {"id": 'haksiz-sartlar', "ad": 'TÜKETİCİ SÖZLEŞMELERİNDEKİ HAKSIZ ŞARTLAR HAKKINDA YÖNETMELİK', "no": '19798', "tur": '7', "tertip": '5'},
    {"id": 'yenilenmis-urunler', "ad": 'YENİLENMİŞ ÜRÜNLER HAKKINDA YÖNETMELİK', "no": '46233', "tur": '7', "tertip": '5'},
    {"id": '6585-perakende-kanunu', "ad": '6585 SAYILI PERAKENDE TİCARETİN DÜZENLENMESİ HAKKINDA KANUN', "no": '6585', "tur": '1', "tertip": '5'},
    {"id": 'haksiz-fiyat', "ad": 'HAKSIZ FİYAT DEĞERLENDİRME KURULU YÖNETMELİĞİ', "no": '34561', "tur": '7', "tertip": '5'},
    {"id": 'tasinmaz-ticareti', "ad": 'TAŞINMAZ TİCARETİ HAKKINDA YÖNETMELİK', "no": '24645', "tur": '7', "tertip": '5'},
    {"id": 'motorlu-kara-ticareti', "ad": 'MOTORLU KARA TAŞITLARININ TİCARETİ HAKKINDA YÖNETMELİK', "no": '40940', "tur": '7', "tertip": '5'},
    {"id": 'kuyum-ticareti', "ad": 'KUYUM TİCARETİ HAKKINDA YÖNETMELİK', "no": '38527', "tur": '7', "tertip": '5'},
    {"id": 'alisveris-merkezleri', "ad": 'ALIŞVERİŞ MERKEZLERİ HAKKINDA YÖNETMELİK', "no": '21431', "tur": '7', "tertip": '5'},
    {"id": 'perakende-ilke-kurallar', "ad": 'PERAKENDE TİCARETTE UYGULANACAK İLKE VE KURALLAR HAKKINDA YÖNETMELİK', "no": '22722', "tur": '7', "tertip": '5'},
    {"id": '6563-elektronik-ticaret', "ad": '6563 SAYILI ELEKTRONİK TİCARETİN DÜZENLENMESİ HAKKINDA KANUN', "no": '6563', "tur": '1', "tertip": '5'}
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140 Safari/537.36",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.7",
}

SUP_START = "[[SUP]]"
SUP_END = "[[/SUP]]"

def now_tr():
    return datetime.now(ZoneInfo("Europe/Istanbul")).isoformat(timespec="seconds")

def official_url(item):
    return (
        "https://www.mevzuat.gov.tr/mevzuat"
        f"?MevzuatNo={item['no']}&MevzuatTur={item['tur']}&MevzuatTertip={item['tertip']}"
    )

def detail_url(item):
    return (
        "https://www.mevzuat.gov.tr/anasayfa/MevzuatFihristDetayIframe"
        f"?MevzuatTur={item['tur']}&MevzuatNo={item['no']}&MevzuatTertip={item['tertip']}"
    )

def get_page(url):
    print("   Cloudflare proxy üzerinden bağlanılıyor...")
    response = requests.get(
        PROXY_URL,
        params={"url": url},
        headers={
            "User-Agent": HEADERS["User-Agent"],
            "Accept-Language": HEADERS["Accept-Language"],
        },
        timeout=90,
    )
    response.raise_for_status()
    if not response.content:
        raise RuntimeError("Cloudflare proxy boş cevap döndürdü.")
    return response

def preserve_superscripts(soup):
    for tag in soup.find_all("sup"):
        value = re.sub(r"\s+", "", tag.get_text(" ", strip=True))
        if value:
            tag.replace_with(f"{SUP_START}{value}{SUP_END}")
        else:
            tag.decompose()

def fetch_mevzuat(item):
    print("\n" + item["ad"])
    print("Kaynak indiriliyor...")
    response = get_page(detail_url(item))
    if not response.encoding or response.encoding.lower() == "iso-8859-1":
        response.encoding = response.apparent_encoding or "utf-8"
    soup = BeautifulSoup(response.text, "html.parser")
    preserve_superscripts(soup)
    return soup

def clean_line(value):
    value = value.replace("\xa0", " ")
    return re.sub(r"[ \t]+", " ", value).strip()

ARTICLE_RE = re.compile(
    r"^\s*(?P<kind>GEÇİCİ|EK)?\s*MADDE\s+"
    r"(?P<num>\d+(?:/[A-ZÇĞİÖŞÜ])?)\s*[-–—:]?",
    re.IGNORECASE,
)

SECTION_RE = re.compile(
    r"^(?:BİRİNCİ|İKİNCİ|ÜÇÜNCÜ|DÖRDÜNCÜ|BEŞİNCİ|ALTINCI|YEDİNCİ|SEKİZİNCİ|"
    r"DOKUZUNCU|ONUNCU|ON BİRİNCİ|ON İKİNCİ|ON ÜÇÜNCÜ|ON DÖRDÜNCÜ|ON BEŞİNCİ|"
    r"ON ALTINCI|ON YEDİNCİ|ON SEKİZİNCİ|ON DOKUZUNCU|YİRMİNCİ)\s+(?:BÖLÜM|KISIM)$",
    re.IGNORECASE,
)

def is_body_line(line):
    return bool(
        re.match(r"^\(\d+\)", line)
        or re.match(r"^[a-zçğıöşü]\)", line, re.IGNORECASE)
        or re.match(r"^\d+\)", line)
        or line.endswith((".", ";", ":", "?", "!"))
        or len(line) > 180
    )

def looks_like_heading(line):
    if not line or ARTICLE_RE.match(line) or is_body_line(line):
        return False
    return len(line) <= 180

def sentence_case_score(text):
    words = re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü]+", text)
    if not words:
        return 0
    if len(words) == 1:
        return 1
    rest = words[1:]
    lower_initial = sum(1 for w in rest if w[:1].islower())
    return lower_initial / len(rest)

def title_case_score(text):
    words = re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü]+", text)
    content = [w for w in words if w.lower() not in {"ve","veya","ile","ileti","ilişkin","hakkında"}]
    if not content:
        return 0
    caps = sum(1 for w in content if w[:1].isupper())
    return caps / len(content)

def normalize_article_heading(value):
    """
    Birleşmiş üst başlık + gerçek madde başlığını ayırır.

    Güvenli örnekler:
      Amaç, Kapsam, Dayanak ve Tanımlar Amaç -> Amaç
      Ön Bilgilendirme Yükümlülüğü Ön bilgilendirme -> Ön bilgilendirme
      Cayma Hakkının Kullanımı ve Tarafların Yükümlülükleri Cayma hakkı -> Cayma hakkı

    Normal sentence-case başlıklara (örn. "Ön bilgilendirmeye ilişkin diğer yükümlülükler")
    dokunmaz.
    """
    value = clean_line(value)
    if not value or SECTION_RE.match(value):
        return ""

    # Olası bölme noktaları: ilk kelimeden sonraki büyük harfle başlayan kelimeler.
    positions = [m.start() for m in re.finditer(r"(?<![A-Za-zÇĞİÖŞÜçğıöşü])[A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşü]*", value)]
    candidates = []

    for pos in positions[1:]:
        prefix = value[:pos].strip(" ,;:-–—")
        suffix = value[pos:].strip(" ,;:-–—")
        if not prefix or not suffix or len(suffix) > 130:
            continue

        # Üst başlık çoğunlukla Title Case; gerçek madde başlığı çoğunlukla sentence case.
        prefix_title = title_case_score(prefix)
        suffix_sentence = sentence_case_score(suffix)

        # Tek kelimelik suffix ("Amaç") da geçerlidir.
        suffix_words = re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü]+", suffix)
        suffix_ok = (len(suffix_words) == 1) or (suffix_sentence >= 0.5)

        # Prefix güçlü biçimde üst başlık görünümündeyse böl.
        if prefix_title >= 0.65 and suffix_ok:
            candidates.append((pos, suffix))

    if candidates:
        # En erken güvenli bölünme, gerçek madde başlığını tam tutar.
        return candidates[0][1]

    return value

def heading_block_before(lines, article_index):
    candidates = []
    pos = article_index - 1

    while pos >= 0 and len(candidates) < 4:
        line = lines[pos]
        if not looks_like_heading(line):
            break
        candidates.append((pos, line))
        pos -= 1

    if not candidates:
        return "", article_index

    nearest_index, nearest_line = candidates[0]
    title = normalize_article_heading(nearest_line)
    block_start = min(x[0] for x in candidates)
    return title, block_start

def format_article_text(body_lines):
    text = " ".join(clean_line(x) for x in body_lines if clean_line(x))
    text = re.sub(r"\s+", " ", text).strip()

    # Fıkralar: (2), (3)...; değişiklik dipnotundaki "(2)" çoğunlukla ")" sonrasındadır,
    # bu yüzden hemen öncesi ")" ise yeni fıkra sayılmaz.
    text = re.sub(
        r"(?<!\))\s+(?=\((?:[2-9]|[1-9]\d)\)\s)",
        "\n",
        text,
    )

    # Cümle sonundan sonra (1) dahil yeni fıkra.
    text = re.sub(
        r"(?<=[.!?;:])\s+(?=\((?:[1-9]|[1-9]\d)\)\s)",
        "\n",
        text,
    )

    # Bentler ve alt bentler.
    text = re.sub(r"(?<!^)\s+(?=[a-zçğıöşü]\)\s)", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"(?<!^)\s+(?=\d+\)\s)", "\n", text)

    return re.sub(r"\n{2,}", "\n", text).strip()

def parse_articles(soup):
    for tag in soup(["script", "style", "noscript", "iframe"]):
        tag.decompose()

    raw_text = soup.get_text("\n").replace("\xa0", " ").replace("\r", "\n")
    lines = [clean_line(x) for x in raw_text.split("\n")]
    lines = [x for x in lines if x]

    positions = []
    for index, line in enumerate(lines):
        match = ARTICLE_RE.match(line)
        if match:
            title, block_start = heading_block_before(lines, index)
            positions.append({
                "index": index,
                "match": match,
                "title": title,
                "block_start": block_start,
            })

    articles = []
    for n, info in enumerate(positions):
        index = info["index"]
        match = info["match"]
        end_index = positions[n + 1]["block_start"] if n + 1 < len(positions) else len(lines)

        first = ARTICLE_RE.sub("", lines[index], count=1).strip()
        body = ([first] if first else []) + lines[index + 1:end_index]

        # Bölüm/kısım başlığı sarkmışsa madde metnine dahil etme.
        cleaned = []
        for line in body:
            if SECTION_RE.match(line):
                break
            cleaned.append(line)

        kind = (match.group("kind") or "").upper()
        articles.append({
            "madde": match.group("num"),
            "tur": "gecici" if kind == "GEÇİCİ" else ("ek" if kind == "EK" else "normal"),
            "baslik": info["title"],
            "metin": format_article_text(cleaned),
        })

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
    return data

def catalogue_entry(data, durum="guncel", hata=None):
    return {
        "id": data["id"],
        "ad": data["ad"],
        "dosya": f"data/{data['id']}.json",
        "kaynak": data["kaynak"],
        "madde_sayisi": data.get("madde_sayisi", 0),
        "son_guncelleme": data.get("son_guncelleme"),
        "durum": durum,
        "hata": hata,
    }

def main():
    print("=" * 60)
    print("MEVZUAT KÜTÜPHANESİ")
    print("Güncelleme başladı:", now_tr())
    print("=" * 60)

    catalogue, errors = [], []

    for item in MEVZUATLAR:
        try:
            data = save_mevzuat(item)
            catalogue.append(catalogue_entry(data))
        except Exception as exc:
            err = str(exc)
            print(f"✗ HATA: {item['ad']} -> {err}")
            errors.append({"id": item["id"], "ad": item["ad"], "hata": err})

            # Gece bir mevzuat geçici olarak alınamazsa eski başarılı JSON'u koru.
            old_path = DATA_DIR / f"{item['id']}.json"
            if old_path.exists():
                try:
                    old = json.loads(old_path.read_text(encoding="utf-8"))
                    catalogue.append(catalogue_entry(old, durum="eski_kopya", hata=err))
                    print("  ↳ Önceki başarılı kopya korunuyor.")
                except Exception:
                    pass

        time.sleep(2)

    catalogue_data = {
        "son_guncelleme": now_tr(),
        "mevzuat_sayisi": len(MEVZUATLAR),
        "basarili_veya_korumali": len(catalogue),
        "mevzuatlar": catalogue,
        "hatalar": errors,
    }
    (DATA_DIR / "mevzuatlar.json").write_text(
        json.dumps(catalogue_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("=" * 60)
    print("İŞLEM TAMAMLANDI")
    print("Katalogda:", len(catalogue))
    print("Hatalı:", len(errors))
    print("=" * 60)

    # Hiç veri yoksa workflow başarısız olsun.
    if not catalogue:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
