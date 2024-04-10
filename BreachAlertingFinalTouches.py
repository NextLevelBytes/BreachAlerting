# Author: Jonathan Luytjes
# Date: April 9, 2024
# Description: The Breach Alert System is a script that actively searches for mentions of specified keywords related to cyber breaches on various partnering company domains 
#   as it scrapes the content of relevant articles, extracts a summary using Azure Text Analytics, and logs important information for further analysis.
# This version is modified to allow public to copy, file directories are changed and given a #modify statement
# Another version of this code is availiable XYZ which does not contain all of these folders that makes this program a messy.

import json
import os
import keyring
import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime
import logging
from logging.handlers import TimedRotatingFileHandler
from azure.core.credentials import AzureKeyCredential
from azure.ai.textanalytics import TextAnalyticsClient
import azure.core.exceptions
from azure.core.exceptions import HttpResponseError
from urllib.parse import urlparse

# Configuration variables for Azure and search queries.
SEARCH_SERVICE_NAME = "BreachAlerting_Search_Instance"
SEARCH_USERNAME = "APISearchBreachKey"
SUMMARY_SERVICE_NAME = "BreachAlerting_Summary_Instance"
SUMMARY_USERNAME = "APISummaryBreachKey"

# Define the base directory for your configs
config_dir = r'C:\Users\FirstName.LastName\Documents\Scripts\'    #Modify within '' with your file location

# Paths for specific files
blocked_searches_path = os.path.join(config_dir, 'blockedsearches.json')    #Modify 'blockedsearches.json' if you have another name for the blocked searches
domains_to_check_path = os.path.join(config_dir, 'domainsToCheck.txt')    #Modify 'domainsToCheck.txt' if you have another name for the domains you want to search for
base_dir = r'C:\Users\FirstName.LastName\Documents\Scripts'    #Modify within '' with your file location
output_dir = os.path.join(base_dir, 'Output')

# Create the Output directory if it doesn't exist
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# Log file path (assuming you want the logs in the Scripts directory itself)
log_file_path = "BingAlertSystemLogs.log"

# Output directory (assuming you want the output in the Scripts directory itself)
output_dir = os.path.join('Logging')

# These are the keywords added to the search query when searching Bing. For example "CompanyName" AND "breach"OR"cyber attack"OR"hack"
KEYWORDS = [
    "breach", "cyber attack", "hack"
]

# Blocked websites, Social Media Platforms, Specific Words, and Countries placed in function using a jason file to store values
def load_config(config_path):
    with open(config_path, 'r') as file:
        return json.load(file)

# Load the configuration
config_path = r'C:\Users\FirstName.LastName\Documents\Scripts\Configs\blockedsearches.json'    #Modify within '' with your file location
config = load_config(config_path)
BLOCKED_URL_PATTERNS = config['blocked_urls']
BLOCKED_KEYWORDS = config['blocked_keywords']

# Creates a rolling log, which makes a new log file for every day, keeping a backup of the last 7 days.
logger = logging.getLogger("my_logger")
logger.setLevel(logging.INFO)
fileHandler = TimedRotatingFileHandler(r"C:\Users\FirstName.LastName\Documents\Scripts\Logging\BingAlertSystemLogs.log", backupCount=7, when="d", interval=1)    #Modify within "" with your file location
fileFormatter = logging.Formatter("%(asctime)s - %(levelname)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
fileHandler.setFormatter(fileFormatter)
fileHandler.namer = lambda name: name.replace(".log", "") + ".log"
logger.addHandler(fileHandler)

# Azure can only intake 1MB of data per call, Two functions 'trim_text_to_fit' and 'split_text_into_chunks' aim to segment and chunk the 'ExampleSumToCheck' txt file
# Allowing Azure to process the whole file no matter the file size, successfully compiles.
def trim_text_to_fit(text, max_bytes=1000000):  # Default is roughly 1MB, considering some overhead
    # Ensure text data fits within a certain byte size
    encoded_text = text.encode("utf-8")
    if len(encoded_text) <= max_bytes:
        return text
    else:
        return text[:max_bytes].decode("utf-8", errors="ignore")

# Split text into chunks, each with a maximum length of max_length.
# This function tries to split at the closest paragraph or newline before the max_length.
def split_text_into_chunks(text, max_length=1000000):  # Adjust max_length as needed

    chunks = []
    while text:
        if len(text) <= max_length:
            chunks.append(text)
            break

        # Find the closest paragraph break or newline before the max_length
        split_position = max_length
        while split_position > 0 and text[split_position] not in ['\n', '.']:
            split_position -= 1

        chunk, text = text[:split_position], text[split_position:]
        chunks.append(chunk.strip())

    return chunks


# This function reads throught the variables from Function load_config. If page is blocked for any reason, this function returns boolean T/F to scrape_and_save_content 
def is_blocked_url(url):
    for pattern in BLOCKED_URL_PATTERNS or BLOCKED_KEYWORDS:
        if pattern in url:
            logger.debug(f"Blocked URL: {url}")
            return True
    return False

# Retrieves the domain of a given URL without the "www." prefix, if it exists.
# And returns the cleaned-up domain name to the caller of the function
# "https://www.example.com/some/path", it will return "example.com". If you call it with a URL like "https://example.com/some/path", it will still return "example.com".
def get_domain_without_www(url):
    parsed_url = urlparse(url)
    domain = parsed_url.netloc.lower().replace("www.", "")
    return domain

# Creates the prameters for the Azure search instance v7
# Contains the search term/ search query for Bing
# Looks for results found on bing (within the last day, and sorted by date for relevance

def fetch_search_results(search_term, subscription_key):
    search_url = "https://api.bing.microsoft.com/v7.0/search"    #Modify within "" with your Bing Search v7 API
    headers = {"Ocp-Apim-Subscription-Key": subscription_key}
    # The search parameters here are enhanced to get very recent results (past 24 hours).
    # It will look for articles specific to terms like 'breach',
    # Create a combined query with all the keywords
    combined_query = " OR ".join(f'"{keyword}"' for keyword in KEYWORDS)
    params = {
        #I added quotes around "({combined_query})" to see if it makes a difference
        "q": f'"{search_term}" AND ({combined_query})',
        "textDecorations": True,
        "freshness": "Week",
        "textFormat": "HTML",
        "mkt": "en-US",
        #"sortBy": "Date",
        #"since": datetime.now().strftime('%Y-%m-%d')
    }
    # Parses through the results from Bing
    try:
        response = requests.get(search_url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        return response.json().get('webPages', {}).get('value', [])
    except requests.exceptions.RequestException as e:
        logger.error(f"Error occurred while fetching search results: {e}")
        return []

# Scrapes the content of the given URLs and saves the content to be summarized, while also grabbing the URL of the website, and it tries to find the Last Modified Date.
def scrape_and_save_content(search_term, urls, output_file_path):
    counter = 0
    with open(output_file_path, "a", encoding="utf-8") as file:
        file.write(f"SearchTerm: {search_term}\n")
        for url in urls:
            if is_blocked_url(url):
                continue  # Skip this URL if it's blocked
            if counter >= 3:
                break
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()

                # Use the apparent encoding from the response to decode content correctly
                content = response.content.decode(response.apparent_encoding, errors='replace')
                soup = BeautifulSoup(content, 'html.parser')
                text = ' '.join(soup.find('body').get_text().strip().split())

                if not text.strip():
                    logger.debug(f"No content extracted from the URL: {url}. Skipping...")
                    continue
                
                file.write(f"URL: {url}\n")
                file.write(f"Last Modified: {response.headers.get('Last-Modified', '')}\n")
                file.write(f"{text}\n\n")
                counter += 1
            except Exception as e:
                logger.debug(f"Issue occurred while scraping {url}: {e}")

# Creates a new Summary file with a timestamp each time the program runs
def generate_timestamped_filename(base_name, extension):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return f"{base_name}_{timestamp}.{extension}"

SUMMARY_FILE_NAME = generate_timestamped_filename("BreachAlertSummary", "txt")


# Extracts a summary from a given document (text content) using Azure's Text Analytics API.
# This function splits the document into manageable chunks to fit Azure's data size limitations,
#  sends each chunk for summarization, and then prioritizes sentences containing predefined keywords
#   in the summary. Finally, it writes the combined summary to a file, optionally including the search term.
def extract_summary(search_term, input_url, document, endpoint, key, write_search_term):
    # Split the document into chunks
    document_chunks = split_text_into_chunks(document)
    
    combined_summary = []

    for chunk in document_chunks:
        try:
            client = TextAnalyticsClient(endpoint=endpoint, credential=AzureKeyCredential(key))
            poller = client.begin_extract_summary(chunk)
            extract_summary_results = poller.result()

            summary = [sentence.text for result in extract_summary_results if result.kind == "ExtractiveSummarization"
                    for sentence in result.sentences]

            # Prioritize sentences containing the keywords
            prioritized_summary = [sentence for sentence in summary if any(keyword in sentence.lower() for keyword in KEYWORDS)]
            combined_summary.extend(prioritized_summary if prioritized_summary else summary)

        except ClientAuthenticationError:
            logger.error("Authentication failed. Check the Azure endpoint and subscription key.")
            break  # Authentication issues are critical; no need to proceed with further chunks.
        except ResourceNotFoundError:
            logger.error("The resource could not be found. Check the Azure endpoint URL.")
            break  # Similar to authentication, a critical issue that requires immediate attention.
        except HttpResponseError as e:
            # Log and continue with other chunks, as this might be a transient error or specific to one chunk.
            logger.warning(f"An HTTP error occurred during summarization: {str(e)}")
        except Exception as e:
            # Catch-all for other exceptions, which could be useful for debugging unexpected issues.
            logger.error(f"An unexpected error occurred: {str(e)}")
            break  # For unexpected errors, safer to stop processing further.

    # Write the combined summary to the file
    ## Added a few extra \n for the formatting in Teams, this does add excessive spacing in Summary file when read
    try:
        with open(SUMMARY_FILE_NAME, "a", encoding="utf-8") as output_file:
            if write_search_term:
                output_file.write(f"\n**Partner Company: {search_term}**\n")
            output_file.write(f"\nSummary extracted from {input_url}:\n\n{' '.join(combined_summary)}\n")
    except Exception as e:
        logger.error(f"Error writing to {SUMMARY_FILE_NAME}: {e}")

# Send the Extracted summary to Teams using workflows > WebHook.
# chunk_size and delay ensures that the information transfers to teams no-matter the amount of data, and spreads the sent chunks out to avoid errors in transit
def send_chunked_messages_to_teams(webhook_url, file_path, chunk_size=15000, delay=4):

    headers = {'Content-Type': 'application/json'}

    # Read the file with UTF-8 encoding
    with open(file_path, 'r', encoding='utf-8') as file:
        message = file.read()

    # Split the message into chunks based on teams transfer limit
    chunks = [message[i:i+chunk_size] for i in range(0, len(message), chunk_size)]

    for chunk in chunks:
        data = {'text': chunk}
        response = requests.post(webhook_url, headers=headers, data=json.dumps(data))
        if response.status_code != 200:
            print(f"Failed to send chunk: {response.text}")
        time.sleep(delay)  # Wait for a few seconds before sending the next chunk


def main():
    # Main function to orchestrate the flow of the script.
    logger.info("Started main function.")
    
    # Retrieve API keys from keyring.
    try:
        searchAPI = keyring.get_password(SEARCH_SERVICE_NAME, SEARCH_USERNAME)
        summaryAPI = keyring.get_password(SUMMARY_SERVICE_NAME, SUMMARY_USERNAME)
    except Exception as e:
        logger.critical(f"Error retrieving API keys from keyring: {e}")
        return

    # Read search terms from the domainsToCheck.txt file.
    try:
        with open(domains_to_check_path, 'r') as file:
            search_terms = [line.strip() for line in file]
    except Exception as e:
        logger.critical(f"Error reading domainsToCheck.txt: {e}")
        return

    # Check if searchAPI or summaryAPI is None
    if searchAPI is None or summaryAPI is None:
        logger.critical("One or more API keys could not be retrieved.")
        return

    # Clearing contents of the file before use
    try:
        with open("ExampleSumToCheck.txt", "w", encoding="utf-8") as file:
            file.write("")
    except Exception as e:
        logger.critical(f"Error clearing ExampleSumToCheck.txt: {e}")
        return

    # For each search term, fetch relevant search results, scrape content, and save it.
    for search_term in search_terms:
        try:
            search_results = fetch_search_results(search_term, searchAPI)
            # Logs how many webpages are availavle for each search (Usally how many are on the first page. Sends to 'BingAlertSystemLogs.log')
            #logger.info(f"Fetched {len(search_results)} results for search term: {search_term}")
            
            urls_to_scrape = [result['url'] for result in search_results]
            scrape_and_save_content(search_term, urls_to_scrape, "ExampleSumToCheck.txt")
            time.sleep(2)  # Introduce a 2-second delay
        except Exception as e:
            logger.error(f"Error processing search term '{search_term}': {e}")

    # Opening the 'ExampleSumToCheck.txt' file in read mode to access its content.
    # The encoding is set to 'utf-8' to ensure that any special characters are read correctly.
    try:
        # Attempt to open and read the file, handling potential IO errors.
        with open("ExampleSumToCheck.txt", "r", encoding="utf-8") as file:
            lines = [line.strip() for line in file]
    except FileNotFoundError:
        logger.error("ExampleSumToCheck.txt not found. Please ensure the file exists.")
        return
    except IOError as e:
        logger.error(f"An I/O error occurred: {e}")
        return

    # Initialize 'url' and 'search_term' to None at the start.
    url = None
    search_term = None
    document = []
    first_url = True

    # Iterate over each cleaned line from the 'lines' list.
    for line in lines:
        try:
            if line.startswith("SearchTerm:"):
                # Check and write the summary for the last URL of the previous search_term
                if url and document:
                    extract_summary(search_term, url, document, 'https://breachalertinglanguage.cognitiveservices.azure.com/', summaryAPI, first_url)    #Modify within '' with your Language Service API
                    url, document = None, []

                first_url = True
                search_term = line.replace("SearchTerm: ", "").strip()
            elif line.startswith("URL:"):
                if url and document:
                    extract_summary(search_term, url, document, 'https://breachalertinglanguage.cognitiveservices.azure.com/', summaryAPI, first_url)    #Modify within '' with your Language Service API
                    first_url = False
                url = line.replace("URL: ", "")
                document = []  # Reset document for the new URL
            elif line.startswith("Last Modified:"):
                continue
            else:
                document.append(line)
        except Exception as e:
            logger.error(f"An error occurred processing the line: {line}. Error: {e}")
            # Decide how to handle the error: skip this line, break the loop, etc.
            continue  # Here we choose to log the error and continue processing.

    # Extract summary for the last document of the last search_term
    if url and document:
        extract_summary(search_term, url, document, 'https://breachalertinglanguage.cognitiveservices.azure.com/', summaryAPI, first_url)    #Modify within '' with your Language Service API

    logger.info("Completed main function.")

    # Send Extracted summary to Teams.
    # Teams API using workflows > WebHook
    webhook_url = ''    #Modify within '' with your WebHook API for TEAMS chat. Click on a Channel and right click or click on the three dots (...) for the group and click 'Manage Channel'
                          # and you can Edit 'Connectors' and Configure 'Incoming Webhook', give it a name and copy the API key in your code here within the ''
    file_path = SUMMARY_FILE_NAME
    send_chunked_messages_to_teams(webhook_url, file_path)

if __name__ == "__main__":
    main()
