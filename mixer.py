import requests
import xml.etree.ElementTree as ET
import re
from datetime import datetime

FEED_URL_1 = "https://dsnkeyms.hook-dsn.pp.ua/feed/full-stock/catalog?token=c4b11a00d00657fffe4371ef43c3ea5f5d531cbd0903e8c1&offer_id=legacy"
FEED_URL_2 = "https://pkkopt.com.ua/content/export/e60e78a6b01d00d09fe25c1b666cc415.xml?1777544130"
OUTPUT_FILE = "prom_full_auto_feed.xml"

def process_feed_to_memory(url, prefix):
    print(f"Çàâàíòàæåííÿ ô³äà {prefix}...")
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    content = response.text

    print(f"Äîäàâàííÿ ïðåô³êñ³â äëÿ {prefix}...")
    content = re.sub(r'<offer id="', f'<offer id="{prefix}', content)
    content = re.sub(r'<categoryId>', f'<categoryId>{prefix}', content)
    content = re.sub(r'<category id="', f'<category id="{prefix}', content)
    content = re.sub(r'parentId="', f'parentId="{prefix}', content)
    content = re.sub(r'<vendorCode>', f'<vendorCode>{prefix}', content)
    
    return content

try:
    feed1_text = process_feed_to_memory(FEED_URL_1, "DSN_")
    feed2_text = process_feed_to_memory(FEED_URL_2, "PKK_")
    
    print("Âèòÿãóâàííÿ êàòåãîð³é òà òîâàð³â...")
    cats1 = re.findall(r'<category[\s\S]*?<\/category>', feed1_text)
    cats2 = re.findall(r'<category[\s\S]*?<\/category>', feed2_text)
    
    offers1 = re.findall(r'<offer[\s\S]*?<\/offer>', feed1_text)
    offers2 = re.findall(r'<offer[\s\S]*?<\/offer>', feed2_text)
    
    all_categories = "".join(cats1) + "".join(cats2)
    all_offers = "".join(offers1) + "".join(offers2)
    
    print("Ôîðìóâàííÿ ô³íàëüíîãî XML ôàéëó...")
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="utf-8"?>\n')
        f.write(f'<yml_catalog date="{current_time}">\n')
        f.write('<shop>\n')
        f.write('<categories>\n')
        f.write(all_categories)
        f.write('</categories>\n')
        f.write('<offers>\n')
        f.write(all_offers)
        f.write('</offers>\n')
        f.write('</shop>\n')
        f.write('</yml_catalog>\n')
        
    print(f"ÓÑÏ²Õ! Ôàéë {OUTPUT_FILE} óñïåøíî ñòâîðåíî.")

except Exception as e:
    print(f"Êðèòè÷íà ïîìèëêà ï³ä ÷àñ âèêîíàííÿ ñêðèïòà: {e}")
    exit(1)
