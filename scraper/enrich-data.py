import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def get_field_value(driver, element_id, fallback_title=None):
    """
    Attempts to find an input element using its ID.
    If not found and fallback_title is provided, uses an XPath searching for an element
    whose title attribute contains fallback_title.
    Returns the element's value or None if not found.
    """
    try:
        element = driver.find_element(By.ID, element_id)
    except Exception as e:
        if fallback_title:
            try:
                xpath = f'//input[contains(@title, "{fallback_title}")]'
                element = driver.find_element(By.XPATH, xpath)
            except Exception as inner_e:
                print(f"[ERROR] Field with id '{element_id}' and title '{fallback_title}' not found: {inner_e}")
                return None
        else:
            print(f"[ERROR] Field with id '{element_id}' not found: {e}")
            return None
    return element.get_attribute("value")


def scrape_contract_page(driver, url):
    """
    Opens the given URL and extracts the desired fields.
    Returns a dictionary with the field names and their values.
    """
    driver.get(url)
    # Wait for the page body to be present.
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
    except Exception as e:
        print(f"Page did not load in time: {e}")
    time.sleep(0.5)  # Additional delay if needed

    # Define the fields to extract.
    fields = [
        {"name": "Organization Type", "id": "organizationType", "fallback": "Organization Type"},
        {"name": "Reason For Modification", "id": "reasonForModification", "fallback": "Reason For Modification"},
        {"name": "Legal Business Name", "id": "vendorName", "fallback": "Legal Business Name"},
        {"name": "cage Code", "id": "cageCode", "fallback": "cage Code"},
        {"name": "Principal NAICS Code", "id": "principalNAICSCode", "fallback": "Principal NAICS Code"},
        {"name": "Doing Business As Name", "id": "vendorDoingAsBusinessName", "fallback": "Doing Business As Name"},
        {"name": "Unique Entity Identifier", "id": "UEINumber", "fallback": "Unique Entity Identifier"},
        {"name": "NAICS Code Description", "id": "NAICSCodeDescription", "fallback": "NAICS Code Description"}
    ]
    
    result = {}
    for field in fields:
        field_name = field["name"]
        element_id = field["id"]
        fallback = field.get("fallback")
        result[field_name] = get_field_value(driver, element_id, fallback)
        print(f"{field_name}: {result[field_name]}")
    return result


def main():
    # Setup Chrome with headless options.
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.binary_location = "/usr/bin/google-chrome"  # Adjust this path if needed

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )

    # Read the original CSV.
    contracts_df = pd.read_csv("contracts_selenium_data.csv")
    
    if "LINK" not in contracts_df.columns:
        print("CSV file does not contain a column named 'LINK'.")
        driver.quit()
        return

    # For every contract, scrape the page and add the extracted fields to the DataFrame.
    extracted_data = {
        "Organization Type": [],
        "Reason For Modification": [],
        "Legal Business Name": [],
        "cage Code": [],
        "Principal NAICS Code": [],
        "Doing Business As Name": [],
        "Unique Entity Identifier": [],
        "NAICS Code Description": []
    }
    
    total_contracts = len(contracts_df)
    for idx, row in contracts_df.iterrows():
        url = row["LINK"]
        print(f"[INFO] Processing contract {idx+1}/{total_contracts}: {url}")
        try:
            fields = scrape_contract_page(driver, url)
            # Append the field values to the extracted_data dictionary.
            for key in extracted_data.keys():
                extracted_data[key].append(fields.get(key))
        except Exception as err:
            print(f"[ERROR] Processing link {url} failed: {err}")
            # Append None if error occurs.
            for key in extracted_data.keys():
                extracted_data[key].append(None)

    # Close the Selenium driver.
    driver.quit()

    # Add the new fields to the original DataFrame.
    for col, values in extracted_data.items():
        contracts_df[col] = values

    # Save the updated DataFrame to CSV.
    output_file = "contracts_with_extracted_fields.csv"
    contracts_df.to_csv(output_file, index=False)
    print(f"[INFO] Extraction complete. Data saved to '{output_file}'")


if __name__ == "__main__":
    main()
