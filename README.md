# Autoaiscore
This is a repo template to generate score for PubMed RSS update based on research abstract. You could custom this repo by changing the propmt and RSS links.

# Usage

- Fork and clone this repo to your own account or click `use this template - Create a new Repository`

- Set up AI API

Add your API token as `OPENAI_API_KEY` in your repo's Settings - Security - Actions - Repository secrets.

- Fill RSS 

Change Line 9 of `update.py` to your own rss.

- Change prompt

Change Line 21 to fit your research interests.

- Change issue repo

Fill your GitHub user name in Line 103.

- Trigger the first update

Click your repo's Actions, select Weekly Article, and click run workflow in the right panel.
