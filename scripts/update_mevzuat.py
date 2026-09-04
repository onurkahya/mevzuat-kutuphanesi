import json
import re
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup


# =========================================================
# AYARLAR
# =========================================================

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

# Cloudflare Worker adresimiz
PROXY_URL = "https://mevzuat-proxy.onur-kahya.workers.dev/"

# Şimdilik test için iki mevzuat.
# Bunlar doğru ayrıştırıldıktan sonra tüm listeyi ekleyeceğiz.
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
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/140 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


# =========================================================
# TARİH / URL
# =========================================================

def now_tr():
    return datetime.now(
        ZoneInfo("Europe/Istanbul")
    ).isoformat(timespec="seconds")


def official_url(item):
    return (
        "https://www.mevzuat.gov.tr/mevzuat"
        f"?MevzuatNo={item['no']}"
        f"&MevzuatTur={item['tur']}"
        f"&MevzuatTertip={item['tertip']}"
    )


def detail_url(item):
    return (
        "https://www.mevzuat.gov.tr/"
        "anasayfa/MevzuatFihristDetayIframe"
        f"?MevzuatTur={item['tur']}"
        f"&MevzuatNo={item['no']}"
        f"&MevzuatTertip={item['tertip']}"
    )


# =========================================================
# CLOUDFLARE PROXY
# =========================================================

def get_page(url):
    """
    GitHub Actions -> Cloudflare Worker -> mevzuat.gov.tr
    """

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
        raise RuntimeError(
            "Cloudflare proxy boş cevap döndürdü."
        )

    return response


# =========================================================
# ÜST KARAKTER / DİPNOT KORUMA
# =========================================================

SUP_START = "[[SUP]]"
SUP_END = "[[/SUP]]"


def preserve_superscripts(soup):
    """
    Kaynaktaki <sup> işaretlerini JSON içinde korur.

    Örnek:
        <sup>(1)</sup>

    JSON:
        [[SUP]](1)[[/SUP]]

    Yeni web arayüzünde bu işaretler tekrar gerçek <sup>
    etiketi olarak gösterilecek.
    """

    for tag in soup.find_all("sup"):
        value = tag.get_text(" ", strip=True)
        value = re.sub(r"\s+", "", value)

        if value:
            tag.replace_with(
                f"{SUP_START}{value}{SUP_END}"
            )
        else:
            tag.decompose()


# =========================================================
# HTML AL
# =========================================================

def fetch_mevzuat(item):
    print()
    print(item["ad"])
    print("Kaynak indiriliyor...")

    response = get_page(
        detail_url(item)
    )

    if (
        not response.encoding
        or response.encoding.lower() == "iso-8859-1"
    ):
        response.encoding = (
            response.apparent_encoding or "utf-8"
        )

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    preserve_superscripts(soup)

    return soup


# =========================================================
# METİN YARDIMCILARI
# =========================================================

def clean_line(value):
    value = value.replace("\xa0", " ")
    value = re.sub(r"[ \t]+", " ", value)
    return value.strip()


def normalize_article_heading(value):
    """
    Mevzuat.gov.tr bazı yerlerde bölüm/alt bölüm başlığı ile gerçek
    madde başlığını aynı metin parçasında birleştirebiliyor.

    Örnekler:
      "Amaç, Kapsam, Dayanak ve Tanımlar Amaç" -> "Amaç"
      "Ön Bilgilendirme Yükümlülüğü Ön bilgilendirme" -> "Ön bilgilendirme"
      "Cayma Hakkının Kullanımı ve Tarafların Yükümlülükleri Cayma hakkı"
          -> "Cayma hakkı"

    Genel kural:
    Başlığın ilk anlamlı kelimesi metin içinde tekrar başlıyorsa,
    son tekrarın başladığı yer gerçek madde başlığı kabul edilir.
    """
    value = clean_line(value)

    if not value:
        return ""

    # SUP işaretleri başlıkta görünse bile karşılaştırmayı bozmasın.
    plain = re.sub(r"\[\[/?SUP\]\]", "", value)

    words = list(re.finditer(r"[A-Za-zÇĞİÖŞÜçğıöşü]+", plain))
    if not words:
        return value

    first_word = words[0].group(0)

    repeated_positions = []
    for m in re.finditer(
        rf"(?i)(?<![A-Za-zÇĞİÖŞÜçğıöşü]){re.escape(first_word)}(?![A-Za-zÇĞİÖŞÜçğıöşü])",
        plain
    ):
        if m.start() > 0:
            repeated_positions.append(m.start())

    if repeated_positions:
        pos = repeated_positions[-1]
        suffix = plain[pos:].strip(" ,;:-–—")

        # Suffix makul bir madde başlığı uzunluğundaysa onu kullan.
        if 1 <= len(suffix) <= 120:
            return suffix

    return value


ARTICLE_RE = re.compile(
    r"^\s*(?P<temp>GEÇİCİ\s+)?MADDE\s+"
    r"(?P<num>\d+(?:/[A-ZÇĞİÖŞÜ])?)\s*[-–—:]?",
    re.IGNORECASE,
)


SECTION_RE = re.compile(
    r"^(?:"
    r"BİRİNCİ|İKİNCİ|ÜÇÜNCÜ|DÖRDÜNCÜ|BEŞİNCİ|"
    r"ALTINCI|YEDİNCİ|SEKİZİNCİ|DOKUZUNCU|ONUNCU|"
    r"ON BİRİNCİ|ON İKİNCİ|ON ÜÇÜNCÜ|ON DÖRDÜNCÜ|"
    r"ON BEŞİNCİ|ON ALTINCI|ON YEDİNCİ|ON SEKİZİNCİ|"
    r"ON DOKUZUNCU|YİRMİNCİ"
    r")\s+(?:BÖLÜM|KISIM)$",
    re.IGNORECASE,
)


def is_body_line(line):
    """
    Bu satırın madde gövdesi olma ihtimali yüksek mi?
    """

    if not line:
        return False

    if re.match(r"^\(\d+\)", line):
        return True

    if re.match(
        r"^[a-zçğıöşü]\)",
        line,
        re.IGNORECASE
    ):
        return True

    if re.match(r"^\d+\)", line):
        return True

    if line.endswith((".", ";", ":", "?", "!")):
        return True

    if len(line) > 180:
        return True

    return False


def looks_like_heading(line):
    """
    Madde başlığı / bölüm alt başlığı olabilecek kısa satır.
    """

    if not line:
        return False

    if ARTICLE_RE.match(line):
        return False

    if SECTION_RE.match(line):
        return True

    if is_body_line(line):
        return False

    # Aşırı uzun satır başlık değildir.
    if len(line) > 160:
        return False

    return True


def heading_block_before(lines, article_index):
    """
    MADDE satırından hemen önceki başlık bloğunu bulur.

    Örnek:
        Ön Bilgilendirme Yükümlülüğü
        Ön bilgilendirme
        MADDE 5 -

    Burada:
      madde başlığı = "Ön bilgilendirme"
      üst başlık     = "Ön Bilgilendirme Yükümlülüğü"

    JSON'a sadece en yakın satır olan gerçek madde başlığı yazılır.

    Ayrıca bu bloğun başlangıç indeksini döndürür. Böylece bu
    başlıkların önceki maddenin sonuna yanlışlıkla eklenmesi engellenir.
    """

    candidates = []

    pos = article_index - 1

    while pos >= 0 and len(candidates) < 4:
        line = lines[pos]

        if not looks_like_heading(line):
            break

        candidates.append(
            (pos, line)
        )

        pos -= 1

    if not candidates:
        return "", article_index

    # En yakın satır gerçek madde başlığıdır.
    nearest_index, nearest_line = candidates[0]

    # "BİRİNCİ BÖLÜM" doğrudan madde başlığı değildir.
    if SECTION_RE.match(nearest_line):
        title = ""
    else:
        title = normalize_article_heading(nearest_line)

    # Önceki maddeden çıkarılması gereken başlık bloğunun
    # en erken satırı.
    block_start = min(
        x[0] for x in candidates
    )

    return title, block_start


def format_article_text(body_lines):
    """
    Madde gövdesini okunabilir biçimde oluşturur.

    - Kaynaktaki gereksiz satır parçalanmalarını birleştirir.
    - (2), (3)... fıkraları satır başına alır.
    - a), b), c)... bentlerini satır başına alır.
    - 1), 2), 3)... alt bentleri satır başına alır.
    - [[SUP]]...[[/SUP]] dipnot işaretlerini aynen korur.
    """

    text = " ".join(
        clean_line(x)
        for x in body_lines
        if clean_line(x)
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    ).strip()

    # Cümle bittikten sonra gelen yeni fıkra
    text = re.sub(
        r"(?<=[.!?])\s+"
        r"(?=\((?:[1-9]|[1-9]\d)\)\s)",
        "\n",
        text,
    )

    # Bazı metinlerde fıkra öncesinde nokta bulunmayabiliyor.
    # (2) ve sonrası için kontrollü ikinci kural.
    text = re.sub(
        r"(?<!^)\s+"
        r"(?=\((?:[2-9]|[1-9]\d)\)\s"
        r"(?:[A-ZÇĞİÖŞÜ]|"
        r"\[\[SUP\]\]))",
        "\n",
        text,
    )

    # Bentler: a), b), c), ç)...
    text = re.sub(
        r"(?<!^)\s+"
        r"(?=[a-zçğıöşü]\)\s)",
        "\n",
        text,
        flags=re.IGNORECASE,
    )

    # Alt bentler: 1), 2), 3)...
    text = re.sub(
        r"(?<!^)\s+"
        r"(?=\d+\)\s)",
        "\n",
        text,
    )

    text = re.sub(
        r"\n{2,}",
        "\n",
        text,
    )

    return text.strip()


# =========================================================
# MADDE AYRIŞTIRMA
# =========================================================

def parse_articles(soup):
    """
    Önemli mantık:

    Bir sonraki MADDE satırından hemen önce bulunan madde başlığı
    ve varsa üst bölüm başlıkları, önceki maddenin gövdesinden
    çıkarılır.

    Böylece:
      Madde 7'nin sonuna
      "Ön bilgilendirmeye ilişkin diğer yükümlülükler"
      gibi Madde 8 başlığı eklenmez.
    """

    for tag in soup(
        ["script", "style", "noscript", "iframe"]
    ):
        tag.decompose()

    raw_text = soup.get_text("\n")

    raw_text = raw_text.replace(
        "\xa0",
        " "
    )

    raw_text = raw_text.replace(
        "\r",
        "\n"
    )

    lines = [
        clean_line(x)
        for x in raw_text.split("\n")
    ]

    lines = [
        x for x in lines if x
    ]

    article_positions = []

    for index, line in enumerate(lines):
        match = ARTICLE_RE.match(line)

        if match:
            title, block_start = (
                heading_block_before(
                    lines,
                    index
                )
            )

            article_positions.append({
                "index": index,
                "match": match,
                "title": title,
                "block_start": block_start,
            })

    articles = []

    for n, info in enumerate(
        article_positions
    ):
        index = info["index"]
        match = info["match"]

        # Bir sonraki maddenin başlık bloğunda bitecek.
        if n + 1 < len(article_positions):
            next_info = article_positions[n + 1]
            end_index = next_info["block_start"]
        else:
            end_index = len(lines)

        # MADDE satırının kendisindeki "MADDE X -" sonrasını al.
        first_remainder = ARTICLE_RE.sub(
            "",
            lines[index],
            count=1,
        ).strip()

        body_lines = []

        if first_remainder:
            body_lines.append(
                first_remainder
            )

        body_lines.extend(
            lines[index + 1:end_index]
        )

        # Bölüm başlığı mevcut maddenin içine sarkmışsa kes.
        cleaned_body = []

        for line in body_lines:
            if SECTION_RE.match(line):
                break

            cleaned_body.append(line)

        is_temp = bool(
            match.group("temp")
        )

        num = match.group("num")

        articles.append({
            "madde": num,
            "gecici": is_temp,
            "baslik": info["title"],
            "metin": format_article_text(
                cleaned_body
            ),
        })

    return articles


# =========================================================
# TEK MEVZUATI KAYDET
# =========================================================

def save_mevzuat(item):
    soup = fetch_mevzuat(item)

    articles = parse_articles(
        soup
    )

    if not articles:
        raise RuntimeError(
            f"{item['ad']} için hiçbir MADDE bulunamadı."
        )

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

    output = (
        DATA_DIR
        / f"{item['id']}.json"
    )

    output.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        f"✓ {len(articles)} madde bulundu."
    )

    print(
        f"✓ Kaydedildi: {output.name}"
    )

    return {
        "id": item["id"],
        "ad": item["ad"],
        "dosya": f"data/{item['id']}.json",
        "kaynak": official_url(item),
        "madde_sayisi": len(articles),
        "son_guncelleme": data["son_guncelleme"],
    }


# =========================================================
# ANA İŞLEM
# =========================================================

def main():
    print("=" * 60)
    print("MEVZUAT KÜTÜPHANESİ")
    print(
        "Güncelleme başladı:",
        now_tr()
    )
    print("=" * 60)

    catalogue = []
    errors = []

    for item in MEVZUATLAR:
        try:
            result = save_mevzuat(
                item
            )

            catalogue.append(
                result
            )

        except Exception as exc:
            print(
                f"✗ HATA: {item['ad']}"
            )

            print(exc)

            errors.append({
                "id": item["id"],
                "ad": item["ad"],
                "hata": str(exc),
            })

        # Resmî kaynağa arka arkaya çok hızlı istek göndermeyelim.
        time.sleep(2)

    catalogue_data = {
        "son_guncelleme": now_tr(),
        "mevzuatlar": catalogue,
        "hatalar": errors,
    }

    catalogue_file = (
        DATA_DIR
        / "mevzuatlar.json"
    )

    catalogue_file.write_text(
        json.dumps(
            catalogue_data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print("=" * 60)
    print("İŞLEM TAMAMLANDI")
    print(
        f"Başarılı: {len(catalogue)}"
    )
    print(
        f"Hatalı: {len(errors)}"
    )
    print("=" * 60)

    # İki test mevzuatı da başarısızsa workflow kırmızı olsun.
    if not catalogue:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
