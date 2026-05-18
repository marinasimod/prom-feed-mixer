import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import time

FEED_URL_1 = "https://dsnkeyms.hook-dsn.pp.ua/feed/full-stock/catalog?token=c4b11a00d00657fffe4371ef43c3ea5f5d531cbd0903e8c1&offer_id=legacy"
FEED_URL_2 = "https://pkkopt.com.ua/content/export/e60e78a6b01d00d09fe25c1b666cc415.xml?1777544130"
OUTPUT_FILE = "prom_full_auto_feed.xml"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def load_xml(url, name):
    print(f"--- DOWNLOAD {name} ---", flush=True)
    res = requests.get(url, headers=HEADERS, timeout=60)
    res.raise_for_status()
    return ET.fromstring(res.content)

try:
    root_out = ET.Element("yml_catalog", date=datetime.now().strftime("%Y-%m-%d %H:%M"))
    shop_out = ET.SubElement(root_out, "shop")
    categories_out = ET.SubElement(shop_out, "categories")
    offers_out = ET.SubElement(shop_out, "offers")

    # 1. ОБРОБКА DSN (Захищено префіксами від накладання)
    root1 = load_xml(FEED_URL_1, "DSN")
    for cat in root1.findall(".//category"):
        c_id = cat.get("id")
        p_id = cat.get("parentId")
        if c_id: cat.set("id", f"DSN_{c_id}")
        if p_id: cat.set("parentId", f"DSN_{p_id}")
        categories_out.append(cat)

    for offer in root1.findall(".//offer"):
        o_id = offer.get("id")
        if o_id: offer.set("id", f"DSN_{o_id}")
        c_id = offer.find("categoryId")
        if c_id is not None and c_id.text: c_id.text = f"DSN_{c_id.text}"
        v_code = offer.find("vendorCode")
        if v_code is not None and v_code.text: v_code.text = f"DSN_{v_code.text}"
        offers_out.append(offer)

    time.sleep(1)

    # 2. ОБРОБКА PKK (Математичний захист без букв)
    root2 = load_xml(FEED_URL_2, "PKK")
    for cat in root2.findall(".//category"):
        c_id = cat.get("id")
        p_id = cat.get("parentId")
        # Зсуваємо ID категорій у зону чистих мільярдів, щоб не накладалися на DSN
        if c_id and c_id.isdigit(): cat.set("id", str(int(c_id) + 900000000))
        if p_id and p_id.isdigit(): cat.set("parentId", str(int(p_id) + 900000000))
        categories_out.append(cat)

    group_data = {}
    all_pkk_offers = root2.findall(".//offer")

    # Збір бази для пустих різновидів
    for offer in all_pkk_offers:
        g_id = offer.get("group_id")
        if g_id:
            name = offer.find("name")
            description = offer.find("description")
            pictures = offer.findall("picture")
            if g_id not in group_data or (name is not None and description is not None):
                group_data[g_id] = {
                    "name": name.text if name is not None else None,
                    "description": description.text if description is not None else None,
                    "pictures": [p.text for p in pictures if p.text]
                }

    for offer in all_pkk_offers:
        o_id = offer.get("id")  # Оригінальний ID товару (наприклад, 326622)
        g_id = offer.get("group_id")
        
        # ЗАХИСТ: ID товару залишаємо ЧИСТО ЧИСЛОВИМ, щоб Пром його впізнав!
        # Але додаємо зсув на 900 мільйонів, ТІЛЬКИ якщо ваші картки колись завантажувалися через PKK-коди.
        # Оскільки на скріншоті видно чистий код PKK, ми просто віддаємо чистий числовий ID.
        if o_id and o_id.isdigit():
            offer.set("id", o_id) 
            
        if g_id and g_id.isdigit():
            # Зсув груп у числу зону, щоб не перетиналися з групами DSN
            numeric_group_id = int(g_id) + 900000000
            offer.set("group_id", str(numeric_group_id))
            
            # Відновлення порожніх карток
            if offer.find("name") is None or not offer.find("name").text:
                if group_data.get(g_id) and group_data[g_id]["name"]:
                    ET.SubElement(offer, "name").text = group_data[g_id]["name"]
            
            if offer.find("description") is None or not offer.find("description").text:
                if group_data.get(g_id) and group_data[g_id]["description"]:
                    ET.SubElement(offer, "description").text = group_data[g_id]["description"]
            
            if offer.find("picture") is None:
                if group_data.get(g_id) and group_data[g_id]["pictures"]:
                    for pic_url in group_data[g_id]["pictures"]:
                        ET.SubElement(offer, "picture").text = pic_url

            # Унікальний тон, щоб не було дублів характеристик
            for p in offer.findall("param"):
                if p.get("name") in ["Цвет", "Колір"]:
                    offer.remove(p)
            ET.SubElement(offer, "param", name="Колір").text = f"№ {o_id}"

        c_id = offer.find("categoryId")
        if c_id is not None and c_id.text and c_id.text.isdigit():
            c_id.text = str(int(c_id.text) + 900000000)
        
        # Артикул віддаємо чистим числом, як у картці Прому
        v_code = offer.find("vendorCode")
        if v_code is not None and v_code.text:
            v_code.text = v_code.text.strip()

        # Контроль кількості
        quantity_tag = offer.find("quantity")
        is_available = offer.get("available")
        
        if is_available == "false" or (quantity_tag is not None and quantity_tag.text == "0"):
            offer.set("available", "false")
            if quantity_tag is not None: quantity_tag.text = "0"
            else: ET.SubElement(offer, "quantity").text = "0"
        elif quantity_tag is None or not quantity_tag.text:
            ET.SubElement(offer, "quantity").text = "5"

        price_tag = offer.find("price")
        oldprice_tag = offer.find("oldprice")
        if oldprice_tag is not None and oldprice_tag.text:
            if price_tag is not None: price_tag.text = oldprice_tag.text
            offer.remove(oldprice_tag)

        offers_out.append(offer)

    print("--- SAVING SAFE SMART FEED ---", flush=True)
    tree = ET.ElementTree(root_out)
    tree.write(OUTPUT_FILE, encoding="utf-8", xml_declaration=True)
    print("--- SUCCESS ---", flush=True)

except Exception as e:
    print(f"ERROR: {e}", flush=True)
    exit(1)
