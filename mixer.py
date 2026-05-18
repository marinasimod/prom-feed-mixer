import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import time
import os
import re

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

id_map = {}
try:
    import zipfile
    excel_file = None
    for f in os.listdir('.'):
        if f.endswith('.xlsx'):
            excel_file = f
            break
            
    if excel_file:
        print(f"--- DETECTED EXCEL: {excel_file} ---", flush=True)
        with zipfile.ZipFile(excel_file) as z:
            shared_strings = []
            if 'xl/sharedStrings.xml' in z.namelist():
                ss_content = z.read('xl/sharedStrings.xml')
                ss_root = ET.fromstring(ss_content)
                for t in ss_root.findall('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t'):
                    shared_strings.append(t.text if t.text else "")
            
            sheet_content = z.read('xl/worksheets/sheet1.xml')
            sheet_root = ET.fromstring(sheet_content)
            
            rows = []
            for row in sheet_root.findall('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row'):
                r_data = {}
                for cell in row.findall('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c'):
                    r = cell.get('r')
                    col_letter = re.sub(r'\d+', '', r)
                    val_tag = cell.find('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v')
                    if val_tag is not None:
                        val = val_tag.text
                        if cell.get('t') == 's' and val.isdigit():
                            val = shared_strings[int(val)]
                        r_data[col_letter] = str(val).strip()
                if r_data:
                    rows.append(r_data)
            
            # Шукаємо колонку з ID Прому (зазвичай колонка А)
            id_col = None
            if rows:
                for col, val in rows[0].items():
                    if "ідентифікатор" in val.lower() or "id" in val.lower():
                        id_col = col
                        break
                if not id_col: id_col = 'A'
                
                # ТОТАЛЬНИЙ ПОШУК: перевіряємо всі клітинки в рядку
                for r in rows[1:]:
                    p_id = r.get(id_col)
                    if p_id and p_id.isdigit():
                        for col_letter, cell_value in r.items():
                            if col_letter != id_col and cell_value and cell_value.isdigit():
                                id_map[str(cell_value)] = str(p_id)
                                
        print(f"--- TOTAL DEEP MATCHED {len(id_map)} ARTIFACTS FROM EXCEL ---", flush=True)
except Exception as e:
    print(f"--- EXCEL DEEP MAPPER NOTICE: {e} ---", flush=True)

try:
    root_out = ET.Element("yml_catalog", date=datetime.now().strftime("%Y-%m-%d %H:%M"))
    shop_out = ET.SubElement(root_out, "shop")
    categories_out = ET.SubElement(shop_out, "categories")
    offers_out = ET.SubElement(shop_out, "offers")

    # DSN
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

    # PKK (Зустрічний глибокий пошук)
    root2 = load_xml(FEED_URL_2, "PKK")
    for cat in root2.findall(".//category"):
        categories_out.append(cat)

    for offer in root2.findall(".//offer"):
        o_id = offer.get("id")
        
        clean_offer = ET.Element("offer")
        
        # Якщо оригінальний код хоч десь був в Excel — даємо картці її рідний ID Прому
        if o_id in id_map:
            clean_offer.set("id", id_map[o_id])
        else:
            if o_id: clean_offer.set("id", o_id)

        g_id = offer.get("group_id")
        if g_id: clean_offer.set("group_id", g_id)

        c_id = offer.find("categoryId")
        if c_id is not None and c_id.text:
            ET.SubElement(clean_offer, "categoryId").text = c_id.text
            
        v_code = offer.find("vendorCode")
        if v_code is not None and v_code.text:
            ET.SubElement(clean_offer, "vendorCode").text = v_code.text.strip()
            
        name_tag = offer.find("name")
        if name_tag is not None:
            ET.SubElement(clean_offer, "name").text = name_tag.text

        price_tag = offer.find("price")
        oldprice_tag = offer.find("oldprice")
        if oldprice_tag is not None and oldprice_tag.text:
            ET.SubElement(clean_offer, "price").text = oldprice_tag.text
        elif price_tag is not None:
            ET.SubElement(clean_offer, "price").text = price_tag.text

        quantity_tag = offer.find("quantity")
        is_available = offer.get("available")
        
        if is_available == "false" or (quantity_tag is not None and quantity_tag.text == "0"):
            clean_offer.set("available", "false")
            ET.SubElement(clean_offer, "quantity").text = "0"
        elif quantity_tag is not None and quantity_tag.text:
            clean_offer.set("available", "true")
            ET.SubElement(clean_offer, "quantity").text = quantity_tag.text
        else:
            clean_offer.set("available", "true")
            ET.SubElement(clean_offer, "quantity").text = "5"

        offers_out.append(clean_offer)

    print("--- SAVING TOTAL PERFECT FEED ---", flush=True)
    tree = ET.ElementTree(root_out)
    tree.write(OUTPUT_FILE, encoding="utf-8", xml_declaration=True)
    print("--- SUCCESS ---", flush=True)

except Exception as e:
    print(f"ERROR: {e}", flush=True)
    exit(1)
