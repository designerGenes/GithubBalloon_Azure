import datetime
import json
import os
import random
import logging
import azure.functions as func
from azure.storage.blob import BlobServiceClient
import requests
from github import Github
from github import GithubException

def main(timer: func.TimerRequest) -> None:
    try:
        # Generate a random hour for the next execution
        random_hour = random.randint(0, 23)
        
        # Set up the next execution time
        next_execution = datetime.datetime.utcnow().replace(hour=random_hour, minute=0, second=0, microsecond=0)
        if next_execution <= datetime.datetime.utcnow():
            next_execution += datetime.timedelta(days=1)
        
        # Update the NCRONTAB setting
        os.environ['WEBSITE_TIME_ZONE'] = 'UTC'
        os.environ['NCRONTAB'] = f"0 {random_hour} * * *"

        # Call OpenAI API
        openai_api_key = os.environ.get('OPENAI_API_KEY')
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")

        openai_url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {openai_api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {
                    "role": "user",
                    "content": "Return a clever but brief Python coding challenge, as well as a working solution to that challenge in Python code. The text of the challenge should be enclosed in a multi-line Python comment. The entire response should be valid Python code, as if copied from a valid Python file."
                }
            ]
        }

        response = requests.post(openai_url, headers=headers, json=data)
        response.raise_for_status()  # Raises an HTTPError for bad responses
        chatgpt_response = response.json()['choices'][0]['message']['content']

        # Write response to a file
        current_date = datetime.datetime.now().strftime("%Y-%m-%d")
        filename = f"{current_date}.py"
        with open(filename, "w") as f:
            f.write(chatgpt_response)

        # Commit file to GitHub
        github_token = os.environ.get('GITHUB_TOKEN')
        if not github_token:
            raise ValueError("GITHUB_TOKEN environment variable is not set")

        repo_name = "designerGenes/GithubBalloon"
        g = Github(github_token)
        repo = g.get_repo(repo_name)
        with open(filename, "r") as file:
            content = file.read()
        
        try:
            repo.create_file(filename, f"Daily coding challenge: {current_date}", content, branch="main")
        except GithubException as e:
            if e.status == 422:  # File already exists
                file = repo.get_contents(filename)
                repo.update_file(filename, f"Update daily coding challenge: {current_date}", content, file.sha, branch="main")
            else:
                raise

        # Clean up local file
        os.remove(filename)

        logging.info(f"Function executed successfully. Next execution scheduled for {next_execution}")

    except requests.RequestException as e:
        logging.error(f"Error calling OpenAI API: {str(e)}")
    except GithubException as e:
        logging.error(f"Error interacting with GitHub: {str(e)}")
    except ValueError as e:
        logging.error(str(e))
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")

    # Even if an error occurred, we want to reschedule the function
    try:
        # Ensure NCRONTAB is set for next execution
        if 'NCRONTAB' not in os.environ:
            random_hour = random.randint(0, 23)
            os.environ['WEBSITE_TIME_ZONE'] = 'UTC'
            os.environ['NCRONTAB'] = f"0 {random_hour} * * *"
            logging.info(f"Rescheduled next execution for {random_hour}:00 UTC")
    except Exception as e:
        logging.error(f"Error rescheduling function: {str(e)}")
