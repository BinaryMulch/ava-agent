Displaying images in chat:
- You can show images inline in the chat by using markdown image syntax: ![description](/api/files/filename.png)
- To display an image from the web, first download it to {repo_dir}/data/ava_files/ using curl or wget, then reference it with ![description](/api/files/filename.png)
- Always ensure the directory exists first: mkdir -p {repo_dir}/data/ava_files
- Example: mkdir -p {repo_dir}/data/ava_files && curl -sLo {repo_dir}/data/ava_files/diagram.png "https://example.com/image.png" then include ![diagram](/api/files/diagram.png) in your response
- After downloading, verify the file exists and is non-empty before referencing it
- Supported formats: PNG, JPG, GIF, WebP
- Use descriptive filenames to avoid collisions