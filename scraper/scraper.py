import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

def extract_embedded_json_improved(html_text):
    """Extract JSON data from the script tags with improved pattern matching"""
    # Look for contract data in the specific format we've identified
    contract_pattern = r'\{"date":"([^"]+)","piid":"([^"]+)","agency":"([^"]+)","ceiling_value":"([^"]+)","value":"([^"]+)","update_date":"([^"]+)","fpds_status":"([^"]+)","fpds_link":"([^"]+)","vendor":"([^"]+)","description":"([^"]+)"\}'
    
    contracts = re.findall(contract_pattern, html_text)
    
    if contracts:
        # Convert to DataFrame with appropriate column names
        columns = ['date', 'piid', 'agency', 'ceiling_value', 'value', 'update_date', 
                  'fpds_status', 'fpds_link', 'vendor', 'description']
        df = pd.DataFrame(contracts, columns=columns)
        
        # Clean up numeric values
        for col in ['ceiling_value', 'value']:
            df[col] = df[col].str.replace(',', '').str.replace('$', '').str.strip()
            # Convert to numeric
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        return df
    
    # If the specific pattern doesn't match, try a more general approach
    json_pattern = r'self\.__next_f\.push\(\[1,"([^"]+)"\]\)'
    matches = re.findall(json_pattern, html_text)
    
    if matches:
        combined_data = "".join(matches)
        
        # Try to extract any JSON-like structures
        try:
            # Look for objects with agency and ceiling_value
            agency_pattern = r'\{"[^"]+":"[^"]+","agency":"([^"]+)","ceiling_value":"([^"]+)","value":"([^"]+)"'
            agency_matches = re.findall(agency_pattern, combined_data)
            
            if agency_matches:
                df = pd.DataFrame(agency_matches, columns=['agency', 'ceiling_value', 'value'])
                
                # Clean up numeric values
                for col in ['ceiling_value', 'value']:
                    df[col] = df[col].str.replace(',', '').str.replace('$', '').str.strip()
                    # Convert to numeric
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                
                return df
        except Exception as e:
            print(f"Error parsing JSON data: {e}")
    
    return pd.DataFrame()  # Return empty DataFrame if no data found

def extract_contracts_via_javascript(driver):
    """Try to extract contract data directly via JavaScript execution"""
    try:
        # This is a simplified approach - the actual data structure might be more complex
        js_script = """
        // Try to find contract data in the window object
        let contractData = [];
        
        // Look for data in various possible locations
        if (window.__NEXT_DATA__ && window.__NEXT_DATA__.props && 
            window.__NEXT_DATA__.props.pageProps && 
            window.__NEXT_DATA__.props.pageProps.contracts) {
            contractData = window.__NEXT_DATA__.props.pageProps.contracts;
        }
        
        // Return whatever we found
        return JSON.stringify(contractData);
        """
        
        result = driver.execute_script(js_script)
        
        if result and result != "[]":
            # Parse the JSON result
            contracts = json.loads(result)
            
            if isinstance(contracts, list) and len(contracts) > 0:
                # Convert to DataFrame
                df = pd.DataFrame(contracts)
                return df
    
    except Exception as e:
        print(f"Error extracting contracts via JavaScript: {e}")
    
    return pd.DataFrame()

def scrape_with_selenium():
    """Use Selenium to scrape the page, which can handle JavaScript-rendered content"""
    url = "https://doge.gov/savings"
    
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.binary_location = "/usr/bin/google-chrome"  # Set the path as needed
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), 
                             options=options)
    
    try:
        driver.get(url)
        
        # Wait for the page to load completely
        time.sleep(5)
        
        # First, try to extract data directly from JavaScript
        print("Attempting to extract data directly from JavaScript...")
        js_data = extract_contracts_via_javascript(driver)
        
        if not js_data.empty:
            print(f"Successfully extracted {len(js_data)} records directly from JavaScript!")
        
        results = {}
        if not js_data.empty:
            results['JS_Contracts'] = js_data
        
        # Check if there's a "View All Contracts" button and click it
        try:
            view_all_contracts = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'View All Contracts')]"))
            )
            view_all_contracts.click()
            print("Clicked 'View All Contracts' button")
            time.sleep(3)  # Wait for all contracts to load
        except Exception as e:
            print(f"Could not find or click 'View All Contracts' button: {e}")
        
        # Extract all tables
        
        # 1. Extract Contracts table
        try:
            contracts_section = driver.find_element(By.XPATH, "//h2[contains(text(), 'Contracts')]")
            contracts_table = contracts_section.find_element(By.XPATH, "./following::table[1]")
            
            # Extract headers
            headers = [th.text.strip() for th in contracts_table.find_elements(By.TAG_NAME, "th")]
            
            # Extract all rows
            rows = []
            for tr in contracts_table.find_elements(By.XPATH, ".//tbody/tr"):
                row = {}
                cells = tr.find_elements(By.TAG_NAME, "td")
                
                for i, td in enumerate(cells):
                    if i < len(headers):
                        # Handle different cell types
                        if td.get_attribute('title'):  # Full text in title attribute
                            row[headers[i]] = td.get_attribute('title')
                        elif td.find_elements(By.TAG_NAME, "a"):  # Link
                            link = td.find_element(By.TAG_NAME, "a").get_attribute('href')
                            row[headers[i]] = link
                        else:
                            # For value cells, clean up the text
                            cell_text = td.text.strip()
                            if '$' in cell_text:
                                # Extract just the number
                                value_match = re.search(r'\$\s*([0-9,]+)', cell_text)
                                if value_match:
                                    row[headers[i]] = value_match.group(1).replace(',', '')
                            else:
                                row[headers[i]] = cell_text
                
                if row:
                    rows.append(row)
            
            results['Contracts'] = pd.DataFrame(rows)
            print(f"Extracted {len(rows)} contract rows from HTML table")
        except Exception as e:
            print(f"Error extracting contracts table: {e}")
        
        # Try to click "View All Grants" button
        try:
            view_all_grants = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'View All Grants')]"))
            )
            view_all_grants.click()
            print("Clicked 'View All Grants' button")
            time.sleep(3)  # Wait for all grants to load
        except Exception as e:
            print(f"Could not find or click 'View All Grants' button: {e}")
        
        # 2. Extract Grants table
        try:
            grants_section = driver.find_element(By.XPATH, "//h2[contains(text(), 'Grants')]")
            grants_table = grants_section.find_element(By.XPATH, "./following::table[1]")
            
            # Extract headers
            headers = [th.text.strip() for th in grants_table.find_elements(By.TAG_NAME, "th")]
            
            # Extract all rows
            rows = []
            for tr in grants_table.find_elements(By.XPATH, ".//tbody/tr"):
                row = {}
                cells = tr.find_elements(By.TAG_NAME, "td")
                
                for i, td in enumerate(cells):
                    if i < len(headers):
                        # Handle different cell types
                        if td.get_attribute('title'):  # Full text in title attribute
                            row[headers[i]] = td.get_attribute('title')
                        else:
                            # For value cells, clean up the text
                            cell_text = td.text.strip()
                            if '$' in cell_text:
                                # Extract just the number
                                value_match = re.search(r'\$\s*([0-9,]+)', cell_text)
                                if value_match:
                                    row[headers[i]] = value_match.group(1).replace(',', '')
                            else:
                                row[headers[i]] = cell_text
                
                if row:
                    rows.append(row)
            
            results['Grants'] = pd.DataFrame(rows)
            print(f"Extracted {len(rows)} grant rows from HTML table")
        except Exception as e:
            print(f"Error extracting grants table: {e}")
        
        # Try to click "View All Leases" button
        try:
            view_all_leases = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'View All Leases')]"))
            )
            view_all_leases.click()
            print("Clicked 'View All Leases' button")
            time.sleep(3)  # Wait for all leases to load
        except Exception as e:
            print(f"Could not find or click 'View All Leases' button: {e}")
        
        # 3. Extract Real Estate table
        try:
            real_estate_section = driver.find_element(By.XPATH, "//h2[contains(text(), 'Real Estate')]")
            real_estate_table = real_estate_section.find_element(By.XPATH, "./following::table[1]")
            
            # Extract headers
            headers = [th.text.strip() for th in real_estate_table.find_elements(By.TAG_NAME, "th")]
            
            # Extract all rows
            rows = []
            for tr in real_estate_table.find_elements(By.XPATH, ".//tbody/tr"):
                row = {}
                cells = tr.find_elements(By.TAG_NAME, "td")
                
                for i, td in enumerate(cells):
                    if i < len(headers):
                        # Handle different cell types
                        if td.get_attribute('title'):  # Full text in title attribute
                            row[headers[i]] = td.get_attribute('title')
                        else:
                            # For value cells, clean up the text
                            cell_text = td.text.strip()
                            if '$' in cell_text:
                                # Extract just the number
                                value_match = re.search(r'\$\s*([0-9,]+)', cell_text)
                                if value_match:
                                    row[headers[i]] = value_match.group(1).replace(',', '')
                            else:
                                row[headers[i]] = cell_text
                
                if row:
                    rows.append(row)
            
            results['Real Estate'] = pd.DataFrame(rows)
            print(f"Extracted {len(rows)} real estate rows from HTML table")
        except Exception as e:
            print(f"Error extracting real estate table: {e}")
        
        # 4. Try to extract embedded JSON data from page source
        try:
            page_source = driver.page_source
            json_data = extract_embedded_json_improved(page_source)
            if isinstance(json_data, pd.DataFrame) and not json_data.empty:
                results['Embedded_Data'] = json_data
                print(f"Extracted {len(json_data)} rows from embedded JSON")
        except Exception as e:
            print(f"Error extracting embedded JSON: {e}")
        
        return results
    
    finally:
        driver.quit()

def scrape_with_requests():
    """Use requests and BeautifulSoup to scrape the page"""
    url = "https://doge.gov/savings"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        results = {}
        
        # Process each table
        for table_section in ['Contracts', 'Grants', 'Real Estate']:
            # Find the section heading
            section = soup.find('h2', string=lambda t: t and table_section in t)
            if not section:
                continue
                
            # Find the table
            table = section.find_next('table')
            if not table:
                continue
                
            # Extract headers
            headers = [th.text.strip() for th in table.find_all('th')]
            
            # Extract rows
            rows = []
            for tr in table.find_all('tr')[1:]:  # Skip header row
                row = {}
                cells = tr.find_all('td')
                
                for i, td in enumerate(cells):
                    if i < len(headers):
                        # Handle different cell types
                        if td.get('title'):  # Full text in title attribute
                            row[headers[i]] = td.get('title')
                        elif td.find('a'):  # Link
                            row[headers[i]] = td.find('a')['href']
                        else:
                            # For value cells, clean up the text
                            cell_text = td.text.strip()
                            if '$' in cell_text:
                                # Extract just the number
                                value_match = re.search(r'\$\s*([0-9,]+)', cell_text)
                                if value_match:
                                    row[headers[i]] = value_match.group(1).replace(',', '')
                            else:
                                row[headers[i]] = cell_text
                
                if row:
                    rows.append(row)
            
            results[table_section] = pd.DataFrame(rows)
            print(f"Extracted {len(rows)} {table_section.lower()} rows")
        
        # Try to extract embedded JSON data
        json_data = extract_embedded_json_improved(response.text)
        if isinstance(json_data, pd.DataFrame) and not json_data.empty:
            results['Embedded_Data'] = json_data
            print(f"Extracted {len(json_data)} rows from embedded JSON")
        
        return results
    
    except requests.exceptions.RequestException as e:
        print(f"Error fetching the webpage: {e}")
        return None

if __name__ == "__main__":
    print("Starting scraping process...")
    
    # Try both methods and use the one that works better
    print("\nTrying with requests and BeautifulSoup first...")
    data_from_requests = scrape_with_requests()
    
    if data_from_requests:
        for table_name, df in data_from_requests.items():
            if isinstance(df, pd.DataFrame) and not df.empty:
                print(f"\n{table_name} Data (first 5 rows):")
                print(df.head())
                print(f"Total rows: {len(df)}")
                # Save to CSV
                df.to_csv(f"{table_name.lower().replace(' ', '_')}_data.csv", index=False)
                print(f"Saved to {table_name.lower().replace(' ', '_')}_data.csv")
    
    print("\nTrying with Selenium for more complete data...")
    data_from_selenium = scrape_with_selenium()
    
    if data_from_selenium:
        for table_name, df in data_from_selenium.items():
            if isinstance(df, pd.DataFrame) and not df.empty:
                print(f"\n{table_name} Data (first 5 rows):")
                print(df.head())
                print(f"Total rows: {len(df)}")
                # Save to CSV
                file_name = f"{table_name.lower().replace(' ', '_')}_selenium_data.csv"
                df.to_csv(file_name, index=False)
                print(f"Saved to {file_name}")
    
    print("\nScraping process completed!")
