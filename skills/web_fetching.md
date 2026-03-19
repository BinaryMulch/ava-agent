Fetching and reading web content:
When asked to read a URL, check a webpage, summarize an article, or fetch content from the web:

Fetching a page:
- Use curl with a browser-like user agent to avoid being blocked:
  curl -sL -A "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36" "URL"
- For JSON APIs, use: curl -sL -H "Accept: application/json" "URL"
- Always use -L to follow redirects
- Use -m 30 to set a 30-second timeout to avoid hanging

Extracting readable text from HTML:
- If html2text is available: curl -sL -A "Mozilla/5.0" "URL" | html2text
- If html2text is not installed, install it: apt-get install -y html2text
- Alternative if html2text is unavailable: curl -sL "URL" | sed 's/<[^>]*>//g' | sed '/^\s*$/d' | head -200
- For very long pages, pipe through head to avoid overwhelming output: | head -500

Checking if a site is up:
- Quick status check: curl -sL -o /dev/null -w "%{http_code} %{time_total}s %{url_effective}" "URL"
- Include response headers: curl -sIL "URL"

Fetching API endpoints:
- GET: curl -sL "URL" | python3 -m json.tool
- POST: curl -sL -X POST -H "Content-Type: application/json" -d '{"key":"value"}' "URL"
- With auth: curl -sL -H "Authorization: Bearer TOKEN" "URL"

Downloading files:
- Download to a specific path: curl -sL -o /path/to/file "URL"
- Show progress for large files: curl -L --progress-bar -o /path/to/file "URL"
- Verify the download: ls -lh /path/to/file && file /path/to/file

Guidelines:
- Always summarize the content rather than dumping raw HTML
- If a page is very long, extract the most relevant sections
- If a fetch fails, report the HTTP status code and suggest possible reasons (blocked, DNS failure, timeout)
- For sites that block automated access, let the user know rather than retrying aggressively
- When fetching content the user wants to reference later, consider saving it to a file