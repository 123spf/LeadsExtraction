import zipfile
import xml.etree.ElementTree as ET
import html
import re
import csv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def extract_links_and_names(odt_path):
    """Parses the ODT XML structure to extract link text and hyperlinked URLs."""
    records = []
    
    with zipfile.ZipFile(odt_path, 'r') as archive:
        xml_content = archive.read('content.xml')
        root = ET.fromstring(xml_content)
        
        # XML namespaces used inside ODT content documents
        namespaces = {
            'text': 'urn:oasis:names:tc:opendocument:xmlns:text:1.0',
            'xlink': 'http://www.w3.org/1999/xlink'
        }
        
        # Find all hyperlink tags inside the document
        for a_tag in root.findall('.//text:a', namespaces):
            url = a_tag.attrib.get(f"{{{namespaces['xlink']}}}href", '')
            raw_text = "".join(a_tag.itertext()).strip()
            
            if url and "controller.cfm" in url:
                # Unescape XML entity codes (e.g., &amp; -> &)
                clean_url = html.unescape(url)
                
                # Parse Name: Expected "LAST NAME, FIRST NAME"
                if ',' in raw_text:
                    last_name, first_name = [part.strip() for part in raw_text.split(',', 1)]
                else:
                    last_name = raw_text.strip()
                    first_name = ""
                    
                records.append({
                    'first_name': first_name,
                    'last_name': last_name,
                    'url': clean_url
                })
                
    return records

def process_leads(odt_file, output_csv):
    records = extract_links_and_names(odt_file)
    print(f"Extracted {len(records)} records from {odt_file}.")

    # Configure CSV Output Header matching DIRECT-MAIL-CSV-TEMPLATE
    csv_headers = [
        "Record Id", "Salutation", "First Name", "Middle Name", "Last Name",
        "Name Suffix", "Title", "Business", "Address 1", "Address 2",
        "City", "State", "Zip"
    ]

    driver = webdriver.Chrome()
    driver.get("") #enter website name
    
    input("Please log in, in the browser window. Press Enter in the terminal once logged in...")

    with open(output_csv, mode='w', newline='', encoding='utf-8') as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(csv_headers)

        for index, record in enumerate(records, start=1):
            url = record['url']
            print(f"[{index}/{len(records)}] Processing: {record['first_name']} {record['last_name']}")
            driver.get(url)

            address_1 = ""
            address_2 = ""
            city = ""
            state = "PA"
            zip_code = ""

            try:
                # Retrieve container holding address elements
                container = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//*[@id='leftContactDiv']/div/table[1]/tbody/tr/td[2]/div/div"))
                )
                
                # Extract non-empty lines from the rendered text
                raw_lines = [line.strip() for line in container.text.splitlines() if line.strip()]
                
                # Exclude the trailing unnecessary line identified in testing
                if len(raw_lines) > 1:
                    address_lines = raw_lines[:-1]
                else:
                    address_lines = raw_lines

                # Process Address block based on line count
                if len(address_lines) == 2:
                    # Format: Line 1 = Address 1 | Line 2 = City, State Zip
                    address_1 = address_lines[0]
                    city_state_zip_line = address_lines[1]
                elif len(address_lines) >= 3:
                    # Format: Line 1 = Address 1 | Line 2 = Address 2 | Line 3 = City, State Zip
                    address_1 = address_lines[0]
                    address_2 = address_lines[1]
                    city_state_zip_line = address_lines[2]
                else:
                    city_state_zip_line = ""

                # Parse City and Zip from the 2nd-to-last line
                if city_state_zip_line:
                    # Extract City (text prior to comma)
                    if ',' in city_state_zip_line:
                        city = city_state_zip_line.split(',')[0].strip()
                    
                    # Extract 5-digit ZIP code using Regex
                    zip_match = re.search(r'\b\d{5}(?:-\d{4})?\b', city_state_zip_line)
                    if zip_match:
                        zip_code = zip_match.group(0)

            except Exception as e:
                print(f"Failed to parse address for {url}: {e}")

            # Write row formatted specifically to your required template
            writer.writerow([
                index,                  # Record Id
                "",                     # Salutation
                record['first_name'],   # First Name
                "",                     # Middle Name
                record['last_name'],    # Last Name
                "",                     # Name Suffix
                "",                     # Title
                "",                     # Business
                address_1,              # Address 1
                address_2,              # Address 2
                city,                   # City
                state,                  # State ("PA")
                zip_code                # Zip
            ])

    driver.quit()
    print(f"Extraction completed. Data saved to {output_csv}")

if __name__ == "__main__":
    process_leads("Leads.odt", "mail_list.csv")