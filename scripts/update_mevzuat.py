import json
import re
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------------------------------------------------------
# AYARLAR
# ---------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

# Şimdilik SADECE 2 mevzuatla test ediyoruz.
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
    "Referer": "https://www.mevzuat.gov.tr/",
}


# ---------------------------------------------------------
# YARDIMCI FONKSİYONLAR
# ---------------------------------------------------------

def now_tr():
    return datetime.now(ZoneInfo("Europe/Istanbul")).isoformat(
        timespec="seconds"
    )


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


def clean_text(text):
    """Gereksiz boşlukları temizler ama paragraf yapısını korur."""
    text = text.replace("\xa0", " ")
    text = text.replace("\r", "\n")

    lines = []

    for line in text.split("\n"):
        line = re.sub(r"[ \t]+", " ", line).strip()

        if line:
            lines.append(line)

    return "\n".join(lines)


def get_page(url):
    """
    Önce normal SSL doğrulaması ile dener.
    Mevzuat.gov.tr sertifika zinciri sorun çıkarırsa
    ikinci denemede SSL doğrulamasını kapatır.
    """

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=45,
        )

        response.raise_for_status()
        return response

    except requests.exceptions.SSLError:
        print("   SSL doğrulaması başarısız. Yedek yöntem deneniyor...")

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=45,
            verify=False,
        )

        response.raise_for_status()
        return response


# ---------------------------------------------------------
# ÜST KARAKTER / DİPNOT KORUMA
# ---------------------------------------------------------

def preserve_superscripts(soup):
    """
    Kaynaktaki <sup> dipnotlarını kaybetmeden JSON'a aktarır.

    Örneğin:
        <sup>[1]</sup>

    JSON içinde:
        [[SUP]][1][[/SUP]]

    olarak tutulur.

    Daha sonra web sitesi bunu tekrar gerçek <sup>
    biçiminde gösterecek.
    """

    for tag in soup.find_all("sup"):

        value = tag.get_text(" ", strip=True)
        value = re.sub(r"\s+", "", value)

        if value:
            tag.replace_with(
                f"[[SUP]]{value}[[/SUP]]"
            )
        else:
            tag.decompose()


# ---------------------------------------------------------
# MEVZUAT HTML'İNİ AL
# ---------------------------------------------------------

def fetch_mevzuat(item):

    url = detail_url(item)

    print(f"\n{item['ad']}")
    print("Kaynak indiriliyor...")

    response = get_page(url)

    # Türkçe karakter problemi yaşamamak için
    # mümkünse sunucunun tahmin ettiği encoding kullanılır.
    if not response.encoding or response.encoding.lower() == "iso-8859-1":
        response.encoding = response.apparent_encoding

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    preserve_superscripts(soup)

    return soup


# ---------------------------------------------------------
# MADDELERİ AYRIŞTIR
# ---------------------------------------------------------

ARTICLE_RE = re.compile(
    r"^\s*MADDE\s+(\d+)\s*[-–—]",
    re.IGNORECASE
)


def parse_articles(soup):

    # script/style gibi görünmeyen içerikleri kaldır
    for tag in soup(
        ["script", "style", "noscript", "iframe"]
    ):
        tag.decompose()

    text = soup.get_text("\n")

    text = text.replace("\xa0", " ")
    text = text.replace("\r", "\n")

    # Fazla boş satırları temizle
    text = re.sub(r"\n[ \t]*\n+", "\n", text)

    lines = [
        re.sub(r"[ \t]+", " ", x).strip()
        for x in text.split("\n")
    ]

    lines = [x for x in lines if x]

    articles = []

    current = None
    previous_line = ""

    for line in lines:

        match = ARTICLE_RE.match(line)

        if match:

            # Önceki maddeyi kaydet
            if current:
                current["metin"] = clean_text(
                    "\n".join(current["body"])
                )

                del current["body"]

                articles.append(current)

            number = int(match.group(1))

            # MADDE satırından önce gelen satır genellikle
            # madde başlığıdır.
            title = previous_line.strip()

            # Bölüm başlıklarının yanlışlıkla madde başlığı
            # olmasını engelle.
            if re.match(
                r"^(BİRİNCİ|İKİNCİ|ÜÇÜNCÜ|DÖRDÜNCÜ|"
                r"BEŞİNCİ|ALTINCI|YEDİNCİ|SEKİZİNCİ|"
                r"DOKUZUNCU|ONUNCU)\s+BÖLÜM$",
                title,
                re.IGNORECASE,
            ):
                title = ""

            # "MADDE 7 –" kısmından sonrasını al
            remainder = ARTICLE_RE.sub(
                "",
                line,
                count=1
            ).strip()

            current = {
                "madde": number,
                "baslik": title,
                "body": [],
            }

            if remainder:
                current["body"].append(remainder)

        else:

            if current:
                current["body"].append(line)

        previous_line = line

    # Son madde
    if current:

        current["metin"] = clean_text(
            "\n".join(current["body"])
        )

        del current["body"]

        articles.append(current)

    return articles


# ---------------------------------------------------------
# TEK MEVZUATI KAYDET
# ---------------------------------------------------------

def save_mevzuat(item):

    soup = fetch_mevzuat(item)

    articles = parse_articles(soup)

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

    output = DATA_DIR / f"{item['id']}.json"

    output.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2
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


# ---------------------------------------------------------
# ANA İŞLEM
# ---------------------------------------------------------

def main():

    print("=" * 60)
    print("MEVZUAT KÜTÜPHANESİ")
    print("Güncelleme başladı:", now_tr())
    print("=" * 60)

    catalogue = []
    errors = []

    for item in MEVZUATLAR:

        try:
            result = save_mevzuat(item)
            catalogue.append(result)

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

        # Mevzuat.gov.tr'ye arka arkaya çok hızlı
        # istek göndermeyelim.
        time.sleep(2)

    catalogue_data = {
        "son_guncelleme": now_tr(),
        "mevzuatlar": catalogue,
        "hatalar": errors,
    }

    catalogue_file = DATA_DIR / "mevzuatlar.json"

    catalogue_file.write_text(
        json.dumps(
            catalogue_data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("\n" + "=" * 60)
    print("İŞLEM TAMAMLANDI")
    print(f"Başarılı: {len(catalogue)}")
    print(f"Hatalı: {len(errors)}")
    print("=" * 60)

    # Tüm mevzuatlar başarısızsa GitHub Actions
    # çalışmasını başarısız say.
    if not catalogue:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
