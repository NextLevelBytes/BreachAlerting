**Description:**
The Bing Alert System is an advanced monitoring tool designed to scan the web for specific security-related keywords (e.g., "breach", "cyber attack", "hack") associated with a list of domains. It leverages Azure's Text Analytics API to extract and summarize relevant content. This script performs searches using Bing, filters out blocked URLs and keywords, and logs activities for auditing purposes. The summarized content is then sent to a Microsoft Teams channel via a webhook, facilitating real-time alerts on potential security incidents.

**Features**
- Search and Alert: Automatically searches for specified keywords related to cyber security incidents and alerts via Microsoft Teams.
- Content Filtering: Ignores content from blocked URLs or containing blocked keywords, customizable through a JSON configuration file (blockedsearches.json).
- Azure Integration: Utilizes Azure Text Analytics for summarizing relevant information from web pages.
- Logging: Maintains detailed logs with a rolling policy for auditing and troubleshooting.
- Customizable Search Terms: Searches can be tailored with a list of domains and keywords, ensuring focused monitoring.

**Requirements**
```
Python 3.6+
Requests
Beautifulsoup4
azure-ai-textanalytics
```

**Azure Credentials**
- A Microsoft Azure subscription for Text Analytics API access.
- A Microsoft Teams channel with an incoming webhook configured for alerts.

**Azure Credentials:** Below are two different ways to store your Azure credentials in your system's keyring with:
```python
import keyring
keyring.set_password(SEARCH_SERVICE_NAME, SEARCH_USERNAME, 'your_search_api_key')
keyring.set_password(SUMMARY_SERVICE_NAME, SUMMARY_USERNAME, 'your_summary_api_key')
```
**OR**
- You can add the credentials to the credential manager on windows directly 'Control Panel\All Control Panel Items\Credential Manager'
- Click on Windows Credentials and Add a generic credential (you will have to do this twice, one for the search instance, and another for the summary instance)

1. For the search instance
- Internet or network address: 'Azure_Search_Instance'
- User name: 'APIKEYSearch'
- Password: {API key from Azure resource}

2. For the summary instance
- Internet or network address: 'Azure_Summary_Instance'
- User name: 'APIKEYSummary'
- Password: {API key from Azure resource}

# Microsoft Azure Configuration:

**Creating the 'Subscription'**
- From https://portal.azure.com/#home, we can create a free subscription key (No Names for Azure have to be specific to work, names below are an idea)
- Subscription name: PartnerBreachAlertingSystem
- For the Biling account and profile, that would have to be determined ahead of time, this project was built to handle the free versions and runs the free 
  resources and will cost Nothing if setup properly (unless Azure changes plans)
- Under the Advanced Tab, the directory, Management group and subscription owner would need to be set.
- Under the Budget Tab I created a $2 alert just incase something was to be set incorrectly
- Tags are not required

**Creating the 'Resource Group'**
- In the basics tab, for Project details enter the Subscription from the previous step and choose a Region in the US.
- Tags are not required

**Creating 'Cognitive Services'  Now called 'Azure AI services'**
- Side note: First time around I did not need to create this while on the free trial, but after the trial ended and I had to rebuild everything in Azure, this was the piece that allowed me to use the other Cognitive Features which are free, this one is a paid peice, but is more of an entry way. With all of the times I've run the program, it shows my usage at 0%
- To fill in the blanks, this is all the same as above using the subscription that was created and the Resource group we just created
- There is only one Pricing tier S0 at this time.
- On the leading tabs, Network, Identity, Tags, are to be determined by the team

**Creating 'Bing Search v7'**
- Note: This is not Bing Custom Search, these are two different things
- To fill in the blanks, this is all the same as above using the subscription that was created and the Resource group we just created, Instance Name does not matter (bingsearchapi)
- F1 is the Free Pricing Tier
- Once created, no settings need to be configured, just like the Language service (summarizer) below all the settings and features are called within the script itself.

**Creating 'Language service'** (this would be the Summarization Instance)  --> We will also create a storage instance inside of this
- The language service is a bundle of many things, the script calls for specific features within it with all the settings configured.
- First thing asked under Select additional features in the Custom features choose the box that says 'Custom text classification, Custom named entity recognition, 
  Custom summarization, Custom sentiment analysis & Custom Text Analytics for health'
- Fill in the blanks as the others with Subscription, Resource group, Region and Instance Name (SummarizingTextInstance)
- Pricing tier is F0 which limits this program to run with 5k transactions per month which is more than enough
- This does require a storage account. Choose new storage account and choose Standard LRS (That has worked for me, but I have not used it so what do I know), although this does cost money, 
  with the way the program is setup, we use our own storage as everything is needed in the file the program is ran from, which at this point runs less than 2 MB with the information stored.
- As a side note, at the bottom of the page it gives a 'Responsible AI Notice' which gives three documents outlining the Responsible Use of AI for Health, PII, and Language
- On the leading tabs, Network, Identity, Tags, are to be determined by the team

**Monitors and Alerts can be created for Usage and Cost (Cost me nothing so far)(Less than $.01 or $0.00 at the end of each month)**

# **Setup**

**Install Dependencies:**
```
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
```

**The requirements.txt file should include:**
```
'requests'
'beautifulsoup4'
'azure-ai-textanalytics'
'keyring'
```
**Configure API Keys:**
- Store your Azure Text Analytics API key and Bing Search API key securely in your system's keyring under the names APIKEYSearch and APIKEYSummary, respectively.

**Configure Blocked Searches:**
- Edit blockedsearches.json to add any URLs, keywords, or other elements you wish to exclude from searches.

**Set Up Microsoft Teams Webhook:**
- Replace the webhook_url in the script with your Microsoft Teams channel webhook URL.

**Add Search Terms:**
- Populate domainsToCheck.txt with the domains or keywords you want to monitor.

**Usage**
- Run the script with Python:
- python bing_alert_system.py

**The script will execute the following steps:**
- Load search terms from domainsToCheck.txt.
- Perform searches using Bing for each term, combined with the specified security keywords.
- Filter and scrape content from the search results.
- Summarize the content using Azure's Text Analytics.
- Send the summaries to the specified Microsoft Teams channel.

**Logging**
- Logs are stored in BingAlertSystemLogs.log, with a new log file created daily and older logs preserved for seven days.

**Customization**
- Keywords and Blocked Elements: Modify KEYWORDS in the script and entries in blockedsearches.json for custom filtering.
- Search and Summary Configuration: Adjust Azure API and Bing search parameters within the script as needed.
