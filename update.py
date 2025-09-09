import feedparser
from datetime import datetime, timedelta, timezone
import json
import requests
import os
import openai

# Example PubMed RSS feed URL
rss_url = 'https://pubmed.ncbi.nlm.nih.gov/rss/search/1BsDMEWA_ZXeDiqmjuX8stoSY6U8uLseWdwk5HWoqyOvYipwoU/?limit=50&utm_campaign=pubmed-2&fc=20250312220950'

access_token = os.getenv('GITHUB_TOKEN')
openaiapikey = os.getenv('OPENAI_API_KEY')

client = openai.OpenAI(api_key=openaiapikey, base_url="https://api.deepseek.com")
# if you use deepseek api key, change to: client = openai.OpenAI(api_key=openaiapikey, base_url="https://api.deepseek.com")

def extract_scores(text):
    # Use OpenAI API to get Research Score and Social Impact Score with multiple fallback strategies
    
    # Strategy 1: Try deepseek-chat (more reliable than deepseek-reasoner for structured output)
    try:
        response = client.chat.completions.create(
            model="deepseek-chat", 
            messages=[
                {"role": "system", "content": "You are a Natural Killer cell therapy expert and researcher. Evaluate research articles and provide scores."},
                {"role": "user", "content": f"Evaluate this research article and provide scores:\n\n{text}\n\n"
                                            "IMPORTANT: Respond with ONLY this exact format (no extra text):\n"
                                            "Research Score: [number 0-100]\n"
                                            "Social Impact Score: [number 0-100]\n"
                                            "Research Justification: [brief explanation]\n"
                                            "Social Justification: [brief explanation]\n\n"
                                            "Scoring criteria:\n"
                                            "- Research Score: Innovation, methodological rigor, data reliability\n"
                                            "- Social Impact Score: Public attention potential, policy relevance, societal impact"}
            ],
            max_tokens=500,
            temperature=0.1
        )

        generated_text = response.choices[0].message.content.strip()
        
        print(f"🔍 Raw API response (first 200 chars): {generated_text[:200]}...")
        
        if not generated_text:
            print("⚠️  Empty response from API")
            return "N/A", "N/A", "Empty API response", "Empty API response"
        
        # Parse the structured text response
        return parse_structured_response(generated_text)
            
    except Exception as e:
        print(f"❌ Error calling deepseek-chat API: {e}")
        
        # Strategy 2: Fallback to deepseek-reasoner if chat fails
        print("🔄 Trying deepseek-reasoner as fallback...")
        try:
            response = client.chat.completions.create(
                model="deepseek-reasoner", 
                messages=[
                    {"role": "system", "content": "You are a Natural Killer cell therapy expert. Provide research evaluation scores."},
                    {"role": "user", "content": f"Rate this research article:\n\n{text}\n\n"
                                                "Give me:\n"
                                                "Research Score: [0-100]\n"
                                                "Social Impact Score: [0-100]\n"
                                                "Brief explanation for each score."}
                ],
                max_tokens=300,
                temperature=0.1
            )
            
            generated_text = response.choices[0].message.content.strip()
            print(f"🔍 Fallback response (first 200 chars): {generated_text[:200]}...")
            
            if generated_text:
                return parse_structured_response(generated_text)
            else:
                return "N/A", "N/A", "Empty fallback response", "Empty fallback response"
                
        except Exception as e2:
            print(f"❌ Fallback API also failed: {e2}")
            return "Error", "Error", "All API calls failed", "All API calls failed"

def parse_structured_response(generated_text):
    """Parse structured text response from API"""
    research_score = "N/A"
    social_impact_score = "N/A"
    research_justification = "No explanation provided"
    social_justification = "No explanation provided"
    
    lines = generated_text.split('\n')
    
    for line in lines:
        line = line.strip()
        
        # Extract research score
        if line.startswith("Research Score:"):
            score_part = line[len("Research Score:"):].strip()
            # Extract number (handles formats like "85", "85/100", "Score: 85", etc.)
            import re
            numbers = re.findall(r'\d+', score_part)
            if numbers:
                research_score = numbers[0]
        
        # Extract social impact score
        elif line.startswith("Social Impact Score:") or line.startswith("Social Score:"):
            prefix = "Social Impact Score:" if line.startswith("Social Impact Score:") else "Social Score:"
            score_part = line[len(prefix):].strip()
            numbers = re.findall(r'\d+', score_part)
            if numbers:
                social_impact_score = numbers[0]
        
        # Extract research justification
        elif line.startswith("Research Justification:") or line.startswith("Research:"):
            prefix = "Research Justification:" if line.startswith("Research Justification:") else "Research:"
            justification = line[len(prefix):].strip()
            if justification:
                research_justification = justification
        
        # Extract social justification
        elif line.startswith("Social Justification:") or line.startswith("Social:"):
            prefix = "Social Justification:" if line.startswith("Social Justification:") else "Social:"
            justification = line[len(prefix):].strip()
            if justification:
                social_justification = justification
    
    # If structured parsing fails, try fallback parsing
    if research_score == "N/A" or social_impact_score == "N/A":
        print("🔄 Structured parsing failed, trying fallback parsing...")
        return fallback_parse_any_format(generated_text)
    
    return research_score, social_impact_score, research_justification, social_justification

def fallback_parse_any_format(generated_text):
    """Ultra-flexible fallback parsing for any response format"""
    import re
    
    # Look for any numbers that might be scores
    numbers = re.findall(r'\b(\d{1,3})\b', generated_text)
    
    research_score = "N/A"
    social_impact_score = "N/A"
    
    # Try to find scores near keywords
    text_lower = generated_text.lower()
    
    # Look for research-related scores
    research_patterns = ['research', 'innovation', 'methodolog', 'rigor', 'data']
    social_patterns = ['social', 'impact', 'public', 'policy', 'society']
    
    for i, num in enumerate(numbers):
        num_val = int(num)
        if 0 <= num_val <= 100:  # Valid score range
            # Check context around this number
            start_pos = max(0, generated_text.find(num) - 50)
            end_pos = min(len(generated_text), generated_text.find(num) + 50)
            context = generated_text[start_pos:end_pos].lower()
            
            # Assign to research score if context matches
            if any(pattern in context for pattern in research_patterns) and research_score == "N/A":
                research_score = num
            # Assign to social score if context matches
            elif any(pattern in context for pattern in social_patterns) and social_impact_score == "N/A":
                social_impact_score = num
    
    # If we still don't have scores, just use the first two valid numbers found
    valid_numbers = [n for n in numbers if 0 <= int(n) <= 100]
    if research_score == "N/A" and valid_numbers:
        research_score = valid_numbers[0]
    if social_impact_score == "N/A" and len(valid_numbers) > 1:
        social_impact_score = valid_numbers[1]
    elif social_impact_score == "N/A" and len(valid_numbers) == 1:
        social_impact_score = valid_numbers[0]  # Use same score for both if only one found
    
    return research_score, social_impact_score, "Extracted from response text", "Extracted from response text"

def get_pubmed_abstracts(rss_url):
    abstracts_with_urls = []

    # Parse the PubMed RSS feed
    feed = feedparser.parse(rss_url)

    # Calculate the date one week ago
    one_week_ago = datetime.now(timezone.utc) - timedelta(weeks=1)

    # Iterate over entries in the PubMed RSS feed and extract abstracts and URLs
    for entry in feed.entries:
        # Get the publication date of the entry
        published_date = datetime.strptime(entry.published, '%a, %d %b %Y %H:%M:%S %z')

        # If the publication date is within one week, extract the abstract and URL
        if published_date >= one_week_ago:
            # Get the abstract and DOI of the entry
            title = entry.title
            abstract = entry.content[0].value
            doi = entry.dc_identifier
            abstracts_with_urls.append({"title": title, "abstract": abstract, "doi": doi})

    return abstracts_with_urls

# Get the abstracts from the PubMed RSS feed
try:
    pubmed_abstracts = get_pubmed_abstracts(rss_url)
    print(f"✅ Successfully retrieved {len(pubmed_abstracts)} articles from PubMed RSS feed")
except Exception as e:
    print(f"❌ Error retrieving PubMed abstracts: {e}")
    pubmed_abstracts = []

if not pubmed_abstracts:
    print("⚠️  No articles found or error retrieving articles. Creating empty report.")

# Create an empty list to store each abstract with its scores
new_articles_data = []

for i, abstract_data in enumerate(pubmed_abstracts, 1):
    try:
        print(f"🔄 Processing article {i}/{len(pubmed_abstracts)}: {abstract_data['title'][:50]}...")
        
        title = abstract_data.get("title", "No title available")
        abstract_text = abstract_data.get("abstract", "No abstract available")
        doi = abstract_data.get("doi", "No DOI available")
        
        # Skip if no meaningful content
        if len(abstract_text) < 50:
            print(f"⚠️  Skipping article with insufficient abstract content")
            continue
            
        research_score, social_impact_score, research_justification, social_justification = extract_scores(abstract_text)
        
        new_articles_data.append({
            "title": title,
            "research_score": research_score,
            "social_impact_score": social_impact_score,
            "research_justification": research_justification,
            "social_justification": social_justification,
            "doi": doi
        })
        
        print(f"✅ Processed: Research Score: {research_score}, Social Impact: {social_impact_score}")
        
    except Exception as e:
        print(f"❌ Error processing article {i}: {e}")
        # Continue with next article instead of failing completely
        continue

print(f"\n📊 Processing complete. Successfully analyzed {len(new_articles_data)} articles.")
    
# Filter and sort articles
def get_score_value(score_str):
    """Convert score string to integer for filtering and sorting"""
    try:
        return int(''.join(filter(str.isdigit, str(score_str)))) if score_str != "N/A" and score_str != "Error" else 0
    except:
        return 0

# Filter articles with valid scores and minimum thresholds
filtered_articles = []
for article in new_articles_data:
    research_val = get_score_value(article["research_score"])
    social_val = get_score_value(article["social_impact_score"])
    
    # Only include articles with research score >= 70 OR social impact score >= 70
    if research_val >= 70 or social_val >= 70:
        article["research_score_val"] = research_val
        article["social_impact_score_val"] = social_val
        filtered_articles.append(article)

# Sort by combined score (research + social impact)
filtered_articles.sort(key=lambda x: x["research_score_val"] + x["social_impact_score_val"], reverse=True)

# Create issue title and content
issue_title = f"🔬 Weekly NK Cell Research Highlights - {datetime.now().strftime('%Y-%m-%d')}"

if not filtered_articles:
    issue_body = "## 📊 Weekly Research Summary\n\nNo articles met the minimum quality threshold (Research Score ≥ 70 OR Social Impact Score ≥ 70) this week.\n\n"
else:
    issue_body = f"""## 📊 Weekly Research Summary

Found **{len(filtered_articles)}** high-quality articles (out of {len(new_articles_data)} total) from the past week that meet our quality criteria.

### 🏆 Top Articles (Research Score ≥ 70 OR Social Impact Score ≥ 70)

"""

    for i, article in enumerate(filtered_articles, 1):
        title = article["title"]
        research_score = article["research_score"]
        social_impact_score = article["social_impact_score"]
        research_justification = article.get("research_justification", "No justification provided")
        social_justification = article.get("social_justification", "No justification provided")
        doi = article.get("doi", "No DOI available")
        
        # Determine priority based on scores
        total_score = article["research_score_val"] + article["social_impact_score_val"]
        if total_score >= 160:
            priority = "🔥 **PRIORITY**"
        elif total_score >= 140:
            priority = "⭐ **HIGH**"
        else:
            priority = "📌 **NOTABLE**"
        
        issue_body += f"""
---

### {i}. {title}

{priority} | Research: **{research_score}**/100 | Social Impact: **{social_impact_score}**/100

#### 🔬 Research Analysis
{research_justification}

#### 🌍 Social Impact Analysis  
{social_justification}

**📄 DOI:** `{doi}`
**🔗 Link:** https://doi.org/{doi.replace('doi:', '') if doi.startswith('doi:') else doi}

"""

    issue_body += f"""
---

### 📈 Summary Statistics
- **Total Articles Reviewed:** {len(new_articles_data)}
- **High-Quality Articles:** {len(filtered_articles)}
- **Quality Rate:** {len(filtered_articles)/len(new_articles_data)*100:.1f}%

### 🔍 Filtering Criteria
Articles included if they meet **at least one** of the following:
- Research Score ≥ 70 (Innovation, methodology, data reliability)
- Social Impact Score ≥ 70 (Public attention, policy relevance, societal impact)

*Generated automatically via NK Cell Research Monitoring System*
"""

def create_github_issue(title, body, access_token):
    """Create a GitHub issue with error handling and validation"""
    if not access_token:
        print("❌ Error: GitHub access token not found. Please set GITHUB_TOKEN environment variable.")
        return False
        
    try:
        url = f"https://api.github.com/repos/whiteSongLin/test/issues"
        headers = {
            "Authorization": f"token {access_token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json"
        }
        payload = {
            "title": title,
            "body": body
        }

        print(f"🔄 Creating GitHub issue: {title}")
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=30)

        if response.status_code == 201:
            issue_data = response.json()
            issue_url = issue_data.get('html_url', 'Unknown URL')
            print(f"✅ Issue created successfully!")
            print(f"🔗 Issue URL: {issue_url}")
            return True
        else:
            print(f"❌ Failed to create issue. Status code: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print("❌ Timeout error when creating GitHub issue")
        return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Network error when creating GitHub issue: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error when creating GitHub issue: {e}")
        return False

# Validate required environment variables
if not access_token:
    print("❌ Error: GITHUB_TOKEN environment variable not set")
    exit(1)

if not openaiapikey:
    print("❌ Error: OPENAI_API_KEY environment variable not set")
    exit(1)

print(f"🔄 Creating GitHub issue with {len(filtered_articles) if 'filtered_articles' in locals() else 0} articles...")

# Save results to local file for backup
try:
    backup_filename = f"research_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    with open(backup_filename, 'w', encoding='utf-8') as f:
        f.write(f"# {issue_title}\n\n")
        f.write(issue_body)
    print(f"💾 Results saved to local file: {backup_filename}")
except Exception as e:
    print(f"⚠️  Warning: Could not save backup file: {e}")

# Create the issue
success = create_github_issue(issue_title, issue_body, access_token)

if success:
    print(f"\n🎉 Weekly research report completed successfully!")
    print(f"📊 Summary: {len(new_articles_data)} articles processed, {len(filtered_articles) if 'filtered_articles' in locals() else 0} high-quality articles identified")
else:
    print(f"\n⚠️  Research analysis completed but GitHub issue creation failed")
    print("You can manually create the issue with the generated content below:")
    print("="*50)
    print(f"TITLE: {issue_title}")
    print("="*50)
    print(issue_body)
