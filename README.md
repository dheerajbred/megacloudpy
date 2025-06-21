# Megacloud API

A Python API for extracting sources from Megacloud URLs. This can be deployed as a serverless function on Netlify.

## Features

- Extract video sources from Megacloud embed URLs
- RESTful API endpoints
- CORS enabled for cross-origin requests
- Error handling and validation
- Health check endpoint

## API Endpoints

### GET /api/extract
Extract sources using a URL query parameter.

**Example:**
```
GET /api/extract?url=https://megacloud.blog/embed-2/v2/e-1/1Iz9gXT6aAOs?z=&autoPlay=0&asi=0
```

### POST /api/extract
Extract sources using a JSON body.

**Example:**
```json
{
  "url": "https://megacloud.blog/embed-2/v2/e-1/1Iz9gXT6aAOs?z=&autoPlay=0&asi=0"
}
```

### GET /health
Health check endpoint.

### GET /
API documentation and examples.

## Response Format

**Success Response:**
```json
{
  "success": true,
  "data": {
    "sources": [...],
    "intro": [start, end],
    "outro": [start, end],
    ...
  }
}
```

**Error Response:**
```json
{
  "success": false,
  "error": "Error message"
}
```

## Local Development

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the Flask development server:
```bash
python api.py
```

3. Test the API:
```bash
# GET request
curl "http://localhost:8080/api/extract?url=https://megacloud.blog/embed-2/v2/e-1/1Iz9gXT6aAOs?z=&autoPlay=0&asi=0"

# POST request
curl -X POST http://localhost:8080/api/extract \
  -H "Content-Type: application/json" \
  -d '{"url": "https://megacloud.blog/embed-2/v2/e-1/1Iz9gXT6aAOs?z=&autoPlay=0&asi=0"}'
```

## Netlify Deployment

### Option 1: Deploy via Netlify CLI

1. Install Netlify CLI:
```bash
npm install -g netlify-cli
```

2. Login to Netlify:
```bash
netlify login
```

3. Initialize and deploy:
```bash
netlify init
netlify deploy --prod
```

### Option 2: Deploy via Git

1. Push your code to a Git repository (GitHub, GitLab, etc.)

2. Connect your repository to Netlify:
   - Go to [Netlify](https://netlify.com)
   - Click "New site from Git"
   - Choose your repository
   - Set build settings:
     - Build command: (leave empty)
     - Publish directory: (leave empty)

3. Deploy settings will be automatically configured from `netlify.toml`

### Option 3: Manual Deploy

1. Create a new site on Netlify
2. Upload the entire project folder
3. Netlify will automatically detect the Python function

## File Structure

```
├── megacloud.py          # Original Megacloud extraction logic
├── api.py               # Flask API for local development
├── requirements.txt     # Python dependencies
├── netlify.toml        # Netlify configuration
├── functions/          # Netlify serverless functions
│   ├── api.py         # Serverless function handler
│   └── requirements.txt # Function dependencies
└── README.md          # This file
```

## Environment Variables

No environment variables are required for basic functionality.

## Limitations

- Netlify functions have a 10-second timeout limit
- Maximum payload size is 6MB
- Cold start delays may occur

## Troubleshooting

### Common Issues

1. **Timeout Errors**: The extraction process might take longer than 10 seconds for some URLs
2. **Import Errors**: Make sure all dependencies are listed in `functions/requirements.txt`
3. **CORS Issues**: The API includes CORS headers, but you may need to configure your client

### Debug Mode

For local development, you can enable debug mode by setting the `FLASK_ENV` environment variable:

```bash
export FLASK_ENV=development
python api.py
```

## License

This project is for educational purposes only. Please respect the terms of service of the websites you're extracting from.
