# ABM Egypt Assessment - Python Developer (Automation & Crawling)

This repository contains my solution for the ABM Egypt assessment tasks.

Folders:
- task1_automation
- task2_network_interception
- task3_dom_scraping
- task4_system_design

## Requirements
Python 3.13.7 .

Install dependencies:
pip install -r requirements.txt

Install Playwright browsers:
python -m playwright install

## Task 1 - Automation (Turnstile)
Location:
task1_automation/

What it does:
- Opens https://cd.captchaaiplus.com/turnstile.html
- Runs 10 attempts
- Captures Turnstile token from cf-turnstile-response (when available)
- Submits the form and logs success/failure per attempt
- Saves JSON report + screenshots under outputs/

Videos:
Task 1 demo video is provided separately by email as requested.

## Task 2 - Network Interception
Location:
task2_network_interception/

Goal:
- Block/intercept Turnstile from loading while capturing its details (sitekey and related params)
- Inject a valid token captured from Task 1 (single-use token)
- Demonstrate successful verification without loading the widget

Videos:
Task 2 demo video is provided separately by email as requested.

## Task 3 - DOM Scraping
Location:
task3_dom_scraping/

Outputs (generated locally under outputs/):
- allimages.json: Base64 for all discovered images
- visible_images_only.json: exactly 9 visible captcha tiles as Base64 (3x3 crop)
- visible_text.json: visible (human-readable) instructions text
- captcha_grid.png: screenshot used for cropping

## Task 4 - System Design
Location:
task4_system_design/

Includes:
- RabbitMQ task distribution (main queue, retry path, DLQ)
- Worker pool with horizontal scaling
- SQL database
- Monitoring integration points (health, load, logging)
- Failover and recovery mechanisms

## AI/LLM Assistance
I used LLM tools (ChatGPT, Gemini, and Claude) as a productivity aid (requirement clarification, approach brainstorming, and documentation cleanup).
Example prompt patterns are documented in prompts_used.md.
